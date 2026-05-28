import os
import logging
import threading
import time
from datetime import datetime
import pytz
import requests
import yfinance as yf
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
# ទាញយក URL របស់ Render Web Service (ឧទាហរណ៍៖ https://e11-bot.onrender.com)
RENDER_APP_URL = os.getenv("RENDER_EXTERNAL_URL") 

app_web = Flask('')

@app_web.route('/')
def home():
    return "E11 Lab Bot is active and anti-sleep mechanism is running!"

def run_web_server():
    # គម្រោង Free របស់ Render ប្រើ Port 10000 ជាទូទៅ
    port = int(os.getenv("PORT", 10000))
    app_web.run(host='0.0.0.0', port=port)

# មុខងារ Keep-Alive (ដាស់ខ្លួនឯងរៀងរាល់ ១២ នាទី ការពារ Server លក់ស្រទំ)
def ping_self():
    while True:
        # រង់ចាំ ១២ នាទី (៧២០ វិនាទី) មុននឹង Ping ម្ដង
        time.sleep(720)
        if RENDER_APP_URL:
            try:
                response = requests.get(RENDER_APP_URL)
                logger.info(f"Self-ping status: {response.status_code} - Bot kept alive successfully.")
            except Exception as e:
                logger.error(f"Self-ping failed: {e}")
        else:
            logger.warning("RENDER_EXTERNAL_URL is not set. Anti-sleep ping skipped.")

# --- ផ្នែកទាញទិន្នន័យទីផ្សារ (SMC/ICT Framework) ---
def fetch_market_data():
    try:
        gold = yf.Ticker("GC=F")
        dxy = yf.Ticker("DX-Y.NYB")
        us10y = yf.Ticker("^TNX")
        
        g_hist = gold.history(period="20d")
        d_hist = dxy.history(period="5d")
        u_hist = us10y.history(period="5d")
        
        if g_hist.empty or d_hist.empty or u_hist.empty:
            return None
            
        current_price = g_hist['Close'].iloc[-1]
        prev_close = g_hist['Close'].iloc[-2]
        daily_change = ((current_price - prev_close) / prev_close) * 100
        
        high_price = g_hist['High'].iloc[-1]
        low_price = g_hist['Low'].iloc[-1]
        
        sma_20 = g_hist['Close'].mean()
        bias = "Bullish 📈" if current_price > sma_20 else "Bearish 📉"
        
        g_hist['TR'] = g_hist['High'] - g_hist['Low']
        atr = g_hist['TR'].mean()
        
        pivot = (g_hist['High'].iloc[-2] + g_hist['Low'].iloc[-2] + g_hist['Close'].iloc[-2]) / 3
        r1 = (2 * pivot) - g_hist['Low'].iloc[-2]
        s1 = (2 * pivot) - g_hist['High'].iloc[-2]
        
        dxy_trend = "Strong 💪" if d_hist['Close'].iloc[-1] > d_hist['Close'].iloc[-2] else "Weak 📉"
        yield_trend = "Strong 💪" if u_hist['Close'].iloc[-1] > u_hist['Close'].iloc[-2] else "Weak 📉"
        
        macro_summary = f"DXY មានសន្ទុះ {dxy_trend} និង US10Y Bond Yield មានសន្ទុះ {yield_trend}។"
        
        return {
            "price": round(current_price, 2),
            "change": round(daily_change, 2),
            "high": round(high_price, 2),
            "low": round(low_price, 2),
            "bias": bias,
            "macro": macro_summary,
            "supply": round(r1, 2),
            "demand": round(s1, 2),
            "pivot": round(pivot, 2),
            "atr": round(atr, 2)
        }
    except Exception as e:
        logger.error(f"Error fetching market data: {e}")
        return None

def fetch_economic_calendar():
    today_news = [
        {"time": "19:30", "event": "USD Core CPI (MoM)", "forecast": "0.3%"},
        {"time": "21:00", "event": "USD FOMC Statement", "forecast": "High Volatility"}
    ]
    table_md = "| ម៉ោង (GMT+7) | ព្រឹត្តិការណ៍សេដ្ឋកិច្ច (Event) | ព្យាករណ៍ (Forecast) |\n| :--- | :--- | :--- |\n"
    for news in today_news:
        table_md += f"| {news['time']} | {news['event']} | {news['forecast']} |\n"
    return table_md

def generate_report():
    m_data = fetch_market_data()
    news_table = fetch_economic_calendar()
    
    if not m_data:
        return "❌ មិនអាចបង្កើតរបាយការណ៍បានទេ ដោយសារមានបញ្ហាទាញទិន្នន័យទីផ្សារ។"
        
    current_date = datetime.now(pytz.timezone('Asia/Phnom_Penh')).strftime('%Y-%m-%d')
    
    if "Bullish" in m_data["bias"]:
        entry_a = m_data["demand"] + (m_data["atr"] * 0.1)
        sl_a = entry_a - (m_data["atr"] * 1.5)
        tp_a = entry_a + (m_data["atr"] * 3)
        rr_a = "1:2"
        entry_b = m_data["supply"] - (m_data["atr"] * 0.2)
        sl_b = entry_b + (m_data["atr"] * 1.5)
        tp_b = entry_b - (m_data["atr"] * 2.5)
    else:
        entry_a = m_data["supply"] - (m_data["atr"] * 0.1)
        sl_a = entry_a + (m_data["atr"] * 1.5)
        tp_a = entry_a - (m_data["atr"] * 3)
        rr_a = "1:2"
        entry_b = m_data["demand"] + (m_data["atr"] * 0.2)
        sl_b = entry_b - (m_data["atr"] * 1.5)
        tp_b = entry_b + (m_data["atr"] * 2.5)

    return f"""# 📊 របាយការណ៍វិភាគមាសប្រចាំថ្ងៃ (XAU/USD)
**Institutional Grade Analysis (OANDA Data) | {current_date}**
* Current Price: ${m_data['price']} | Daily % Change: {m_data['change']}%
* Today's High/Low: ${m_data['high']} / ${m_data['low']}

### 🌍 ១. ស្ថានភាព Macro & ព័ត៌មាន (Fundamental)
📊 និន្នាការ៖ {m_data['macro']}
បច្ចុប្បន្នភាពទីផ្សារមាសកំពុងរងឥទ្ធិពលពីលំហូរការប្រាក់អាមេរិក និងសន្ទុះដុល្លារដែលរៀបចំឡើងតាមយន្តការ Market Structure (SMC)។

📰 High Impact News ថ្ងៃនេះ:
{news_table}

### 🎯 ២. INTRADAY EXECUTION ROADMAP
🏗️ Technical Framework:
- Daily Bias (D1): {m_data['bias']}
- Key Zones: [Supply: ${m_data['supply']} | Pivot: ${m_data['pivot']} | Demand: ${m_data['demand']}]

⚡ Trade Scenarios:
- Scenario A (High Probability): Entry: ${round(entry_a, 2)} | SL: ${round(sl_a, 2)} | TP: ${round(tp_a, 2)} | RR Ratio: {rr_a}
- Scenario B (Low/Medium Probability): Entry: ${round(entry_b, 2)} | SL: ${round(sl_b, 2)} | TP: ${round(tp_b, 2)}

### ⚠️ ៣. ការគ្រប់គ្រងហានិភ័យ (Risk Management)
- សូមប្រុងប្រយ័ត្នខ្ពស់នៅម៉ោងព័ត៌មានចេញ (High Impact News) ទីផ្សារអាចមានការប្រែប្រួលខ្លាំង (Spread Expansion)។
- គ្រប់គ្រងហានិភ័យដោយប្រើប្រាស់ទំហំឡូតសមរម្យ (Proper Lot Sizing) និងមិនត្រូវលុប SL ដាច់ខាត។

---
*Generated by E11 Lab Bot 🚀 | Educational Purpose Only*"""

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🙏 សួស្តីបង! ខ្ញុំជា E11 Lab Bot (គម្រោង Free Web Service)។ ខ្ញុំនឹងផ្ញើរបាយការណ៍ជូនរៀងរាល់ម៉ោង ០៨:០០ ព្រឹក។\n\nវាយ /get_report ដើម្បីមើលភ្លាមៗបាន!")

async def manual_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 កំពុងទាញទិន្នន័យវិភាគផ្សារចុងក្រោយ...")
    report = generate_report()
    await update.message.reply_text(text=report, parse_mode="Markdown")

def start_scheduler(application):
    scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Phnom_Penh'))
    
    def scheduled_job():
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(application.bot.send_message(chat_id=CHAT_ID, text=generate_report(), parse_mode="Markdown"))

    scheduler.add_job(scheduled_job, 'cron', hour=8, minute=0)
    scheduler.start()
    logger.info("Cron Scheduler hooked at 08:00 AM KH Time.")

if __name__ == '__main__':
    # បើក Flask web server
    threading.Thread(target=run_web_server, daemon=True).start()
    
    # បើកប្រព័ន្ធការពារការលក់សម្រាន្ត (Anti-Sleep)
    threading.Thread(target=ping_self, daemon=True).start()

    if not TOKEN or not CHAT_ID:
        logger.error("Missing Environment Variables!")
    else:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("get_report", manual_report_command))
        
        start_scheduler(app)
        
        logger.info("Bot is running under Web Service with Anti-Sleep protocol...")
        app.run_polling()
    
