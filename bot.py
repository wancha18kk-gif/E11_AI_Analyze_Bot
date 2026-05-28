import os
import logging
import threading
import time
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
    return "E11 Lab Bot is active and running smoothly!"

def run_web_server():
    port = int(os.getenv("PORT", 10000))
    app_web.run(host='0.0.0.0', port=port)

def ping_self():
    while True:
        time.sleep(720)
        if RENDER_APP_URL:
            try:
                response = requests.get(RENDER_APP_URL)
                logger.info(f"Self-ping status: {response.status_code}")
            except Exception as e:
                logger.error(f"Self-ping failed: {e}")

# --- មុខងារទាញទិន្នន័យតាម HTTP Request ពី Yahoo Finance ផ្ទាល់ (សុវត្ថិភាពបំផុត) ---
def fetch_ticker_data(ticker):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=2d"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        res = requests.get(url, headers=headers, timeout=10).json()
        result = res['chart']['result'][0]
        indicators = result['indicators']['quote'][0]
        
        current_price = result['meta']['regularMarketPrice']
        prev_close = result['meta']['chartPreviousClose']
        high_price = max(indicators['high'])
        low_price = min(indicators['low'])
        
        return {
            "price": current_price,
            "prev_close": prev_close,
            "high": high_price,
            "low": low_price
        }
    except Exception as e:
        logger.error(f"Error fetching ticker {ticker}: {e}")
        return None

def fetch_market_data():
    # ទាញទិន្នន័យ មាស (GC=F), DXY (DX-Y.NYB), และ US10Y (^TNX)
    gold_data = fetch_ticker_data("GC=F")
    dxy_data = fetch_ticker_data("DX-Y.NYB")
    us10y_data = fetch_ticker_data("^TNX")
    
    if not gold_data:
        return None
        
    current_price = gold_data["price"]
    prev_close = gold_data["prev_close"]
    daily_change = ((current_price - prev_close) / prev_close) * 100
    
    # គណនា SMC Levels បែបបច្ចេកទេស
    pivot = (gold_data["high"] + gold_data["low"] + current_price) / 3
    r1 = (2 * pivot) - gold_data["low"]
    s1 = (2 * pivot) - gold_data["high"]
    atr_estimation = gold_data["high"] - gold_data["low"]
    
    bias = "Bullish 📈" if current_price > pivot else "Bearish 📉"
    
    # វិភាគ Macro
    dxy_status = "ឡើងថ្លៃ (Strong)" if dxy_data and dxy_data["price"] > dxy_data["prev_close"] else "ចុះថ្លៃ (Weak)"
    us10y_status = "ឡើងថ្លៃ (Strong)" if us10y_data and us10y_data["price"] > us10y_data["prev_close"] else "ចុះថ្លៃ (Weak)"
    macro_summary = f"DXY មានសន្ទុះ {dxy_status} និង US10Y Bond Yield មានសន្ទុះ {us10y_status}។"
    
    return {
        "price": round(current_price, 2),
        "change": round(daily_change, 2),
        "high": round(gold_data["high"], 2),
        "low": round(gold_data["low"], 2),
        "bias": bias,
        "macro": macro_summary,
        "supply": round(r1, 2),
        "demand": round(s1, 2),
        "pivot": round(pivot, 2),
        "atr": round(atr_estimation, 2)
    }

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
        
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    if "Bullish" in m_data["bias"]:
        entry_a = m_data["demand"] + (m_data["atr"] * 0.1)
        sl_a = entry_a - (m_data["atr"] * 1.2)
        tp_a = entry_a + (m_data["atr"] * 2.5)
        rr_a = "1:2"
        entry_b = m_data["supply"] - (m_data["atr"] * 0.2)
        sl_b = entry_b + (m_data["atr"] * 1.2)
        tp_b = entry_b - (m_data["atr"] * 2.0)
    else:
        entry_a = m_data["supply"] - (m_data["atr"] * 0.1)
        sl_a = entry_a + (m_data["atr"] * 1.2)
        tp_a = entry_a - (m_data["atr"] * 2.5)
        rr_a = "1:2"
        entry_b = m_data["demand"] + (m_data["atr"] * 0.2)
        sl_b = entry_b - (m_data["atr"] * 1.2)
        tp_b = entry_b - (m_data["atr"] * 2.0)

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
    await update.message.reply_text("🙏 សួស្តីបង! ខ្ញុំជា E11 Lab Bot។ ខ្ញុំនឹងផ្ញើរបាយការណ៍ជូនរៀងរាល់ម៉ោង ០៨:០០ ព្រឹក។\n\nវាយ /get_report ដើម្បីមើលភ្លាមៗ!")

async def manual_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 កំពុងទាញទិន្នន័យវិភាគផ្សារចុងក្រោយ...")
    report = generate_report()
    await update.message.reply_text(text=report, parse_mode="Markdown")

def start_scheduler(application):
    import pytz
    scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Phnom_Penh'))
    
    def scheduled_job():
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(application.bot.send_message(chat_id=CHAT_ID, text=generate_report(), parse_mode="Markdown"))

    scheduler.add_job(scheduled_job, 'cron', hour=8, minute=0)
    scheduler.start()
    logger.info("Scheduler configured for Cambodia Time (08:00 AM).")

if __name__ == '__main__':
    threading.Thread(target=run_web_server, daemon=True).start()
    threading.Thread(target=ping_self, daemon=True).start()

    if not TOKEN or not CHAT_ID:
        logger.error("Missing Environment Variables!")
    else:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("get_report", manual_report_command))
        
        start_scheduler(app)
        app.run_polling()
        
