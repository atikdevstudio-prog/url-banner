    loggAPK Converter Studio starting…")
import logging
import io
import os
import threading
from html import escape

import requests
import telebot
from PIL import Image, ImageDraw, ImageFilter
from telebot import types

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
# বিনামূল্যে ওয়েবসাইট স্ক্রিনশট নেওয়ার জন্য একটি ফ্রি API ব্যবহার করা হয়েছে
SCREENSHOT_API = "https://image.thum.io/get/width/1200/crop/800/"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("banner_bot")

if not BOT_TOKEN or ":" not in BOT_TOKEN:
    raise SystemExit("Set a valid BOT_TOKEN environment variable before running.")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
sessions = {}

def kb_main_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("📸 Create Website Banner", callback_data="menu:new"))
    kb.add(types.InlineKeyboardButton("ℹ️ About Bot", callback_data="menu:about"))
    return kb

def kb_cancel():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✖️ Cancel", callback_data="flow:cancel"))
    return kb

@bot.message_handler(commands=["start", "menu"])
def cmd_start(message):
    sessions.pop(message.chat.id, None)
    text = (
        "<b>Website Banner & Screenshot Bot</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🌐 Send any website link, and this bot will generate a professional preview banner for you!\n\n"
        "<i>Fast • Automated • Clean Design</i>"
    )
    bot.send_message(message.chat.id, text, reply_markup=kb_main_menu())

@bot.callback_query_handler(func=lambda c: c.data == "menu:new")
def cb_new(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    sessions[chat_id] = {}
    msg = bot.send_message(chat_id, "🌐 <b>Send the Website URL</b>\n\nExample: <code>https://google.com</code>", reply_markup=kb_cancel())
    bot.register_next_step_handler(msg, step_get_url)

def step_get_url(message):
    chat_id = message.chat.id
    if chat_id not in sessions:
        return
    
    url = (message.text or "").strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        msg = bot.send_message(chat_id, "⚠️ <b>Invalid URL</b>\n\nPlease send a valid website URL starting with <code>http://</code> or <code>https://</code>:", reply_markup=kb_cancel())
        bot.register_next_step_handler(msg, step_get_url)
        return

    sessions[chat_id]["url"] = url
    
    # প্রসেসিং মেসেজ পাঠানো
    processing_msg = bot.send_message(chat_id, "⚙️ <b>Generating banner...</b> Please wait a moment.")
    
    try:
        # ১. ওয়েবসাইট স্ক্রিনশট ফেচ করা
        response = requests.get(SCREENSHOT_API + url, timeout=30)
        if response.status_code != 200:
            raise Exception("Failed to capture website preview.")
        
        screenshot_bytes = response.content
        
        # ২. Pillow দিয়ে আকর্ষণীয় ব্যানার ডিজাইন করা
        banner_img = create_custom_banner(screenshot_bytes, url)
        
        # ৩. ইউজারের কাছে পাঠানো
        bot.send_photo(chat_id, banner_img, caption=f"🎉 <b>Here is your website banner!</b>\n\n🔗 URL: <code>{escape(url)}</code>", reply_markup=kb_main_menu())
        bot.delete_message(chat_id, processing_msg.message_id)
        
    except Exception as exc:
        logger.exception("Banner generation failed")
        bot.edit_message_text(f"❌ <b>Error:</b> {escape(str(exc))}\n\nCould not process this website.", chat_id, processing_msg.message_id, reply_markup=kb_main_menu())
    
    sessions.pop(chat_id, None)

def create_custom_banner(screenshot_bytes, site_url):
    # ব্যানার সাইজ
    w, h = 1200, 675
    base = Image.new("RGB", (w, h), "#0f172a")
    
    # ব্যাকগ্রাউন্ড গ্লো ইফেক্ট
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)
    draw.ellipse((800, -100, 1300, 400), fill=(59, 130, 246, 100))
    draw.ellipse((-100, 400, 400, 900), fill=(16, 185, 129, 60))
    glow = glow.filter(ImageFilter.GaussianBlur(60))
    base = Image.alpha_composite(base.convert("RGBA"), glow)
    
    # ওয়েবসাইটের স্ক্রিনশট ইমেজ লোড করা এবং রাউন্ডেড উইন্ডো বানানো
    try:
        ss_img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
        ss_img = ss_img.resize((1040, 500))
        
        # স্ক্রিনশটের জন্য একটি উইন্ডো ফ্রেম তৈরি
        frame = Image.new("RGBA", (1080, 560), (30, 41, 59, 255))
        frame_draw = ImageDraw.Draw(frame)
        # ব্রাউজার টপ বার (ম্যাক স্টাইল ডট)
        frame_draw.rectangle((0, 0, 1080, 40), fill=(15, 23, 42, 255))
        frame_draw.ellipse((20, 12, 28, 20), fill="#ef4444")
        frame_draw.ellipse((40, 12, 48, 20), fill="#f59e0b")
        frame_draw.ellipse((60, 12, 68, 20), fill="#10b981")
        
        # URL টেক্সট বারে বসানো
        frame_draw.text((90, 12), site_url[:60], fill="#94a3b8")
        
        # স্ক্রিনশট পেস্ট করা
        frame.paste(ss_img, (20, 50))
        
        # মূল ব্যানারে ফ্রেমটি বসানো (মাঝ বরাবর)
        base.paste(frame, (60, 60), frame)
    except Exception:
        pass
        
    output = io.BytesIO()
    base.convert("RGB").save(output, format="PNG", optimize=True)
    output.seek(0)
    return output

@bot.callback_query_handler(func=lambda c: c.data == "flow:cancel")
def cb_cancel(call):
    sessions.pop(call.message.chat.id, None)
    bot.answer_callback_query(call.id, "Cancelled")
    bot.edit_message_text("✖️ <b>Cancelled</b>\n\nChoose an option below:", call.message.chat.id, call.message.message_id, reply_markup=kb_main_menu())

@bot.callback_query_handler(func=lambda c: c.data == "menu:about")
def cb_about(call):
    bot.answer_callback_query(call.id)
    text = "<b>ℹ️ About Banner Bot</b>\n\nThis bot captures live website previews and converts them into beautiful promotional banners using Python and Pillow."
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb_main_menu())

if __name__ == "__main__":
    logger.info("Banner Bot starting...")
    bot.infinity_polling(skip_pending=True)
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)