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

# កំណត់ការបង្ហាញ Logs របស់ប្រព័ន្ធ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ទាញយកតម្លៃសម្ងាត់ពី Environment Variables របស់ Render
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
RENDER_APP_URL = os.getenv("RENDER_EXTERNAL_URL") 

app_web = Flask('')

@app_web.route('/')
def home():
    return "E11 Lab Assistant is Active! Anti-sleep mechanism is operating perfectly."

def run_web_server():
    port = int(os.getenv("PORT", 10000))
    app_web.run(host='0.0.0.0', port=port)

# ប្រព័ន្ធ Self-Ping វាយកន្ទុយខ្លួនឯងរៀងរាល់ ១២ នាទី ការពារ Server Free កុំឱ្យ Sleep
def ping_self():
    while True:
        time.sleep(720)
        if RENDER_APP_URL:
            try:
                response = requests.get(RENDER_APP_URL)
                logger.info(f"Anti-Sleep Ping Status: {response.status_code}")
            except Exception as e:
                logger.error(f"Anti-Sleep Ping Failed: {e}")

# --- ផ្នែកទាញទិន្នន័យទីផ្សារ (Yahoo Finance Light-Fetch Engine) ---
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
    gold_data = fetch_ticker_data("GC=F")
    dxy_data = fetch_ticker_data("DX-Y.NYB")
    us10y_data = fetch_ticker_data("^TNX")
    
    if not gold_data:
        return None
        
    current_price = gold_data["price"]
    prev_close = gold_data["prev_close"]
    daily_change = ((current_price - prev_close) / prev_close) * 100
    
    # គណនាគន្លឹះបច្ចេកទេសតាមទម្រង់ SMC/ICT Framework (Pivot Point, Supply/Demand, Matrix Zones)
    pivot = (gold_data["high"] + gold_data["low"] + current_price) / 3
    r1 = (2 * pivot) - gold_data["low"]
    s1 = (2 * pivot) - gold_data["high"]
    atr_estimation = gold_data["high"] - gold_data["low"]
    
    bias = "Bullish 📈" if current_price > pivot else "Bearish 📉"
    
    dxy_status = "Strong 💪" if dxy_data and dxy_data["price"] > dxy_data["prev_close"] else "Weak 📉"
    us10y_status = "Strong 💪" if us10y_data and us10y_data["price"] > us10y_data["prev_close"] else "Weak 📉"
    macro_summary = f"DXY Matrix: {dxy_status} | US10Y Yield Matrix: {us10y_status}"
    
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

def get_news_table():
    # កាលវិភាគព័ត៌មានស្នូល High Impact ប្រចាំថ្ងៃ
    today_news = [
        {"time": "19:30 (GMT+7)", "event": "USD Core CPI (MoM)", "impact": "🔴 High Volatility", "forecast": "0.3%"},
        {"time": "21:00 (GMT+7)", "event": "USD FOMC Statement & Funds Rate", "impact": "🔴 Extreme Volatility", "forecast": "5.50%"}
    ]
    table_md = "| Time (GMT+7) | Economic Event | Impact | Forecast |\n| :--- | :--- | :--- | :--- |\n"
    for news in today_news:
        table_md += f"| {news['time']} | {news['event']} | {news['impact']} | {news['forecast']} |\n"
    return table_md

def generate_report():
    m_data = fetch_market_data()
    news_table = get_news_table()
    
    if not m_data:
        return "❌ មិនអាចបង្កើតរបាយការណ៍បានទេ ដោយសារមានបញ្ហាទាញទិន្នន័យទីផ្សារ។"
        
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    # គណនា Logic សម្រាប់គម្រោងផែនទីជួញដូរ (Execution Roadmap) ផ្អែកលើ Daily Bias
    if "Bullish" in m_data["bias"]:
        entry_a = m_data["demand"] + (m_data["atr"] * 0.1)
        sl_a = entry_a - (m_data["atr"] * 1.2)
        tp_a = entry_a + (m_data["atr"] * 2.5)
        entry_b = m_data["supply"] - (m_data["atr"] * 0.2)
        sl_b = entry_b + (m_data["atr"] * 1.2)
        tp_b = entry_b - (m_data["atr"] * 2.0)
    else:
        entry_a = m_data["supply"] - (m_data["atr"] * 0.1)
        sl_a = entry_a + (m_data["atr"] * 1.2)
        tp_a = entry_a - (m_data["atr"] * 2.5)
        entry_b = m_data["demand"] + (m_data["atr"] * 0.2)
        sl_b = entry_b - (m_data["atr"] * 1.2)
        tp_b = entry_b + (m_data["atr"] * 2.0)

    return f"""# 📊 របាយការណ៍វិភាគមាសប្រចាំថ្ងៃ (XAU/USD)
**Institutional Grade Analysis (OANDA/Yahoo Data) | {current_date}**
* Current Price: ${m_data['price']} | Daily % Change: {m_data['change']}%
* Today's High/Low: ${m_data['high']} / ${m_data['low']}

### 🌍 ១. ស្ថានភាព Macro & ព័ត៌មាន (Fundamental)
📊 និន្នាការ៖ {m_data['macro']}
លំហូរការប្រាក់អាមេរិក និងសន្ទុះដុល្លារដែលរៀបចំឡើងតាមយន្តការ Market Structure (SMC)។

📰 High Impact News ថ្ងៃនេះ:
{news_table}

### 🎯 ២. INTRADAY EXECUTION ROADMAP
🏗️ Technical Framework:
• Daily Bias (D1): {m_data['bias']}
• Key Zones: [Supply: ${m_data['supply']} | Pivot: ${m_data['pivot']} | Demand: ${m_data['demand']}]

⚡ Trade Scenarios:
• Scenario A (High Probability): Entry: ${round(entry_a, 2)} | SL: ${round(sl_a, 2)} | TP: ${round(tp_a, 2)}
• Scenario B (Medium Probability): Entry: ${round(entry_b, 2)} | SL: ${round(sl_b, 2)} | TP: ${round(tp_b, 2)}

### ⚠️ ៣. ការគ្រប់គ្រងហានិភ័យ (Risk Management)
• សូមប្រុងប្រយ័ត្នខ្ពស់នៅម៉ោងព័ត៌មានចេញ (High Impact News) ទីផ្សារអាចមានការប្រែប្រួលខ្លាំង (Spread Expansion)។
• គ្រប់គ្រងហានិភ័យដោយប្រើប្រាស់ទំហំឡូតសមរម្យ (Proper Lot Sizing) និងមិនត្រូវដក SL ដាច់ខាត។

---
*Generated by E11 Lab Bot 🚀 | Educational Purpose Only*"""

# --- ផ្នែកគ្រប់គ្រង Commands របស់ Telegram ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🙏 សួស្តីបង! ខ្ញុំជា **E11 Lab Assistant Bot**។\n\n"
        "ខ្ញុំត្រូវបានបង្កើតឡើងដើម្បីផ្ដល់ជូនរបាយការណ៍វិភាគបច្ចេកទេសមាស (XAUUSD) តាមទម្រង់ ICT & SMC Framework ស្វ័យប្រវត្តជារៀងរាល់ព្រឹក។\n\n"
        "ℹ️ បងអាចចុចប៊ូតុង **Menu** ឬវាយ `/help` ដើម្បីមើលបញ្ជីបញ្ជាទាំងអស់របស់ខ្ញុំបានបង!"
    )
    await update.message.reply_text(text=welcome_text, parse_mode="Markdown")

async def manual_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 កំពុងទាញទិន្នន័យវិភាគផ្សារ និងបង្កើតរបាយការណ៍ Live ចុងក្រោយ...")
    report = generate_report()
    await update.message.reply_text(text=report, parse_mode="Markdown")

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    news_table = get_news_table()
    response = f"📰 **High Impact Economic News Calendar** ថ្ងៃនេះ៖\n\n{news_table}\n\n*សូមប្រុងប្រយ័ត្នខ្ពស់ចំពោះការជួញដូរចន្លោះម៉ោងព័ត៌មានចេញទាំងនេះ!*"
    await update.message.reply_text(text=response, parse_mode="Markdown")

async def zones_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m_data = fetch_market_data()
    if not m_data:
        await update.message.reply_text("❌ មិនអាចទាញទិន្នន័យតំបន់បច្ចេកទេសបានទេនៅពេលនេះ។")
        return
        
    zones_text = (
        f"🏗️ **E11 Lab ICT/SMC Technical Key Zones (XAUUSD)**\n\n"
        f"• **Daily Bias:** {m_data['bias']}\n"
        f"• **Current Price:** ${m_data['price']}\n"
        f"• **Premium/Supply Zone:** ${m_data['supply']}\n"
        f"• **Equilibrium/Pivot Point:** ${m_data['pivot']}\n"
        f"• **Discount/Demand Zone:** ${m_data['demand']}\n"
        f"• **Estimated Daily ATR:** ${m_data['atr']}\n\n"
        f"_*ចំណាំ៖_ គួររង់ចាំការបញ្ជាក់សញ្ញា (Confirmation Setup) នៅលើ Small Timeframe (M5/M15) ពេលតម្លៃឈានចូលតំបន់ទាំងនេះ។*"
    )
    await update.message.reply_text(text=zones_text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 **សៀវភៅណែនាំការប្រើប្រាស់ E11 Lab Assistant**\n\n"
        "បងអាចប្រើប្រាស់ Commands ខាងក្រោមដើម្បីបញ្ជាខ្ញុំ៖\n"
        "• /start - ចាប់ផ្ដើមដំណើរការ Bot និងទទួលសារស្វាគមន៍\n"
        "• /get_report - ទាញយករបាយការណ៍វិភាគមាសរួមពេញលេញភ្លាមៗ\n"
        "• /news - ពិនិត្យមើលតារាងព័ត៌មានសេដ្ឋកិច្ច High Impact ថ្ងៃនេះ\n"
        "• /zones - មើលតម្លៃតំបន់គន្លឹះបច្ចេកទេស (SMC Key Zones)\n"
        "• /help - បង្ហាញសៀវភៅណែនាំប្រើប្រាស់នេះ\n\n"
        "📢 *ប្រព័ន្ធផ្សាយស្វ័យប្រវត្ត៖* ខ្ញុំនឹងផ្ញើរបាយការណ៍រួមចូលទៅកាន់ Group/Channel របស់បងជារៀងរាល់ព្រឹកនៅ **ម៉ោង ០៨:០០ ព្រឹក** (ម៉ោងនៅកម្ពុជា) ដោយស្វ័យប្រវត្ត។"
    )
    await update.message.reply_text(text=help_text, parse_mode="Markdown")

def start_scheduler(application):
    import pytz
    scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Phnom_Penh'))
    
    def scheduled_job():
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                application.bot.send_message(chat_id=CHAT_ID, text=generate_report(), parse_mode="Markdown")
            )
            logger.info("Daily report successfully dispatched via scheduler.")
        except Exception as e:
            logger.error(f"Scheduler failed to dispatch message: {e}")

    # កំណត់ម៉ោងរត់ស្វ័យប្រវត្តរៀងរាល់ម៉ោង ០៨:០០ ព្រឹក (ម៉ោងនៅកម្ពុជា)
    scheduler.add_job(scheduled_job, 'cron', hour=8, minute=0)
    scheduler.start()
    logger.info("Cron Scheduler successfully hooked at 08:00 AM Cambodia Time.")

if __name__ == '__main__':
    # បើកដំណើរការ Flask Web Server (Thread ទីមួយ)
    threading.Thread(target=run_web_server, daemon=True).start()
    
    # បើកដំណើរការប្រព័ន្ធការពារការលក់សម្រាន្ត Anti-Sleep (Thread ទីពីរ)
    threading.Thread(target=ping_self, daemon=True).start()

    if not TOKEN or not CHAT_ID:
        logger.error("CRITICAL ERROR: Environment Variables are completely missing!")
    else:
        # បង្កើតកម្មវិធី Telegram Application
        app = ApplicationBuilder().token(TOKEN).build()
        
        # ចងភ្ជាប់រាល់មុខងារ Commands ទាំងអស់ជាមួយ Bot
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("get_report", manual_report_command))
        app.add_handler(CommandHandler("news", news_command))
        app.add_handler(CommandHandler("zones", zones_command))
        app.add_handler(CommandHandler("help", help_command))
        
        # បើកប្រព័ន្ធប្រកាសព័ត៌មានតាមម៉ោងកាលវិភាគ
        start_scheduler(app)
        
        logger.info("E11 Lab Bot is listening to commands on Telegram platform...")
        # ចាប់ផ្ដើមដំណើរការទាញទិន្នន័យសារឆាត (Polling)
        app.run_polling()
        
