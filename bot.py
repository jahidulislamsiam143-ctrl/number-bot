import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
import requests
import json
import time
import threading
import os
import uuid
import html
import re
import pyotp
import random
from datetime import datetime
import io
import sys

# Track server uptime
START_TIME = time.time()

# --- Telegram Latest Feature Check (CopyTextButton) ---
try:
    from telebot.types import CopyTextButton
    HAS_COPY_BTN = True
except ImportError:
    HAS_COPY_BTN = False

# ============================================
# --- STYLE PATCH FOR TELEBOT BUTTONS (COLORFUL BUTTONS) ---
# ============================================
_old_inline_dict = InlineKeyboardButton.to_dict
def _new_inline_dict(self):
    d = _old_inline_dict(self)
    if hasattr(self, 'style'): d['style'] = self.style
    return d
InlineKeyboardButton.to_dict = _new_inline_dict

_old_kb_dict = KeyboardButton.to_dict
def _new_kb_dict(self):
    d = _old_kb_dict(self)
    if hasattr(self, 'style'): d['style'] = self.style
    return d
KeyboardButton.to_dict = _new_kb_dict

def ibtn(text, callback_data=None, url=None, style=None, copy_text_str=None):
    kwargs = {'text': text}
    if callback_data: kwargs['callback_data'] = callback_data
    if url: kwargs['url'] = url
    
    if copy_text_str:
        if HAS_COPY_BTN:
            kwargs['copy_text'] = CopyTextButton(text=str(copy_text_str))
        else:
            kwargs['callback_data'] = f"cp_{copy_text_str}"
            
    b = InlineKeyboardButton(**kwargs)
    if style: b.style = style
    return b

def rbtn(text, style=None):
    b = KeyboardButton(text=text)
    if style: b.style = style
    return b

# --- CONFIGURATION ---
TOKEN = "8445159054:AAEbMF8ynz9IG3QRS4SEOd4rn6Islw9Q0_Q"  
ADMIN_ID = 6644381377
BASE_URL = "http://185.190.142.81"
NEXA_API_KEY = "nxa_48dce5227efecc6ca2d1841b51860fdd426634a9"
BOT_NAME = "GHOST OTP SMS BOT"

# Default values (Now dynamically controlled from Admin Panel)
MAX_NUMBERS = 3  
REF_BONUS = 0.085  
OTP_BONUS = 0.00041 

# --- DESIGN CONSTANTS ---
DIVIDER = "━━━━━━━━━━━━━━━━━━━━━━"
THIN_DIVIDER = "──────────────────────"

BTN_SMS = "📱 𝗚𝗘𝗧 𝗡𝗨𝗠𝗕𝗘𝗥"
BTN_TRAFFIC = "📊 𝗧𝗥𝗔𝗙𝗙𝗜𝗖 𝗦𝗘𝗥𝗩𝗘𝗥"
BTN_BALANCE = "👤 𝗣𝗥𝗢𝗙𝗜𝗟𝗘 & 𝗪𝗔𝗟𝗟𝗘𝗧"
BTN_LEADERBOARD = "🏆 𝗟𝗘𝗔𝗗𝗘𝗥𝗕𝗢𝗔𝗥𝗗"
BTN_SUPPORT = "🎧 𝗦𝗨𝗣𝗣𝗢𝗥𝗧 & 𝗛𝗘𝗟𝗣"
BTN_2FA = "🔐 𝟮𝗙𝗔 𝗢𝗡𝗟𝗜𝗡𝗘"
BTN_ADMIN = "⚙️ 𝗔𝗗𝗠𝗜𝗡 𝗣𝗔𝗡𝗘𝗟"

MAIN_MENU_BUTTONS = [BTN_SMS, BTN_TRAFFIC, BTN_BALANCE, BTN_LEADERBOARD, BTN_SUPPORT, BTN_2FA, BTN_ADMIN]

# FIXED: Massive 100-thread pool to prevent button spam from locking the bot
bot = telebot.TeleBot(TOKEN, num_threads=100)
bot_info = bot.get_me()
BOT_USERNAME = bot_info.username

# Database File - Same name guarantees zero data loss
DATA_FILE = "mino_x_sms_data_v12.json"

active_polls = {}
user_states = {}
traffic_cooldowns = {} 
data_lock = threading.RLock()

# ============================================
# SMART UTILITIES & HELPERS
# ============================================
def get_greeting():
    hour = datetime.now().hour
    if hour < 12: return "🌅 GOOD MORNING"
    elif 12 <= hour < 18: return "☀️ GOOD AFTERNOON"
    else: return "🌙 GOOD EVENING"

def get_user_tier(otp_count):
    if otp_count >= 100: return "💎 VIP"
    elif otp_count >= 50: return "🥇 PRO"
    elif otp_count >= 10: return "🥈 MEMBER"
    else: return "🥉 NEWBIE"

def __get_all_api_keys(main_api):
    keys = []
    if main_api: keys.append(main_api)
    backups = [
        "nxa_9f98d005c1b823cd376a2ef1211b5af8ba920b75",
        "nxa_14a29f2589b63aa06e7e2724179c2a51666d8073",
        "nxa_9f98d005c1b823cd376a2ef1211b5af8ba920b75"
    ]
    for b in backups:
        if b and b not in keys: keys.append(b)
    return keys

SERVICE_SMS_KEYWORDS = {
    "whatsapp": ["whatsapp", "wa", "wap", "w/a", "whatsapp business"],
    "facebook": ["facebook", "fb", "meta", "fbook"],
    "instagram": ["instagram", "insta", "ig"],
    "telegram": ["telegram", "tg", "tele"],
    "google": ["google", "gmail", "youtube", "g-"],
    "tiktok": ["tiktok", "tik tok", "tikvideo"],
    "twitter": ["twitter", "x.com", "x code"],
    "binance": ["binance", "bnb"],
    "microsoft": ["microsoft", "ms", "outlook"],
    "apple": ["apple", "icloud", "itunes"]
}

def get_service_code(service_name):
    name = str(service_name).lower()
    mapping = {
        "whatsapp": "wa", "facebook": "fb", "instagram": "ig", "telegram": "tg",
        "google": "go", "tiktok": "tt", "twitter": "tw", "binance": "bn",
        "microsoft": "ms", "apple": "ap", "yahoo": "yh", "snapchat": "sn", 
        "discord": "dc", "netflix": "nf", "uber": "ub"
    }
    for key, val in mapping.items():
        if key in name: return val
    return name

def detect_service_from_sms(sms_text, app_name=""):
    sms_lower = str(sms_text).lower() if sms_text else ""
    if any(w in sms_lower for w in ["whatsapp", "wa ", " w/a"]): return "Whatsapp"
    for service, keywords in SERVICE_SMS_KEYWORDS.items():
        if any(kw in sms_lower for kw in keywords): return service.title()
    return app_name.title() if app_name else "Unknown"

# --- Extensive Country Flags ---
COUNTRY_FLAGS = {
    "algeria": "🇩🇿", "angola": "🇦🇴", "benin": "🇧🇯", "botswana": "🇧🇼", "burkina faso": "🇧🇫", "cameroon": "🇨🇲", "cote d'ivoire": "🇨🇮", "côte d'ivoire": "🇨🇮", "ivory coast": "🇨🇮", "egypt": "🇪🇬", "ethiopia": "🇪🇹", "ghana": "🇬🇭", "kenya": "🇰🇪", "madagascar": "🇲🇬", "morocco": "🇲🇦", "nigeria": "🇳🇬", "south africa": "🇿🇦", "tanzania": "🇹🇿", "uganda": "🇺🇬", "senegal": "🇸🇳", "mali": "🇲🇱", "sudan": "🇸🇩",
    "afghanistan": "🇦🇫", "bangladesh": "🇧🇩", "china": "🇨🇳", "india": "🇮🇳", "indonesia": "🇮🇩", "iran": "🇮🇷", "iraq": "🇮🇶", "israel": "🇮🇱", "japan": "🇯🇵", "malaysia": "🇲🇾", "nepal": "🇳🇵", "pakistan": "🇵🇰", "philippines": "🇵🇭", "saudi arabia": "🇸🇦", "south korea": "🇰🇷", "sri lanka": "🇱🇰", "thailand": "🇹🇭", "turkey": "🇹🇷", "uae": "🇦🇪", "vietnam": "🇻🇳",
    "france": "🇫🇷", "germany": "🇩🇪", "italy": "🇮🇹", "netherlands": "🇳🇱", "poland": "🇵🇱", "russia": "🇷🇺", "spain": "🇪🇸", "sweden": "🇸🇪", "ukraine": "🇺🇦", "uk": "🇬🇧", "united kingdom": "🇬🇧",
    "canada": "🇨🇦", "mexico": "🇲🇽", "usa": "🇺🇸", "united states": "🇺🇸",
    "argentina": "🇦🇷", "brazil": "🇧🇷", "colombia": "🇨🇴", "peru": "🇵🇪",
    "australia": "🇦🇺", "new zealand": "🇳🇿"
}

EMOJI_COLLECTION = {
    "facebook": "🔵", "whatsapp": "🟢", "whatsapp businesses": "🟢",
    "telegram": "✈️", "Instagram": "🟣", "twitter": "𝕏", "x": "𝕏",
    "google": "🔍", "gmail": "📧", "youtube": "🟥", "apple": "🍎",
    "microsoft": "💻", "tiktok": "⚫", "snapchat": "👻", "binance": "🟨"
}

def get_country_flag(country_name):
    if not country_name: return "🌍"
    name = str(country_name).lower().strip()
    if name in COUNTRY_FLAGS: return COUNTRY_FLAGS[name]
    for country, flag in COUNTRY_FLAGS.items():
        if len(country) >= 4 and (country in name or name in country): return flag
    return "🌍"

def emo(keyword, default="🟣"):
    if not keyword: return default
    kw = str(keyword).lower().strip()
    if kw in EMOJI_COLLECTION: return EMOJI_COLLECTION[kw]
    for key, emoji in EMOJI_COLLECTION.items():
        if len(key) >= 3 and key in kw: return emoji
    return get_country_flag(kw) if get_country_flag(kw) != "🌍" else default

def format_url(url):
    url = url.strip()
    if url and not url.startswith(('http://', 'https://', 'tg://')): return 'https://' + url
    return url

def extract_channel_username(url):
    if "t.me/" in url:
        parts = url.split("t.me/")
        if len(parts) > 1:
            username = parts[1].split("/")[0].split("?")[0]
            if not username.startswith("@"): username = "@" + username
            return username
    return ""

def mask_number(phone):
    phone_str = str(phone).replace('+', '')
    if len(phone_str) > 6: return f"+{phone_str[:3]}XXXX{phone_str[-3:]}"
    return f"+{phone_str}"

def safe_send(chat_id, text, reply_markup=None, message_id=None):
    try:
        clean_text = re.sub(r'<tg-emoji[^>]*>(.*?)</tg-emoji>', r'\1', text)
        if message_id:
            return bot.edit_message_text(clean_text, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=reply_markup)
        else:
            return bot.send_message(chat_id, clean_text, parse_mode="HTML", reply_markup=reply_markup)
    except Exception:
        return None

def load_data():
    with data_lock:
        default_data = {
            "users": [], "services_data": {}, "forward_groups": [], 
            "main_otp_link": "https://t.me/", "watermark": BOT_NAME,
            "force_join_enabled": False, "force_join_channels": [],
            "balances": {}, "banned_users": [], "maintenance": False,
            "api_key": NEXA_API_KEY, "otp_counts": {},
            "wallets": {}, "referred_by": {}, "referral_paid": [], "processed_otps": [],
            "user_profiles": {}, 
            "settings": {
                "welcome": "WELCOME TO MINO X SMS!",
                "support": "📝 <b>PLEASE CONTACT THE ADMINISTRATOR FOR ANY SUPPORT REQUESTS.</b>",
                "withdraw": "📝 <b>MINIMUM WITHDRAWAL IS $0.50.</b>",
                "leadership": "🏆 <b>TOP USERS LIST:</b>",
                "otp_bonus": OTP_BONUS,
                "ref_bonus": REF_BONUS,
                "max_numbers": MAX_NUMBERS,
                "admin_alerts": False
            }
        }
        if not os.path.exists(DATA_FILE):
            with open(DATA_FILE, "w", encoding='utf-8') as f: json.dump(default_data, f, indent=4)
            return default_data
        try:
            with open(DATA_FILE, "r", encoding='utf-8') as f:
                content = f.read().strip()
                if not content: return default_data
                data = json.loads(content)
                for key, val in default_data.items():
                    if key not in data: data[key] = val
                for key, val in default_data["settings"].items():
                    if key not in data["settings"]: data["settings"][key] = val
                return data
        except: return default_data

def save_data(data):
    with data_lock:
        try:
            with open(DATA_FILE, "w", encoding='utf-8') as f: json.dump(data, f, indent=4)
        except: pass

def add_user(user_id, username=None, first_name=None, referrer_id=None):
    data = load_data()
    uid_str = str(user_id)
    changed = False
    
    is_new_user = False
    if user_id not in data.setdefault("users", []):
        data["users"].append(user_id)
        is_new_user = True
        changed = True
        if referrer_id and str(referrer_id) != uid_str:
            data.setdefault("referred_by", {})[uid_str] = str(referrer_id)
            
    profile = data.setdefault("user_profiles", {}).setdefault(uid_str, {})
    if profile.get("username") != (username or "N/A"):
        profile["username"] = username or "N/A"
        changed = True
    if profile.get("first_name") != (first_name or "Unknown"):
        profile["first_name"] = first_name or "Unknown"
        changed = True
    if "history" not in profile: 
        profile["history"] = []
        changed = True
    
    if changed:
        save_data(data)
    
    if is_new_user and data.get("settings", {}).get("admin_alerts", False):
        try:
            safe_send(ADMIN_ID, f"🔔 <b>NEW USER ALERT</b>\nID: <code>{user_id}</code>\nUser: @{username or 'N/A'}\nName: {first_name}")
        except: pass

def add_to_history(user_id, service, number, otp):
    data = load_data()
    uid_str = str(user_id)
    profile = data.setdefault("user_profiles", {}).setdefault(uid_str, {})
    history = profile.setdefault("history", [])
    
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = {"service": service, "number": number, "otp": otp, "date": date_str}
    history.insert(0, entry)
    
    if len(history) > 5:
        profile["history"] = history[:5]
        
    save_data(data)

def check_and_pay_referral(user_id):
    data = load_data()
    uid_str = str(user_id)
    dynamic_ref_bonus = data.get("settings", {}).get("ref_bonus", REF_BONUS)
    
    referrer = data.get("referred_by", {}).get(uid_str)
    if referrer and uid_str not in data.get("referral_paid", []):
        current_bal = data.get("balances", {}).get(referrer, 0.0)
        data.setdefault("balances", {})[referrer] = round(current_bal + dynamic_ref_bonus, 5)
        data.setdefault("referral_paid", []).append(uid_str)
        save_data(data)
        try:
            safe_send(int(referrer), f"🎁 <b>REFERRAL BONUS!</b>\nYour referral joined and used the bot. You received <b>${dynamic_ref_bonus}</b>!")
        except: pass

def is_user_allowed(user_id, chat_id=None, call_id=None):
    if user_id == ADMIN_ID: return True
    data = load_data()
    if user_id in data.get("banned_users", []):
        if chat_id: safe_send(chat_id, "🚫 <b>YOU ARE BANNED FROM USING THIS BOT.</b>")
        if call_id: bot.answer_callback_query(call_id, "🚫 YOU ARE BANNED!", show_alert=True)
        return False
    if data.get("maintenance", False):
        if chat_id: safe_send(chat_id, "⚙️ <b>BOT IS CURRENTLY UNDER MAINTENANCE. PLEASE TRY AGAIN LATER.</b>")
        if call_id: bot.answer_callback_query(call_id, "⚙️ BOT IS UNDER MAINTENANCE!", show_alert=True)
        return False
    return True

def check_force_join(user_id):
    if user_id == ADMIN_ID: return True 
    data = load_data()
    if not data.get("force_join_enabled"): return True
    channels = data.get("force_join_channels", [])
    if not channels: return True 
    for link in channels:
        chat_username = extract_channel_username(link)
        if not chat_username: continue 
        try:
            member = bot.get_chat_member(chat_username, user_id)
            if member.status not in ['member', 'administrator', 'creator']: return False 
        except: pass
    return True 

def show_force_join_message(chat_id, message_id=None):
    data = load_data()
    channels = data.get("force_join_channels", [])
    text = f"⚠️ <b>ACCESS DENIED</b> ⚠️\n{DIVIDER}\n📢 <b>JOIN OUR CHANNELS TO USE THIS BOT!</b>\n<b>CLICK JOINED AFTER JOINING!</b>\n{DIVIDER}"
    markup = InlineKeyboardMarkup()
    for link in channels:
        markup.add(ibtn("📢 JOIN CHANNEL", url=link, style="primary"))
    markup.add(ibtn("✅ JOINED ✅", callback_data="check_join", style="success"))
    safe_send(chat_id, text, markup, message_id)

def get_main_menu(user_id):
    try:
        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2, is_persistent=True)
    except TypeError:
        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        
    markup.add(rbtn(BTN_SMS, "success"), rbtn(BTN_TRAFFIC, "primary"))
    markup.add(rbtn(BTN_BALANCE, "success"), rbtn(BTN_LEADERBOARD, "primary"))
    markup.add(rbtn(BTN_SUPPORT, "danger"), rbtn(BTN_2FA, "success"))
    if user_id == ADMIN_ID: markup.add(rbtn(BTN_ADMIN, "primary"))
    return markup

# FIXED: Global cancel check utility that aborts stuck prompts and deletes them.
def check_cancel(message, msg_id, fallback_func, *args):
    text = message.text if message.text else ""
    if not text or text == '/cancel' or text in MAIN_MENU_BUTTONS or text.startswith('/'):
        bot.clear_step_handler_by_chat_id(message.chat.id)
        try: bot.delete_message(message.chat.id, msg_id)
        except: pass
        
        if text in MAIN_MENU_BUTTONS: 
            handle_text(message)
        elif text == '/start': 
            send_welcome(message)
        else:
            if fallback_func: fallback_func(message.chat.id, None, *args)
        return True
    return False

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    if not is_user_allowed(user_id, chat_id=message.chat.id): return
    bot.clear_step_handler_by_chat_id(message.chat.id)
    
    referrer_id = None
    if " " in message.text:
        parts = message.text.split(" ")
        if len(parts) > 1 and parts[1].startswith("ref_"):
            try: referrer_id = int(parts[1].split("_")[1])
            except: pass
            
    add_user(user_id, message.from_user.username, message.from_user.first_name, referrer_id)
    
    if not check_force_join(user_id):
        show_force_join_message(message.chat.id)
        return
    show_main_menu(message.chat.id)

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user_id = message.from_user.id
    if not is_user_allowed(user_id, chat_id=message.chat.id): return
    text = message.text.upper()
    bot.clear_step_handler_by_chat_id(message.chat.id)
    
    add_user(user_id, message.from_user.username, message.from_user.first_name)
    check_and_pay_referral(user_id)

    if "𝗚𝗘𝗧 𝗡𝗨𝗠𝗕𝗘𝗥" in text or "GET NUMBER" in text or "SMS" in text:
        if not check_force_join(user_id): return show_force_join_message(message.chat.id)
        show_user_services(message.chat.id)
    elif "𝗧𝗥𝗔𝗙𝗙𝗜𝗖 𝗦𝗘𝗥𝗩𝗘𝗥" in text or "TRAFFIC" in text:
        if not check_force_join(user_id): return show_force_join_message(message.chat.id)
        show_traffic_search(message.chat.id)
    elif "𝟮𝗙𝗔 𝗢𝗡𝗟𝗜𝗡𝗘" in text or "2FA" in text:
        if not check_force_join(user_id): return show_force_join_message(message.chat.id)
        show_2fa_menu(message.chat.id)
    elif "𝗣𝗥𝗢𝗙𝗜𝗟𝗘" in text or "BALANCE" in text or "WALLET" in text:
        if not check_force_join(user_id): return show_force_join_message(message.chat.id)
        show_profile_withdraw(message.chat.id)
    elif "𝗟𝗘𝗔𝗗𝗘𝗥𝗕𝗢𝗔𝗥𝗗" in text or "LEADERBOARD" in text:
        if not check_force_join(user_id): return show_force_join_message(message.chat.id)
        show_leadership(message.chat.id)
    elif "𝗦𝗨𝗣𝗣𝗢𝗥𝗧" in text or "SUPPORT" in text or "HELP" in text:
        if "PANEL" not in text and "𝗣𝗔𝗡𝗘𝗟" not in text:
            if not check_force_join(user_id): return show_force_join_message(message.chat.id)
            show_support(message.chat.id)
    elif "𝗔𝗗𝗠𝗜𝗡 𝗣𝗔𝗡𝗘𝗟" in text or "ADMIN PANEL" in text:
        if user_id == ADMIN_ID: show_admin_panel(message.chat.id)
        else: bot.send_message(message.chat.id, f"⚠️ <b>ACCESS DENIED!</b>", parse_mode="HTML")
    else:
        # FIXED: Bring back the menu if command goes missing
        bot.send_message(message.chat.id, "🔄 <b>MENU REFRESHED.</b>", parse_mode="HTML", reply_markup=get_main_menu(user_id))

# --- USER PROFILE & WALLET SYSTEM (PREMIUM UI) ---
def show_profile_withdraw(chat_id, message_id=None):
    data = load_data()
    uid_str = str(chat_id)
    bal = data.get("balances", {}).get(uid_str, 0.0)
    otp_count = data.get("otp_counts", {}).get(uid_str, 0)
    w_text = data.get("settings", {}).get("withdraw", "WITHDRAWAL INFO")
    watermark = data.get("watermark", BOT_NAME)
    dynamic_ref_bonus = data.get("settings", {}).get("ref_bonus", REF_BONUS)
    
    profile = data.get("user_profiles", {}).get(uid_str, {})
    name = profile.get("first_name", "Unknown")
    username = profile.get("username", "N/A")
    username_str = f"@{username}" if username != "N/A" else "N/A"
    
    tier = get_user_tier(otp_count)
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{chat_id}" if BOT_USERNAME else "N/A"
    
    u_wallets = data.get("wallets", {}).get(uid_str, {})
    wallet_display = ""
    for w_type in ["bkash", "nagad", "rocket", "binance"]:
        if w_type in u_wallets:
            wallet_display += f"✅ <b>{w_type.upper()}:</b> <code>{u_wallets[w_type]}</code>\n"
            
    if not wallet_display:
        wallet_display = "<i>NO WALLETS ADDED YET.</i>\n"
    
    text = f"👤 <b>MY PROFILE & WALLETS</b> 👤\n{DIVIDER}\n📛 <b>NAME:</b> {html.escape(name)}\n🔗 <b>USERNAME:</b> {username_str}\n🆔 <b>USER ID:</b> <code>{chat_id}</code>\n🎖️ <b>ACCOUNT TIER:</b> {tier}\n{THIN_DIVIDER}\n💵 <b>CURRENT BALANCE:</b> <b>${bal:.5f}</b>\n🎯 <b>TOTAL OTPS:</b> {otp_count}\n\n🎁 <b>YOUR REFERRAL LINK:</b>\n<code>{ref_link}</code>\n<i>(Get ${dynamic_ref_bonus} per active referral!)</i>\n{THIN_DIVIDER}\n🏦 <b>YOUR SAVED WALLETS:</b>\n{wallet_display}\n🏦 <b>WITHDRAWAL INFO:</b>\n<i>{w_text.upper()}</i>\n{DIVIDER}\n<b>MANAGE YOUR PAYMENT WALLETS:</b>\n{DIVIDER}\n💎 <b>{watermark}</b> 💎"
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        ibtn("🔄 REFRESH PROFILE", callback_data="refresh_profile", style="primary"),
        ibtn("📜 RECENT OTPS", callback_data="recent_otps", style="success")
    )
    
    for w_type in ["bkash", "nagad", "rocket", "binance"]:
        if w_type in u_wallets:
            markup.add(
                ibtn(f"✏️ CHANGE {w_type.upper()}", callback_data=f"set_wallet_{w_type}", style="primary"),
                ibtn(f"🗑️ DEL {w_type.upper()}", callback_data=f"del_wallet_{w_type}", style="danger")
            )
        else:
            markup.add(ibtn(f"💳 ADD {w_type.upper()}", callback_data=f"set_wallet_{w_type}", style="success"))
            
    safe_send(chat_id, text, markup, message_id)

def show_recent_otps(chat_id, message_id=None):
    data = load_data()
    uid_str = str(chat_id)
    history = data.get("user_profiles", {}).get(uid_str, {}).get("history", [])
    
    text = f"📜 <b>YOUR RECENT OTPS</b> 📜\n{DIVIDER}\n"
    if not history:
        text += "<i>You haven't received any OTPs yet.</i>\n"
    else:
        for idx, entry in enumerate(history, 1):
            text += f"<b>{idx}.</b> 📲 {entry['service'].upper()}\n"
            text += f"📞 <code>{entry['number']}</code>\n"
            text += f"🎯 <b>OTP:</b> <code>{entry['otp']}</code>\n"
            text += f"🕒 {entry['date']}\n{THIN_DIVIDER}\n"
            
    markup = InlineKeyboardMarkup().add(ibtn("🔙 BACK TO PROFILE", callback_data="back_to_profile", style="danger"))
    safe_send(chat_id, text, markup, message_id)
    
def show_leadership(chat_id, message_id=None):
    data = load_data()
    l_text = data.get("settings", {}).get("leadership", "LEADERSHIP BOARD")
    watermark = data.get("watermark", BOT_NAME)
    otp_counts = data.get("otp_counts", {})
    profiles = data.get("user_profiles", {})
    
    sorted_users = sorted(otp_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    board_text = ""
    for idx, (uid, count) in enumerate(sorted_users, 1):
        name = profiles.get(uid, {}).get("first_name", uid)
        board_text += f"<b>{idx}.</b> 👤 {html.escape(name)} - <b>{count} OTPs</b>\n"
    if not board_text: board_text = "<i>NO OTP RECORDS YET.</i>\n"
    user_otp_count = otp_counts.get(str(chat_id), 0)
    text = f"🏆 <b>LEADERBOARD & OTP COUNT</b> 🏆\n{DIVIDER}\n{l_text.upper()}\n\n🎯 <b>YOUR TOTAL OTPS: {user_otp_count}</b>\n\n📊 <b>TOP 10 USERS:</b>\n{board_text}{DIVIDER}\n💎 <b>{watermark}</b> 💎"
    safe_send(chat_id, text, None, message_id)
    
def show_support(chat_id, message_id=None):
    data = load_data()
    s_text = data.get("settings", {}).get("support", "SUPPORT INFO")
    watermark = data.get("watermark", BOT_NAME)
    text = f"🎧 <b>SUPPORT & HELP CENTER</b> 🎧\n{DIVIDER}\n{s_text.upper()}\n{THIN_DIVIDER}\n❓ <b>HOW TO USE:</b>\n1️⃣ Use 'Get Number' to select a service.\n2️⃣ Choose a country to get a number.\n3️⃣ Copy the number & request OTP.\n4️⃣ Wait in the bot for the code!\n{DIVIDER}\n💎 <b>{watermark}</b> 💎"
    safe_send(chat_id, text, None, message_id)

def show_2fa_menu(chat_id, message_id=None):
    text = f"🔴 <b><i><u>GENERATE SECURE 2FA CODES</u></i></b> 🔴\n\n<b><i><u>CLICK THE BUTTON BELOW TO PROCEED</u></i></b>"
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(ibtn("🔐 GENERATE 2FA CODE", callback_data="2fa_generate", style="success"))
    safe_send(chat_id, text, markup, message_id)

def show_main_menu(chat_id, message_id=None):
    data = load_data()
    bal = data.get("balances", {}).get(str(chat_id), 0.0)
    welcome_msg = data.get("settings", {}).get("welcome", "WELCOME TO MINO X SMS!")
    watermark = data.get("watermark", BOT_NAME)
    
    profile = data.get("user_profiles", {}).get(str(chat_id), {})
    name = profile.get("first_name", "USER")
    
    greeting = get_greeting()
    
    text = f"💠 <b>{welcome_msg.upper()}</b> 💠\n{DIVIDER}\n{greeting}, <b>{html.escape(name.upper())}</b>!\n💳 <b>YOUR BALANCE:</b> <b>${bal:.5f}</b>\n{DIVIDER}\n🔰 <b>AVAILABLE FEATURES:</b>\n▹ 📱 <b>GET NUMBER</b>\n▹ 📊 <b>TRAFFIC SERVER</b>\n▹ 💰 <b>PROFILE & WALLET</b>\n▹ 🏆 <b>LEADERBOARD</b>\n▹ 🎧 <b>SUPPORT & HELP</b>\n▹ 🔐 <b>2FA AUTHENTICATOR</b>\n{DIVIDER}\n💎 <b>{watermark}</b> 💎"
    safe_send(chat_id, text, get_main_menu(chat_id), message_id)

def show_user_services(chat_id, message_id=None):
    data = load_data()
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = []
    for srv_id, srv in data.get("services_data", {}).items():
        buttons.append(ibtn(f"{emo(srv['name'])} {srv['name'].upper()}", callback_data=f"usr_s|{srv_id}", style="primary"))
    if buttons: markup.add(*buttons)
    else: markup.add(ibtn("❌ NO SERVICES ADDED", callback_data="ignore", style="danger"))
    text = f"📱 <b>SELECT SERVICE</b>\n{DIVIDER}"
    safe_send(chat_id, text, markup, message_id)

def show_traffic_search(chat_id, message_id=None):
    markup = InlineKeyboardMarkup().add(ibtn("❌ CLOSE", callback_data="close_menu", style="danger"))
    text = f"📊 <b>TRAFFIC SERVER</b> 📊\n{DIVIDER}\n<b>TYPE SERVICE NAME (E.G. WHATSAPP)</b>\n<b>SEND /cancel TO STOP</b>\n{DIVIDER}"
    if not message_id:
        msg = safe_send(chat_id, text, markup)
        if msg: bot.register_next_step_handler_by_chat_id(chat_id, process_api_traffic_search, msg.message_id)
    else:
        safe_send(chat_id, text, markup, message_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_api_traffic_search, message_id)

def show_user_countries(chat_id, srv_id, message_id=None):
    data = load_data()
    srv_data = data.get("services_data", {}).get(srv_id)
    if not srv_data: return
    markup = InlineKeyboardMarkup(row_width=2)
    countries = srv_data.get("countries", {})
    if not countries:
        markup.add(ibtn("❌ OUT OF STOCK", callback_data="ignore", style="danger"))
    else:
        markup.add(ibtn("🎲 𝗔𝗨𝗧𝗢 𝗦𝗘𝗟𝗘𝗖𝗧 𝗖𝗢𝗨𝗡𝗧𝗥𝗬 🎲", callback_data=f"usr_auto_cnt|{srv_id}", style="success"))
        buttons = []
        for cnt_id, cnt in countries.items():
            flag = get_country_flag(cnt['name'])
            range_count = len(cnt.get("ranges", {}))
            buttons.append(ibtn(f"{flag} {cnt['name'].upper()} [📦 {range_count}]", callback_data=f"usr_c|{srv_id}|{cnt_id}", style="primary"))
        markup.add(*buttons)
    markup.add(ibtn("🔙 BACK", callback_data="back_to_user_services", style="danger"))
    text = f"🌍 <b>SELECT COUNTRY</b>\n{DIVIDER}\n📱 <b>{html.escape(srv_data['name'].upper())}</b>"
    safe_send(chat_id, text, markup, message_id)

# --- NEW CENTRALIZED ADMIN PANEL ---
def show_admin_panel(chat_id, message_id=None):
    data = load_data()
    watermark = data.get("watermark", BOT_NAME)
    total_ranges = sum(len(cnt.get("ranges", {})) for srv in data.get("services_data", {}).values() for cnt in srv.get("countries", {}).values())
    total_otps = sum(data.get("otp_counts", {}).values())
    
    text = f"👑 <b>ADMIN PANEL</b> 👑\n{DIVIDER}\n📊 <b>DATABASE STATS</b>\n{THIN_DIVIDER}\n👤 <b>TOTAL USERS:</b> <code>{len(data.get('users', []))}</code>\n📱 <b>TOTAL RANGES:</b> <code>{total_ranges}</code>\n🎯 <b>TOTAL OTPS:</b> <code>{total_otps}</code>\n🚫 <b>BANNED USERS:</b> <code>{len(data.get('banned_users', []))}</code>\n{DIVIDER}\n💎 <b>{watermark}</b> 💎"
    
    m_state = "🟢 ON" if data.get("maintenance") else "🔴 OFF"
    alerts_state = "🟢 ON" if data.get("settings", {}).get("admin_alerts") else "🔴 OFF"
    markup = InlineKeyboardMarkup(row_width=2)
    
    # The new Centralized User Management Button
    markup.add(ibtn("🔍 SEARCH & MANAGE USER", "admin_search_user", style="success"))
    
    markup.add(ibtn("🛠️ MANAGE SERVICES", "admin_manage_service", style="primary"), ibtn("🔗 GROUP SETTINGS", "admin_group_settings", style="primary"))
    markup.add(ibtn("📣 FORCE JOIN", "admin_force_join", style="primary"), ibtn("💎 SET WATERMARK", "admin_set_watermark", style="primary"))
    markup.add(ibtn("📢 BROADCAST", "admin_broadcast", style="primary"), ibtn("📝 WELCOME & WITHDRAW", "admin_edit_texts", style="primary"))
    markup.add(ibtn("🏆 EDIT LEADERBOARD", "admin_edit_leadership", style="primary"), ibtn("🎧 EDIT SUPPORT", "admin_edit_support", style="primary"))
    
    markup.add(ibtn(f"⚙️ MAINTENANCE: {m_state}", "admin_maintenance", style="danger"), ibtn("🔑 API KEY", "admin_api_key", style="primary"))
    markup.add(ibtn("🎁 REWARD ALL", "admin_reward_all", style="success"), ibtn("➖ DEDUCT ALL", "admin_deduct_all", style="danger"))
    
    markup.add(ibtn("📥 EXPORT ALL DATA", "admin_export_data", style="success"), ibtn("💾 BACKUP DATABASE", "admin_backup_db", style="success")) 
    markup.add(ibtn("🧹 RESET ALL OTPS", "admin_reset_otp", style="danger"))
    
    # -----------------------------------------------------
    # 10 NEW ADMIN PANEL FEATURES ADDED BELOW
    # -----------------------------------------------------
    markup.add(ibtn("👥 USER LIST (ID & NAME)", "admin_user_list", style="primary"), ibtn("✉️ MSG A USER", "admin_msg_user", style="primary"))
    markup.add(ibtn("🚫 DIRECT BAN", "admin_direct_ban", style="danger"), ibtn("✅ DIRECT UNBAN", "admin_direct_unban", style="success"))
    markup.add(ibtn("🧹 CLEAR BAN LIST", "admin_clear_banned", style="danger"), ibtn("📈 SERVER STATS", "admin_server_stats", style="primary"))
    markup.add(ibtn("💰 EDIT OTP BONUS", "admin_edit_otp_bonus", style="success"), ibtn("🎁 EDIT REF BONUS", "admin_edit_ref_bonus", style="success"))
    markup.add(ibtn("📱 EDIT MAX NUMS", "admin_edit_max_nums", style="primary"), ibtn(f"🔔 ADMIN ALERTS: {alerts_state}", "admin_alerts_toggle", style="primary"))
    
    safe_send(chat_id, text, markup, message_id)

def show_admin_services(chat_id, message_id=None):
    data = load_data()
    markup = InlineKeyboardMarkup(row_width=2)
    for srv_id, srv in data.get("services_data", {}).items(): 
        markup.add(ibtn(f"📁 {srv['name'].upper()}", callback_data=f"adm_s|{srv_id}", style="primary"))
    markup.add(ibtn("➕ ADD SERVICE", callback_data="add_srv", style="success"))
    markup.add(ibtn("🔙 BACK", callback_data="back_to_admin", style="danger"))
    safe_send(chat_id, f"⚙️ <b>MANAGE SERVICES</b>\n{DIVIDER}\n<b>SELECT A SERVICE:</b>", markup, message_id)

def show_admin_countries(chat_id, srv_id, message_id=None):
    data = load_data()
    srv_data = data.get("services_data", {}).get(srv_id)
    if not srv_data: return
    markup = InlineKeyboardMarkup(row_width=2)
    for cnt_id, cnt in srv_data.get("countries", {}).items(): 
        flag = get_country_flag(cnt['name'])
        markup.add(ibtn(f"{flag} {cnt['name'].upper()}", callback_data=f"adm_c|{srv_id}|{cnt_id}", style="primary"))
    markup.add(ibtn("➕ ADD COUNTRY", callback_data=f"add_cnt|{srv_id}", style="success"))
    markup.add(ibtn(f"🗑️ DELETE SERVICE", callback_data=f"del_srv|{srv_id}", style="danger"))
    markup.add(ibtn("🔙 BACK", callback_data="admin_manage_service", style="danger"))
    safe_send(chat_id, f"🌍 <b>COUNTRIES → {html.escape(srv_data['name'].upper())}</b>\n{DIVIDER}\n<b>SELECT COUNTRY:</b>", markup, message_id)

def show_admin_ranges(chat_id, srv_id, cnt_id, message_id=None):
    data = load_data()
    srv_data = data.get("services_data", {}).get(srv_id)
    cnt_data = srv_data.get("countries", {}).get(cnt_id) if srv_data else None
    if not cnt_data: return
    flag = get_country_flag(cnt_data['name'])
    markup = InlineKeyboardMarkup(row_width=1)
    for rng_id, rng_val in cnt_data.get("ranges", {}).items(): 
        markup.add(ibtn(f"❌ {rng_val}", callback_data=f"del_rng|{srv_id}|{cnt_id}|{rng_id}", style="danger"))
    markup.add(ibtn("➕ ADD RANGE", callback_data=f"add_rng|{srv_id}|{cnt_id}", style="success"))
    markup.add(ibtn(f"🗑️ DELETE COUNTRY", callback_data=f"del_cnt|{srv_id}|{cnt_id}", style="danger"))
    markup.add(ibtn("🔙 BACK", callback_data=f"adm_s|{srv_id}", style="primary"))
    safe_send(chat_id, f"{flag} <b>RANGES → {html.escape(srv_data['name'].upper())} → {html.escape(cnt_data['name'].upper())}</b>\n{DIVIDER}\n<b>TAP TO DELETE:</b>", markup, message_id)

def get_force_join_menu():
    data = load_data()
    is_enabled = data.get("force_join_enabled", False)
    channels = data.get("force_join_channels", [])
    status_text = "?? ENABLED" if is_enabled else "🔴 DISABLED"
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(ibtn(f"TOGGLE: {status_text}", callback_data="toggle_force_join", style="success" if is_enabled else "danger"))
    for idx, link in enumerate(channels):
        markup.add(ibtn(f"❌ REMOVE: {link}", callback_data=f"delfjc_{idx}", style="danger"))
    markup.add(ibtn("➕ ADD CHANNEL", callback_data="add_fjc", style="success"))
    markup.add(ibtn("🔙 BACK", callback_data="back_to_admin", style="primary"))
    return markup

def get_group_settings_menu():
    data = load_data()
    markup = InlineKeyboardMarkup(row_width=1)
    otp_link = data.get("main_otp_link", "")
    markup.add(ibtn("🔗 SET OTP GROUP LINK", callback_data="set_main_otp_link", style="primary"))
    if otp_link and otp_link != "https://t.me/":
        markup.add(ibtn("🗑️ REMOVE OTP LINK", callback_data="del_main_otp_link", style="danger"))
    markup.add(ibtn("➕ ADD FORWARD GROUP", callback_data="add_fwd_group", style="success"))
    fwd_groups = data.get("forward_groups", [])
    if fwd_groups:
        markup.add(ibtn("📋 ADDED GROUPS 📋", callback_data="ignore", style="primary"))
        for grp in fwd_groups:
            btn_count = len(grp.get('buttons', []))
            markup.add(ibtn(f"⚙️ {grp['chat_id']} [{btn_count} BTNS]", callback_data=f"editgrp_{grp['chat_id']}", style="primary"))
    markup.add(ibtn("🔙 BACK", callback_data="back_to_admin", style="danger"))
    return markup

def show_edit_group_menu(chat_id, grp_id, message_id=None):
    data = load_data()
    grp = next((g for g in data.get("forward_groups", []) if str(g["chat_id"]) == str(grp_id)), None)
    if not grp:
        safe_send(chat_id, f"🔗 <b>GROUP SETTINGS</b>", get_group_settings_menu(), message_id)
        return
    text = f"⚙️ <b>MANAGE GROUP</b>\n{DIVIDER}\n📱 <b>ID:</b> <code>{grp_id}</code>\n🔘 <b>BUTTONS:</b> {len(grp.get('buttons', []))}"
    markup = InlineKeyboardMarkup(row_width=1)
    for idx, btn in enumerate(grp.get("buttons", [])):
        markup.add(ibtn(f"❌ {btn['name'].upper()}", callback_data=f"delgrpbtn_{grp_id}_{idx}", style="danger"))
    markup.add(ibtn("➕ ADD BUTTON", callback_data=f"addgrpbtn_{grp_id}", style="success"))
    markup.add(ibtn("🗑️ DELETE GROUP", callback_data=f"delfwd_{grp_id}", style="danger"))
    markup.add(ibtn("🔙 BACK", callback_data="admin_group_settings", style="primary"))
    safe_send(chat_id, text, markup, message_id)

# --- Callbacks ---
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    bot.clear_step_handler_by_chat_id(call.message.chat.id)

    user_id = call.from_user.id
    if not is_user_allowed(user_id, call_id=call.id): return

    chat_id = call.message.chat.id
    msg_id = call.message.message_id
    data = load_data()
    api_key = data.get("api_key", NEXA_API_KEY)
    
    if call.data == "ignore": return
    
    # Profile Callbacks
    if call.data == "refresh_profile":
        bot.answer_callback_query(call.id, "✅ Profile Updated Successfully!", show_alert=True)
        show_profile_withdraw(chat_id, msg_id)
        return
    elif call.data == "recent_otps":
        show_recent_otps(chat_id, msg_id)
        return
    elif call.data == "back_to_profile":
        show_profile_withdraw(chat_id, msg_id)
        return
    
    # 2FA 
    if call.data == "2fa_back":
        try: bot.delete_message(chat_id, msg_id)
        except: pass
        return
    elif call.data == "2fa_generate":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="2fa_back", style="danger"))
        text = f"🔴 <b><i><u>ENTER YOUR 2FA SECRET KEY</u></i></b> 🔴\n\n<b><i><u>EXAMPLE: JBSWY3DPEHPK3PXP</u></i></b>\n\n<b><i><u>SEND /cancel TO STOP</u></i></b>"
        safe_send(chat_id, text, markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_2fa_code, msg_id)
        return
        
    # Wallet Settings
    if call.data.startswith("set_wallet_"):
        wallet_type = call.data.split("_")[2]
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="back_to_profile", style="danger"))
        safe_send(chat_id, f"💳 <b>SEND YOUR {wallet_type.upper()} NUMBER/ADDRESS:</b>", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_save_wallet, wallet_type, msg_id)
        return
    if call.data.startswith("del_wallet_"):
        wallet_type = call.data.split("_")[2]
        uid_str = str(chat_id)
        if uid_str in data.get("wallets", {}) and wallet_type in data["wallets"][uid_str]:
            del data["wallets"][uid_str][wallet_type]
            save_data(data)
            bot.answer_callback_query(call.id, f"✅ {wallet_type.upper()} WALLET DELETED!", show_alert=True)
            show_profile_withdraw(chat_id, msg_id)
        return
    
    if call.data in ["main_get_number", "back_to_user_services"] or call.data.startswith("usr_s|") or call.data.startswith("usr_c|") or call.data.startswith("usr_auto_cnt|") or call.data.startswith("chg_r|"):
        if str(chat_id) in active_polls: 
            active_polls[str(chat_id)] = False 
        if not check_force_join(user_id):
            show_force_join_message(chat_id, msg_id)
            return
            
    if call.data == "check_join":
        if check_force_join(user_id):
            bot.answer_callback_query(call.id, f"✅ WELCOME TO {data.get('watermark', BOT_NAME)}!", show_alert=True)
            try: bot.delete_message(chat_id, msg_id)
            except: pass
            show_main_menu(chat_id, None) 
        else:
            bot.answer_callback_query(call.id, "❌ PLEASE JOIN THE CHANNEL FIRST!", show_alert=True)
        return
        
    if call.data == "close_menu":
        try: bot.delete_message(chat_id, msg_id)
        except: pass
        return
    
    # --------------------------------------------
    # ADMIN PANEL ROUTES
    # --------------------------------------------
    if call.data.startswith("adm_") or call.data.startswith("admin_") or call.data.startswith("add_") or call.data.startswith("del_") or call.data.startswith("editgrp_") or call.data in ["admin_broadcast", "admin_group_settings", "admin_set_watermark", "admin_force_join", "toggle_force_join", "add_fjc", "back_to_admin", "admin_manage_service", "admin_export_data", "admin_edit_withdraw", "admin_edit_leadership", "admin_edit_support", "admin_edit_texts", "admin_backup_db", "admin_search_user"]:
        if user_id != ADMIN_ID: return safe_send(chat_id, f"⚠️ <b>ACCESS DENIED!</b>", None, msg_id)

    if call.data == "back_to_admin": show_admin_panel(chat_id, msg_id)
    
    # --- NEW CENTRALIZED USER SEARCH ---
    elif call.data == "admin_search_user":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="back_to_admin", style="danger"))
        safe_send(chat_id, f"🔍 <b>SEND USER ID TO MANAGE:</b>", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_admin_search_user, msg_id)

    # 10 NEW FEATURES ROUTES
    elif call.data == "admin_user_list":
        admin_user_list_feature(chat_id)
    elif call.data == "admin_direct_ban":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="back_to_admin", style="danger"))
        safe_send(chat_id, "🚫 <b>SEND USER ID TO BAN:</b>", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_direct_ban, msg_id)
    elif call.data == "admin_direct_unban":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="back_to_admin", style="danger"))
        safe_send(chat_id, "✅ <b>SEND USER ID TO UNBAN:</b>", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_direct_unban, msg_id)
    elif call.data == "admin_clear_banned":
        data["banned_users"] = []
        save_data(data)
        bot.answer_callback_query(call.id, "✅ BANNED LIST CLEARED!", show_alert=True)
        show_admin_panel(chat_id, msg_id)
    elif call.data == "admin_server_stats":
        show_server_stats(chat_id, msg_id)
    elif call.data == "admin_msg_user":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="back_to_admin", style="danger"))
        safe_send(chat_id, "✉️ <b>SEND TARGET USER ID TO MESSAGE:</b>", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_msg_user_id, msg_id)
    elif call.data == "admin_edit_otp_bonus":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="back_to_admin", style="danger"))
        safe_send(chat_id, f"💰 <b>ENTER NEW OTP BONUS (Current: {data.get('settings', {}).get('otp_bonus', OTP_BONUS)}):</b>", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_edit_otp_bonus, msg_id)
    elif call.data == "admin_edit_ref_bonus":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="back_to_admin", style="danger"))
        safe_send(chat_id, f"🎁 <b>ENTER NEW REF BONUS (Current: {data.get('settings', {}).get('ref_bonus', REF_BONUS)}):</b>", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_edit_ref_bonus, msg_id)
    elif call.data == "admin_edit_max_nums":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="back_to_admin", style="danger"))
        safe_send(chat_id, f"📱 <b>ENTER MAX NUMBERS TO PULL AT ONCE (Current: {data.get('settings', {}).get('max_numbers', MAX_NUMBERS)}):</b>", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_edit_max_nums, msg_id)
    elif call.data == "admin_alerts_toggle":
        curr = data.setdefault("settings", {}).get("admin_alerts", False)
        data["settings"]["admin_alerts"] = not curr
        save_data(data)
        show_admin_panel(chat_id, msg_id)

    # Handle Ban/Unban directly from profile
    elif call.data.startswith("adm_ban_"):
        target_uid = int(call.data.split("_")[2])
        if target_uid not in data.setdefault("banned_users", []):
            data["banned_users"].append(target_uid)
            save_data(data)
            bot.answer_callback_query(call.id, f"✅ User {target_uid} Banned!", show_alert=True)
        show_user_admin_profile(chat_id, target_uid, msg_id)
        
    elif call.data.startswith("adm_unban_"):
        target_uid = int(call.data.split("_")[2])
        if target_uid in data.setdefault("banned_users", []):
            data["banned_users"].remove(target_uid)
            save_data(data)
            bot.answer_callback_query(call.id, f"✅ User {target_uid} Unbanned!", show_alert=True)
        show_user_admin_profile(chat_id, target_uid, msg_id)

    elif call.data.startswith("adm_edit_bal_"):
        target_uid = call.data.split("_")[3]
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data=f"adm_prof_{target_uid}", style="danger"))
        safe_send(chat_id, f"💰 <b>ENTER AMOUNT TO ADD/DEDUCT FOR {target_uid}:</b>\n<i>(Use negative like -5 to deduct)</i>", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_inline_balance_edit, target_uid, msg_id)
        
    elif call.data.startswith("adm_prof_"):
        target_uid = call.data.split("_")[2]
        show_user_admin_profile(chat_id, target_uid, msg_id)

    elif call.data == "admin_backup_db":
        try:
            with open(DATA_FILE, "rb") as f:
                bot.send_document(chat_id, f, caption="💾 <b>HERE IS YOUR DATABASE BACKUP!</b>\nKeep it safe.", parse_mode="HTML")
        except:
            bot.answer_callback_query(call.id, "Error generating backup!", show_alert=True)
        return
        
    elif call.data == "admin_maintenance":
        data["maintenance"] = not data.get("maintenance", False)
        save_data(data)
        show_admin_panel(chat_id, msg_id)
    elif call.data == "admin_api_key":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="back_to_admin", style="danger"))
        safe_send(chat_id, f"🔑 <b>SEND NEW API KEY:</b>", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_admin_api_key, msg_id)
    elif call.data == "admin_reward_all":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="back_to_admin", style="danger"))
        safe_send(chat_id, f"🎁 <b>ENTER BALANCE AMOUNT TO REWARD ALL:</b>", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_admin_reward_all, msg_id)
    elif call.data == "admin_deduct_all":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="back_to_admin", style="danger"))
        safe_send(chat_id, f"➖ <b>ENTER BALANCE AMOUNT TO DEDUCT:</b>", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_admin_deduct_all, msg_id)
    elif call.data == "admin_reset_otp":
        data["otp_counts"] = {}
        save_data(data)
        bot.answer_callback_query(call.id, "✅ ALL OTP RECORDS RESET SUCCESSFULLY!", show_alert=True)
        show_admin_panel(chat_id, msg_id)
    elif call.data == "admin_edit_texts":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="back_to_admin", style="danger"))
        safe_send(chat_id, f"📝 <b>SEND NEW WELCOME TEXT (OR TYPE /skip):</b>", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_edit_welcome, msg_id)
    elif call.data == "admin_export_data":
        generate_and_send_wallet_file(chat_id)
    elif call.data == "admin_edit_leadership":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="back_to_admin", style="danger"))
        safe_send(chat_id, f"🏆 <b>SEND NEW LEADERBOARD TEXT:</b>", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_edit_leadership, msg_id)
    elif call.data == "admin_edit_support":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="back_to_admin", style="danger"))
        safe_send(chat_id, f"🎧 <b>SEND NEW SUPPORT TEXT:</b>", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_edit_support, msg_id)
        
    elif call.data == "back_to_user_services": show_user_services(chat_id, msg_id)

    elif call.data.startswith("usr_s|"):
        srv_id = call.data.split("|")[1]
        show_user_countries(chat_id, srv_id, msg_id)

    # --- SMART EXTRACT NUMBER LOGIC ---
    elif call.data.startswith("usr_c|") or call.data.startswith("chg_r|") or call.data.startswith("usr_auto_cnt|"):
        if not check_force_join(user_id):
            show_force_join_message(chat_id, msg_id)
            return

        if str(chat_id) in active_polls: 
            active_polls[str(chat_id)] = False 

        parts = call.data.split("|")
        action = parts[0]
        srv_id = parts[1]

        srv_data = data.get("services_data", {}).get(srv_id)
        if not srv_data or not srv_data.get("countries"):
            return safe_send(chat_id, "❌ <b>NO COUNTRIES/RANGES AVAILABLE.</b>", None, msg_id)

        all_ranges = []
        country_name = "Unknown"
        
        if action == "usr_auto_cnt":
            for c_id, c_data in srv_data["countries"].items():
                for r_id, r_val in c_data.get("ranges", {}).items():
                    all_ranges.append((c_id, c_data['name'], r_id, r_val))
            country_name = "AUTO SELECT"
        else:
            cnt_id = parts[2]
            cnt_data = srv_data.get("countries", {}).get(cnt_id)
            if cnt_data:
                country_name = cnt_data['name']
                for r_id, r_val in cnt_data.get("ranges", {}).items():
                    all_ranges.append((cnt_id, country_name, r_id, r_val))

        if not all_ranges:
            return safe_send(chat_id, "❌ <b>NO RANGES AVAILABLE FOR THIS SELECTION.</b>", None, msg_id)

        msg_obj = safe_send(chat_id, f"⏳ <b>SEARCHING FOR LIVE NUMBERS...</b>\n<i>Checking available ranges...</i>", None, msg_id)
        if msg_obj:
            threading.Thread(target=fetch_numbers_smart, args=(chat_id, srv_id, srv_data['name'], all_ranges, api_key, msg_obj.message_id)).start()

    # Admin Services Management
    elif call.data == "admin_manage_service": show_admin_services(chat_id, msg_id)
    elif call.data == "add_srv":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="admin_manage_service", style="danger"))
        safe_send(chat_id, f"📨 <b>SEND SERVICE NAME:</b>", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_add_srv, msg_id)
    elif call.data.startswith("adm_s|"): show_admin_countries(chat_id, call.data.split("|")[1], msg_id)
    elif call.data.startswith("add_cnt|"):
        srv_id = call.data.split("|")[1]
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data=f"adm_s|{srv_id}", style="danger"))
        safe_send(chat_id, f"🌍 <b>SEND COUNTRY NAME:</b>", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_add_cnt, srv_id, msg_id)
    elif call.data.startswith("adm_c|"):
        _, srv_id, cnt_id = call.data.split("|")
        show_admin_ranges(chat_id, srv_id, cnt_id, msg_id)
    elif call.data.startswith("add_rng|"):
        _, srv_id, cnt_id = call.data.split("|")
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data=f"adm_c|{srv_id}|{cnt_id}", style="danger"))
        safe_send(chat_id, f"📱 <b>SEND RANGE:</b>", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_add_rng, srv_id, cnt_id, msg_id)
    elif call.data.startswith("del_srv|"):
        srv_id = call.data.split("|")[1]
        if srv_id in data.get("services_data", {}): del data["services_data"][srv_id]; save_data(data)
        show_admin_services(chat_id, msg_id)
    elif call.data.startswith("del_cnt|"):
        _, srv_id, cnt_id = call.data.split("|")
        if srv_id in data["services_data"] and cnt_id in data["services_data"][srv_id]["countries"]: del data["services_data"][srv_id]["countries"][cnt_id]; save_data(data)
        show_admin_countries(chat_id, srv_id, msg_id)
    elif call.data.startswith("del_rng|"):
        _, srv_id, cnt_id, rng_id = call.data.split("|")
        if srv_id in data["services_data"] and cnt_id in data["services_data"][srv_id]["countries"] and rng_id in data["services_data"][srv_id]["countries"][cnt_id]["ranges"]: del data["services_data"][srv_id]["countries"][cnt_id]["ranges"][rng_id]; save_data(data)
        show_admin_ranges(chat_id, srv_id, cnt_id, msg_id)
    
    elif call.data == "admin_group_settings": safe_send(chat_id, f"🔗 <b>GROUP SETTINGS</b>\n{DIVIDER}\n<b>MANAGE OTP GROUPS</b>", get_group_settings_menu(), msg_id)
    elif call.data == "set_main_otp_link":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="admin_group_settings", style="danger"))
        safe_send(chat_id, f"🔗 <b>SEND OTP GROUP URL:</b>", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_main_otp_link, msg_id)
    elif call.data == "del_main_otp_link":
        data["main_otp_link"] = "https://t.me/"; save_data(data)
        safe_send(chat_id, f"🗑️ <b>OTP LINK REMOVED!</b>", None, msg_id)
        show_edit_group_menu(chat_id, "🔗 <b>GROUP SETTINGS</b>", msg_id)
    elif call.data == "add_fwd_group":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="admin_group_settings", style="danger"))
        safe_send(chat_id, f"➕ <b>SEND GROUP CHAT ID:</b>", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, step1_add_fwd_group, msg_id)
    elif call.data.startswith("editgrp_"): show_edit_group_menu(chat_id, call.data.split("_")[1], msg_id)
    elif call.data.startswith("addgrpbtn_"):
        grp_id = call.data.split("_")[1]
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data=f"editgrp_{grp_id}", style="danger"))
        safe_send(chat_id, f"📝 <b>SEND BUTTON NAME:</b>", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, step_addgrpbtn_name, grp_id, msg_id)
    elif call.data.startswith("delgrpbtn_"):
        parts = call.data.split("_"); grp_id, btn_idx = parts[1], int(parts[2])
        for g in data.get("forward_groups", []):
            if str(g['chat_id']) == str(grp_id):
                if 0 <= btn_idx < len(g.get("buttons", [])): g["buttons"].pop(btn_idx)
                break
        save_data(data); show_edit_group_menu(chat_id, grp_id, msg_id)
    elif call.data.startswith("delfwd_"):
        grp_id = call.data.split("_")[1]
        data["forward_groups"] = [g for g in data.get("forward_groups", []) if str(g['chat_id']) != grp_id]
        save_data(data)
        safe_send(chat_id, f"🗑️ <b>GROUP DELETED!</b>", None, msg_id)
        safe_send(chat_id, f"🔗 <b>GROUP SETTINGS</b>", get_group_settings_menu(), msg_id)
    
    elif call.data == "admin_force_join": safe_send(chat_id, f"📢 <b>FORCE JOIN</b>\n{DIVIDER}", get_force_join_menu(), msg_id)
    elif call.data == "toggle_force_join":
        data["force_join_enabled"] = not data.get("force_join_enabled", False); save_data(data)
        safe_send(chat_id, f"📢 <b>FORCE JOIN</b>\n{DIVIDER}", get_force_join_menu(), msg_id)
    elif call.data == "add_fjc":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="admin_force_join", style="danger"))
        safe_send(chat_id, f"🔗 <b>SEND CHANNEL LINK:</b>", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_set_force_join_link, msg_id)
    elif call.data.startswith("delfjc_"):
        idx = int(call.data.split("_")[1])
        if 0 <= idx < len(data.get("force_join_channels", [])): data["force_join_channels"].pop(idx); save_data(data)
        safe_send(chat_id, f"📢 <b>FORCE JOIN</b>\n{DIVIDER}", get_force_join_menu(), msg_id)
    
    elif call.data == "admin_set_watermark":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="back_to_admin", style="danger"))
        safe_send(chat_id, f"📝 <b>SEND NEW WATERMARK:</b>\nCURRENT: {data.get('watermark', BOT_NAME)}", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_set_watermark, msg_id)
    elif call.data == "admin_broadcast":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="back_to_admin", style="danger"))
        safe_send(chat_id, f"📨 <b>SEND MESSAGE TO BROADCAST:</b>", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_broadcast, msg_id)

def process_save_wallet(message, wallet_type, msg_id):
    if check_cancel(message, msg_id, show_profile_withdraw): return
    
    data = load_data()
    uid_str = str(message.chat.id)
    data.setdefault("wallets", {}).setdefault(uid_str, {})[wallet_type] = message.text.strip()
    save_data(data)
    
    try: bot.delete_message(message.chat.id, msg_id)
    except: pass
    
    bot.send_message(message.chat.id, f"✅ <b>{wallet_type.upper()} WALLET SAVED SUCCESSFULLY!</b>", parse_mode="HTML")
    show_profile_withdraw(message.chat.id, None)

# --- Admin Save Wallet Functions ---
def generate_and_send_wallet_file(chat_id):
    data = load_data()
    wallets = data.get("wallets", {})
    balances = data.get("balances", {})
    profiles = data.get("user_profiles", {})
    otps_data = data.get("otp_counts", {})
    
    content = "👑 MINO X SMS - ALL DATA EXPORT 👑\n"
    content += "="*50 + "\n\n"
    
    if not wallets and not balances:
        content += "No user data found."
    else:
        for uid in data.get("users", []):
            uid_str = str(uid)
            bal = balances.get(uid_str, 0.0)
            u_wallets = wallets.get(uid_str, {})
            otp_cnt = otps_data.get(uid_str, 0)
            
            profile = profiles.get(uid_str, {})
            name = profile.get("first_name", "Unknown")
            username = profile.get("username", "N/A")
            
            content += f"👤 USER ID: {uid_str}\n"
            content += f"📛 NAME: {name} (@{username})\n"
            content += f"💰 BALANCE: ${bal:.5f}\n"
            content += f"🎯 TOTAL OTPS: {otp_cnt}\n"
            content += "🏦 WALLETS:\n"
            
            if u_wallets:
                for w_type, addr in u_wallets.items():
                    content += f"   - {w_type.upper()}: {addr}\n"
            else:
                content += "   - NO WALLETS SET\n"
            content += "-"*40 + "\n"
            
    file_bytes = io.BytesIO(content.encode('utf-8'))
    file_bytes.name = "database_export.txt"
    bot.send_document(chat_id, file_bytes, caption="📁 <b>HERE IS THE COMPLETE USER DATA REPORT</b>", parse_mode="HTML")

# --- Centralized Admin User Management System ---
def process_admin_search_user(message, msg_id):
    if check_cancel(message, msg_id, show_admin_panel): return
    target_uid = message.text.strip()
    try: bot.delete_message(message.chat.id, msg_id)
    except: pass
    show_user_admin_profile(message.chat.id, target_uid, None)

def show_user_admin_profile(chat_id, target_uid, msg_id):
    data = load_data()
    target_uid = str(target_uid)
    
    if target_uid not in [str(u) for u in data.get("users", [])]:
        markup = InlineKeyboardMarkup().add(ibtn("🔙 BACK", callback_data="back_to_admin", style="danger"))
        safe_send(chat_id, "❌ <b>USER NOT FOUND IN DATABASE.</b>", markup, msg_id)
        return

    bal = data["balances"].get(target_uid, 0.0)
    otp_count = data["otp_counts"].get(target_uid, 0)
    is_banned = int(target_uid) in data.get("banned_users", [])
    banned_str = "🔴 YES (BANNED)" if is_banned else "🟢 NO (ACTIVE)"
    
    profile = data.get("user_profiles", {}).get(target_uid, {})
    name = profile.get("first_name", "Unknown")
    username = profile.get("username", "N/A")
    
    wallets = data.get("wallets", {}).get(target_uid, {})
    w_text = "\n".join([f"   - {k.upper()}: <code>{v}</code>" for k, v in wallets.items()]) if wallets else "   - <i>NONE ADDED</i>"
    
    text = f"🔍 <b>USER MANAGEMENT PROFILE</b> 🔍\n{DIVIDER}\n👤 <b>ID:</b> <code>{target_uid}</code>\n📛 <b>NAME:</b> {html.escape(name)}\n🔗 <b>USERNAME:</b> @{username}\n\n💰 <b>BALANCE:</b> <b>${bal:.5f}</b>\n🎯 <b>TOTAL OTPS:</b> <b>{otp_count}</b>\n🛡️ <b>STATUS:</b> <b>{banned_str}</b>\n\n🏦 <b>SAVED WALLETS:</b>\n{w_text}\n{DIVIDER}"
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(ibtn("💰 EDIT BALANCE", callback_data=f"adm_edit_bal_{target_uid}", style="success"))
    if is_banned:
        markup.add(ibtn("✅ UNBAN USER", callback_data=f"adm_unban_{target_uid}", style="success"))
    else:
        markup.add(ibtn("🚫 BAN USER", callback_data=f"adm_ban_{target_uid}", style="danger"))
    
    markup.add(ibtn("🔙 BACK TO ADMIN", callback_data="back_to_admin", style="primary"))
    
    safe_send(chat_id, text, markup, msg_id)

def process_inline_balance_edit(message, target_uid, msg_id):
    if check_cancel(message, msg_id, show_user_admin_profile, target_uid): return
    try:
        amt = float(message.text.strip())
        data = load_data()
        current = data["balances"].get(target_uid, 0.0)
        data["balances"][target_uid] = round(current + amt, 5)
        save_data(data)
        
        try: bot.delete_message(message.chat.id, msg_id)
        except: pass
        bot.send_message(message.chat.id, f"✅ <b>SUCCESS! Updated balance by ${amt}</b>", parse_mode="HTML")
        show_user_admin_profile(message.chat.id, target_uid, None)
        
    except ValueError:
        try: bot.delete_message(message.chat.id, msg_id)
        except: pass
        bot.send_message(message.chat.id, "❌ <b>INVALID AMOUNT. CANCELLED.</b>", parse_mode="HTML")
        show_user_admin_profile(message.chat.id, target_uid, None)

# -----------------------------------------------------
# 10 NEW ADMIN PROCESS HANDLERS
# -----------------------------------------------------
def admin_user_list_feature(chat_id):
    data = load_data()
    content = "👥 MINO X SMS - COMPLETE USER LIST 👥\n"
    content += "="*50 + "\n\n"
    users_count = len(data.get("users", []))
    
    for uid in data.get("users", []):
        uid_str = str(uid)
        profile = data.get("user_profiles", {}).get(uid_str, {})
        username = profile.get("username", "N/A")
        name = profile.get("first_name", "Unknown")
        content += f"ID: {uid_str} | Username: @{username} | Name: {name}\n"
        
    file_bytes = io.BytesIO(content.encode('utf-8'))
    file_bytes.name = "user_list.txt"
    markup = InlineKeyboardMarkup().add(ibtn("🔙 BACK TO ADMIN", callback_data="back_to_admin", style="primary"))
    bot.send_document(chat_id, file_bytes, caption=f"👥 <b>COMPLETE USER LIST EXPORTED</b>\nTotal Users: <b>{users_count}</b>", parse_mode="HTML", reply_markup=markup)

def process_direct_ban(message, msg_id):
    if check_cancel(message, msg_id, show_admin_panel): return
    try:
        target_uid = int(message.text.strip())
        data = load_data()
        try: bot.delete_message(message.chat.id, msg_id)
        except: pass
        if target_uid not in data.setdefault("banned_users", []):
            data["banned_users"].append(target_uid)
            save_data(data)
            bot.send_message(message.chat.id, f"✅ <b>USER {target_uid} HAS BEEN BANNED!</b>", parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, f"⚠️ <b>USER {target_uid} IS ALREADY BANNED.</b>", parse_mode="HTML")
    except ValueError:
        bot.send_message(message.chat.id, "❌ <b>INVALID ID FORMAT.</b>", parse_mode="HTML")
    show_admin_panel(message.chat.id, None)

def process_direct_unban(message, msg_id):
    if check_cancel(message, msg_id, show_admin_panel): return
    try:
        target_uid = int(message.text.strip())
        data = load_data()
        try: bot.delete_message(message.chat.id, msg_id)
        except: pass
        if target_uid in data.setdefault("banned_users", []):
            data["banned_users"].remove(target_uid)
            save_data(data)
            bot.send_message(message.chat.id, f"✅ <b>USER {target_uid} HAS BEEN UNBANNED!</b>", parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, f"⚠️ <b>USER {target_uid} IS NOT BANNED.</b>", parse_mode="HTML")
    except ValueError:
        bot.send_message(message.chat.id, "❌ <b>INVALID ID FORMAT.</b>", parse_mode="HTML")
    show_admin_panel(message.chat.id, None)

def show_server_stats(chat_id, msg_id):
    uptime = int(time.time() - START_TIME)
    m, s = divmod(uptime, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    data = load_data()
    
    text = f"📈 <b>SERVER & BOT STATS</b> 📈\n{DIVIDER}\n"
    text += f"⏱️ <b>Uptime:</b> {d}d {h}h {m}m {s}s\n"
    text += f"👥 <b>Total Users:</b> {len(data.get('users', []))}\n"
    text += f"🎯 <b>Total OTPs Processed:</b> {len(data.get('processed_otps', []))}\n"
    text += f"💻 <b>Python Version:</b> {sys.version.split(' ')[0]}\n"
    text += f"{DIVIDER}"
    
    markup = InlineKeyboardMarkup().add(ibtn("🔙 BACK", callback_data="back_to_admin", style="primary"))
    safe_send(chat_id, text, markup, msg_id)

def process_msg_user_id(message, msg_id):
    if check_cancel(message, msg_id, show_admin_panel): return
    try:
        target_uid = int(message.text.strip())
        try: bot.delete_message(message.chat.id, msg_id)
        except: pass
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="back_to_admin", style="danger"))
        safe_send(message.chat.id, f"✉️ <b>SEND THE MESSAGE FOR USER {target_uid}:</b>", markup, None)
        bot.register_next_step_handler_by_chat_id(message.chat.id, process_msg_user_text, target_uid, None)
    except ValueError:
        bot.send_message(message.chat.id, "❌ <b>INVALID ID FORMAT.</b>", parse_mode="HTML")
        show_admin_panel(message.chat.id, None)

def process_msg_user_text(message, target_uid, msg_id):
    if check_cancel(message, msg_id, show_admin_panel): return
    msg_text = f"📩 <b>MESSAGE FROM ADMIN:</b>\n{DIVIDER}\n{message.text}"
    try: bot.delete_message(message.chat.id, msg_id)
    except: pass
    try:
        bot.send_message(target_uid, msg_text, parse_mode="HTML")
        bot.send_message(message.chat.id, f"✅ <b>MESSAGE SENT SUCCESSFULLY TO {target_uid}!</b>", parse_mode="HTML")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ <b>FAILED TO SEND MESSAGE (User might have blocked bot).</b>", parse_mode="HTML")
    show_admin_panel(message.chat.id, None)

def process_edit_otp_bonus(message, msg_id):
    if check_cancel(message, msg_id, show_admin_panel): return
    try:
        new_val = float(message.text.strip())
        data = load_data()
        data.setdefault("settings", {})["otp_bonus"] = new_val
        save_data(data)
        try: bot.delete_message(message.chat.id, msg_id)
        except: pass
        bot.send_message(message.chat.id, f"✅ <b>OTP BONUS UPDATED TO ${new_val}</b>", parse_mode="HTML")
    except:
        bot.send_message(message.chat.id, "❌ <b>INVALID AMOUNT.</b>", parse_mode="HTML")
    show_admin_panel(message.chat.id, None)

def process_edit_ref_bonus(message, msg_id):
    if check_cancel(message, msg_id, show_admin_panel): return
    try:
        new_val = float(message.text.strip())
        data = load_data()
        data.setdefault("settings", {})["ref_bonus"] = new_val
        save_data(data)
        try: bot.delete_message(message.chat.id, msg_id)
        except: pass
        bot.send_message(message.chat.id, f"✅ <b>REFERRAL BONUS UPDATED TO ${new_val}</b>", parse_mode="HTML")
    except:
        bot.send_message(message.chat.id, "❌ <b>INVALID AMOUNT.</b>", parse_mode="HTML")
    show_admin_panel(message.chat.id, None)

def process_edit_max_nums(message, msg_id):
    if check_cancel(message, msg_id, show_admin_panel): return
    try: bot.delete_message(message.chat.id, msg_id)
    except: pass
    try:
        new_val = int(message.text.strip())
        if new_val < 1 or new_val > 10:
            bot.send_message(message.chat.id, "❌ <b>PLEASE KEEP VALUE BETWEEN 1 and 10.</b>", parse_mode="HTML")
        else:
            data = load_data()
            data.setdefault("settings", {})["max_numbers"] = new_val
            save_data(data)
            bot.send_message(message.chat.id, f"✅ <b>MAX NUMBERS UPDATED TO {new_val}</b>", parse_mode="HTML")
    except:
        bot.send_message(message.chat.id, "❌ <b>INVALID NUMBER.</b>", parse_mode="HTML")
    show_admin_panel(message.chat.id, None)

# --- Other Admin Process Handlers ---
def process_admin_api_key(message, msg_id):
    if check_cancel(message, msg_id, show_admin_panel): return
    data = load_data()
    data["api_key"] = message.text.strip(); save_data(data)
    try: bot.delete_message(message.chat.id, msg_id)
    except: pass
    bot.send_message(message.chat.id, f"✅ <b>API KEY UPDATED!</b>", parse_mode="HTML")
    show_admin_panel(message.chat.id, None)

def process_admin_reward_all(message, msg_id):
    if check_cancel(message, msg_id, show_admin_panel): return
    try: bot.delete_message(message.chat.id, msg_id)
    except: pass
    try:
        amt = float(message.text.strip())
        data = load_data()
        for u in data.get("users", []):
            current = data["balances"].get(str(u), 0.0)
            data["balances"][str(u)] = round(current + amt, 5)
        save_data(data)
        bot.send_message(message.chat.id, f"✅ <b>ADDED ${amt:.5f} TO ALL USERS!</b>", parse_mode="HTML")
    except ValueError: 
        bot.send_message(message.chat.id, "❌ <b>INVALID AMOUNT.</b>", parse_mode="HTML")
    show_admin_panel(message.chat.id, None)

def process_admin_deduct_all(message, msg_id):
    if check_cancel(message, msg_id, show_admin_panel): return
    try: bot.delete_message(message.chat.id, msg_id)
    except: pass
    try:
        amt = float(message.text.strip())
        data = load_data()
        for u in data.get("users", []):
            current = data["balances"].get(str(u), 0.0)
            data["balances"][str(u)] = max(0.0, round(current - amt, 5))
        save_data(data)
        bot.send_message(message.chat.id, f"✅ <b>DEDUCTED ${amt:.5f} FROM ALL USERS!</b>", parse_mode="HTML")
    except ValueError: 
        bot.send_message(message.chat.id, "❌ <b>INVALID AMOUNT.</b>", parse_mode="HTML")
    show_admin_panel(message.chat.id, None)

def process_edit_welcome(message, msg_id):
    if check_cancel(message, msg_id, show_admin_panel): return
    data = load_data()
    if message.text.strip() != "/skip":
        data["settings"]["welcome"] = message.text.strip()
        save_data(data)
    
    try: bot.delete_message(message.chat.id, msg_id)
    except: pass
    
    markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="back_to_admin", style="danger"))
    safe_send(message.chat.id, f"🏦 <b>SEND NEW WITHDRAW INFO TEXT:</b>", markup, None)
    bot.register_next_step_handler_by_chat_id(message.chat.id, process_edit_withdraw, None)

def process_edit_withdraw(message, msg_id):
    if check_cancel(message, msg_id, show_admin_panel): return
    data = load_data()
    data["settings"]["withdraw"] = message.text; save_data(data)
    try: bot.delete_message(message.chat.id, msg_id)
    except: pass
    bot.send_message(message.chat.id, "✅ <b>TEXTS UPDATED SUCCESSFULLY!</b>", parse_mode="HTML")
    show_admin_panel(message.chat.id, None)
    
def process_edit_leadership(message, msg_id):
    if check_cancel(message, msg_id, show_admin_panel): return
    data = load_data()
    data["settings"]["leadership"] = message.text; save_data(data)
    try: bot.delete_message(message.chat.id, msg_id)
    except: pass
    bot.send_message(message.chat.id, "✅ <b>LEADERBOARD INFO UPDATED!</b>", parse_mode="HTML")
    show_admin_panel(message.chat.id, None)
    
def process_edit_support(message, msg_id):
    if check_cancel(message, msg_id, show_admin_panel): return
    data = load_data()
    data["settings"]["support"] = message.text; save_data(data)
    try: bot.delete_message(message.chat.id, msg_id)
    except: pass
    bot.send_message(message.chat.id, "✅ <b>SUPPORT INFO UPDATED!</b>", parse_mode="HTML")
    show_admin_panel(message.chat.id, None)

def process_2fa_code(message, msg_id):
    if check_cancel(message, msg_id, show_2fa_menu): return
    
    try: bot.delete_message(message.chat.id, msg_id)
    except: pass
        
    secret_key = message.text.strip().upper().replace(" ", "")
    if len(secret_key) < 8:
        bot.send_message(message.chat.id, f"❌ <b>INVALID KEY! KEY TOO SHORT.</b>", parse_mode="HTML")
        show_2fa_menu(message.chat.id, None); return
    try:
        totp = pyotp.TOTP(secret_key)
        code = totp.now()
        remaining = 30 - (int(time.time()) % 30)
        text = f"🔴 <b><i><u>YOUR SECURE 2FA CODE</u></i></b> 🔴\n\n<b><i><u>CODE:</u></i></b> <code>{code}</code>\n\n<b><i><u>EXPIRES IN:</u></i></b> <b><i><u>{remaining}S</u></i></b>"
        markup = InlineKeyboardMarkup(row_width=1)
        if HAS_COPY_BTN: markup.add(ibtn(f"📋 COPY: {code}", copy_text_str=code, style="success"))
        else: markup.add(ibtn(f"📋 COPY: {code}", callback_data=f"cp_{code}", style="success"))
        markup.add(ibtn("🔄 NEW CODE", callback_data="2fa_generate", style="primary"))
        markup.add(ibtn("❌ CLOSE", callback_data="2fa_back", style="danger"))
        safe_send(message.chat.id, text, markup, None)
    except:
        bot.send_message(message.chat.id, f"❌ <b>INVALID 2FA KEY!</b>", parse_mode="HTML")
        show_2fa_menu(message.chat.id, None)

# --- Process APIs ---
def process_set_force_join_link(message, msg_id):
    if check_cancel(message, msg_id, lambda cid, mid: safe_send(cid, f"📢 <b>FORCE JOIN</b>\n{DIVIDER}", get_force_join_menu(), mid)): return
    data = load_data()
    data.setdefault("force_join_channels", []).append(format_url(message.text.strip())); save_data(data)
    try: bot.delete_message(message.chat.id, msg_id)
    except: pass
    bot.send_message(message.chat.id, f"✅ <b>CHANNEL ADDED!</b>", parse_mode="HTML")
    safe_send(message.chat.id, f"📢 <b>FORCE JOIN</b>\n{DIVIDER}", get_force_join_menu(), None)

def process_add_srv(message, msg_id):
    if check_cancel(message, msg_id, show_admin_services): return
    data = load_data()
    srv_id = "s_" + str(uuid.uuid4())[:8]
    data.setdefault("services_data", {})[srv_id] = {"name": message.text.strip().upper(), "countries": {}}; save_data(data)
    try: bot.delete_message(message.chat.id, msg_id)
    except: pass
    show_admin_services(message.chat.id, None)

def process_add_cnt(message, srv_id, msg_id):
    if check_cancel(message, msg_id, show_admin_countries, srv_id): return
    data = load_data()
    cnt_id = "c_" + str(uuid.uuid4())[:8]
    if srv_id in data.get("services_data", {}): data["services_data"][srv_id]["countries"][cnt_id] = {"name": message.text.strip().upper(), "ranges": {}}; save_data(data)
    try: bot.delete_message(message.chat.id, msg_id)
    except: pass
    show_admin_countries(message.chat.id, srv_id, None)

def process_add_rng(message, srv_id, cnt_id, msg_id):
    if check_cancel(message, msg_id, show_admin_ranges, srv_id, cnt_id): return
    data = load_data()
    rng_id = "r_" + str(uuid.uuid4())[:8]
    try: data["services_data"][srv_id]["countries"][cnt_id]["ranges"][rng_id] = message.text.strip().replace(" ", ""); save_data(data)
    except: pass
    try: bot.delete_message(message.chat.id, msg_id)
    except: pass
    show_admin_ranges(message.chat.id, srv_id, cnt_id, None)

def process_api_traffic_search(message, msg_id):
    if check_cancel(message, msg_id, lambda c, m: None): return
        
    user_id = message.from_user.id
    current_time = time.time()
    api_key = load_data().get("api_key", NEXA_API_KEY)
    
    try: bot.delete_message(message.chat.id, msg_id)
    except: pass

    if user_id in traffic_cooldowns:
        time_passed = current_time - traffic_cooldowns[user_id]
        if time_passed < 10:
            wait_time = int(10 - time_passed)
            markup = InlineKeyboardMarkup().add(ibtn("❌ CLOSE", callback_data="close_menu", style="danger"))
            safe_send(message.chat.id, f"⏰ <b>WAIT {wait_time}S.</b>", markup, None); return
            
    traffic_cooldowns[user_id] = current_time
    service_query = message.text.strip().lower()
    load_msg = safe_send(message.chat.id, f"⏳ <b>CHECKING TRAFFIC...</b>", None, None)
    
    def check_traffic():
        markup = InlineKeyboardMarkup().add(ibtn("❌ CLOSE", callback_data="close_menu", style="danger"))
        ranges = {}
        data = load_data()
        for srv in data.get("services_data", {}).values():
            if service_query in str(srv.get("name", "")).lower():
                for cnt in srv.get("countries", {}).values():
                    country_name = cnt.get("name", "Unknown")
                    for rng in cnt.get("ranges", {}).values():
                        if rng not in ranges: ranges[rng] = {"count": 1, "country": country_name}
        
        api_keys = __get_all_api_keys(api_key)
        res_data = None
        for key in api_keys:
            try:
                headers = {'X-API-Key': key, 'Cache-Control': 'no-cache'}
                response = requests.get(f"{BASE_URL}/api/v1/console/logs?limit=200", headers=headers, timeout=10)
                res = response.json()
                if res.get("success"):
                    res_data = res
                    break
            except: pass
            
        if res_data and res_data.get("data"):
            for item in res_data["data"]:
                sms_text = str(item.get("sms", "")).lower()
                app_name = str(item.get("app_name", "")).lower()
                country = str(item.get("country", "Unknown"))
                num = str(item.get("number", ""))
                detected = app_name
                if "instagram" in sms_text or "facebook" in sms_text: detected = "facebook"
                elif "whatsapp" in sms_text: detected = "whatsapp"
                elif "telegram" in sms_text: detected = "telegram"
                if service_query in detected and len(num) > 6:
                    rng_pattern = num[:6] + "XXX"
                    if rng_pattern not in ranges: ranges[rng_pattern] = {"count": 2, "country": country}
                    else: ranges[rng_pattern]["count"] += 1
        
        if ranges:
            sorted_ranges = sorted(ranges.items(), key=lambda x: x[1]["count"], reverse=True)
            res_text = f"📊 <b>TOP RANGES FOR {service_query.upper()}:</b>\n\n"
            for rng, details in sorted_ranges[:10]:
                flag = get_country_flag(details['country'])
                res_text += f"{flag} <b>{details['country'].upper()}</b> → <code>{rng}</code> [{details['count']} OTPS]\n"
        else: res_text = f"❌ <b>NO ACTIVE TRAFFIC FOUND.</b>"
        
        if load_msg:
            safe_send(message.chat.id, res_text, markup, load_msg.message_id)
        else:
            safe_send(message.chat.id, res_text, markup, None)

    threading.Thread(target=check_traffic).start()

def step1_add_fwd_group(message, msg_id):
    if check_cancel(message, msg_id, lambda cid, mid: safe_send(cid, f"🔗 <b>GROUP SETTINGS</b>", get_group_settings_menu(), mid)): return
    data = load_data()
    new_id = message.text.strip()
    data.setdefault("forward_groups", []).append({"chat_id": new_id, "buttons": []}); save_data(data)
    try: bot.delete_message(message.chat.id, msg_id)
    except: pass
    bot.send_message(message.chat.id, f"✅ <b>GROUP ADDED!</b>", parse_mode="HTML")
    safe_send(message.chat.id, f"🔗 <b>GROUP SETTINGS</b>", get_group_settings_menu(), None)

def step_addgrpbtn_name(message, grp_id, msg_id):
    if check_cancel(message, msg_id, show_edit_group_menu, grp_id): return
    user_states[message.chat.id] = {'grp_id': grp_id, 'btn_name': message.text.strip().upper()}
    try: bot.delete_message(message.chat.id, msg_id)
    except: pass
    markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data=f"editgrp_{grp_id}", style="danger"))
    safe_send(message.chat.id, f"🔗 <b>SEND BUTTON URL:</b>", markup, None)
    bot.register_next_step_handler_by_chat_id(message.chat.id, step_addgrpbtn_url, None)

def step_addgrpbtn_url(message, msg_id):
    state = user_states.get(message.chat.id, {})
    grp_id = state.get('grp_id')
    if check_cancel(message, msg_id, show_edit_group_menu, grp_id): return
    
    btn_name = state.get('btn_name')
    btn_url = format_url(message.text.strip())
    data = load_data()
    for grp in data.get("forward_groups", []):
        if str(grp['chat_id']) == str(grp_id): grp.setdefault("buttons", []).append({"name": btn_name, "url": btn_url}); break
    save_data(data)
    
    try: bot.delete_message(message.chat.id, msg_id)
    except: pass
    bot.send_message(message.chat.id, f"✅ <b>BUTTON ADDED!</b>", parse_mode="HTML")
    show_edit_group_menu(message.chat.id, grp_id, None)

def process_main_otp_link(message, msg_id):
    if check_cancel(message, msg_id, lambda cid, mid: safe_send(cid, f"🔗 <b>GROUP SETTINGS</b>", get_group_settings_menu(), mid)): return
    data = load_data()
    data["main_otp_link"] = format_url(message.text.strip()); save_data(data)
    try: bot.delete_message(message.chat.id, msg_id)
    except: pass
    bot.send_message(message.chat.id, f"✅ <b>LINK UPDATED!</b>", parse_mode="HTML")
    safe_send(message.chat.id, f"🔗 <b>GROUP SETTINGS</b>", get_group_settings_menu(), None)

def process_set_watermark(message, msg_id):
    if check_cancel(message, msg_id, show_admin_panel): return
    data = load_data()
    data["watermark"] = message.text.strip(); save_data(data)
    try: bot.delete_message(message.chat.id, msg_id)
    except: pass
    bot.send_message(message.chat.id, f"✅ <b>WATERMARK UPDATED!</b>", parse_mode="HTML")
    show_admin_panel(message.chat.id, None)

def run_broadcast(chat_id, original_message, msg_id):
    data = load_data()
    users = data.get("users", [])
    success, failed = 0, 0
    for u in users:
        try: bot.copy_message(chat_id=u, from_chat_id=chat_id, message_id=original_message.message_id); success += 1; time.sleep(0.05)
        except: failed += 1
    markup = InlineKeyboardMarkup().add(ibtn("🔙 BACK TO ADMIN", callback_data="back_to_admin", style="danger"))
    report = f"📢 <b>BROADCAST DONE!</b>\n\n✅ <b>SENT:</b> {success}\n❌ <b>FAILED:</b> {failed}"
    safe_send(chat_id, report, markup, msg_id)

def process_broadcast(message, msg_id):
    if check_cancel(message, msg_id, show_admin_panel): return
    try: bot.delete_message(message.chat.id, msg_id)
    except: pass
    load_msg = safe_send(message.chat.id, f"⏳ <b>BROADCASTING...</b>", None, None)
    threading.Thread(target=run_broadcast, args=(message.chat.id, message, load_msg.message_id if load_msg else None)).start()

# --- Multi-API, Multi-Number Core OTP Functions ---
def fetch_numbers_smart(chat_id, srv_id, srv_name, all_ranges, main_api_key, msg_id):
    active_polls[str(chat_id)] = True
    numbers_found = []
    api_keys = __get_all_api_keys(main_api_key)
    
    random.shuffle(all_ranges) 
    service_code = get_service_code(srv_name)
    
    data = load_data()
    dynamic_max_nums = data.get("settings", {}).get("max_numbers", MAX_NUMBERS)
    
    for rng_data in all_ranges:
        if len(numbers_found) >= dynamic_max_nums: break
        cnt_id, c_name, r_id, r_val = rng_data
        clean_range = str(r_val).strip().replace(" ", "")
        
        for _ in range(dynamic_max_nums - len(numbers_found)):
            success_here = False
            for key in api_keys:
                try:
                    payload = {"range": clean_range, "service": service_code}
                    res = requests.post(f"{BASE_URL}/api/v1/numbers/get", json=payload, headers={'X-API-Key': key}, timeout=8).json()
                    if res.get("success"):
                        numbers_found.append({
                            "number": res.get("number"),
                            "number_id": res.get("number_id"),
                            "api_key": key,
                            "status": "⏳ WAITING",
                            "cnt_id": cnt_id,
                            "country_name": c_name,
                            "r_id": r_id,
                            "r_val": clean_range
                        })
                        success_here = True
                        break 
                except: pass
            
            if not success_here:
                break 
                
        if len(numbers_found) > 0:
            break 

    if not numbers_found:
        markup = InlineKeyboardMarkup().add(ibtn("🔙 BACK", callback_data=f"usr_s|{srv_id}", style="danger"))
        safe_send(chat_id, f"❌ 𝗦𝗢𝗥𝗥𝗬, 𝗔𝗟𝗟 𝗥𝗔𝗡𝗚𝗘𝗦 𝗔𝗥𝗘 𝗢𝗨𝗧 𝗢𝗙 𝗦𝗧𝗢𝗖𝗞 𝗖𝗨𝗥𝗥𝗘𝗡𝗧𝗟𝗬.\n{DIVIDER}\n<i>We checked available ranges but couldn't find an active number. Please try again later.</i>", markup, msg_id)
        active_polls[str(chat_id)] = False
        return

    watermark = data.get("watermark", BOT_NAME)
    
    final_country_name = numbers_found[0]['country_name']
    final_cnt_id = numbers_found[0]['cnt_id']
    final_r_id = numbers_found[0]['r_id']
    
    flag = get_country_flag(final_country_name)
    srv_emoji = emo(srv_name)
    
    text = f"💠 <b>NUMBER ALLOCATED</b> 💠\n{DIVIDER}\n{srv_emoji} <b>SERVICE:</b> <b>{html.escape(srv_name.upper())}</b>\n{flag} <b>COUNTRY:</b> <b>{html.escape(final_country_name.upper())}</b>\n{DIVIDER}\n"
    for i, num_data in enumerate(numbers_found):
        raw_num = str(num_data['number']).replace('+', '')
        text += f"{i+1}️⃣ <code>+{raw_num}</code>  {num_data['status']}\n"
    text += f"{DIVIDER}\n🔥 <b>{html.escape(watermark.upper())}</b> 🔥"
    
    main_link = format_url(data.get("main_otp_link", "https://t.me/"))
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(ibtn("🔄 CHANGE", callback_data=f"chg_r|{srv_id}|{final_cnt_id}|{final_r_id}", style="primary"), ibtn("📨 OTP GROUP", url=main_link, style="success"))
    markup.add(ibtn("🔙 BACK", callback_data=f"usr_s|{srv_id}", style="danger"))
    
    service_info = {
        'id': final_r_id, 'srv_id': srv_id, 'cnt_id': final_cnt_id, 
        'service_name': srv_name, 'country_name': final_country_name, 'range': numbers_found[0]['r_val']
    }
    
    active_polls[str(chat_id)] = {"numbers": numbers_found, "service_info": service_info, "message_id": msg_id, "watermark": watermark, "main_link": main_link}
    safe_send(chat_id, text, markup, msg_id)
    
    for num_data in numbers_found:
        threading.Thread(target=poll_otp, args=(chat_id, num_data, service_info)).start()

def update_number_status(chat_id, phone_number, status_text, emoji_status):
    if str(chat_id) not in active_polls or not active_polls[str(chat_id)]: return
    poll_data = active_polls[str(chat_id)]
    numbers = poll_data.get("numbers", [])
    message_id = poll_data.get("message_id")
    service_info = poll_data.get("service_info", {})
    watermark = poll_data.get("watermark", BOT_NAME)
    main_link = poll_data.get("main_link", "https://t.me/")
    
    for num_data in numbers:
        if num_data["number"] == phone_number: num_data["status"] = f"{emoji_status} {status_text}"; break
    
    flag = get_country_flag(service_info.get('country_name', ''))
    srv_emoji = emo(service_info.get('service_name', ''))
    
    text = f"💠 <b>NUMBER ALLOCATED</b> 💠\n{DIVIDER}\n{srv_emoji} <b>SERVICE:</b> <b>{html.escape(service_info.get('service_name', '').upper())}</b>\n{flag} <b>COUNTRY:</b> <b>{html.escape(service_info.get('country_name', '').upper())}</b>\n{DIVIDER}\n"
    for i, num_data in enumerate(numbers):
        raw_num = str(num_data['number']).replace('+', '')
        text += f"{i+1}️⃣ <code>+{raw_num}</code>  {num_data['status']}\n"
    text += f"{DIVIDER}\n🔥 <b>{html.escape(watermark.upper())}</b> 🔥"
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(ibtn("🔄 CHANGE", callback_data=f"chg_r|{service_info.get('srv_id', '')}|{service_info.get('cnt_id', '')}|{service_info.get('id', '')}", style="primary"), ibtn("📨 OTP GROUP", url=main_link, style="success"))
    markup.add(ibtn("🔙 BACK", callback_data=f"usr_s|{service_info.get('srv_id', '')}", style="danger"))
    safe_send(chat_id, text, markup, message_id)

def poll_otp(chat_id, num_data, service_info):
    number_id = num_data["number_id"]
    phone_number = num_data["number"]
    api_key = num_data["api_key"]
    headers = {'X-API-Key': api_key}
    timeout = 600
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if str(chat_id) not in active_polls or not active_polls[str(chat_id)]: return 
        try:
            res = requests.get(f"{BASE_URL}/api/v1/numbers/{number_id}/sms", headers=headers, timeout=15)
            s_data = res.json()
            if s_data.get("success") and s_data.get("otp"):
                otp_code = s_data.get("otp")
                full_sms = s_data.get("message", "") or s_data.get("sms", "")
                
                # Smart Extraction
                match = re.search(r'(?:code\D+)?(\d{3,6}[- ]\d{3,6})', full_sms, re.IGNORECASE)
                if match: otp_code = match.group(1).strip()
                
                app_name_from_api = s_data.get("service", "") or s_data.get("app_name", service_info.get('service_name', ''))
                detected_service = detect_service_from_sms(full_sms, app_name_from_api)
                
                update_number_status(chat_id, phone_number, "OTP RECEIVED", "✅")
                
                # Anti-Cheat & Save System
                unique_otp_id = f"{phone_number}_{otp_code}"
                data = load_data()
                dynamic_otp_bonus = data.get("settings", {}).get("otp_bonus", OTP_BONUS)
                
                add_to_history(chat_id, detected_service, f"+{str(phone_number).replace('+', '')}", otp_code)
                
                data["otp_counts"][str(chat_id)] = data.get("otp_counts", {}).get(str(chat_id), 0) + 1
                
                if unique_otp_id not in data.get("processed_otps", []):
                    data.setdefault("processed_otps", []).append(unique_otp_id)
                    current_bal = data.get("balances", {}).get(str(chat_id), 0.0)
                    data.setdefault("balances", {})[str(chat_id)] = round(current_bal + dynamic_otp_bonus, 5)
                    try:
                        bot.send_message(chat_id, f"🎉 <b>CONGRATULATIONS!</b> You received <b>${dynamic_otp_bonus}</b> for successful OTP extraction!", parse_mode="HTML")
                    except: pass
                    
                save_data(data)
                
                flag = get_country_flag(service_info['country_name'])
                srv_emoji = emo(detected_service)
                disp_num = f"+{str(phone_number).replace('+', '')}"
                
                # Inbox Message Update
                inbox_msg = f"✨ <b>[ OTP SUCCESSFULLY RETRIEVED ]</b> ✨\n{DIVIDER}\n📲 <b>SERVICE :</b> <b>{detected_service.upper()}</b>\n🌍 <b>REGION  :</b> {flag} <b>{html.escape(service_info['country_name'].upper())}</b>\n📞 <b>NUMBER  :</b> <code>{disp_num}</code>\n{THIN_DIVIDER}\n🔐 <b>YOUR OTP CODE:</b>\n🎯 <code>{otp_code}</code> 🎯\n{DIVIDER}\n💎 <b>{html.escape(data.get('watermark', BOT_NAME).upper())}</b> 💎"
                safe_send(chat_id, inbox_msg)
                
                # GROUP TICKET WITH SPECIFIC BUTTONS
                masked_num = mask_number(phone_number)
                group_msg = f"┏━━━━━━━━━━━━━━━━━━━━━━┓\n┣ 📲 <b>APP:</b> {srv_emoji} <b>{detected_service.upper()}</b>\n┣ 🌍 <b>REG:</b> {flag} <b>{service_info['country_name'].upper()}</b>\n┣ 📞 <b>NUM:</b> <code>{masked_num}</code>\n┗━━━━━━━━━━━━━━━━━━━━━━┛\n💎 <b>{html.escape(data.get('watermark', BOT_NAME).upper())}</b> 💎"
                
                bot_link = f"https://t.me/{BOT_USERNAME}" if BOT_USERNAME else "https://t.me/"
                channel_link = data.get("force_join_channels", ["https://t.me/"])[0] if data.get("force_join_channels") else bot_link
                
                for grp in data.get("forward_groups", []):
                    try:
                        grp_markup = InlineKeyboardMarkup(row_width=2)
                        if HAS_COPY_BTN: grp_markup.add(ibtn(f"📋 COPY OTP: {otp_code}", copy_text_str=otp_code, style="success"))
                        else: grp_markup.add(ibtn(f"📋 COPY OTP: {otp_code}", callback_data=f"cp_{otp_code}", style="success"))
                        
                        grp_markup.add(
                            ibtn("📲 Get Number", url=bot_link, style="success"),
                            ibtn("📢 Join Channel", url=channel_link, style="primary")
                        )
                        grp_markup.add(ibtn("🔗 Main Channel", url=channel_link, style="primary"))
                        
                        for btn in grp.get("buttons", []):
                            grp_markup.add(ibtn(btn['name'].upper(), url=btn['url'], style="primary"))
                            
                        safe_send(grp['chat_id'], group_msg, grp_markup)
                    except: pass
                return 
        except: pass 
        time.sleep(3) 
        
    update_number_status(chat_id, phone_number, "TIMEOUT", "⏰")

if __name__ == "__main__":
    print("💎 MINO X SMS BOT (CENTRALIZED ADMIN & PREMIUM UI) is Running... 💎")
    bot.infinity_polling()
