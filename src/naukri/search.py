from urllib.parse import quote_plus, urlencode
import re

BASE='https://www.naukri.com'

def _slug(value):
    return re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', (value or '').lower())).strip('-')

def build_search_url(keyword, location, minimum_experience=8, maximum_experience=10, freshness_days=1, sort='date'):
    path_keyword=_slug(keyword)
    path_location=_slug(location)
    params=urlencode({'experience': f'{minimum_experience}-{maximum_experience}'})
    return f'{BASE}/{path_keyword}-jobs-in-{path_location}?{params}'

def _looks_like_error(page_text):
    t=(page_text or '').lower()
    return (
        'oops! something went wrong' in t or
        'there was an error loading the page' in t or
        'page not found' in t
    )

async def _open_search_page(page, keyword, location, minimum_experience, maximum_experience, freshness_days):
    primary=build_search_url(
        keyword, location, minimum_experience, maximum_experience,
        freshness_days, 'date'
    )
    attempts=[
        primary,
        primary.split('?')[0]+'?'+urlencode({'jobAge':str(freshness_days)}),
        primary.split('?')[0]
    ]

    last_error=None
    for index,url in enumerate(attempts,1):
        try:
            print('SEARCH URL ATTEMPT '+str(index)+' '+url)
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_timeout(1800)

            body_text=''
            try:
                body_text=(await page.locator('body').inner_text())[:12000]
            except Exception:
                pass

            if _looks_like_error(body_text):
                print('NAUKRI ERROR PAGE DETECTED | attempt='+str(index))
                continue

            cards=await page.locator(
                'div.srp-jobtuple-wrapper, article.jobTuple, .jobTuple'
            ).count()

            if cards == 0:
                await page.wait_for_timeout(2500)
                cards=await page.locator(
                    'div.srp-jobtuple-wrapper, article.jobTuple, .jobTuple'
                ).count()

            if cards > 0:
                print('SEARCH PAGE OK | cards='+str(cards)+' | '+page.url)
                return {
                    'url': page.url,
                    'server_experience_filter': 'experience='+str(minimum_experience)+'-'+str(maximum_experience) in page.url,
                    'server_freshness_filter': 'jobAge='+str(freshness_days) in page.url,
                    'attempt': index
                }

            if 'search' in (await page.title()).lower() or 'jobs' in page.url.lower():
                print('SEARCH PAGE LOADED | zero cards currently visible | '+page.url)
                return {
                    'url': page.url,
                    'server_experience_filter': 'experience='+str(minimum_experience)+'-'+str(maximum_experience) in page.url,
                    'server_freshness_filter': 'jobAge='+str(freshness_days) in page.url,
                    'attempt': index
                }

        except Exception as exc:
            last_error=exc
            print('SEARCH NAVIGATION FAILED | attempt='+str(index)+' | '+str(exc))

    raise RuntimeError(
        'Naukri search page could not be loaded for '+keyword+' | '+location+
        '. Last error: '+str(last_error)
    )

async def _click_text_variants(page, variants, timeout=2500):
    for value in variants:
        selectors=[
            'button:has-text("'+value+'")',
            'a:has-text("'+value+'")',
            'div:has-text("'+value+'")',
            'span:has-text("'+value+'")'
        ]
        for selector in selectors:
            try:
                loc=page.locator(selector).first
                if await loc.count() and await loc.is_visible():
                    await loc.click(timeout=timeout)
                    return True
            except Exception:
                pass
    return False

async def _apply_ui_filters(page, freshness_days):
    # The query-string form of jobAge can trigger an SRP error on some
    # Naukri routes. Apply freshness and date sorting through the visible UI
    # after the stable search page has loaded.
    applied_freshness=False
    applied_sort=False

    try:
        opened=await _click_text_variants(
            page, ['Freshness', 'freshness'], timeout=2000
        )
        if opened:
            day_label='1 Day' if int(freshness_days)==1 else str(freshness_days)+' Days'
            applied_freshness=await _click_text_variants(
                page,
                [day_label, day_label.lower(), 'Last '+str(freshness_days)+' day',
                 'Last '+str(freshness_days)+' days'],
                timeout=2500
            )
            if applied_freshness:
                await page.wait_for_timeout(1200)
    except Exception:
        pass

    try:
        opened=await _click_text_variants(
            page,
            ['Sort by: Relevance', 'Sort By: Relevance', 'Relevance'],
            timeout=2000
        )
        if opened:
            applied_sort=await _click_text_variants(
                page, ['Date', 'date', 'Newest', 'Newest first'],
                timeout=2500
            )
            if applied_sort:
                await page.wait_for_timeout(1200)
    except Exception:
        pass

    print(
        'UI FILTER RESULT | freshness='+str(applied_freshness)+
        ' | sort_date='+str(applied_sort)
    )
    return applied_freshness, applied_sort

async def search(page, keyword, location, max_pages=10, use_ui_filters=True,
                 minimum_experience=8, maximum_experience=10, freshness_days=1):
    results=[]
    state=await _open_search_page(
        page, keyword, location,
        minimum_experience, maximum_experience, freshness_days
    )

    print(
        'FILTERED SEARCH '+keyword+' | '+location+
        ' | experience='+str(minimum_experience)+'-'+str(maximum_experience)+
        ' | freshness='+str(freshness_days)+'day | sort=date'
    )
    print(
        'FILTER STATE | experience='+str(state['server_experience_filter'])+
        ' | freshness='+str(state['server_freshness_filter'])+
        ' | fallback_attempt='+str(state['attempt'])
    )
    print('SEARCH URL '+state['url'])

    ui_freshness=False
    ui_sort=False
    if use_ui_filters:
        ui_freshness, ui_sort=await _apply_ui_filters(page, freshness_days)
    if not ui_freshness:
        print('FRESHNESS UI FILTER NOT CONFIRMED; final is_recent() check remains mandatory.')
    if not ui_sort:
        print('DATE SORT UI FILTER NOT CONFIRMED; continuing with available result order.')

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
                if not await link.count():
                    continue

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
                    'server_experience_filter':state['server_experience_filter'],
                    'server_freshness_filter':state['server_freshness_filter'],
                    'ui_freshness_filter':ui_freshness,
                    'ui_sort_date':ui_sort,
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
            await page.wait_for_timeout(1200)
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
