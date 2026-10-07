async def enrich(page,job):
    """Open the supplied page and replace the search-card text with the full JD."""
    if not job.get('url'):
        return job
    try:
        await page.goto(job['url'],wait_until='domcontentloaded',timeout=60000)
        await page.wait_for_timeout(500)
        body=page.locator('body')
        text=(await body.inner_text()).strip()
        if text:
            job['description']=text[:40000]

        if not job.get('company'):
            el=page.locator('a.employer-name').first
            if await el.count():
                job['company']=(await el.inner_text()).strip()
    except Exception:
        raise
    return job
