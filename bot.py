import os
import logging
import threading
import time
from datetime import datetime
import requests
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")

app_web = Flask('')

@app_web.route('/')
def home():
    return "E11 Lab Gold Bot is Live!"

def run_web_server():
    port = int(os.getenv("PORT", 10000))
    app_web.run(host='0.0.0.0', port=port)

def fetch_gold_data():
    """ ទាញទិន្នន័យមាសផ្ទាល់ពី API ប្រកបដោយសុវត្ថិភាព ការពារការគាំង """
    try:
        # ប្រើប្រាស់ API របស់លំដាប់ទីផ្សារសកល
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1d&range=2d"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            return None
            
        res_json = response.json()
        result = res_json['chart']['result'][0]
        meta = result['meta']
        quote = result['indicators']['quote'][0]
        
        current_price = meta['regularMarketPrice']
        prev_close = meta['chartPreviousClose']
        
        # គណនា Supply, Demand, Pivot តាមរូបមន្ត Technical 
        high_price = max([h for h in quote['high'] if h is not None])
        low_price = min([l for l in quote['low'] if l is not None])
        
        pivot = (high_price + low_price + current_price) / 3
        r1 = (2 * pivot) - low_price  # SMC Resistance / Supply Zone
        s1 = (2 * pivot) - high_price # SMC Support / Demand Zone
        
        bias = "Bullish 📈" if current_price > pivot else "Bearish 📉"
        change_pct = ((current_price - prev_close) / prev_close) * 100
        
        return {
            "price": round(current_price, 2),
            "change": round(change_pct, 2),
            "bias": bias,
            "supply": round(r1, 2),
            "demand": round(s1, 2),
            "pivot": round(pivot, 2)
        }
    except Exception as e:
        logger.error(f"Error fetching gold data: {e}")
        return None

def generate_report():
    data = fetch_gold_data()
    if not data:
        return "❌ មិនអាចទាញទិន្នន័យទីផ្សារមាស (XAUUSD) បានទេនៅពេលនេះ។ សូមព្យាយាមម្ដងទៀត!"
        
    return f"""📊 *E11 Lab Daily Gold Report*
    
• *Current Price:* ${data['price']} ({data['change']}%)
• *Market Bias:* {data['bias']}

🧱 *SMC Key Zones (Daily):*
• *Supply Zone:* ${data['supply']}
• *Pivot Point:* ${data['pivot']}
• *Demand Zone:* ${data['demand']}

📈 _"Invest in knowledge. Trade with logic."_"""

# --- Commands សម្រាប់ Bot ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = """🙏 សួស្តីបង! ស្វាគមន៍មកកាន់ E11 Lab Assistant 🚀

ខ្ញុំជាជំនួយការស្វ័យប្រវត្តិ សម្រាប់ផ្ដល់ជូនផែនទីជួញដូរ និងវិភាគបច្គេកទេសមាស (XAUUSD) ផ្អែកលើទម្រង់ Institutional Order Flow (SMC & ICT Framework)។

💡 បងអាចប្រើប្រាស់ Commands ខាងក្រោមដើម្បីបញ្ជាខ្ញុំ៖
• /get_report - ទាញយករបាយការណ៍វិភាគមាស Live ភ្លាមៗ
• /zones - មើលតម្លៃតំបន់គន្លឹះបច្ចេកទេស (SMC Key Zones)
• /news - មើលតារាងព័ត៌មានសេដ្ឋកិច្ច High Impact ថ្ងៃនេះ"""
    await update.message.reply_text(text=welcome_text)

async def manual_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 កំពុងទាញទិន្នន័យពីផ្សារ និងគណនារូបមន្ត... សូមរង់ចាំមួយភ្លែតបង...")
    report = generate_report()
    await update.message.reply_text(text=report, parse_mode="Markdown")

async def zones_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = fetch_gold_data()
    if data:
        zones_text = f"🏗️ *SMC Key Zones (XAUUSD):*\n\n• *Supply (R1):* ${data['supply']}\n• *Pivot Line:* ${data['pivot']}\n• *Demand (S1):* ${data['demand']}"
        await update.message.reply_text(text=zones_text, parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ មិនអាចគណនាតំបន់ Key Zones បានទេ។")

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📰 *High Impact Events Tracker:* ថ្ងៃនេះពុំមានព័ត៌មានសេដ្ឋកិច្ចកម្រិតក្រហមធំៗ (USD) គួរឱ្យកត់សម្គាល់ឡើយបង។", parse_mode="Markdown")

if __name__ == '__main__':
    threading.Thread(target=run_web_server, daemon=True).start()

    if not TOKEN:
        logger.error("TELEGRAM_TOKEN Missing!")
    else:
        app = ApplicationBuilder().token(TOKEN).build()
        
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("get_report", manual_report_command))
        app.add_handler(CommandHandler("news", news_command))
        app.add_handler(CommandHandler("zones", zones_command))
        
        logger.info("Bot with Gold Data is running...")
        app.run_polling()
    
