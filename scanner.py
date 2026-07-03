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
# 🔥 CONFIG
# ======================================================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT")

# ======================================================
# 📥 NIFTY 500 FETCH
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
# 📈 TECHNICAL ANALYSIS
# ======================================================
def analyze_df(df):
    if len(df) < 50:
        return {'ema': False, 'pattern': False, 'signal': False, 'pattern_name': ''}
    
    # 🔥 Flatten MultiIndex
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ['_'.join(col).strip() for col in df.columns.values]
        df.columns = [col.split('_')[0] for col in df.columns]
    
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
    
    engulf = ta.cdl_engulfing(df['Open'], df['High'], df['Low'], df['Close'])
    if engulf is not None and not engulf.empty and len(engulf) > 0 and engulf.iloc[-1] > 0:
        pattern_detected = True; pattern_name = "Bullish Engulfing"
    
    if not pattern_detected:
        hammer = ta.cdl_hammer(df['Open'], df['High'], df['Low'], df['Close'])
        if hammer is not None and not hammer.empty and len(hammer) > 0 and hammer.iloc[-1] > 0:
            pattern_detected = True; pattern_name = "Hammer"
    
    if not pattern_detected:
        dragon = ta.cdl_dragonfly_doji(df['Open'], df['High'], df['Low'], df['Close'])
        if dragon is not None and not dragon.empty and len(dragon) > 0 and dragon.iloc[-1] > 0:
            pattern_detected = True; pattern_name = "Dragonfly Doji"
    
    if not pattern_detected:
        ms = ta.cdl_morning_star(df['Open'], df['High'], df['Low'], df['Close'])
        if ms is not None and not ms.empty and len(ms) > 0 and ms.iloc[-1] > 0:
            pattern_detected = True; pattern_name = "Morning Star"
    
    return {
        'ema': ema_cross,
        'pattern': pattern_detected,
        'signal': ema_cross and pattern_detected,  # Strict Tech
        'pattern_name': pattern_name
    }

# ======================================================
# 🔍 SCAN SINGLE STOCK (4 QUADRANTS)
# ======================================================
def scan_stock(ticker):
    try:
        # 1H Data
        df1 = yf.download(ticker, period='60d', interval='1h', progress=False, auto_adjust=True)
        if df1.empty or len(df1) < 200:
            return None
        if isinstance(df1.columns, pd.MultiIndex):
            df1.columns = ['_'.join(col).strip() for col in df1.columns.values]
            df1.columns = [col.split('_')[0] for col in df1.columns]
        
        r1 = analyze_df(df1)
        
        # 4H Data (Resample)
        df4 = df1.resample('4h').agg({'Open':'first','High':'max','Low':'min','Close':'last'}).dropna()
        r4 = analyze_df(df4)
        
        # Daily Data
        dfd = yf.download(ticker, period='60d', interval='1d', progress=False, auto_adjust=True)
        if dfd.empty or len(dfd) < 200:
            dfd = df1.resample('1d').agg({'Open':'first','High':'max','Low':'min','Close':'last'}).dropna()
        if isinstance(dfd.columns, pd.MultiIndex):
            dfd.columns = ['_'.join(col).strip() for col in dfd.columns.values]
            dfd.columns = [col.split('_')[0] for col in dfd.columns]
        rd = analyze_df(dfd)
        
        # Fundamentals
        funda = get_fundamentals(ticker)
        if funda is None:
            return None
        
        # 🔥 🔥 🔥 4 QUADRANT LOGIC 🔥 🔥 🔥
        has_ema = r1['ema'] or r4['ema'] or rd['ema']
        has_pattern = r1['pattern'] or r4['pattern'] or rd['pattern']
        funda_ok = funda['score'] >= 3
        
        # Quadrants
        cat_pattern_funda = has_ema and has_pattern and funda_ok          # 1️⃣ Best: Pattern + Funda
        cat_pattern_nofunda = has_ema and has_pattern and not funda_ok    # 2️⃣ Tech Strong, Funda Weak
        cat_nopattern_funda = has_ema and not has_pattern and funda_ok    # 3️⃣ Pure EMA, Funda Strong
        cat_nopattern_nofunda = has_ema and not has_pattern and not funda_ok # 4️⃣ Pure EMA, No Funda
        
        # Total Tech Signal (Strict)
        tech_strict = has_ema and has_pattern
        # Total Pure EMA (Loose)
        tech_loose = has_ema
        
        try:
            name = yf.Ticker(ticker).info.get('longName', ticker)[:25]
        except:
            name = ticker
        
        return {
            'ticker': ticker, 'name': name,
            'df_1h': df1, 'df_4h': df4, 'df_d': dfd,
            'r1': r1, 'r4': r4, 'rd': rd,
            'funda': funda,
            # Raw signals
            'has_ema': has_ema,
            'has_pattern': has_pattern,
            'funda_ok': funda_ok,
            # 4 Quadrants
            'cat_pattern_funda': cat_pattern_funda,
            'cat_pattern_nofunda': cat_pattern_nofunda,
            'cat_nopattern_funda': cat_nopattern_funda,
            'cat_nopattern_nofunda': cat_nopattern_nofunda,
            # Aggregated
            'tech_strict': tech_strict,
            'tech_loose': tech_loose,
            'final_recommendation': '🔥 STRONG BUY' if cat_pattern_funda else 
                                    ('📈 TECH WATCH' if cat_pattern_nofunda else 
                                     ('💪 FUNDA WATCH' if cat_nopattern_funda else '⛔ AVOID'))
        }
    except Exception as e:
        return None

# ======================================================
# 📧 EMAIL SENDER
# ======================================================
def send_email_with_pdf(pdf_path, subject, body):
    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT]):
        print("❌ Email config missing. Set GitHub Secrets.")
        return False
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER; msg['To'] = EMAIL_RECIPIENT; msg['Subject'] = subject
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
# 📊 CHART + PDF GENERATOR
# ======================================================
def create_stock_charts(result):
    ticker = result['ticker']; name = result['name']
    r1, r4, rd = result['r1'], result['r4'], result['rd']
    df1, df4, dfd = result['df_1h'], result['df_4h'], result['df_d']
    funda = result['funda']
    rec = result['final_recommendation']
    
    df1 = df1.tail(90); df4 = df4.tail(90); dfd = dfd.tail(90)
    charts = []
    
    def plot_tf(df, tf_name, cross_data, pattern_name):
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = ['_'.join(col).strip() for col in df.columns.values]
            df.columns = [col.split('_')[0] for col in df.columns]
        
        df['EMA_200'] = ta.ema(df['Close'], length=200)
        mc = mpf.make_marketcolors(up='#00ff00', down='#ff0000', wick='inherit')
        s = mpf.make_mpf_style(marketcolors=mc, gridstyle=':', y_on_right=True)
        ap_ema = mpf.make_addplot(df['EMA_200'], color='orange', width=1.5)
        
        title = f"{ticker} - {name[:20]} ({tf_name}) | {rec}\nPattern: {pattern_name if pattern_name else 'None'}"
        
        fig, axes = mpf.plot(df, type='candle', style=s, addplot=ap_ema,
                             volume=False, figsize=(10, 6), returnfig=True,
                             tight_layout=True, title=title)
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
    
    fig1 = plot_tf(df1, '1 Hour', r1, r1.get('pattern_name', ''))
    fig2 = plot_tf(df4, '4 Hour', r4, r4.get('pattern_name', ''))
    fig3 = plot_tf(dfd, 'Daily', rd, rd.get('pattern_name', ''))
    
    info_text = f"""
    📊 {ticker} - {name}
    ========================================
    🏷️ Recommendation: {rec}
    ----------------------------------------
    📈 Fundamentals Score: {funda['score']}/5
    PE: {funda['pe']:.2f} | ROE: {funda['roe']*100:.2f}%
    Debt/Equity: {funda['debt']:.2f} | Margin: {funda['margin']*100:.2f}%
    Revenue Growth: {funda['growth']*100:.2f}%
    ----------------------------------------
    🔍 Timeframe Breakdown:
    1H:  ✅ EMA: {r1['ema']} | Pattern: {r1['pattern']} ({r1['pattern_name'] or 'None'})
    4H:  ✅ EMA: {r4['ema']} | Pattern: {r4['pattern']} ({r4['pattern_name'] or 'None'})
    Daily: ✅ EMA: {rd['ema']} | Pattern: {rd['pattern']} ({rd['pattern_name'] or 'None'})
    """
    return [fig1, fig2, fig3, info_text]

# ======================================================
# 🚀 MAIN
# ======================================================
def main():
    print(f"🔄 Scanning {len(STOCKS)} stocks...")
    print("⏱️ Estimated time: 30-45 minutes")
    
    all_results = []
    total = len(STOCKS)
    
    for i, t in enumerate(STOCKS):
        if i % 20 == 0:
            print(f"  Progress: {i}/{total} ({i/total*100:.1f}%)")
        res = scan_stock(t)
        if res:
            all_results.append(res)
        time.sleep(0.5)
    
    print(f"✅ Scan complete! Total processed: {len(all_results)}")
    
    # 🔥 FILTER 4 QUADRANTS
    cat1 = [r for r in all_results if r['cat_pattern_funda']]       # With Pattern, With Funda
    cat2 = [r for r in all_results if r['cat_pattern_nofunda']]     # With Pattern, No Funda
    cat3 = [r for r in all_results if r['cat_nopattern_funda']]     # No Pattern, With Funda
    cat4 = [r for r in all_results if r['cat_nopattern_nofunda']]   # No Pattern, No Funda
    
    print("\n" + "="*60)
    print("📊 QUADRANT ANALYSIS RESULTS")
    print("="*60)
    print(f"🔥 1. With Pattern + With Funda (STRONG BUY): {len(cat1)} stocks")
    print(f"📈 2. With Pattern + No Funda (TECH WATCH): {len(cat2)} stocks")
    print(f"💪 3. No Pattern + With Funda (FUNDA WATCH): {len(cat3)} stocks")
    print(f"⛔ 4. No Pattern + No Funda (AVOID): {len(cat4)} stocks")
    
    # If no stocks in Cat1, send simpler email
    if not cat1 and not cat2 and not cat3:
        send_email_with_pdf(
            pdf_path=None,
            subject=f"📊 SPRZ Scan - {datetime.now().strftime('%d-%b-%Y')}",
            body=f"No significant signals found today.\nScanned {len(STOCKS)} stocks.\n\nDetailed counts:\nCat1 (Strong Buy): 0\nCat2 (Tech Watch): {len(cat2)}\nCat3 (Funda Watch): {len(cat3)}\nCat4 (Avoid): {len(cat4)}"
        )
        print("No significant signals. Email sent without PDF.")
        return
    
    # 📄 PDF Generate - Include Cat1, Cat2, Cat3 (Cat4 avoid karo)
    stocks_to_show = cat1 + cat2 + cat3
    pdf_path = f"SPRZ_Signals_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    with PdfPages(pdf_path) as pdf:
        # 📋 Summary Page
        fig_summary, ax_summary = plt.subplots(figsize=(14, 10))
        ax_summary.axis('off')
        summary_text = f"""
        📊 SPRZ SCANNER REPORT - {datetime.now().strftime('%d-%b-%Y')}
        ============================================================
        🔥 CAT 1: With Pattern + With Funda (STRONG BUY) → {len(cat1)} stocks
        {chr(10).join([f"     - {s['ticker']} ({s['name']})" for s in cat1]) if cat1 else "     (None)"}
        
        📈 CAT 2: With Pattern + No Funda (TECH WATCH) → {len(cat2)} stocks
        {chr(10).join([f"     - {s['ticker']} ({s['name']})" for s in cat2]) if cat2 else "     (None)"}
        
        💪 CAT 3: No Pattern + With Funda (FUNDA WATCH) → {len(cat3)} stocks
        {chr(10).join([f"     - {s['ticker']} ({s['name']})" for s in cat3]) if cat3 else "     (None)"}
        
        ⛔ CAT 4: No Pattern + No Funda (AVOID) → {len(cat4)} stocks (Not shown)
        ============================================================
        📈 Total EMA Crossovers: {len([r for r in all_results if r['has_ema']])}
        🕯️ Total Patterns Detected: {len([r for r in all_results if r['has_pattern']])}
        """
        ax_summary.text(0.05, 0.95, summary_text, fontsize=12, family='monospace', verticalalignment='top')
        pdf.savefig(fig_summary)
        plt.close(fig_summary)
        
        # Charts for Cat1, Cat2, Cat3
        for stock in stocks_to_show:
            print(f"  Generating charts for {stock['ticker']}...")
            chart_data = create_stock_charts(stock)
            for i in range(3):
                if chart_data[i]:
                    pdf.savefig(chart_data[i])
                    plt.close(chart_data[i])
            fig_info, ax_info = plt.subplots(figsize=(12, 8))
            ax_info.axis('off')
            ax_info.text(0.05, 0.95, chart_data[3], fontsize=11, family='monospace', verticalalignment='top')
            pdf.savefig(fig_info)
            plt.close(fig_info)
    
    print(f"✅ PDF generated: {pdf_path}")
    
    # 📧 Email
    subject = f"🚀 SPRZ Scan - Cat1:{len(cat1)} | Cat2:{len(cat2)} | Cat3:{len(cat3)} ({datetime.now().strftime('%d-%b-%Y')})"
    body = f"""
    Hi,
    
    ✅ Scan complete!
    
    🔥 1. With Pattern + With Funda (STRONG BUY): {len(cat1)} stocks
    {chr(10).join([f"    - {s['ticker']} ({s['name']})" for s in cat1]) if cat1 else "    (None)"}
    
    📈 2. With Pattern + No Funda (TECH WATCH): {len(cat2)} stocks
    {chr(10).join([f"    - {s['ticker']} ({s['name']})" for s in cat2]) if cat2 else "    (None)"}
    
    💪 3. No Pattern + With Funda (FUNDA WATCH): {len(cat3)} stocks
    {chr(10).join([f"    - {s['ticker']} ({s['name']})" for s in cat3]) if cat3 else "    (None)"}
    
    📊 Full PDF report attached.
    
    Regards,
    SPRZ Scanner Bot
    """
    
    send_email_with_pdf(pdf_path, subject, body)

if __name__ == "__main__":
    main()
