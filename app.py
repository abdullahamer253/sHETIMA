#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os
import sqlite3
import json
import google.generativeai as genai
from flask import Flask, request, jsonify
from telegram import Update, Bot, ChatPermissions
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime, timedelta
import calendar
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Configuration ---
TELEGRAM_BOT_TOKEN = "8112033822:AAH2X-sSkf_djHKIzpyqU__Jlh-84gYnAJA"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
DB_NAME = "offense_log.db"
SWEAR_WORDS_FILE = "extracted_swear_words.txt"
MAIN_GROUP_CHAT_ID = int(os.getenv("MAIN_GROUP_CHAT_ID", "-1001734737806"))
ADMIN_CHAT_ID = None

# Offense thresholds
DAILY_OFFENSE_LIMIT = 2
MONTHLY_ENCOURAGEMENT_THRESHOLD = 10
MAX_PRIVATE_MESSAGES_PER_RUN = 5
RESTRICTION_DURATION_SECONDS = 300

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configure Gemini AI
try:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-1.5-flash")
    logger.info("Gemini AI configured successfully.")
except Exception as e:
    logger.error(f"Failed to configure Gemini AI: {e}")
    gemini_model = None

# Flask app
app = Flask(__name__)

# Global bot application
bot_application = None

# --- Database Setup and Functions ---
def get_db_connection():
    """Creates and returns a database connection."""
    return sqlite3.connect(DB_NAME, timeout=10)

def init_db():
    """Initializes the database and table if they don't exist."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS offenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                message_date TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                daily_count INTEGER DEFAULT 1,
                total_count INTEGER DEFAULT 1
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_date ON offenses (user_id, message_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON offenses (user_id)")
            conn.commit()
            logger.info(f"Database {DB_NAME} initialized/checked.")
    except sqlite3.Error as e:
        logger.error(f"Database initialization error: {e}")

def get_last_total_offenses(user_id):
    """Gets the last recorded total offense count for a user."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT total_count FROM offenses WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1", (user_id,))
            result = cursor.fetchone()
            return result[0] if result else 0
    except sqlite3.Error as e:
        logger.error(f"Error getting last total offenses for user {user_id}: {e}")
        return 0

def log_offense(user_id, chat_id, username, first_name):
    """Logs an offense, updates counts, and returns the new daily count."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    timestamp_str = datetime.now().isoformat()
    username = username or ""
    first_name = first_name or ""

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, daily_count, total_count FROM offenses WHERE user_id = ? AND message_date = ?", (user_id, today_str))
            today_record = cursor.fetchone()

            if today_record:
                record_id, current_daily, current_total = today_record
                new_daily_count = current_daily + 1
                new_total_count = current_total + 1
                cursor.execute("""
                UPDATE offenses
                SET daily_count = ?, total_count = ?, timestamp = ?, username = ?, first_name = ?
                WHERE id = ?
                """, (new_daily_count, new_total_count, timestamp_str, username, first_name, record_id))
                conn.commit()
                logger.info(f"Updated offense log for user {user_id} on {today_str}. Daily: {new_daily_count}, Total: {new_total_count}")
                return new_daily_count
            else:
                last_total = get_last_total_offenses(user_id)
                new_total_count = last_total + 1
                cursor.execute("""
                INSERT INTO offenses (user_id, chat_id, username, first_name, message_date, timestamp, daily_count, total_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, chat_id, username, first_name, today_str, timestamp_str, 1, new_total_count))
                conn.commit()
                logger.info(f"Created new offense log for user {user_id} on {today_str}. Daily: 1, Total: {new_total_count}")
                return 1
    except sqlite3.Error as e:
        logger.error(f"Error logging offense for user {user_id}: {e}")
        return -1

# --- Load Swear Words ---
def load_swear_words(filename):
    """Loads swear words from a file."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            words = {line.strip().lower() for line in f if line.strip()}
            logger.info(f"Loaded {len(words)} swear words from {filename} (for AI reference).")
            return words
    except FileNotFoundError:
        logger.warning(f"Swear words file not found: {filename}.")
        return set()

swear_word_list_reference = load_swear_words(SWEAR_WORDS_FILE)

# --- Core Bot Logic ---
async def check_ai_strict_profanity(original_text):
    """Uses AI to check for very strong profanity, deciding whether to delete."""
    if not gemini_model:
        logger.warning("Gemini model not available, skipping AI check.")
        return False, "AI Unavailable"

    prompt = f"""أنت نظام فلترة محتوى صارم جداً ومهمتك تحليل النص التالي بدقة لتحديد ما إذا كان يحتوي على شتائم قوية جداً تستدعي الحذف الفوري.
استند بشكل أساسي إلى قائمة الشتائم المعروفة (مثل الكلمات المتعلقة بالإهانات البالغة، الأعضاء التناسلية، الأفعال الجنسية المهينة، الإهانات الدينية الشديدة "مضافات حرف الخاء تعتبر اهانة قوية و قول مثلا انت عيل بصان يكون المستخدم قصده انت عيل بضان و لكنه موهها ب ازالة حرف او اضافة رموز و خخخخخخ بنقاط او غيرها و شتيمة ابن الوارمة   و و كلمة احا و بز و زب ).
بالإضافة إلى ذلك، استخدم حكمك لتحديد أي شتائم أخرى قوية جداً وغير مقبولة إطلاقاً في بيئة محترمة، حتى لو لم تكن ضمن قائمة شائعة.
كن صارماً للغاية: لا تحذف إلا الشتائم الواضحة والقوية جداً. تجاهل الكلمات العامية العادية، النقد، أو الألفاظ التي قد تكون غير لائقة ولكنها ليست شتائم قوية.
النص لتحليله:
{original_text}```
هل يجب حذف هذا النص بسبب احتوائه على شتائم قوية جداً؟ أجب بـ \'نعم\' أو \'لا\' فقط."""

    try:
        response = await asyncio.to_thread(gemini_model.generate_content, prompt)
        generated_text = response.text.strip().lower()
        logger.info(f"Gemini Strict Check Response: '{generated_text}' for text: '{original_text[:50]}...'")

        should_delete = generated_text.startswith("نعم") or generated_text.startswith("yes")
        reason = "AI Strict Decision" if should_delete else "AI Strict Decision (No)"
        return should_delete, reason

    except Exception as e:
        logger.error(f"Error calling Gemini API for strict check: {e}")
        return False, "AI Error"

async def restrict_user_temporarily(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, RESTRICTION_DURATION_SECONDS: int):
    """Restricts a user from sending messages for a specified duration."""
    try:
        until_date = int((datetime.now() + timedelta(seconds=RESTRICTION_DURATION_SECONDS)).timestamp())
        permissions = ChatPermissions(
            can_send_messages=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
            can_change_info=False,
            can_invite_users=False,
            can_pin_messages=False
        )
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=permissions,
            until_date=until_date
        )
        logger.info(f"Successfully restricted user {user_id} in chat {chat_id} for {RESTRICTION_DURATION_SECONDS} seconds.")
        return True
    except Exception as e:
        logger.error(f"Failed to restrict user {user_id} in chat {chat_id}: {e}")
        return False

# --- Message Handler ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not (message.text or message.caption):
        return

    chat = message.chat
    user = message.from_user
    if not chat or not user:
        return

    if user.is_bot:
        return

    chat_id = chat.id
    user_id = user.id
    message_id = message.message_id
    first_name = user.first_name
    username = user.username
    text = message.text or message.caption

    logger.info(f"Received message from {username or first_name} (ID: {user_id}) in chat {chat_id}: '{text[:50]}...'")

    should_delete, reason = await check_ai_strict_profanity(text)

    if should_delete:
        logger.warning(f"Offensive message detected ({reason}) from {user_id} in chat {chat_id}. Deleting.")

        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            logger.info(f"Deleted message {message_id} from chat {chat_id}.")
        except Exception as e:
            logger.error(f"Failed to delete message {message_id} from chat {chat_id}: {e}")

        daily_count = await asyncio.to_thread(log_offense, user_id, chat_id, username, first_name)

        if daily_count == -1:
            logger.error(f"Failed to log offense for user {user_id}. Aborting further action.")
            if ADMIN_CHAT_ID:
                try:
                    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"Error logging offense for user {user_id} ({username or first_name}) in chat {chat_id}.")
                except Exception as admin_e:
                    logger.error(f"Failed to send admin notification: {admin_e}")
            return

        mention = f"@{username}" if username else f"<a href='tg://user?id={user_id}'>{first_name}</a>"
        parse_mode_to_use = ParseMode.HTML

        try:
            if daily_count >= DAILY_OFFENSE_LIMIT:
                logger.warning(f"User {user_id} reached daily limit ({daily_count}). Attempting to restrict.")
                restriction_success = await restrict_user_temporarily(context, chat_id, user_id, RESTRICTION_DURATION_SECONDS)
                if restriction_success:
                    restriction_text = f"{mention}، تم تقييد حسابك مؤقتاً لمدة {RESTRICTION_DURATION_SECONDS // 60} دقائق بسبب تكرار نشر محتوى غير لائق."
                    await context.bot.send_message(chat_id=chat_id, text=restriction_text, parse_mode=parse_mode_to_use)
                else:
                    restriction_fail_text = f"فشل تقييد المستخدم {mention}. تم تسجيل السيئة رقم {daily_count} اليوم. يرجى المراجعة الإدارية."
                    await context.bot.send_message(chat_id=chat_id, text=restriction_fail_text, parse_mode=parse_mode_to_use)
            else:
                warning_text = f"{mention}، تم حذف رسالتك لاحتوائها على ألفاظ غير لائقة. هذه هي السيئة رقم {daily_count} اليوم. تكرار السيئات سيؤدي إلى التقييد المؤقت."
                await context.bot.send_message(chat_id=chat_id, text=warning_text, parse_mode=parse_mode_to_use)
        except Exception as send_e:
            logger.error(f"Failed to send warning/restriction message to chat {chat_id}: {send_e}")
    else:
        if reason != "AI Unavailable" and reason != "AI Error":
             logger.info(f"AI decided not to delete message from {user_id} ({reason}). Text: '{text[:50]}...'")

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("مرحباً! أنا بوت فلترة الشتائم. سأقوم بمراقبة الرسائل وحذف المحتوى غير اللائق وتسجيل السيئات بناءً على تحليل الذكاء الاصطناعي الصارم. السيئة الثانية في اليوم تؤدي إلى تقييد مؤقت (mute) لمدة 5 دقائق.")

async def stat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the user their personal offense statistics."""
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name

    today_str = datetime.now().strftime("%Y-%m-%d")
    current_month_str = datetime.now().strftime("%Y-%m")

    daily_offenses = 0
    monthly_offenses = 0
    total_offenses = 0

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT daily_count FROM offenses WHERE user_id = ? AND message_date = ?", (user_id, today_str))
            result = cursor.fetchone()
            if result: daily_offenses = result[0]

            cursor.execute("SELECT SUM(daily_count) FROM offenses WHERE user_id = ? AND message_date LIKE ?", (user_id, f"{current_month_str}-%"))
            result = cursor.fetchone()
            if result and result[0]: monthly_offenses = result[0]

            cursor.execute("SELECT total_count FROM offenses WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1", (user_id,))
            result = cursor.fetchone()
            if result: total_offenses = result[0]

        message = (
            f"📊 <b>إحصائياتك الشخصية يا {first_name}:</b>\n"
            f"اليوم: {daily_offenses} سيئة\n"
            f"هذا الشهر: {monthly_offenses} سيئة\n"
            f"إجمالي السيئات: {total_offenses} سيئة\n\n"
            "تذكر، الهدف هو الحفاظ على بيئة نقاش إيجابية! 😊"
        )
        await update.message.reply_text(message, parse_mode=ParseMode.HTML)

    except sqlite3.Error as e:
        logger.error(f"Error retrieving stats for user {user_id}: {e}")
        await update.message.reply_text("عذراً، حدث خطأ أثناء جلب إحصائياتك.")

# --- Flask Routes ---
@app.route('/')
def index():
    return jsonify({"status": "Bot is running", "message": "Telegram Bot Webhook Endpoint"})

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming webhook updates from Telegram."""
    try:
        json_data = request.get_json()
        if json_data:
            update = Update.de_json(json_data, bot_application.bot)
            asyncio.create_task(bot_application.process_update(update))
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/set_webhook', methods=['POST'])
def set_webhook():
    """Set the webhook URL for the bot."""
    try:
        webhook_url = WEBHOOK_URL + "/webhook"
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        asyncio.run(bot.set_webhook(url=webhook_url))
        return jsonify({"status": "success", "webhook_url": webhook_url})
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Initialize Bot Application ---
def create_bot_application():
    """Create and configure the bot application."""
    global bot_application
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stat", stat_command))
    
    # Message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    bot_application = application
    return application

init_db()
create_bot_application()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
# For Vercel deployment
app = app

