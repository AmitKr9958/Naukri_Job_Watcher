from urllib.parse import quote_plus
import re

BASE='https://www.naukri.com'

async def _fill_first(page, selectors, value):
    for selector in selectors:
        loc=page.locator(selector).first
        try:
            if await loc.count() and await loc.is_visible():
                await loc.fill(value)
                return True
        except Exception:
            pass
    return False

async def _open_search_ui(page, keyword, location):
    await page.goto(BASE, wait_until='domcontentloaded', timeout=60000)
    await page.wait_for_timeout(1200)
    keyword_ok=await _fill_first(page, [
        'input[placeholder*="Skills" i]',
        'input[placeholder*="skill" i]',
        'input[placeholder*="designation" i]',
        'input[name*="keyword" i]',
        'input[placeholder*="Search jobs" i]'
    ], keyword)
    location_ok=await _fill_first(page, [
        'input[placeholder*="Location" i]',
        'input[placeholder*="location" i]',
        'input[name*="location" i]'
    ], location)
    if not (keyword_ok and location_ok):
        return False
    try:
        loc=page.locator('input[placeholder*="skill" i], input[placeholder*="Skills" i], input[name*="keyword" i]').first
        if await loc.count():
            await loc.press('Enter')
    except Exception:
        pass
    await page.wait_for_timeout(1500)
    return True

async def _apply_ui_filters(page):
    applied=[]
    for label in ('1 Day','1 day','Last 1 day','24 hours'):
        try:
            loc=page.get_by_text(label, exact=True).first
            if await loc.count() and await loc.is_visible():
                await loc.click()
                applied.append('freshness=1day')
                break
        except Exception:
            pass
    for label in ('Date','date'):
        try:
            loc=page.get_by_text(label, exact=True).first
            if await loc.count() and await loc.is_visible():
                await loc.click()
                applied.append('sort=date')
                break
        except Exception:
            pass
    return applied

async def search(page,keyword,location,max_pages=20,use_ui_filters=True,minimum_experience=8,maximum_experience=10):
    results=[]
    ui_ok=False
    try:
        ui_ok=await _open_search_ui(page,keyword,location)
        if ui_ok and use_ui_filters:
            applied=await _apply_ui_filters(page,minimum_experience,maximum_experience)
            logging_text='; '.join(applied) if applied else 'no UI filters detected'
            print('FILTERS '+keyword+' | '+location+' | '+logging_text)
    except Exception:
        ui_ok=False

    if not ui_ok:
        url=BASE+'/'+quote_plus(keyword).replace('+','-')+'-jobs-in-'+quote_plus(location).replace('+','-')
        await page.goto(url,wait_until='domcontentloaded',timeout=60000)
        await page.wait_for_timeout(1000)

    seen_on_search=set()
    last_signature=None
    for page_no in range(1,max_pages+1):
        await page.wait_for_timeout(700)
        cards=await page.locator('div.srp-jobtuple-wrapper').all()
        if not cards:
            cards=await page.locator('article.jobTuple, .jobTuple').all()
        if not cards:
            break

        page_new=0
        signatures=[]
        for card in cards:
            try:
                link=card.locator('a.title').first
                if not await link.count():
                    link=card.locator('a[href*="/job-listings/"]').first
                title=(await link.inner_text()).strip()
                href=await link.get_attribute('href')
                company=''
                comp=card.locator('a.comp-name').first
                if await comp.count():
                    company=(await comp.inner_text()).strip()
                text=(await card.inner_text()).strip()
                key=href or title+'|'+company
                signatures.append(key)
                if key in seen_on_search:
                    continue
                seen_on_search.add(key)
                page_new+=1
                results.append({
                    'job_key':key,'url':href,'title':title,'company':company,
                    'location':location,'posted_text':text,'description':text,
                    'search_keyword':keyword,'search_location':location,
                    'search_page':page_no,'ui_search':ui_ok
                })
            except Exception:
                pass

        signature='|'.join(signatures[:10])
        if signature and signature==last_signature:
            break
        last_signature=signature
        if page_new==0:
            break

        nxt=page.locator(
            'a.fright.fs12.btn-secondary.br2, '
            'a[aria-label*="Next" i], '
            'button[aria-label*="Next" i]'
        ).first
        if not await nxt.count():
            break
        try:
            await nxt.scroll_into_view_if_needed()
            await nxt.click()
            await page.wait_for_timeout(800)
        except Exception:
            break
    return results

def is_recent(text,hours=24):
    t=(text or '').lower()
    if any(x in t for x in ('just now','few minutes','few hours','today','1 day','1 day ago')):
        return True
    m=re.search(r'(\d+)\s*(minute|minutes|min|mins)',t)
    if m:
        return True
    m=re.search(r'(\d+)\s*(hour|hours|hr|hrs)',t)
    if m:
        return int(m.group(1))<=hours
    m=re.search(r'(\d+)\s*(day|days)',t)
    if m:
        return int(m.group(1))*24<=hours
    return False
