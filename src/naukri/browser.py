from pathlib import Path
import asyncio
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[2]
PROFILE=ROOT/'browser_profile'

class NaukriBrowser:
    async def start(self,headless=True):
        self.pw=await async_playwright().start()
        self.browser=await self.pw.chromium.launch_persistent_context(
            str(PROFILE),
            headless=headless,
            viewport={'width':1440,'height':1000}
        )
        pages=self.browser.pages
        self.page=pages[0] if pages else await self.browser.new_page()

        for extra in pages[1:]:
            try:
                await extra.close()
            except Exception:
                pass

        return self.page

    async def ensure_login(self, timeout_seconds=300):
        page=self.page
        await page.goto(
            'https://www.naukri.com/nlogin/login',
            wait_until='domcontentloaded',
            timeout=60000
        )
        await page.wait_for_timeout(1500)

        # If Naukri redirects an already-authenticated session away from login,
        # no manual action is needed.
        if '/nlogin/' not in page.url.lower():
            print('Naukri session already authenticated.')
            return True

        print('Naukri login required. Complete login/OTP/CAPTCHA in the open browser window.')

        deadline=asyncio.get_running_loop().time()+timeout_seconds
        while asyncio.get_running_loop().time()<deadline:
            await page.wait_for_timeout(2000)

            current=page.url.lower()
            password=page.locator('input[type="password"], input[placeholder*="password" i]').first
            otp=page.locator('input[placeholder*="OTP" i], input[name*="otp" i]').first

            try:
                password_visible=await password.is_visible()
            except Exception:
                password_visible=False

            try:
                otp_visible=await otp.is_visible()
            except Exception:
                otp_visible=False

            # Successful login normally redirects away from the nlogin route.
            if '/nlogin/' not in current and not password_visible and not otp_visible:
                print('Naukri login detected. Continuing.')
                return True

        raise TimeoutError('Naukri login was not completed within the allowed time.')

    async def close(self):
        await self.browser.close()
        await self.pw.stop()
