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
    cfg=json.loads((ROOT/'config.json').read_text(encoding='utf-8')); keys=json.loads((ROOT/'config/keywords.json').read_text(encoding='utf-8'))['keywords']
    db=Database(); browser=NaukriBrowser(); page=await browser.start(cfg.get('headless',True))
    try:
        for location in cfg['locations']:
            for keyword in keys:
                logging.info('Searching %s | %s',keyword,location)
                for job in await search(page,keyword,location,cfg['max_pages_per_search']):
                    if not is_recent(job.get('posted_text'),cfg['posted_within_hours']) or db.seen(job['job_key']): continue
                    job=await enrich(page,job); result=score_job(job)
                    if result['score']<cfg['minimum_match_score']: continue
                    ai=analyze_job(job)
                    if ai: result['ai']=ai
                    message=('Naukri Job Match\n\n'+job.get('title','')+'\n'+job.get('company','')+'\nLocation: '+job.get('location','')+'\nPosted: '+job.get('posted_text','')[:180]+'\nScore: '+str(result['score'])+'/100\nSkills: '+', '.join(result['matched_keywords'][:12])+'\nReason: '+result['reason']+'\nApply: '+str(job.get('url','')))
                    sent=send_telegram(message)
                    db.save(job,result['score'],result['matched_keywords'])
                    logging.info('New match: %s | Telegram=%s',job.get('title',''),sent)
    finally: await browser.close()
async def main():
    cfg=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    while True:
        try: await cycle()
        except Exception: logging.exception('Watcher cycle failed')
        await asyncio.sleep(cfg.get('check_interval_minutes',10)*60)
if __name__=='__main__': asyncio.run(main())
