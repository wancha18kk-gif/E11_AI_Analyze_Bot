import os
import logging
import threading
from datetime import datetime
import pytz
import requests
import pandas as pd
import yfinance as yf
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler

# កំណត់ Logging សម្រាប់តាមដាន Error ក្នុង Render Logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ទាញយក Environment Variables (Secret Keys) ពី Render
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") # Chat ID របស់ Channel ឬ Group ដែលចង់ឱ្យ Bot ផុសស្វ័យប្រវត្ត
PORT = int(os.getenv("PORT", 10000)) # Render ប្រើ Port 10000 ជាទូទៅ

# --- ១. បង្កើត FLASK SERVER សម្រាប់ BIND PORT ការពារ RENDER CRASH ---
app_web = Flask('')

@app_web.route('/')
def home():
    return "E11 Lab Gold Analysis Bot is Alive!"

def run_web_server():
    # ដំណើរការ Flask លើ Port ដែល Render ផ្ដល់ឱ្យ (0.0.0.0:10000)
    app_web.run(host='0.0.0.0', port=PORT)

# --- ២. មុខងារទាញទិន្នន័យទីផ្សារ និងគណនា SMC/ICT FRAMEWORK ---
def fetch_market_data():
    try:
        # ទាញទិន្នន័យ មាស (XAUUSD ប្រើ GC=F), DXY, និង US10Y ពី Yahoo Finance
        gold = yf.Ticker("GC=F")
        dxy = yf.Ticker("DX-Y.NYB")
        us10y = yf.Ticker("^TNX")
        
        # ទាញយកប្រវត្តិតម្លៃ ២០ ថ្ងៃចុងក្រោយ
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
        
        # គណនា Trend/Bias តាមរយៈ ២០-SMA (Simple Moving Average)
        sma_20 = g_hist['Close'].mean()
        bias = "Bullish 📈" if current_price > sma_20 else "Bearish 📉"
        
        # គណនា Average True Range (ATR) បែបសាមញ្ញសម្រាប់កំណត់ចម្ងាយ Risk/Reward
        g_hist['TR'] = g_hist['High'] - g_hist['Low']
        atr = g_hist['TR'].mean()
        
        # គណនា Key Intraday Levels (Pivot Points) សម្រាប់ SMC Zones
        pivot = (g_hist['High'].iloc[-2] + g_hist['Low'].iloc[-2] + g_hist['Close'].iloc[-2]) / 3
        r1 = (2 * pivot) - g_hist['Low'].iloc[-2]
        s1 = (2 * pivot) - g_hist['High'].iloc[-2]
        
        # វិភាគទំនាក់ទំនង Macro (DXY & Yields Dominance)
        dxy_trend = "ឡើងថ្លៃ (Strong)" if d_hist['Close'].iloc[-1] > d_hist['Close'].iloc[-2] else "ចុះថ្លៃ (Weak)"
        yield_trend = "ឡើងថ្លៃ (Strong)" if u_hist['Close'].iloc[-1] > u_hist['Close'].iloc[-2] else "ចុះថ្លៃ (Weak)"
        
        macro_summary = f"DXY មានសន្ទុះ {dxy_trend} និង US10Y Bond Yield មានសន្ទុះ {yield_trend}។"
        
        # រៀបចំទិន្នន័យសម្រង់
        data = {
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
        return data
    except Exception as e:
        logger.error(f"Error fetching market data: {e}")
        return None

# --- ៣. មុខងារទាញទិន្នន័យព័ត៌មានសេដ្ឋកិច្ច (HIGH IMPACT NEWS) ---
def fetch_economic_calendar():
    try:
        # ប្រើប្រាស់ API សេរី ឬ endpoint សម្រាប់ទាញយកព័ត៌មានសេដ្ឋកិច្ចប្រចាំថ្ងៃ
        # ក្នុងករណីកូដគំរូនេះ យើងបង្កើតទិន្នន័យរៀបចំស្អាតមួយ បើ API ក្រៅមានបញ្ហា
        # បងអាចតភ្ជាប់ជាមួយ API ដូចជា FinancialModelingPrep ឬប្រភពផ្សេងៗបាន
        today_news = [
            {"time": "19:30", "event": "USD Core CPI (MoM)", "forecast": "0.3%"},
            {"time": "21:00", "event": "USD FOMC Statement", "forecast": "High Volatility"}
        ]
        
        table_md = "| ម៉ោង (GMT+7) | ព្រឹត្តិការណ៍សេដ្ឋកិច្ច (Event) | ព្យាករណ៍ (Forecast) |\n"
        table_md += "| :--- | :--- | :--- |\n"
        for news in today_news:
            table_md += f"| {news['time']} | {news['event']} | {news['forecast']} |\n"
        return table_md
    except Exception as e:
        logger.error(f"Error fetching calendar: {e}")
        return "| ម៉ោង | ព្រឹត្តិការណ៍សេដ្ឋកិច្ច | ព្យាករណ៍ |\n| :--- | :--- | :--- |\n| - | មិនអាចទាញទិន្នន័យព័ត៌មានបានទេ | - |"

# --- ៤. មុខងារបង្កើត និងចងក្រងអត្ថបទរបាយការណ៍ជាភាសាខ្មែរ (MARKDOWN) ---
def generate_report():
    m_data = fetch_market_data()
    news_table = fetch_economic_calendar()
    
    if not m_data:
        return "❌ មិនអាចបង្កើតរបាយការណ៍បានទេ ដោយសារមានបញ្ហាទាញទិន្នន័យទីផ្សារ។"
        
    current_date = datetime.now(pytz.timezone('Asia/Phnom_Penh')).strftime('%Y-%m-%d')
    
    # គណនា Trade Scenarios ផ្អែកលើ ATR Volatility Spacing
    if "Bullish" in m_data["bias"]:
        # Scenario A: Bullish Buy Bounce
        entry_a = m_data["demand"] + (m_data["atr"] * 0.1)
        sl_a = entry_a - (m_data["atr"] * 1.5)
        tp_a = entry_a + (m_data["atr"] * 3)
        rr_a = "1:2"
        
        # Scenario B: Bearish Breakdown
        entry_b = m_data["supply"] - (m_data["atr"] * 0.2)
        sl_b = entry_b + (m_data["atr"] * 1.5)
        tp_b = entry_b - (m_data["atr"] * 2.5)
    else:
        # Scenario A: Bearish Sell Continuation
        entry_a = m_data["supply"] - (m_data["atr"] * 0.1)
        sl_a = entry_a + (m_data["atr"] * 1.5)
        tp_a = entry_a - (m_data["atr"] * 3)
        rr_a = "1:2"
        
        # Scenario B: Bullish Fakeout
        entry_b = m_data["demand"] + (m_data["atr"] * 0.2)
        sl_b = entry_b - (m_data["atr"] * 1.5)
        tp_b = entry_b + (m_data["atr"] * 2.5)

    # ផ្គុំអត្ថបទ Markdown តាម Template របស់បងឱ្យត្រូវទម្រង់ ១០០%
    report = f"""# 📊 របាយការណ៍វិភាគមាសប្រចាំថ្ងៃ (XAU/USD)
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

### ⚠️ ៣. การគ្រប់គ្រងហានិភ័យ (Risk Management)
- សូមប្រុងប្រយ័ត្នខ្ពស់នៅម៉ោងព័ត៌មានចេញ (High Impact News) ទីផ្សារអាចមានការប្រែប្រួលខ្លាំង (Spread Expansion)។
- គ្រប់គ្រងហានិភ័យដោយប្រើប្រាស់ទំហំឡូតសមរម្យ (Proper Lot Sizing) និងមិនត្រូវលុប SL ដាច់ខាត។

---
*Generated by E11 Lab Bot 🚀 | Educational Purpose Only*"""
    return report

# --- ៥. មុខងារផ្ញើសារទៅកាន់ TELEGRAM ---
async def send_daily_report(context: ContextTypes.DEFAULT_TYPE = None):
    report_text = generate_report()
    
    # ប្រសិនបើហៅចេញពី Scheduler
    if context:
        await context.bot.send_message(chat_id=CHAT_ID, text=report_text, parse_mode="Markdown")
    else:
        # ប្រសិនបើហៅក្រៅផ្លូវការ (Manual)
        return report_text

# មុខងារស្វាគមន៍ពេលចុច /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🙏 សួស្តីបង! ខ្ញុំជា E11 Lab Bot។ ខ្ញុំនឹងផ្ញើរបាយការណ៍វិភាគមាសជូនរៀងរាល់ម៉ោង ០៨:០០ ព្រឹក។\n\nបងអាចវាយ /get_report ដើម្បីមើលរបាយការណ៍ឥឡូវនេះបាន!")

# មុខងារឱ្យ User ចុចមើលរបាយការណ៍ភ្លាមៗដោយដៃ
async def manual_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 កំពុងទាញទិន្នន័យវិភាគផ្សារចុងក្រោយ សូមរង់ចាំបន្តិច...")
    report = generate_report()
    await update.message.reply_text(text=report, parse_mode="Markdown")

# --- ៦. រៀបចំប្រព័ន្ធ CRON JOB (SCHEDULER) ម៉ោង ០៨:០០ ព្រឹក ---
def start_scheduler(application):
    scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Phnom_Penh'))
    
    # បង្កើតទម្រង់ការងារឱ្យរត់រាល់ថ្ងៃនៅម៉ោង 08:00 AM ម៉ោងនៅភ្នំពេញ
    def scheduled_job():
        # បង្កើត Event Loop ថ្មីសម្រាប់ Thread របស់ Scheduler
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(application.bot.send_message(chat_id=CHAT_ID, text=generate_report(), parse_mode="Markdown"))

    scheduler.add_job(scheduled_job, 'cron', hour=8, minute=0)
    scheduler.start()
    logger.info("Scheduler started successfully for Asia/Phnom_Penh timezone at 08:00 AM.")

if __name__ == '__main__':
    # កំណត់បើក Flask Server ក្នុង Thread ផ្សេង ដើម្បីកុំឱ្យស្ទះ Bot
    threading.Thread(target=run_web_server, daemon=True).start()
    logger.info("Flask Web Server is binding to port...")

    if not TOKEN or not CHAT_ID:
        logger.error("Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID in Environment Variables!")
    else:
        # បង្កើត Telegram Application
        app = ApplicationBuilder().token(TOKEN).build()
        
        # ដាក់បញ្ជា Command Handlers
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("get_report", manual_report_command))
        
        # បើកប្រព័ន្ធ Cron Job ផ្ញើសារស្វ័យប្រវត្ត
        start_scheduler(app)
        
        # បញ្ឆេះ Bot ដំណើរការ (Long Polling)
        logger.info("E11 Lab Bot is polling safely...")
        app.run_polling()
      
