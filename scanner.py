import yfinance as yf
import pandas as pd
import pandas_ta as ta
import mplfinance as mpf
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import os
import time
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import warnings
warnings.filterwarnings('ignore')

# ======================================================
# 🔥 CONFIG - GitHub Secrets se aayengi
# ======================================================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT")

# ======================================================
# 📥 NIFTY 500 STOCKS (Auto-Fetch from NSE)
# ======================================================
def get_nifty500_tickers():
    fallback_list = [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
        "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
        "BAJFINANCE.NS", "WIPRO.NS", "HCLTECH.NS", "ASIANPAINT.NS", "AXISBANK.NS",
        "LT.NS", "MARUTI.NS", "TITAN.NS", "SUNPHARMA.NS", "ULTRACEMCO.NS"
    ]
    try:
        print("📥 Fetching Nifty 500 list from NSE...")
        url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
        df = pd.read_csv(url)
        symbols = df['Symbol'].tolist()
        nifty500 = [s + ".NS" for s in symbols]
        print(f"✅ Fetched {len(nifty500)} stocks.")
        return nifty500
    except Exception as e:
        print(f"⚠️ Fetch failed: {e}. Using fallback.")
        return fallback_list

STOCKS = get_nifty500_tickers()
print(f"📊 Total stocks to scan: {len(STOCKS)}")

# ======================================================
# 📊 FUNDAMENTALS SCORING
# ======================================================
def get_fundamentals(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        pe = info.get('trailingPE', 100)
        roe = info.get('returnOnEquity', 0)
        debt = info.get('debtToEquity', 999)
        margin = info.get('profitMargins', 0)
        growth = info.get('revenueGrowth', 0)
        if pe is None or roe is None or pe <= 0:
            return None
        score = 0
        if pe < 30: score += 1
        if roe > 0.15: score += 1
        if debt < 1.5: score += 1
        if margin > 0.10: score += 1
        if growth > 0.10: score += 1
        return {'score': score, 'pe': pe, 'roe': roe, 'debt': debt, 'margin': margin, 'growth': growth}
    except:
        return None

# ======================================================
# 📈 TECHNICAL ANALYSIS (EMA Cross + Patterns)
# ======================================================
def analyze_df(df, tf_name):
    if len(df) < 50:
        return {'ema': False, 'pattern': False, 'signal': False, 'pattern_name': ''}
    
    df = df.copy()
    df['EMA_200'] = ta.ema(df['Close'], length=200)
    if df['EMA_200'].isna().all():
        return {'ema': False, 'pattern': False, 'signal': False, 'pattern_name': ''}
    
    # Crossover Check
    prev_c = df['Close'].iloc[-2]
    curr_c = df['Close'].iloc[-1]
    prev_e = df['EMA_200'].iloc[-2]
    curr_e = df['EMA_200'].iloc[-1]
    ema_cross = (prev_c < prev_e) and (curr_c > curr_e)
    
    # 🕯️ Bullish Pattern Detection
    pattern_name = ""
    pattern_detected = False
    
    # 1. Bullish Engulfing
    engulf = ta.cdl_engulfing(df['Open'], df['High'], df['Low'], df['Close'])
    if engulf is not None and not engulf.empty and len(engulf) > 0 and engulf.iloc[-1] > 0:
        pattern_detected = True
        pattern_name = "Bullish Engulfing"
    
    # 2. Hammer
    if not pattern_detected:
        hammer = ta.cdl_hammer(df['Open'], df['High'], df['Low'], df['Close'])
        if hammer is not None and not hammer.empty and len(hammer) > 0 and hammer.iloc[-1] > 0:
            pattern_detected = True
            pattern_name = "Hammer"
    
    # 3. Dragonfly Doji
    if not pattern_detected:
        dragon = ta.cdl_dragonfly_doji(df['Open'], df['High'], df['Low'], df['Close'])
        if dragon is not None and not dragon.empty and len(dragon) > 0 and dragon.iloc[-1] > 0:
            pattern_detected = True
            pattern_name = "Dragonfly Doji"
    
    # 4. Morning Star
    if not pattern_detected:
        ms = ta.cdl_morning_star(df['Open'], df['High'], df['Low'], df['Close'])
        if ms is not None and not ms.empty and len(ms) > 0 and ms.iloc[-1] > 0:
            pattern_detected = True
            pattern_name = "Morning Star"
    
    return {
        'ema': ema_cross,
        'pattern': pattern_detected,
        'signal': ema_cross and pattern_detected,
        'pattern_name': pattern_name
    }

# ======================================================
# 🔍 SCAN SINGLE STOCK (OPTIMIZED - 2 API calls)
# ======================================================
def scan_stock(ticker):
    try:
        # 🔥 OPTIMIZATION 1: Fetch 15min data (period='30d' enough for EMA200)
        df_15m = yf.download(ticker, period='30d', interval='15m', progress=False, auto_adjust=True)
        if df_15m.empty or len(df_15m) < 100:
            return None
        
        # Resample 15min -> 30min
        df_30m = df_15m.resample('30min').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'
        }).dropna()
        
        # Resample 15min -> 1H
        df_1h = df_15m.resample('1h').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'
        }).dropna()
        
        # Resample 1H -> 4H
        df_4h = df_1h.resample('4h').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'
        }).dropna()
        
        # 🔥 OPTIMIZATION 2: Fetch Daily data (for Daily, Weekly, Monthly)
        df_d = yf.download(ticker, period='60d', interval='1d', progress=False, auto_adjust=True)
        if df_d.empty or len(df_d) < 50:
            return None
        
        # Resample Daily -> Weekly
        df_w = df_d.resample('W').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'
        }).dropna()
        
        # Resample Daily -> Monthly
        df_m = df_d.resample('ME').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'
        }).dropna()
        
        # Analyze all timeframes
        r_15m = analyze_df(df_15m, '15min')
        r_30m = analyze_df(df_30m, '30min')
        r_1h = analyze_df(df_1h, '1H')
        r_4h = analyze_df(df_4h, '4H')
        r_d = analyze_df(df_d, 'Daily')
        r_w = analyze_df(df_w, 'Weekly')
        r_m = analyze_df(df_m, 'Monthly')
        
        # Fundamentals
        funda = get_fundamentals(ticker)
        if funda is None:
            return None
        
        # Final Decision - any timeframe signal
        any_signal = (r_15m['signal'] or r_30m['signal'] or r_1h['signal'] or 
                     r_4h['signal'] or r_d['signal'] or r_w['signal'] or r_m['signal'])
        buy_decision = any_signal and (funda['score'] >= 3)
        
        try:
            name = yf.Ticker(ticker).info.get('longName', ticker)[:25]
        except:
            name = ticker
        
        return {
            'ticker': ticker,
            'name': name,
            'df_15m': df_15m,
            'df_30m': df_30m,
            'df_1h': df_1h,
            'df_4h': df_4h,
            'df_d': df_d,
            'df_w': df_w,
            'df_m': df_m,
            'r_15m': r_15m,
            'r_30m': r_30m,
            'r_1h': r_1h,
            'r_4h': r_4h,
            'r_d': r_d,
            'r_w': r_w,
            'r_m': r_m,
            'funda': funda,
            'buy': buy_decision
        }
    except Exception as e:
        return None

# ======================================================
# 📊 CHART + PDF GENERATOR (7 TIMEFRAMES)
# ======================================================
def create_stock_charts(result):
    ticker = result['ticker']
    name = result['name']
    funda = result['funda']
    
    # All timeframes data and results
    timeframes = [
        ('15min', result['df_15m'], result['r_15m']),
        ('30min', result['df_30m'], result['r_30m']),
        ('1H', result['df_1h'], result['r_1h']),
        ('4H', result['df_4h'], result['r_4h']),
        ('Daily', result['df_d'], result['r_d']),
        ('Weekly', result['df_w'], result['r_w']),
        ('Monthly', result['df_m'], result['r_m']),
    ]
    
    charts = []
    
    def plot_tf(df, tf_name, cross_data, pattern_name):
        if df is None or df.empty or len(df) < 10:
            return None
        
        df = df.tail(90).copy()
        df['EMA_200'] = ta.ema(df['Close'], length=200)
        
        mc = mpf.make_marketcolors(up='#00ff00', down='#ff0000', wick='inherit')
        s = mpf.make_mpf_style(marketcolors=mc, gridstyle=':', y_on_right=True)
        ap_ema = mpf.make_addplot(df['EMA_200'], color='orange', width=1.5)
        
        fig, axes = mpf.plot(df, type='candle', style=s, addplot=ap_ema,
                             volume=False, figsize=(10, 6), returnfig=True,
                             tight_layout=True,
                             title=f"{ticker} - {name[:20]} ({tf_name})\nPattern: {pattern_name if pattern_name else 'None'}")
        
        ax = axes[0]
        if pattern_name and cross_data.get('signal', False):
            last_x = len(df) - 1
            last_high = df['High'].iloc[-1]
            ax.annotate(f'🚀 {pattern_name}', xy=(last_x, last_high),
                        xytext=(last_x - 15, last_high * 1.02),
                        arrowprops=dict(arrowstyle='->', color='yellow', lw=1.5),
                        color='yellow', fontsize=10, weight='bold',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7))
        if cross_data.get('signal', False):
            ax.axvline(x=len(df) - 1, color='cyan', linestyle='--', alpha=0.6, linewidth=2, label='Crossover')
            ax.legend()
        return fig
    
    # Generate charts for all timeframes
    for tf_name, df, r in timeframes:
        fig = plot_tf(df, tf_name, r, r.get('pattern_name', ''))
        if fig:
            charts.append(fig)
    
    # 📋 Fundamental Info Text
    info_text = f"""
    📊 {ticker} - {name}
    ========================================
    📈 Fundamental Score: {funda['score']}/5
    PE: {funda['pe']:.2f}
    ROE: {funda['roe']*100:.2f}%
    Debt/Equity: {funda['debt']:.2f}
    Profit Margin: {funda['margin']*100:.2f}%
    Revenue Growth: {funda['growth']*100:.2f}%
    
    📊 Signal Summary:
    15min:  {'✅' if result['r_15m']['signal'] else '❌'} ({result['r_15m']['pattern_name'] or 'No Pattern'})
    30min:  {'✅' if result['r_30m']['signal'] else '❌'} ({result['r_30m']['pattern_name'] or 'No Pattern'})
    1H:     {'✅' if result['r_1h']['signal'] else '❌'} ({result['r_1h']['pattern_name'] or 'No Pattern'})
    4H:     {'✅' if result['r_4h']['signal'] else '❌'} ({result['r_4h']['pattern_name'] or 'No Pattern'})
    Daily:  {'✅' if result['r_d']['signal'] else '❌'} ({result['r_d']['pattern_name'] or 'No Pattern'})
    Weekly: {'✅' if result['r_w']['signal'] else '❌'} ({result['r_w']['pattern_name'] or 'No Pattern'})
    Monthly: {'✅' if result['r_m']['signal'] else '❌'} ({result['r_m']['pattern_name'] or 'No Pattern'})
    """
    
    return charts + [info_text]

# ======================================================
# 📧 EMAIL SENDER
# ======================================================
def send_email_with_pdf(pdf_path, subject, body):
    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT]):
        print("❌ Email config missing. Set GitHub Secrets.")
        return False
    
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECIPIENT
    msg['Subject'] = subject
    
    msg.attach(MIMEText(body, 'plain'))
    
    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path, 'rb') as f:
            part = MIMEBase('application', 'pdf')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(pdf_path)}')
            msg.attach(part)
    
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())
        server.quit()
        print("✅ Email sent!")
        return True
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False

# ======================================================
# 🚀 MAIN FUNCTION
# ======================================================
def main():
    print(f"🔄 Scanning {len(STOCKS)} stocks (7 timeframes: 15m, 30m, 1H, 4H, Daily, Weekly, Monthly)...")
    print("⏱️ Estimated time: 30-45 minutes")
    
    buy_stocks = []
    total = len(STOCKS)
    failed = 0
    
    for i, t in enumerate(STOCKS):
        if i % 20 == 0:
            print(f"  Progress: {i}/{total} ({i/total*100:.1f}%) - Found {len(buy_stocks)} signals so far")
        
        try:
            res = scan_stock(t)
            if res and res['buy']:
                buy_stocks.append(res)
                print(f"  🚀 BUY: {t}")
            time.sleep(0.5)
        except Exception as e:
            failed += 1
            if failed % 10 == 0:
                print(f"  ⚠️ {failed} stocks failed so far")
            time.sleep(1)
    
    print(f"✅ Scan complete! Found {len(buy_stocks)} buy signals.")
    print(f"⚠️ {failed} stocks failed to scan.")
    
    if not buy_stocks:
        send_email_with_pdf(
            pdf_path=None,
            subject=f"📊 SPRZ Scan - {datetime.now().strftime('%d-%b-%Y')}",
            body=f"No buy signals found today.\nScanned {len(STOCKS)} stocks.\nFailed: {failed}"
        )
        print("No signals found. Email sent without PDF.")
        return
    
    # 📄 PDF Generate
    pdf_path = f"SPRZ_Signals_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    with PdfPages(pdf_path) as pdf:
        for stock in buy_stocks:
            print(f"  Generating charts for {stock['ticker']}...")
            chart_data = create_stock_charts(stock)
            
            # Charts (first 7 elements are figures)
            for i in range(len(chart_data) - 1):
                if chart_data[i]:
                    pdf.savefig(chart_data[i])
                    plt.close(chart_data[i])
            
            # Info page (last element)
            fig_info, ax_info = plt.subplots(figsize=(12, 8))
            ax_info.axis('off')
            ax_info.text(0.05, 0.95, chart_data[-1], fontsize=11, family='monospace', verticalalignment='top')
            pdf.savefig(fig_info)
            plt.close(fig_info)
    
    print(f"✅ PDF generated: {pdf_path}")
    
    # 📧 Email
    subject = f"🚀 SPRZ Scan - {len(buy_stocks)} Buy Signals! {datetime.now().strftime('%d-%b-%Y')}"
    body = f"Hi,\n\n✅ {len(buy_stocks)} stocks matched all criteria across 7 timeframes.\n\nSignals:\n" + "\n".join([f"- {s['ticker']} ({s['name']})" for s in buy_stocks])
    
    send_email_with_pdf(pdf_path, subject, body)

if __name__ == "__main__":
    main()
