import os,json,requests

def analyze_job(job):
    key=os.getenv('OPENROUTER_API_KEY')
    if not key: return None
    prompt='Analyze this job for a Power BI/Data Analytics candidate. Return JSON with relevant, score, skills, reason. Do not include personal data.\n\n'+(job.get('title','')+'\n'+job.get('description',''))[:14000]
    try:
        r=requests.post('https://openrouter.ai/api/v1/chat/completions',headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},json={'model':os.getenv('OPENROUTER_MODEL','openrouter/free'),'messages':[{'role':'user','content':prompt}],'temperature':0},timeout=45)
        r.raise_for_status(); text=r.json()['choices'][0]['message']['content'].strip()
        return json.loads(text.replace('```json','').replace('```','').strip())
    except Exception:
        return None
