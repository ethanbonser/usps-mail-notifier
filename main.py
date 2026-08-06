from flask import Flask, request, jsonify
import os
import imaplib
import email
from email.header import decode_header
import requests
import json
from datetime import datetime, timedelta, timezone

try:
    from dotenv import load_dotenv
    load_dotenv('.env')
except ImportError:
    pass

app = Flask(__name__)

IMAP_SERVER = 'imap.gmail.com'
SEARCH_SENDERS = [
    'USPSInformeddelivery@email.informeddelivery.usps.com',
    'USPSInformedDelivery@usps.gov',
    'USPSInformedDelivery@delivery.usps.com'
]
SEARCH_SUBJECT = 'Informed Delivery'

def send_telegram_request(method, data, files=None):
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '8736647506:AAEaecQFdeLEtE1p9qqxdPVKK8AdyzGvAoE')
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        res = requests.post(url, data=data, files=files, timeout=15)
        return res.json()
    except Exception as e:
        print(f"Error in {method}: {e}")
        return None

def send_dashboard(chat_id):
    menu_text = "✨ <b>MailboxDetector Dashboard</b>\n\nChoose an action below:"
    keyboard = {
        "inline_keyboard": [
            [{"text": "📬 Check Mail", "callback_data": "check_mail"}],
            [
                {"text": "📊 System Status", "callback_data": "status"},
                {"text": "🧹 Clear Chat", "callback_data": "clear_history"}
            ],
            [
                {"text": "🔄 Refresh Inbox", "callback_data": "check_mail"},
                {"text": "❓ Help", "callback_data": "help"}
            ]
        ]
    }
    data = {
        "chat_id": chat_id,
        "text": menu_text,
        "parse_mode": "HTML",
        "reply_markup": json.dumps(keyboard)
    }
    return send_telegram_request("sendMessage", data)

def run_mail_check(chat_id):
    user = os.environ.get('GMAIL_USER', 'ethanbonser@gmail.com')
    pwd = os.environ.get('GMAIL_APP_PASSWORD', 'txvm yiao trje mvnl')
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '8736647506:AAEaecQFdeLEtE1p9qqxdPVKK8AdyzGvAoE')
    
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(user, pwd)
        mail.select("inbox")
        
        et_offset = timezone(timedelta(hours=-5))
        now_et = datetime.now(et_offset)
        today = now_et.strftime("%d-%b-%Y")
        
        uids = []
        for sender in SEARCH_SENDERS:
            status, messages = mail.uid('search', None, f'(FROM "{sender}" SINCE "{today}")')
            if status == 'OK' and messages[0]:
                for uid in messages[0].split():
                    if uid not in uids: uids.append(uid)
                    
        if not uids:
            status, messages = mail.uid('search', None, f'(SUBJECT "{SEARCH_SUBJECT}" SINCE "{today}")')
            if status == 'OK' and messages[0]:
                uids = messages[0].split()
                
        if not uids:
            mail.logout()
            return "📭 <b>No USPS emails found today yet.</b>"
            
        images_sent = 0
        for uid in uids:
            res, msg_data = mail.uid('fetch', uid, "(RFC822)")
            for part_data in msg_data:
                if isinstance(part_data, tuple):
                    msg = email.message_from_bytes(part_data[1])
                    subj, enc = decode_header(msg["Subject"])[0]
                    if isinstance(subj, bytes): subj = subj.decode(enc if enc else 'utf-8')
                    
                    img_idx = 0
                    for part in msg.walk():
                        if "image" in part.get_content_type():
                            img_data = part.get_payload(decode=True)
                            if img_data:
                                img_idx += 1
                                images_sent += 1
                                caption = f"📬 <b>USPS Mail Scan</b>\n{subj}\n(Img {img_idx})"
                                files = {'photo': ('mail.jpg', img_data, 'image/jpeg')}
                                payload = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'}
                                requests.post(f"https://api.telegram.org/bot{token}/sendPhoto", data=payload, files=files, timeout=20)
        mail.logout()
        if images_sent > 0:
            return f"✅ <b>Found and sent {images_sent} mail scan(s)!</b>"
        else:
            return "📭 <b>No mail images found in today's email.</b>"
    except Exception as e:
        return f"❌ <b>Error connecting to Gmail:</b> {str(e)}"

@app.route("/", methods=["GET"])
def health_check():
    return "USPS Mail Notifier 24/7 Webhook API is Live!", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(force=True, silent=True) or {}
    
    if "callback_query" in update:
        cq = update["callback_query"]
        chat_id = str(cq["message"]["chat"]["id"])
        data = cq.get("data")
        cid = cq.get("id")
        
        send_telegram_request("answerCallbackQuery", {"callback_query_id": cid, "text": "Processing..."})
        
        if data == "check_mail":
            send_telegram_request("sendMessage", {"chat_id": chat_id, "text": "🔍 <b>Scanning inbox for today's mail...</b>", "parse_mode": "HTML"})
            res = run_mail_check(chat_id)
            send_telegram_request("sendMessage", {"chat_id": chat_id, "text": res, "parse_mode": "HTML"})
            send_dashboard(chat_id)
        elif data == "status":
            send_telegram_request("sendMessage", {"chat_id": chat_id, "text": "🟢 <b>Status:</b> 24/7 Cloud Service Active\n📬 <b>Account:</b> ethanbonser@gmail.com", "parse_mode": "HTML"})
            send_dashboard(chat_id)
        elif data == "help":
            help_text = "📖 <b>MailboxDetector Help</b>\n\n• <b>Check Mail:</b> Scans inbox for today's USPS Informed Delivery.\n• <b>Status:</b> System health.\n• Auto-scans run daily between 12:30 PM & 1:15 PM ET."
            send_telegram_request("sendMessage", {"chat_id": chat_id, "text": help_text, "parse_mode": "HTML"})

    elif "message" in update:
        msg = update["message"]
        chat_id = str(msg["chat"]["id"])
        text = msg.get("text", "").lower()
        
        if text in ["/start", "/help", "menu"]:
            send_dashboard(chat_id)
        elif text in ["/check", "check"]:
            send_telegram_request("sendMessage", {"chat_id": chat_id, "text": "🔍 <b>Scanning inbox for today's mail...</b>", "parse_mode": "HTML"})
            res = run_mail_check(chat_id)
            send_telegram_request("sendMessage", {"chat_id": chat_id, "text": res, "parse_mode": "HTML"})
            send_dashboard(chat_id)
            
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
