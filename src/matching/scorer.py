from .keywords import find_matches

def score_job(job):
    title=job.get('title','')
    desc=job.get('description','')
    matches=find_matches(title+' '+desc)
    title_matches=find_matches(title)
    score=min(100,len(matches)*4+len(title_matches)*10)
    return {'score':score,'matched_keywords':matches,'reason':str(len(matches))+' matching skills; '+str(len(title_matches))+' found in title.'}
