from urllib.parse import quote_plus
import re
BASE='https://www.naukri.com'
async def search(page,keyword,location,max_pages=20):
    results=[]
    url=BASE+'/'+quote_plus(keyword).replace('+','-')+'-jobs-in-'+quote_plus(location).replace('+','-')
    await page.goto(url,wait_until='domcontentloaded',timeout=60000)
    for _ in range(max_pages):
        await page.wait_for_timeout(1000)
        cards=await page.locator('div.srp-jobtuple-wrapper').all()
        for card in cards:
            try:
                link=card.locator('a.title').first
                title=(await link.inner_text()).strip(); href=await link.get_attribute('href')
                company=''
                comp=card.locator('a.comp-name').first
                if await comp.count(): company=(await comp.inner_text()).strip()
                text=(await card.inner_text()).strip()
                results.append({'job_key':href or title+'|'+company,'url':href,'title':title,'company':company,'location':location,'posted_text':text,'description':text})
            except Exception: pass
        nxt=page.locator('a.fright.fs12.btn-secondary.br2').first
        if not await nxt.count(): break
        try: await nxt.click()
        except Exception: break
    return results

def is_recent(text,hours=24):
    t=(text or '').lower()
    if 'today' in t or 'few hours' in t or 'just now' in t: return True
    m=re.search(r'(\d+)\s*(hour|hr)',t)
    return bool(m and int(m.group(1))<=hours)
