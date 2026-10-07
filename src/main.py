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
    search_workers=int(cfg.get('search_concurrency',8))
    detail_workers=int(cfg.get('detail_concurrency',6))

    browser=NaukriBrowser()
    await browser.start(cfg.get('headless',True))
    search_sem=asyncio.Semaphore(search_workers)
    detail_sem=asyncio.Semaphore(detail_workers)
    jobs_by_key={}

    async def run_search(keyword,location):
        async with search_sem:
            page=await browser.browser.new_page()
            try:
                logging.info('SEARCH %s | %s',keyword,location)
                jobs=await search(page,keyword,location,cfg['max_pages_per_search'])
                for job in jobs:
                    jobs_by_key[job['job_key']]=job
            except Exception:
                logging.exception('Search failed: %s | %s',keyword,location)
            finally:
                await page.close()

    try:
        tasks=[asyncio.create_task(run_search(k,l)) for l in cfg['locations'] for k in keys]
        await asyncio.gather(*tasks)
        logging.info('Search phase complete: %s unique candidates',len(jobs_by_key))

        db=Database()

        async def process(job):
            if db.seen(job['job_key']):
                return

            # Every new candidate gets its full JD read before we decide relevance.
            async with detail_sem:
                page=await browser.browser.new_page()
                try:
                    job=await enrich(page,job)
                finally:
                    await page.close()

            if not is_recent(job.get('posted_text'),cfg['posted_within_hours']):
                logging.info('SKIP OLD | %s | %s',job.get('title',''),job.get('posted_text','')[:100])
                db.save(job,0,[])
                return

            result=score_job(job)

            # AI is optional and only runs for keyword-relevant jobs.
            ai=None
            if result['score'] >= cfg['minimum_match_score']:
                ai=analyze_job(job)
                if ai:
                    result['ai']=ai

            db.save(job,result['score'],result['matched_keywords'])

            if result['score'] < cfg['minimum_match_score']:
                logging.info('FILTERED | %s | score=%s',job.get('title',''),result['score'])
                return

            message=('Naukri Job Match\n\n'+job.get('title','')+'\n'+
                     job.get('company','')+'\nLocation: '+job.get('location','')+
                     '\nPosted: '+job.get('posted_text','')[:180]+
                     '\nScore: '+str(result['score'])+'/100\nSkills: '+
                     ', '.join(result['matched_keywords'][:12])+
                     '\nReason: '+result['reason']+'\nApply: '+str(job.get('url','')))
            sent=send_telegram(message)
            logging.info('MATCH %s | score=%s | Telegram=%s',job.get('title',''),result['score'],sent)

        await asyncio.gather(*(process(j) for j in jobs_by_key.values()))
        logging.info('Cycle complete')
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
