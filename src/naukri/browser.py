from pathlib import Path
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

        # Reuse one tab for Naukri discovery. Close stale watcher tabs
        # from previous cycles, but only inside this dedicated profile.
        pages=self.browser.pages
        self.page=pages[0] if pages else await self.browser.new_page()
        for extra in pages[1:]:
            try:
                await extra.close()
            except Exception:
                pass
        return self.page

    async def close(self):
        await self.browser.close()
        await self.pw.stop()
