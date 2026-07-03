# 📈 SPRZones Stock Scanner - EMA 200 Breakout

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Auto--Scan-brightgreen)](https://github.com/features/actions)

A fully automated stock scanning system that scans **Nifty 500** stocks across **7 timeframes** to identify **200 EMA breakouts** with **bullish candlestick patterns** and **strong fundamentals**. Generates a **PDF report** with charts and emails it daily.

---

## 🚀 Features

| Feature | Description |
| :--- | :--- |
| **📊 Universe** | Scans **Nifty 500** stocks (auto-fetched from NSE) |
| **⏱️ 7 Timeframes** | 15m, 30m, 1H, 4H, Daily, Weekly, Monthly |
| **📈 Technical Filters** | 200 EMA Crossover + Bullish Patterns (Engulfing, Hammer, Dragonfly Doji, Morning Star) |
| **💪 Fundamental Scoring** | PE < 30, ROE > 15%, Debt/Equity < 1.5, Profit Margin > 10%, Revenue Growth > 10% (Score out of 5) |
| **🧩 4-Quadrant Analysis** | Categorizes stocks into Strong Buy, Tech Watch, Funda Watch, and Avoid |
| **📄 PDF Report** | Generates detailed charts for each stock with marked EMA and patterns |
| **📧 Email Delivery** | Sends the PDF report directly to your inbox |
| **⏰ Auto-Scan** | Runs automatically Monday-Friday at 4:00 PM IST via GitHub Actions |

---

## 🧩 How It Works

1. **Fetch Stock List** → Nifty 500 symbols from NSE official website.
2. **Multi-Timeframe Scan** → For each stock, fetches 15m and Daily data, resamples to create 7 timeframes.
3. **Technical Analysis** → Checks for 200 EMA crossover + bullish candlestick patterns on ANY timeframe.
4. **Fundamental Scoring** → Calculates a score (0-5) based on PE, ROE, Debt, Margin, Growth.
5. **Quadrant Classification**:
   - 🔥 **Strong Buy** (Pattern + Funda Score >= 3)
   - 📈 **Tech Watch** (Pattern + Funda Score < 3)
   - 💪 **Funda Watch** (No Pattern + Funda Score >= 3)
   - ⛔ **Avoid** (No Pattern + Funda Score < 3)
6. **PDF Generation** → Creates charts for each qualifying stock (7 timeframes per stock).
7. **Email Delivery** → Sends the PDF report as an email attachment.

---

## 🛠️ Setup & Configuration

### 1. Clone the Repository
```bash
git clone https://github.com/SPRZonesBOT/SPRZones-stock-scanner-EMA200.git
cd SPRZones-stock-scanner-EMA200


2. Install Dependencies
bash
pip install -r requirements.txt
3. Set Up Gmail App Password
Go to your Google Account → Security → 2-Step Verification (Enable it).

Go to App Passwords → Select Mail & Other (Python Script).

Copy the 16-digit password.

4. Add GitHub Secrets
Go to your repository Settings → Secrets and variables → Actions and add:

Secret Name	Value
EMAIL_SENDER	Your Gmail address (e.g., you@gmail.com)
EMAIL_PASSWORD	The 16-digit App Password
EMAIL_RECIPIENT	Email where you want to receive the report
📂 Project Structure
text
SPRZones-stock-scanner-EMA200/
├── .github/
│   └── workflows/
│       └── scan.yml          # GitHub Actions cron job
├── scanner.py                # Main scanning & reporting script
├── requirements.txt          # Python dependencies
└── README.md                 # This file
📦 Dependencies
yfinance → Fetch stock data

pandas → Data manipulation

pandas_ta → Technical indicators (EMA, Candlestick patterns)

matplotlib & mplfinance → Chart generation

smtplib → Email delivery

⏰ Automation (GitHub Actions)
The scanner runs automatically via a cron job defined in .github/workflows/scan.yml:

yaml
on:
  schedule:
    - cron: '30 10 * * 1-5'   # Monday-Friday at 4:00 PM IST
  workflow_dispatch:           # Manual trigger available
You can also manually trigger it from the Actions tab.

📊 Sample Output (Email + PDF)
Email Body:
text
Hi,

✅ Scan complete with 7 Timeframes (15m, 30m, 1H, 4H, Daily, Weekly, Monthly)!

🔥 1. With Pattern + With Funda (STRONG BUY): 3 stocks
    - RELIANCE.NS (Reliance Industries Ltd)
    - TCS.NS (Tata Consultancy Services Ltd)
    - HDFCBANK.NS (HDFC Bank Ltd)

📈 2. With Pattern + No Funda (TECH WATCH): 2 stocks
📊 Full PDF report attached with 7 timeframe charts for each stock.
PDF Report:
Summary Page: Quadrant-wise list of stocks.

Per Stock: 7 charts (15m, 30m, 1H, 4H, Daily, Weekly, Monthly) with 200 EMA (orange line), crossover marked (cyan line), and pattern label (yellow arrow).

Info Page: Fundamentals score, PE, ROE, Debt/Equity, Margin, Growth, and timeframe-wise signal breakdown.

🧪 Local Testing (Optional)
To test the scanner locally:

bash
# Install dependencies
pip install -r requirements.txt

# Run the scanner (ensure EMAIL_* env vars are set)
python scanner.py
⚠️ Disclaimer
This tool is for educational and informational purposes only.

Past performance does not guarantee future results.

Always do your own research (DYOR) before making any investment decisions.

The author is not responsible for any financial losses incurred using this tool.

🤝 Contributing
Pull requests and suggestions are welcome! Feel free to open an issue for bugs or feature requests.

📜 License
This project is licensed under the MIT License.

📬 Contact
For queries or feedback, reach out to: sprzones@gmail.com

Happy Scanning! 🚀📈

text

---

## 🚀 Ab Isko Kaise Use Karein?

1. Apne repo mein **`README.md`** open karo.
2. **Edit** karo.
3. Upar wala poora content **copy-paste** karo.
4. **Commit** karo.

Ab aapka README professional aur detailed ho gaya hai! 🔥
