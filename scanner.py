import yfinance as yf
import pandas as pd
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
# 🔥 FONT SETUP (Emoji Support for PDF)
# ======================================================
plt.rcParams['font.family'] = 'DejaVu Sans'  # Ubuntu par emoji support

# ======================================================
# 📧 CONFIG
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
print("⏱️ 7 Timeframes: 15m, 30m, 1H, 4H, Daily, Weekly, Monthly")

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
# 📈 CUSTOM TECHNICAL ANALYSIS (NO pandas-ta)
# ======================================================
def flatten_multiindex(df):
    if df is None or df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ['_'.join(col).strip() for col in df.columns.values]
        df.columns = [col.split('_')[0] for col in df.columns]
    return df

def custom_ema(series, span=200):
    return series.ewm(span=span, adjust=False).mean()

def detect_patterns(df):
    if len(df) < 3:
        return False, ""
    open_c = df['Open'].iloc[-1]; high_c = df['High'].iloc[-1]
    low_c = df['Low'].iloc[-1]; close_c = df['Close'].iloc[-1]
    body_c = abs(close_c - open_c)
    open_p = df['Open'].iloc[-2]; close_p = df['Close'].iloc[-2]
    body_p = abs(close_p - open_p)
    # Bullish Engulfing
    if (open_c < close_c) and (open_p > close_p):
        if (open_c < close_p) and (close_c > open_p):
            if body_c > (body_p * 1.2):
                return True, "Bullish Engulfing"
    # Hammer
    if body_c > 0:
        upper_wick = high_c - max(open_c, close_c)
        lower_wick = min(open_c, close_c) - low_c
        if (lower_wick > (body_c * 2)) and (upper_wick < (body_c * 0.3)):
            return True, "Hammer"
    # Dragonfly Doji
    candle_range = high_c - low_c
    if candle_range > 0 and body_c < (candle_range * 0.1):
        if (min(open_c, close_c) - low_c) > (candle_range * 0.7):
            return True, "Dragonfly Doji"
    return False, ""

def analyze_df(df):
    if df is None or df.empty or len(df) < 50:
        return {'ema': False, 'pattern': False, 'signal': False, 'pattern_name': '', 'volume_surge': False}
    df = flatten_multiindex(df.copy())
    df['EMA_200'] = custom_ema(df['Close'], 200)
    if df['EMA_200'].isna().all():
        return {'ema': False, 'pattern': False, 'signal': False, 'pattern_name': '', 'volume_surge': False}
    prev_c = df['Close'].iloc[-2]; curr_c = df['Close'].iloc[-1]
    prev_e = df['EMA_200'].iloc[-2]; curr_e = df['EMA_200'].iloc[-1]
    ema_cross = (prev_c < prev_e) and (curr_c > curr_e)
    pattern_name = ""; pattern_detected = False
    if ema_cross:
        pattern_detected, pattern_name = detect_patterns(df)
    volume_surge = False
    if ema_cross and 'Volume' in df.columns and len(df) >= 20:
        avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
        curr_vol = df['Volume'].iloc[-1]
        if avg_vol > 0 and curr_vol > (avg_vol * 1.5):
            volume_surge = True
    return {
        'ema': ema_cross,
        'pattern': pattern_detected,
        'signal': ema_cross and pattern_detected,
        'pattern_name': pattern_name,
        'volume_surge': volume_surge
    }

# ======================================================
# 🔍 SCAN SINGLE STOCK
# ======================================================
def scan_stock(ticker):
    try:
        print(f"  Scanning {ticker}...", end="")
        df15 = yf.download(ticker, period='45d', interval='15m', progress=False, auto_adjust=True)
        if df15.empty or len(df15) < 100:
            print(" ❌ Skip (no 15m data)")
            return None
        df15 = flatten_multiindex(df15)
        df30 = df15.resample('30min').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
        df1h = df15.resample('1h').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
        df4h = df15.resample('4h').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
        dfd = yf.download(ticker, period='60d', interval='1d', progress=False, auto_adjust=True)
        if dfd.empty or len(dfd) < 50:
            print(" ❌ Skip (no daily data)")
            return None
        dfd = flatten_multiindex(dfd)
        dfw = dfd.resample('W').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
        dfm = dfd.resample('ME').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
        
        r15 = analyze_df(df15); r30 = analyze_df(df30); r1h = analyze_df(df1h)
        r4h = analyze_df(df4h); rd = analyze_df(dfd); rw = analyze_df(dfw); rm = analyze_df(dfm)
        funda = get_fundamentals(ticker)
        if funda is None:
            print(" ❌ Skip (no funda)")
            return None
        
        has_ema = r15['ema'] or r30['ema'] or r1h['ema'] or r4h['ema'] or rd['ema'] or rw['ema'] or rm['ema']
        has_pattern = r15['pattern'] or r30['pattern'] or r1h['pattern'] or r4h['pattern'] or rd['pattern'] or rw['pattern'] or rm['pattern']
        has_volume_surge = r15['volume_surge'] or r30['volume_surge'] or r1h['volume_surge'] or r4h['volume_surge'] or rd['volume_surge'] or rw['volume_surge'] or rm['volume_surge']
        funda_ok = funda['score'] >= 3
        
        cat_pattern_funda = has_ema and has_pattern and funda_ok
        cat_pattern_nofunda = has_ema and has_pattern and not funda_ok
        cat_nopattern_funda = has_ema and not has_pattern and funda_ok
        cat_nopattern_nofunda = has_ema and not has_pattern and not funda_ok
        
        try:
            name = yf.Ticker(ticker).info.get('longName', ticker)[:25]
        except:
            name = ticker
        print(" ✅ Done")
        return {
            'ticker': ticker, 'name': name,
            'df15': df15, 'df30': df30, 'df1h': df1h, 'df4h': df4h,
            'dfd': dfd, 'dfw': dfw, 'dfm': dfm,
            'r15': r15, 'r30': r30, 'r1h': r1h, 'r4h': r4h, 'rd': rd, 'rw': rw, 'rm': rm,
            'funda': funda,
            'has_ema': has_ema, 'has_pattern': has_pattern,
            'has_volume_surge': has_volume_surge, 'funda_ok': funda_ok,
            'cat_pattern_funda': cat_pattern_funda,
            'cat_pattern_nofunda': cat_pattern_nofunda,
            'cat_nopattern_funda': cat_nopattern_funda,
            'cat_nopattern_nofunda': cat_nopattern_nofunda,
            'final_recommendation': '🔥 STRONG BUY' if cat_pattern_funda else 
                                    ('📈 TECH WATCH' if cat_pattern_nofunda else 
                                     ('💪 FUNDA WATCH' if cat_nopattern_funda else '⛔ AVOID'))
        }
    except Exception as e:
        print(f" ❌ Error: {e}")
        return None

# ======================================================
# 📧 EMAIL & PDF (With Full Emojis)
# ======================================================
def send_email_with_pdf(pdf_path, subject, body):
    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT]):
        print("❌ Email config missing.")
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

def create_stock_charts(result):
    ticker = result['ticker']; name = result['name']
    funda = result['funda']; rec = result['final_recommendation']
    vol_surge = result['has_volume_surge']
    tf_list = [
        (result['df15'], result['r15'], '15 Min'),
        (result['df30'], result['r30'], '30 Min'),
        (result['df1h'], result['r1h'], '1 Hour'),
        (result['df4h'], result['r4h'], '4 Hours'),
        (result['dfd'], result['rd'], 'Daily'),
        (result['dfw'], result['rw'], 'Weekly'),
        (result['dfm'], result['rm'], 'Monthly'),
    ]
    charts = []
    
    def plot_tf(df, cross_data, tf_name):
        if df is None or df.empty or len(df) < 10:
            return None
        df = flatten_multiindex(df.tail(90).copy())
        df['EMA_200'] = custom_ema(df['Close'], 200)
        mc = mpf.make_marketcolors(up='#00ff00', down='#ff0000', wick='inherit')
        s = mpf.make_mpf_style(marketcolors=mc, gridstyle=':', y_on_right=True)
        ap_ema = mpf.make_addplot(df['EMA_200'], color='orange', width=1.5)
        
        pattern_name = cross_data.get('pattern_name', '')
        vol_tag = " 🔊 Volume Surge!" if cross_data.get('volume_surge', False) else ""
        title = f"{ticker} - {name[:15]} ({tf_name}) | {rec}\nPattern: {pattern_name if pattern_name else 'None'}{vol_tag}"
        
        fig, axes = mpf.plot(df, type='candle', style=s, addplot=ap_ema,
                             volume=False, figsize=(10, 5), returnfig=True,
                             tight_layout=True, title=title)
        ax = axes[0]
        if pattern_name and cross_data.get('signal', False):
            last_x = len(df) - 1
            last_high = df['High'].iloc[-1]
            ax.annotate(f'🚀 {pattern_name}', xy=(last_x, last_high),
                        xytext=(last_x - 15, last_high * 1.02),
                        arrowprops=dict(arrowstyle='->', color='yellow', lw=1.5),
                        color='yellow', fontsize=9, weight='bold',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7))
        if cross_data.get('signal', False):
            ax.axvline(x=len(df) - 1, color='cyan', linestyle='--', alpha=0.6, linewidth=2, label='Crossover')
            ax.legend()
        return fig

    # Generate 7 charts
    for df, r, tf_name in tf_list:
        fig = plot_tf(df, r, tf_name)
        if fig:
            charts.append(fig)
    
    # 📋 Info Text (Full Emojis)
    info_text = f"""
    📊 {ticker} - {name}
    ========================================
    🏷️ Recommendation: {rec}
    🔊 Volume Surge: {'✅ YES' if vol_surge else '❌ NO'}
    ----------------------------------------
    📈 Fundamentals Score: {funda['score']}/5
    PE: {funda['pe']:.2f} | ROE: {funda['roe']*100:.2f}%
    Debt/Equity: {funda['debt']:.2f} | Margin: {funda['margin']*100:.2f}%
    Revenue Growth: {funda['growth']*100:.2f}%
    ----------------------------------------
    🔍 Signal Summary (7 Timeframes):
    15m:   {'✅' if result['r15']['signal'] else '❌'} ({result['r15']['pattern_name'] or 'None'}) {'🔊' if result['r15']['volume_surge'] else ''}
    30m:   {'✅' if result['r30']['signal'] else '❌'} ({result['r30']['pattern_name'] or 'None'}) {'🔊' if result['r30']['volume_surge'] else ''}
    1H:    {'✅' if result['r1h']['signal'] else '❌'} ({result['r1h']['pattern_name'] or 'None'}) {'🔊' if result['r1h']['volume_surge'] else ''}
    4H:    {'✅' if result['r4h']['signal'] else '❌'} ({result['r4h']['pattern_name'] or 'None'}) {'🔊' if result['r4h']['volume_surge'] else ''}
    Daily: {'✅' if result['rd']['signal'] else '❌'} ({result['rd']['pattern_name'] or 'None'}) {'🔊' if result['rd']['volume_surge'] else ''}
    Weekly:{'✅' if result['rw']['signal'] else '❌'} ({result['rw']['pattern_name'] or 'None'}) {'🔊' if result['rw']['volume_surge'] else ''}
    Monthly:{'✅' if result['rm']['signal'] else '❌'} ({result['rm']['pattern_name'] or 'None'}) {'🔊' if result['rm']['volume_surge'] else ''}
    """
    return charts + [info_text]

# ======================================================
# 🚀 MAIN FUNCTION
# ======================================================
def main():
    print(f"\n🔄 Scanning {len(STOCKS)} stocks (7 Timeframes)...")
    print("⏱️ Estimated time: 45-60 minutes")
    
    all_results = []
    total = len(STOCKS)
    for i, t in enumerate(STOCKS):
        if i % 10 == 0:
            print(f"\n📊 Progress: {i}/{total} ({i/total*100:.1f}%)")
        res = scan_stock(t)
        if res:
            all_results.append(res)
        time.sleep(0.5)
    
    print(f"\n✅ Scan complete! Total processed: {len(all_results)}")
    
    # 🔥 Filter 4 Quadrants
    cat1 = [r for r in all_results if r['cat_pattern_funda']]
    cat2 = [r for r in all_results if r['cat_pattern_nofunda']]
    cat3 = [r for r in all_results if r['cat_nopattern_funda']]
    cat4 = [r for r in all_results if r['cat_nopattern_nofunda']]
    vol_stocks = [r for r in all_results if r['has_pattern'] and r['has_ema'] and r['has_volume_surge']]
    
    print("\n" + "="*60)
    print("📊 QUADRANT ANALYSIS RESULTS")
    print("="*60)
    print(f"🔥 CAT 1 (Pattern + Funda) STRONG BUY: {len(cat1)}")
    print(f"📈 CAT 2 (Pattern + No Funda) TECH WATCH: {len(cat2)}")
    print(f"💪 CAT 3 (No Pattern + Funda) FUNDA WATCH: {len(cat3)}")
    print(f"⛔ CAT 4 (No Pattern + No Funda) AVOID: {len(cat4)}")
    print(f"🔊 VOLUME SURGE (Pattern + Volume): {len(vol_stocks)}")
    
    if not cat1 and not cat2 and not cat3 and not vol_stocks:
        send_email_with_pdf(
            pdf_path=None,
            subject=f"📊 SPRZ Scan - {datetime.now().strftime('%d-%b-%Y')}",
            body=f"No significant signals found today.\nScanned {len(STOCKS)} stocks (7 timeframes).\n\n" + \
                 f"🔥 CAT 1 (Pattern + Funda): 0\n" + \
                 f"📈 CAT 2 (Pattern + No Funda): 0\n" + \
                 f"💪 CAT 3 (No Pattern + Funda): 0\n" + \
                 f"⛔ CAT 4 (No Pattern + No Funda): {len(cat4)}\n" + \
                 f"🔊 Volume Surge (Pattern + Volume): 0"
        )
        print("No significant signals. Email sent without PDF.")
        return
    
    stocks_to_show = list({r['ticker']: r for r in (cat1 + cat2 + cat3 + vol_stocks)}.values())
    pdf_path = f"SPRZ_Signals_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    with PdfPages(pdf_path) as pdf:
        # 📋 Summary Page
        fig_summary, ax_summary = plt.subplots(figsize=(16, 12))
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
        
        🔊 VOLUME SURGE (EMA + Pattern + High Volume) → {len(vol_stocks)} stocks
        {chr(10).join([f"     - {s['ticker']} ({s['name']})" for s in vol_stocks]) if vol_stocks else "     (None)"}
        ============================================================
        📈 Total EMA Crossovers: {len([r for r in all_results if r['has_ema']])}
        🕯️ Total Patterns Detected: {len([r for r in all_results if r['has_pattern']])}
        ⏱️ Timeframes Used: 15m, 30m, 1H, 4H, Daily, Weekly, Monthly
        """
        ax_summary.text(0.05, 0.95, summary_text, fontsize=11, family='monospace', verticalalignment='top')
        pdf.savefig(fig_summary)
        plt.close(fig_summary)
        
        # Charts for each stock
        for idx, stock in enumerate(stocks_to_show):
            print(f"  Generating charts for {stock['ticker']} ({idx+1}/{len(stocks_to_show)})...")
            try:
                chart_data = create_stock_charts(stock)
                for i in range(7):
                    if i < len(chart_data) and chart_data[i]:
                        pdf.savefig(chart_data[i])
                        plt.close(chart_data[i])
                fig_info, ax_info = plt.subplots(figsize=(12, 8))
                ax_info.axis('off')
                ax_info.text(0.05, 0.95, chart_data[7], fontsize=10, family='monospace', verticalalignment='top')
                pdf.savefig(fig_info)
                plt.close(fig_info)
            except Exception as chart_err:
                print(f"    ⚠️ Warning: Chart failed for {stock['ticker']}: {chart_err}")
                continue
    
    print(f"✅ PDF generated: {pdf_path}")
    
    # 📧 Email with Emojis
    subject = f"🚀 SPRZ Scan (7TFs) - Cat1:{len(cat1)} | Vol:{len(vol_stocks)} ({datetime.now().strftime('%d-%b-%Y')})"
    body = f"""
    Hi,
    
    ✅ Scan complete with 7 Timeframes (15m, 30m, 1H, 4H, Daily, Weekly, Monthly)!
    
    🔥 CAT 1 (Pattern + Funda) STRONG BUY: {len(cat1)} stocks
    {chr(10).join([f"    - {s['ticker']} ({s['name']})" for s in cat1]) if cat1 else "    (None)"}
    
    📈 CAT 2 (Pattern + No Funda) TECH WATCH: {len(cat2)} stocks
    {chr(10).join([f"    - {s['ticker']} ({s['name']})" for s in cat2]) if cat2 else "    (None)"}
    
    💪 CAT 3 (No Pattern + Funda) FUNDA WATCH: {len(cat3)} stocks
    {chr(10).join([f"    - {s['ticker']} ({s['name']})" for s in cat3]) if cat3 else "    (None)"}
    
    🔊 VOLUME SURGE (EMA + Pattern + High Volume): {len(vol_stocks)} stocks
    {chr(10).join([f"    - {s['ticker']} ({s['name']})" for s in vol_stocks]) if vol_stocks else "    (None)"}
    
    📊 Full PDF report attached with 7 timeframe charts for each stock.
    
    Regards,
    SPRZ Scanner Bot
    """
    
    send_email_with_pdf(pdf_path, subject, body)

if __name__ == "__main__":
    main()
