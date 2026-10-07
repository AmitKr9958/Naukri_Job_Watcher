async def enrich(page,job):
    if not job.get('url'): return job
    p=None
    try:
        p=await page.context.new_page()
        await p.goto(job['url'],wait_until='domcontentloaded',timeout=60000)
        await p.wait_for_timeout(800)
        job['description']=(await p.locator('body').inner_text())[:30000]
        if not job.get('company'):
            el=p.locator('a.employer-name').first
            if await el.count(): job['company']=(await el.inner_text()).strip()
    except Exception:
        pass
    finally:
        if p: await p.close()
    return job
