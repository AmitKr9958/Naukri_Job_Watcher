from urllib.parse import quote_plus, urlencode
import re

BASE='https://www.naukri.com'

def build_search_url(keyword, location, minimum_experience=8, maximum_experience=10, freshness_days=1, sort='date'):
    path_keyword=quote_plus(keyword).replace('+','-')
    path_location=quote_plus(location).replace('+','-')
    params=urlencode({
        'k': keyword,
        'l': location,
        'experience': f'{minimum_experience}-{maximum_experience}',
        'jobAge': str(freshness_days),
        'sort': sort
    })
    return f'{BASE}/{path_keyword}-jobs-in-{path_location}?{params}'

async def search(page, keyword, location, max_pages=10, use_ui_filters=True,
                 minimum_experience=8, maximum_experience=10, freshness_days=1):
    results=[]
    url=build_search_url(
        keyword, location, minimum_experience, maximum_experience,
        freshness_days, 'date'
    )

    # Use Naukri's own search URL/filter state. This is more stable than
    # manipulating the React filter slider with guessed DOM selectors.
    await page.goto(url, wait_until='domcontentloaded', timeout=60000)
    await page.wait_for_timeout(1500)

    print(
        'FILTERED SEARCH '+keyword+' | '+location+
        ' | experience='+str(minimum_experience)+'-'+str(maximum_experience)+
        ' | freshness='+str(freshness_days)+'day | sort=date'
    )
    print('SEARCH URL '+page.url)

    seen_on_search=set()
    last_signature=None

    for page_no in range(1, max_pages+1):
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
                    'job_key':key,
                    'url':href,
                    'title':title,
                    'company':company,
                    'location':location,
                    'posted_text':text,
                    'description':text,
                    'search_keyword':keyword,
                    'search_location':location,
                    'search_page':page_no,
                    'ui_search':True,
                    'filter_experience':f'{minimum_experience}-{maximum_experience}',
                    'filter_freshness_days':freshness_days,
                    'filter_sort':'date',
                    'search_url':page.url
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
            await page.wait_for_timeout(900)
        except Exception:
            break

    return results

def is_recent(text,hours=24):
    t=(text or '').lower()

    if any(x in t for x in (
        'just now','few minutes','few hours','today',
        '1 day','1 day ago','few days'
    )):
        if 'few days' in t:
            return False
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
