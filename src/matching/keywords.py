import json, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def load_keywords():
    return json.loads((ROOT/'config/keywords.json').read_text(encoding='utf-8')).get('keywords', [])
def normalize(text):
    return re.sub(r'\s+', ' ', (text or '').lower()).strip()
def find_matches(text, keywords=None):
    hay=normalize(text); return [k for k in (keywords or load_keywords()) if normalize(k) in hay]
