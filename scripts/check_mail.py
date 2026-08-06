import imaplib
import email
from email.header import decode_header
import requests
import os
import sys
import time
import threading
import json
import pickle
import atexit
import portalocker
from datetime import datetime, timedelta, timezone

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))
except ImportError:
    pass

# Configuration
GMAIL_USER = os.environ.get('GMAIL_USER', 'ethanbonser@gmail.com')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', 'txvm yiao trje mvnl')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8736647506:AAEaecQFdeLEtE1p9qqxdPVKK8AdyzGvAoE')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '5708669092')
SESSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'session_history.pkl')
LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bot.lock')

lock_file_handle = None

def check_for_duplicate():
    global lock_file_handle
    lock_file_handle = open(LOCK_FILE, 'w')
    try:
        portalocker.lock(lock_file_handle, portalocker.LOCK_EX | portalocker.LOCK_NB)
        lock_file_handle.write(str(os.getpid()))
        lock_file_handle.flush()
    except portalocker.exceptions.LockException:
        print("Another instance is already running. Exiting.")
        sys.exit(0)
    
    def remove_lock():
        global lock_file_handle
        if lock_file_handle:
            try:
                portalocker.unlock(lock_file_handle)
                lock_file_handle.close()
                if os.path.exists(LOCK_FILE):
                    os.remove(LOCK_FILE)
            except: pass
    atexit.register(remove_lock)

# Search criteria
IMAP_SERVER = 'imap.gmail.com'
SEARCH_SENDERS = [
    'USPSInformeddelivery@email.informeddelivery.usps.com',
    'USPSInformedDelivery@usps.gov',
    'USPSInformedDelivery@delivery.usps.com'
]
SEARCH_SUBJECT = 'Informed Delivery'

# History tracking for deletion and deduplication
history = {'msg_ids': [], 'processed_uids': []}

def save_history():
    try:
        with open(SESSION_FILE, 'wb') as f:
            pickle.dump(history, f)
    except Exception as e:
        print(f"Error saving history: {e}")

def load_history():
    global history
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, 'rb') as f:
                history = pickle.load(f)
            # Ensure keys exist for backward compatibility
            if 'msg_ids' not in history: history['msg_ids'] = []
            if 'processed_uids' not in history: history['processed_uids'] = []
        except Exception as e:
            print(f"Error loading history: {e}")

def track_msg(res):
    if res and res.get("ok"):
        history['msg_ids'].append(res["result"]["message_id"])
        save_history()

def delete_all_history():
    # 1. Delete tracked message IDs
    for msg_id in list(history['msg_ids']):
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteMessage"
        try:
            requests.post(url, json={'chat_id': TELEGRAM_CHAT_ID, 'message_id': msg_id}, timeout=5)
        except: pass
    history['msg_ids'] = []
    save_history()

    # 2. Sweep recent message ID range to clean untracked bot messages
    try:
        dummy = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data={'chat_id': TELEGRAM_CHAT_ID, 'text': '🧹'}).json()
        if dummy.get("ok"):
            last_id = dummy["result"]["message_id"]
            for m_id in range(max(1, last_id - 40), last_id + 1):
                try:
                    requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteMessage", json={'chat_id': TELEGRAM_CHAT_ID, 'message_id': m_id}, timeout=3)
                except: pass
    except: pass

def set_bot_commands():
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setMyCommands"
    commands = [
        {'command': 'check', 'description': '🔍 Check mail / 查詢信件'},
        {'command': 'clear', 'description': '🧹 Clear all images / 刪除所有圖片'},
        {'command': 'status', 'description': '🟢 System status / 系統狀態'},
        {'command': 'start', 'description': '👋 Open panel / 開啟面板'}
    ]
    try:
        requests.post(url, json={'commands': commands}, timeout=10)
    except: pass

def send_telegram_photo(photo_data, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    files = {'photo': ('mail.jpg', photo_data, 'image/jpeg')}
    data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption, 'parse_mode': 'HTML'}
    try:
        res = requests.post(url, files=files, data=data, timeout=30).json()
        track_msg(res)
        return res
    except Exception as e:
        print(f"Error sending photo: {e}")
        return None

def send_telegram_message(text, show_panel=False):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}
    if show_panel:
        data['reply_markup'] = json.dumps({
            'inline_keyboard': [
                [{'text': '📬 Check Mail', 'callback_data': 'check_mail'}],
                [
                    {'text': '📊 System Status', 'callback_data': 'status'},
                    {'text': '🧹 Clear Chat', 'callback_data': 'clear_history'}
                ],
                [
                    {'text': '🔄 Refresh Inbox', 'callback_data': 'check_mail'},
                    {'text': '❓ Help', 'callback_data': 'help'}
                ]
            ]
        })
    try:
        res = requests.post(url, data=data, timeout=30).json()
        if show_panel: track_msg(res)
        return res
    except Exception as e:
        print(f"Error sending message: {e}")
        return None

def check_usps_mail(is_automatic=False):
    et_offset = timezone(timedelta(hours=-5))
    now_et = datetime.now(et_offset)
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        mail.select("inbox")
        today = now_et.strftime("%d-%b-%Y")
        
        # Search across multiple known senders or subject fallback
        uids = []
        for sender in SEARCH_SENDERS:
            status, messages = mail.uid('search', None, f'(FROM "{sender}" SINCE "{today}")')
            if status == 'OK' and messages[0]:
                for uid in messages[0].split():
                    if uid not in uids:
                        uids.append(uid)
        
        if not uids:
            # Fallback search by subject
            status, messages = mail.uid('search', None, f'(SUBJECT "{SEARCH_SUBJECT}" SINCE "{today}")')
            if status == 'OK' and messages[0]:
                uids = messages[0].split()
        
        if not uids:
            if not is_automatic: send_telegram_message("📭 <b>No USPS emails found today.</b>", show_panel=True)
            mail.logout()
            return False
            
        uids = messages[0].split()
        found_new_mail = False
        
        for uid in uids:
            uid_str = uid.decode()
            if uid_str in history['processed_uids']:
                continue
                
            res, msg_data = mail.uid('fetch', uid, "(RFC822)")
            for part_data in msg_data:
                if isinstance(part_data, tuple):
                    msg = email.message_from_bytes(part_data[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes): subject = subject.decode(encoding if encoding else 'utf-8')
                    
                    image_count = 0
                    has_images = False
                    for part in msg.walk():
                        if "image" in part.get_content_type():
                            image_data = part.get_payload(decode=True)
                            if image_data:
                                image_count += 1
                                send_telegram_photo(image_data, f"📬 <b>USPS Mail</b>\n{subject}\n(Img {image_count})")
                                has_images = True
                    
                    if has_images:
                        found_new_mail = True
                        history['processed_uids'].append(uid_str)
        
        # Keep processed_uids list manageable (e.g., last 100)
        if len(history['processed_uids']) > 100:
            history['processed_uids'] = history['processed_uids'][-100:]
            
        save_history()
        mail.logout()
        
        if found_new_mail:
            if not is_automatic: send_telegram_message("✅ <b>Scan complete! / 查詢完成！</b>", show_panel=True)
        else:
            if not is_automatic: send_telegram_message("📭 <b>No new USPS mail images to show.</b>", show_panel=True)
            
        return found_new_mail
    except imaplib.IMAP4.error as e:
        err_msg = str(e)
        print(f"IMAP Error: {err_msg}")
        if "Invalid credentials" in err_msg or "AUTHENTICATIONFAILED" in err_msg:
            send_telegram_message("⚠️ <b>Gmail Login Failed</b>\nGmail rejected the App Password. Please generate a new App Password in your Google Account settings and update GMAIL_APP_PASSWORD.")
        return False
    except Exception as e:
        print(f"Error in check_usps_mail: {e}")
        return False

def daily_scheduler():
    last_date = ""
    print(f"[{datetime.now()}] Daily scheduler started.")
    while True:
        try:
            et_offset = timezone(timedelta(hours=-5))
            now_et = datetime.now(et_offset)
            today = now_et.strftime("%Y-%m-%d")
            
            # Check window: 12:30 PM to 1:15 PM ET
            if (now_et.hour == 12 and now_et.minute >= 30) or (now_et.hour == 13 and now_et.minute <= 15):
                if last_date != today:
                    print(f"[{now_et}] Automatic check triggered...")
                    if check_usps_mail(is_automatic=True): 
                        last_date = today
                        print(f"[{now_et}] Automatic check: New mail found and notified.")
                    else:
                        # If no mail found, maybe it hasn't arrived yet. 
                        # We'll retry in 10 minutes (within the window).
                        print(f"[{now_et}] Automatic check: No mail found yet.")
                        time.sleep(600)
            
            # Reset last_date if it's a new day (to allow check for tomorrow)
            if last_date != today and last_date != "":
                # If we've passed the window for 'today', we're ready for 'tomorrow'
                if now_et.hour > 13:
                    last_date = ""

            time.sleep(60)
        except Exception as e:
            print(f"Error in daily_scheduler: {e}")
            time.sleep(60)

def listen_for_commands():
    load_history()
    set_bot_commands()
    threading.Thread(target=daily_scheduler, daemon=True).start()
    
    # Get initial offset to avoid processing old messages
    last_id = 0
    try:
        res = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates", params={'limit': 1, 'offset': -1}, timeout=15).json()
        if res.get("ok") and res.get("result"):
            last_id = res["result"][0]["update_id"]
    except Exception as e:
        print(f"Error getting initial update ID: {e}")

    boot_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_telegram_message(f"👋 <b>MailboxDetector Online</b>\nBoot time: {boot_time}", show_panel=True)
    print(f"[{datetime.now()}] Listener active. Waiting for commands...")
    
    while True:
        try:
            res = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates", params={'offset': last_id + 1, 'timeout': 30}, timeout=40).json()
            if res.get("ok"):
                for update in res.get("result", []):
                    last_id = update["update_id"]
                    
                    if "callback_query" in update:
                        cb = update["callback_query"]
                        data = cb.get("data")
                        cid = cb.get("id")
                        chat_id = str(cb.get("message", {}).get("chat", {}).get("id", ""))
                        
                        if chat_id == TELEGRAM_CHAT_ID:
                            if data == "check_mail":
                                requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery", json={'callback_query_id': cid, 'text': "🔍 Scanning..."})
                                check_usps_mail()
                            elif data == "clear_history":
                                requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery", json={'callback_query_id': cid, 'text': "🧹 Clearing chat..."})
                                delete_all_history()
                                send_telegram_message("🧹 <b>All mail images have been cleared.</b>", show_panel=True)
                            elif data == "status":
                                uptime = datetime.now() - datetime.strptime(boot_time, "%Y-%m-%d %H:%M:%S")
                                send_telegram_message(f"🟢 <b>Status:</b> Healthy\n🕒 <b>Uptime:</b> {str(uptime).split('.')[0]}", show_panel=True)
                            elif data == "help":
                                requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery", json={'callback_query_id': cid, 'text': "📖 Showing help..."})
                                send_telegram_message("📖 <b>MailboxDetector Help</b>\n\n• <b>Check Mail:</b> Scans inbox for today's USPS Informed Delivery.\n• <b>Status:</b> System health & uptime.\n• <b>Clear Chat:</b> Removes previous mail photos.\n• Auto-scans run daily between 12:30 PM & 1:15 PM ET.", show_panel=True)
                    
                    msg = update.get("message", {})
                    text = msg.get("text", "")
                    chat_id = str(msg.get("chat", {}).get("id", ""))
                    
                    if chat_id == TELEGRAM_CHAT_ID:
                        if text == "/start": 
                            send_telegram_message("👋 <b>Welcome!</b>", show_panel=True)
                        elif text == "/check": 
                            check_usps_mail()
                        elif text == "/clear": 
                            delete_all_history()
                            send_telegram_message("🧹 <b>Cleared!</b>", show_panel=True)
                        elif text == "/status":
                            uptime = datetime.now() - datetime.strptime(boot_time, "%Y-%m-%d %H:%M:%S")
                            send_telegram_message(f"🟢 <b>Status:</b> Healthy\n🕒 <b>Uptime:</b> {str(uptime).split('.')[0]}", show_panel=True)
        except requests.exceptions.RequestException as e:
            # Network error, wait a bit and retry
            time.sleep(5)
        except Exception as e:
            print(f"Error in listen_for_commands: {e}")
            time.sleep(10)
        time.sleep(0.5)

if __name__ == "__main__":
    check_for_duplicate()
    if "--listen" in sys.argv: listen_for_commands()
    else: check_usps_mail()
