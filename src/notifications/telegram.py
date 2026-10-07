import os
import requests

def send_telegram(text):
    token=os.getenv('TELEGRAM_BOT_TOKEN')
    chat=os.getenv('TELEGRAM_CHAT_ID')
    if not token or not chat:
        return False
    response=requests.post('https://api.telegram.org/bot'+token+'/sendMessage',json={'chat_id':chat,'text':text},timeout=20)
    response.raise_for_status()
    return True
