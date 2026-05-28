import os
import logging
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# បើក Logs មើលជំងឺ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")

app_web = Flask('')

@app_web.route('/')
def home():
    return "E11 Lab Test Bot is Online!"

def run_web_server():
    port = int(os.getenv("PORT", 10000))
    app_web.run(host='0.0.0.0', port=port)

# --- Commands ឆ្លើយតបអត្ថបទធម្មតា (គ្មានទាញទិន្នន័យពីក្រៅ) ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🙏 សួស្តីបង! E11 Lab Assistant ដំណើរការជោគជ័យហើយ! (Test Ok)")

async def manual_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 របាយការណ៍តេស្ត៖ ទីផ្សារមាសកំពុងដំណើរការជាធម្មតា។")

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📰 ប្រព័ន្ធ News Tracker រៀបចំរួចរាល់។")

async def zones_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏗️ តំបន់គន្លឹះ SMC Key Zones កំពុងដំណើរការ។")

if __name__ == '__main__':
    # រត់ Web Server ការពារការ Sleep
    threading.Thread(target=run_web_server, daemon=True).start()

    if not TOKEN:
        logger.error("ERROR: TELEGRAM_TOKEN Missing!")
    else:
        app = ApplicationBuilder().token(TOKEN).build()
        
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("get_report", manual_report_command))
        app.add_handler(CommandHandler("news", news_command))
        app.add_handler(CommandHandler("zones", zones_command))
        
        logger.info("Bot is running...")
        app.run_polling()
        
