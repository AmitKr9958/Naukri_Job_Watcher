from urllib.parse import quote_plus
import re

BASE='https://www.naukri.com'

async def search(page,keyword,location,max_pages=20):
    results=[]
    url=BASE+'/'+quote_plus(keyword).replace('+','-')+'-jobs-in-'+quote_plus(location).replace('+','-')
    await page.goto(url,wait_until='domcontentloaded',timeout=60000)

    seen_on_search=set()
    for _ in range(max_pages):
        await page.wait_for_timeout(700)
        cards=await page.locator('div.srp-jobtuple-wrapper').all()
        if not cards:
            break

        page_new=0
        for card in cards:
            try:
                link=card.locator('a.title').first
                title=(await link.inner_text()).strip()
                href=await link.get_attribute('href')
                company=''
                comp=card.locator('a.comp-name').first
                if await comp.count():
                    company=(await comp.inner_text()).strip()
                text=(await card.inner_text()).strip()
                key=href or title+'|'+company
                if key in seen_on_search:
                    continue
                seen_on_search.add(key)
                page_new += 1
                results.append({
                    'job_key':key,'url':href,'title':title,'company':company,
                    'location':location,'posted_text':text,'description':text
                })
            except Exception:
                pass

        if page_new == 0:
            break

        nxt=page.locator('a.fright.fs12.btn-secondary.br2').first
        if not await nxt.count():
            break
        try:
            await nxt.click()
            await page.wait_for_timeout(400)
        except Exception:
            break

    return results

def is_recent(text,hours=24):
    t=(text or '').lower()
    if any(x in t for x in ('just now','few minutes','few hours','today')):
        return True

    m=re.search(r'(\d+)\s*(minute|minutes|min|mins)',t)
    if m:
        return True

    m=re.search(r'(\d+)\s*(hour|hours|hr|hrs)',t)
    if m:
        return int(m.group(1)) <= hours

    m=re.search(r'(\d+)\s*(day|days)',t)
    if m:
        return int(m.group(1)) * 24 <= hours

    return False
