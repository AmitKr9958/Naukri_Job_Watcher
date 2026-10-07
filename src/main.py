import asyncio,json,logging
from pathlib import Path
from dotenv import load_dotenv
from naukri.browser import NaukriBrowser
from naukri.search import search,is_recent
from naukri.job_details import enrich
from matching.scorer import score_job
from storage.database import Database
from notifications.telegram import send_telegram
from ai.openrouter import analyze_job

ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')

async def cycle():
    cfg=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    keys=json.loads((ROOT/'config/keywords.json').read_text(encoding='utf-8'))['keywords']
    search_workers=int(cfg.get('search_concurrency',5))
    detail_workers=int(cfg.get('detail_concurrency',5))
    tab_count=max(1,min(5,search_workers,detail_workers))

    browser=NaukriBrowser()
    await browser.start(cfg.get('headless',True))
    if cfg.get('require_naukri_login',True):
        await browser.ensure_login(cfg.get('login_wait_seconds',300))

    worker_pages=[browser.page]
    for _ in range(tab_count-1):
        worker_pages.append(await browser.new_worker_page())

    # Persistent Chrome profiles can retain tabs from an interrupted run.
    # Keep exactly the fixed worker tabs for this watcher.
    await browser.close_extra_pages(worker_pages)

    search_page_pool=asyncio.Queue()
    for p in worker_pages:
        await search_page_pool.put(p)
    jobs_by_key={}

    async def run_search(keyword,location):
        page=await search_page_pool.get()
        try:
            logging.info('SEARCH %s | %s',keyword,location)
            jobs=await search(
                    page,
                    keyword,
                    location,
                    cfg['max_pages_per_search'],
                    cfg.get('use_ui_search',True),
                    cfg.get('minimum_experience_years',8),
                    cfg.get('maximum_experience_years',10),
                    cfg.get('freshness_days',1)
            )
            for job in jobs:
                jobs_by_key[job['job_key']]=job
        except Exception:
                logging.exception('Search failed: %s | %s',keyword,location)
        finally:
            # Naukri may occasionally open a new tab from a UI action.
            # Close it immediately; never let tabs accumulate between searches.
            await browser.close_extra_pages(worker_pages)
            await search_page_pool.put(page)

    async def process_worker(worker_id,queue,db,page):
        try:
            while True:
                job=await queue.get()
                if job is None:
                    queue.task_done()
                    return
                try:
                    key=job['job_key']
                    if db.seen(key):
                        logging.info('ALREADY SEEN | %s',job.get('title',''))
                        continue

                    logging.info('JD %s/%s | %s',worker_id,detail_workers,job.get('title',''))
                    try:
                        job=await enrich(page,job)
                    except Exception:
                        logging.exception('JD extraction failed: %s',job.get('url',''))
                        continue

                    if not is_recent(job.get('posted_text'),cfg['posted_within_hours']):
                        logging.info('SKIP OLD | %s | %s',job.get('title',''),job.get('posted_text','')[:100])
                        db.save(job,0,[])
                        continue

                    result=score_job(job)
                    logging.info(
                        'JD COMPLETE | %s | score=%s | skills=%s',
                        job.get('title',''),result['score'],len(result['matched_keywords'])
                    )

                    ai=None
                    if result['score'] >= cfg['minimum_match_score']:
                        ai=await asyncio.to_thread(analyze_job,job)
                        if ai:
                            result['ai']=ai

                    db.save(job,result['score'],result['matched_keywords'])

                    if result['score'] < cfg['minimum_match_score']:
                        logging.info('FILTERED | %s | score=%s',job.get('title',''),result['score'])
                        continue

                    message=('Naukri Job Match\\n\\n'+job.get('title','')+'\\n'+
                             job.get('company','')+'\\nLocation: '+job.get('location','')+
                             '\\nPosted: '+job.get('posted_text','')[:180]+
                             '\\nScore: '+str(result['score'])+'/100\\nSkills: '+
                             ', '.join(result['matched_keywords'][:12])+
                             '\\nReason: '+result['reason']+'\\nApply: '+str(job.get('url','')))

                    sent=await asyncio.to_thread(send_telegram,message)
                    if sent:
                        db.mark_telegram_sent(key)
                    logging.info(
                        'MATCH %s | score=%s | Telegram=%s',
                        job.get('title',''),result['score'],sent
                    )
                finally:
                    queue.task_done()
        finally:
            pass

    try:
        # Phase 1: broad search only. Do not discard candidates on card text.
        tasks=[asyncio.create_task(run_search(k,l)) for l in cfg['locations'] for k in keys]
        await asyncio.gather(*tasks)
        logging.info('Search phase complete: %s unique candidates',len(jobs_by_key))

        # Phase 2: every unique NEW candidate gets a full JD read.
        db=Database()
        queue=asyncio.Queue()
        for job in jobs_by_key.values():
            await queue.put(job)

        workers=[
            asyncio.create_task(process_worker(i+1,queue,db,worker_pages[i]))
            for i in range(min(detail_workers,tab_count))
        ]
        await queue.join()

        for _ in workers:
            await queue.put(None)
        await asyncio.gather(*workers)

        logging.info('Cycle complete: %s candidates collected',len(jobs_by_key))
    finally:
        await browser.close()

async def main():
    cfg=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    while True:
        try:
            await cycle()
        except Exception:
            logging.exception('Watcher cycle failed')
        await asyncio.sleep(cfg.get('check_interval_minutes',10)*60)

if __name__=='__main__':
    asyncio.run(main())
