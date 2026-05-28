import os
import logging
import threading
import time
import pytz
from datetime import datetime
import requests
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
RENDER_APP_URL = os.getenv("RENDER_EXTERNAL_URL") 

app_web = Flask('')

@app_web.route('/')
def home():
    return "E11 Lab Assistant is Online!"

def run_web_server():
    port = int(os.getenv("PORT", 10000))
    app_web.run(host='0.0.0.0', port=port)

def ping_self():
    while True:
        time.sleep(720)
        if RENDER_APP_URL:
            try: requests.get(RENDER_APP_URL)
            except Exception: pass

def fetch_ticker_data(ticker):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=2d"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=10).json()
        result = res['chart']['result'][0]
        indicators = result['indicators']['quote'][0]
        return {
            "price": result['meta']['regularMarketPrice'],
            "prev_close": result['meta']['chartPreviousClose'],
            "high": max(indicators['high']),
            "low": min(indicators['low'])
        }
    except Exception as e:
        logger.error(f"Error {ticker}: {e}")
        return None

def fetch_market_data():
    gold_data = fetch_ticker_data("GC=F")
    if not gold_data: return None
    
    current_price = gold_data["price"]
    prev_close = gold_data["prev_close"]
    pivot = (gold_data["high"] + gold_data["low"] + current_price) / 3
    r1 = (2 * pivot) - gold_data["low"]
    s1 = (2 * pivot) - gold_data["high"]
    atr = gold_data["high"] - gold_data["low"]
    
    bias = "Bullish 📈" if current_price > pivot else "Bearish 📉"
    
    return {
        "price": round(current_price, 2), 
        "change": round(((current_price - prev_close) / prev_close) * 100, 2),
        "bias": bias, "supply": round(r1, 2), "demand": round(s1, 2), "pivot": round(pivot, 2)
    }

def generate_report():
    m_data = fetch_market_data()
    if not m_data: return "❌ មិនអាចទាញទិន្នន័យទីផ្សារបានទេ។"
    return f"""# 📊 E11 Lab Gold Analysis
* Current Price: ${m_data['price']} ({m_data['change']}%)
* Daily Bias: {m_data['bias']}
* Key Zones: [Supply: ${m_data['supply']} | Pivot: ${m_data['pivot']} | Demand: ${m_data['demand']}]
* Run Time: {datetime.now().strftime('%H:%M')}"""

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🙏 សួស្តីបង! E11 Lab Assistant រួចរាល់ហើយ។ វាយ /get_report ដើម្បីតេស្ត!")

async def manual_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 កំពុងបង្កើតរបាយការណ៍ Live ចុងក្រោយ...")
    await update.message.reply_text(text=generate_report(), parse_mode="Markdown")

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📰 High Impact News Tracker is active.")

async def zones_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m_data = fetch_market_data()
    if m_data:
        await update.message.reply_text(f"🏗️ SMC Key Zones:\n• Supply: ${m_data['supply']}\n• Pivot: ${m_data['pivot']}\n• Demand: ${m_data['demand']}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Commands List:\n/start\n/get_report\n/news\n/zones")

def start_scheduler(application):
    if not CHAT_ID:
        logger.warning("No Chat ID found. Auto-scheduler is paused, but Bot commands will work fine!")
        return
    scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Phnom_Penh'))
    def scheduled_job():
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try: loop.run_until_complete(application.bot.send_message(chat_id=CHAT_ID, text=generate_report(), parse_mode="Markdown"))
        except Exception: pass
    scheduler.add_job(scheduled_job, 'cron', hour=8, minute=0)
    scheduler.start()

if __name__ == '__main__':
    threading.Thread(target=run_web_server, daemon=True).start()
    threading.Thread(target=ping_self, daemon=True).start()

    if not TOKEN:
        logger.error("TELEGRAM_TOKEN is missing!")
    else:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("get_report", manual_report_command))
        app.add_handler(CommandHandler("news", news_command))
        app.add_handler(CommandHandler("zones", zones_command))
        app.add_handler(CommandHandler("help", help_command))
        start_scheduler(app)
        app.run_polling()
        
