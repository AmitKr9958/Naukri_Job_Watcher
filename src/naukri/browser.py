from pathlib import Path
import asyncio
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[2]
PROFILE=ROOT/'browser_profile'
HOME='https://www.naukri.com'

class NaukriBrowser:
    async def start(self,headless=True):
        self.pw=await async_playwright().start()
        self.browser=await self.pw.chromium.launch_persistent_context(
            str(PROFILE),
            headless=headless,
            viewport={'width':1440,'height':1000},
            # Use standard Playwright Chromium settings; do not attempt to evade site security.
        )
        pages=self.browser.pages
        self.page=pages[0] if pages else await self.browser.new_page()

        self.allowed_pages=set([self.page])
        for extra in pages[1:]:
            try:
                await extra.close()
            except Exception:
                pass

        return self.page

    async def new_worker_page(self):
        page=await self.browser.new_page()
        self.allowed_pages.add(page)
        return page

    async def close_extra_pages(self, keep_pages):
        """Keep only the fixed worker tabs; close unexpected/pop-up tabs."""
        keep=set(keep_pages)
        for page in list(self.browser.pages):
            if page in keep:
                continue
            try:
                if not page.is_closed():
                    await page.close()
            except Exception:
                pass

    async def _login_visible(self):
        page=self.page
        candidates=[
            'button:has-text("Login")',
            'a:has-text("Login")',
            'div:has-text("Login")'
        ]
        for selector in candidates:
            try:
                loc=page.locator(selector).first
                if await loc.count() and await loc.is_visible():
                    return True
            except Exception:
                pass
        return False

    async def _credential_form_visible(self):
        page=self.page
        selectors=[
            'input[type="password"]',
            'input[placeholder*="password" i]',
            'input[placeholder*="email" i]',
            'input[placeholder*="mobile" i]',
            'input[placeholder*="OTP" i]',
            'input[name*="otp" i]'
        ]
        for selector in selectors:
            try:
                loc=page.locator(selector).first
                if await loc.count() and await loc.is_visible():
                    return True
            except Exception:
                pass
        return False

    async def ensure_login(self, timeout_seconds=300):
        page=self.page

        print('Opening Naukri for manual authentication...')
        await page.goto(HOME, wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(2500)

        # IMPORTANT: never infer authentication from the absence of a single
        # text node. Naukri changes its header/modal DOM frequently.
        if not await self._login_visible():
            print('Naukri login button is not visible. Assuming existing session.')
            return True

        print('')
        print('==============================================')
        print(' NAUKRI LOGIN REQUIRED')
        print(' Complete login/OTP/CAPTCHA in this browser.')
        print(' Do NOT close the Naukri browser window.')
        print('==============================================')
        print('')

        # Open the login UI if possible, but tolerate Naukri changing the
        # exact header element.
        for selector in (
            'button:has-text("Login")',
            'a:has-text("Login")',
            'div:has-text("Login")'
        ):
            try:
                loc=page.locator(selector).first
                if await loc.count() and await loc.is_visible():
                    await loc.click(timeout=3000)
                    break
            except Exception:
                pass

        deadline=asyncio.get_running_loop().time()+timeout_seconds

        while asyncio.get_running_loop().time()<deadline:
            await page.wait_for_timeout(2000)

            # If the browser/context died, fail immediately instead of spawning
            # hundreds of misleading TargetClosedError search failures.
            if page.is_closed() or self.browser.is_closed():
                raise RuntimeError(
                    'Naukri browser closed during login. '
                    'The watcher stopped before starting searches.'
                )

            current=page.url.lower()

            # Login forms can remain visible while OTP is being entered.
            form_visible=await self._credential_form_visible()
            login_visible=await self._login_visible()

            # Strong success signal: credential/OTP form gone AND the page has
            # navigated away from an authentication route, with Login no longer
            # presented as the main header action.
            if not form_visible and not login_visible and '/nlogin/' not in current:
                print('Naukri login confirmed.')
                return True

            # A successful login can redirect to the home/search page while a
            # stale modal disappears a little later.
            if not form_visible and '/nlogin/' not in current:
                await page.wait_for_timeout(1500)
                if not await self._login_visible():
                    print('Naukri login confirmed.')
                    return True

        raise TimeoutError(
            'Naukri login was not completed within '
            +str(timeout_seconds)+' seconds. '
            'The watcher did not start searching.'
        )

    async def close(self):
        try:
            if not self.browser.is_closed():
                await self.browser.close()
        finally:
            await self.pw.stop()
