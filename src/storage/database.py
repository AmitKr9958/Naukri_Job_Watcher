import sqlite3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DB=ROOT/'data'/'jobs.db'

class Database:
    def __init__(self,path=DB):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.con=sqlite3.connect(path)
        self.con.execute("""CREATE TABLE IF NOT EXISTS jobs(
            job_key TEXT PRIMARY KEY,title TEXT,company TEXT,location TEXT,
            posted_text TEXT,url TEXT,description TEXT,score INTEGER,
            matched_keywords TEXT,first_seen TEXT,
            telegram_sent INTEGER DEFAULT 0
        )""")
        self.con.commit()

    def seen(self,key):
        return self.con.execute(
            'SELECT 1 FROM jobs WHERE job_key=?',(key,)
        ).fetchone() is not None

    def save(self,j,score,matches):
        self.con.execute(
            """INSERT INTO jobs(
                job_key,title,company,location,posted_text,url,description,
                score,matched_keywords,first_seen,telegram_sent
            ) VALUES(?,?,?,?,?,?,?,?,?,datetime('now'),0)
            ON CONFLICT(job_key) DO UPDATE SET
                title=excluded.title,
                company=excluded.company,
                location=excluded.location,
                posted_text=excluded.posted_text,
                url=excluded.url,
                description=excluded.description,
                score=excluded.score,
                matched_keywords=excluded.matched_keywords""",
            (
                j['job_key'],j.get('title',''),j.get('company',''),
                j.get('location',''),j.get('posted_text',''),j.get('url',''),
                j.get('description',''),score,','.join(matches)
            )
        )
        self.con.commit()

    def mark_telegram_sent(self,key):
        self.con.execute(
            'UPDATE jobs SET telegram_sent=1 WHERE job_key=?',(key,)
        )
        self.con.commit()

    def telegram_sent(self,key):
        row=self.con.execute(
            'SELECT telegram_sent FROM jobs WHERE job_key=?',(key,)
        ).fetchone()
        return bool(row and row[0])
