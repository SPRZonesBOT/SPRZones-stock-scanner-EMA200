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
# 🔥 FONT SETUP
# ======================================================
plt.rcParams['font.family'] = 'DejaVu Sans'

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
print("⏱️ 4 Timeframes: 4H, Daily, Weekly, Monthly")

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
# 📈 INDICATORS (RSI, MACD)
# ======================================================
def calculate_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(df):
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal

# ======================================================
# 📈 TECHNICAL ANALYSIS
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
        return {'ema': False, 'pattern': False, 'signal': False, 'pattern_name': '',
                'volume_surge': False, 'rsi_bullish': False, 'macd_bullish': False}
    
    df = flatten_multiindex(df.copy())
    df['EMA_200'] = custom_ema(df['Close'], 200)
    if df['EMA_200'].isna().all():
        return {'ema': False, 'pattern': False, 'signal': False, 'pattern_name': '',
                'volume_surge': False, 'rsi_bullish': False, 'macd_bullish': False}
    
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
    
    rsi_bullish = False
    if len(df) > 14:
        rsi = calculate_rsi(df, 14)
        if not rsi.isna().all():
            rsi_last = rsi.iloc[-1]
            rsi_prev = rsi.iloc[-2] if len(rsi) > 1 else rsi_last
            if rsi_last > 50 or (rsi_prev < 50 and rsi_last > 50):
                rsi_bullish = True
    
    macd_bullish = False
    if len(df) > 26:
        macd, signal = calculate_macd(df)
        if not macd.isna().all() and not signal.isna().all():
            if macd.iloc[-1] > signal.iloc[-1]:
                macd_bullish = True
    
    return {
        'ema': ema_cross,
        'pattern': pattern_detected,
        'signal': ema_cross and pattern_detected,
        'pattern_name': pattern_name,
        'volume_surge': volume_surge,
        'rsi_bullish': rsi_bullish,
        'macd_bullish': macd_bullish
    }

# ======================================================
# 🔍 SCAN SINGLE STOCK (4 TIMEFRAMES)
# ======================================================
def scan_stock(ticker):
    try:
        print(f"  Scanning {ticker}...", end="")
        
        # 1. 4H Data (Resample from 1H)
        df1h = yf.download(ticker, period='60d', interval='1h', progress=False, auto_adjust=True)
        if df1h.empty or len(df1h) < 100:
            print(" ❌ Skip (no 1H data)")
            return None
        df1h = flatten_multiindex(df1h)
        df4h = df1h.resample('4h').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
        
        # 2. Daily Data
        dfd = yf.download(ticker, period='60d', interval='1d', progress=False, auto_adjust=True)
        if dfd.empty or len(dfd) < 50:
            print(" ❌ Skip (no daily data)")
            return None
        dfd = flatten_multiindex(dfd)
        
        # 3. Weekly & Monthly
        dfw = dfd.resample('W').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
        dfm = dfd.resample('ME').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
        
        r4h = analyze_df(df4h)
        rd = analyze_df(dfd)
        rw = analyze_df(dfw)
        rm = analyze_df(dfm)
        
        funda = get_fundamentals(ticker)
        if funda is None:
            print(" ❌ Skip (no funda)")
            return None
        
        has_ema = r4h['ema'] or rd['ema'] or rw['ema'] or rm['ema']
        has_pattern = r4h['pattern'] or rd['pattern'] or rw['pattern'] or rm['pattern']
        has_volume = r4h['volume_surge'] or rd['volume_surge'] or rw['volume_surge'] or rm['volume_surge']
        has_rsi = r4h['rsi_bullish'] or rd['rsi_bullish'] or rw['rsi_bullish'] or rm['rsi_bullish']
        has_macd = r4h['macd_bullish'] or rd['macd_bullish'] or rw['macd_bullish'] or rm['macd_bullish']
        confluence = sum([has_ema, has_pattern, has_rsi, has_macd, has_volume])
        funda_ok = funda['score'] >= 3
        
        cat_pattern_funda = has_ema and has_pattern and funda_ok
        cat_pattern_nofunda = has_ema and has_pattern and not funda_ok
        cat_nopattern_funda = has_ema and not has_pattern and funda_ok
        cat_nopattern_nofunda = has_ema and not has_pattern and not funda_ok
        
        # 🔥 Current Price from daily close
        current_price = dfd['Close'].iloc[-1] if not dfd.empty else 0
        current_price = round(current_price, 2)
        
        try:
            info = yf.Ticker(ticker).info
            sector = info.get('sector', 'N/A')
            name = info.get('longName', ticker)[:25]
        except:
            sector = 'N/A'; name = ticker
        
        print(" ✅ Done")
        return {
            'ticker': ticker, 'name': name, 'sector': sector,
            'current_price': current_price,  # 🔥 New field
            'df4h': df4h, 'dfd': dfd, 'dfw': dfw, 'dfm': dfm,
            'r4h': r4h, 'rd': rd, 'rw': rw, 'rm': rm,
            'funda': funda,
            'has_ema': has_ema, 'has_pattern': has_pattern,
            'has_volume_surge': has_volume,
            'has_rsi_bullish': has_rsi,
            'has_macd_bullish': has_macd,
            'confluence_score': confluence,
            'funda_ok': funda_ok,
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
# 📧 EMAIL SENDER
# ======================================================
def send_email_with_pdf(pdf_path, subject, body_text, html_table=""):
    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT]):
        print("❌ Email config missing.")
        return False
    msg = MIMEMultipart('alternative')
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECIPIENT
    msg['Subject'] = subject
    
    part_text = MIMEText(body_text, 'plain')
    msg.attach(part_text)
    
    html_body = f"""
    <html>
    <head><style>
        body {{ font-family: Arial, sans-serif; }}
        table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
        th {{ background-color: #1a237e; color: white; padding: 8px; text-align: left; border: 1px solid #ddd; }}
        td {{ padding: 8px; border: 1px solid #ddd; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .header {{ background-color: #0d47a1; color: white; padding: 10px; text-align: center; }}
    </style></head>
    <body>
        <div class="header">
            <h2>📊 SPRZones Scan - EMA 200 ({datetime.now().strftime('%d-%b-%Y')})</h2>
        </div>
        {html_table}
        <p style="color:#666; font-size:12px; margin-top:20px;">
            📌 Full PDF report attached with 4 timeframe charts (4H, Daily, Weekly, Monthly).
        </p>
    </body>
    </html>
    """
    part_html = MIMEText(html_body, 'html')
    msg.attach(part_html)
    
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
# 📊 CHART GENERATOR (4 TIMEFRAMES - FIXED HEADING)
# ======================================================
def create_stock_charts(result):
    ticker = result['ticker']; name = result['name']; sector = result['sector']
    funda = result['funda']; rec = result['final_recommendation']
    confluence = result['confluence_score']
    price = result['current_price']
    
    tf_list = [
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
        vol_tag = " 🔊VOL" if cross_data.get('volume_surge', False) else ""
        rsi_tag = " 🔥RSI" if cross_data.get('rsi_bullish', False) else ""
        macd_tag = " 📈MACD" if cross_data.get('macd_bullish', False) else ""
        
        short_name = name[:12] if len(name) > 12 else name
        title_text = f"{ticker} - {short_name} ({tf_name}) | {rec}\nPattern: {pattern_name if pattern_name else 'None'}{vol_tag}{rsi_tag}{macd_tag}"
        
        fig, axes = mpf.plot(df, type='candle', style=s, addplot=ap_ema,
                             volume=False, figsize=(16, 8), returnfig=True,
                             tight_layout=False, title='')
        
        ax = axes[0]
        ax.set_title(title_text, fontsize=11, weight='bold', pad=25, loc='center')
        fig.subplots_adjust(left=0.06, right=0.94, top=0.95, bottom=0.08)
        
        if pattern_name and cross_data.get('signal', False):
            last_x = len(df) - 1
            last_high = df['High'].iloc[-1]
            ax.annotate(f'🚀 {pattern_name}', xy=(last_x, last_high),
                        xytext=(last_x - 15, last_high * 1.05),
                        arrowprops=dict(arrowstyle='->', color='yellow', lw=1.5),
                        color='yellow', fontsize=10, weight='bold',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7))
        if cross_data.get('signal', False):
            ax.axvline(x=len(df) - 1, color='cyan', linestyle='--', alpha=0.6, linewidth=2, label='Crossover')
            ax.legend(loc='upper left')
        return fig

    for df, r, tf_name in tf_list:
        fig = plot_tf(df, r, tf_name)
        if fig:
            charts.append(fig)
    
    # Info Table (with current price added)
    fig_table, ax_table = plt.subplots(figsize=(14, 10))
    ax_table.axis('off')
    
    table_data = [
        ['Parameter', 'Value'],
        ['Ticker', ticker],
        ['Name', name],
        ['Sector', sector],
        ['Current Price', f"₹{price}"],
        ['Recommendation', rec],
        ['Confluence Score', f"{confluence}/5"],
        ['Fundamentals Score', f"{funda['score']}/5"],
        ['PE Ratio', f"{funda['pe']:.2f}"],
        ['ROE', f"{funda['roe']*100:.2f}%"],
        ['Debt/Equity', f"{funda['debt']:.2f}"],
        ['Profit Margin', f"{funda['margin']*100:.2f}%"],
        ['Revenue Growth', f"{funda['growth']*100:.2f}%"],
        ['---- Technical Filters ----', ''],
        ['EMA Crossover', '✅' if result['has_ema'] else '❌'],
        ['Bullish Pattern', '✅' if result['has_pattern'] else '❌'],
        ['RSI Bullish (>50)', '✅' if result['has_rsi_bullish'] else '❌'],
        ['MACD Bullish', '✅' if result['has_macd_bullish'] else '❌'],
        ['Volume Surge', '✅' if result['has_volume_surge'] else '❌'],
        ['---- Timeframe Signals ----', ''],
        ['4H', f"{'✅' if result['r4h']['signal'] else '❌'} ({result['r4h']['pattern_name'] or 'None'})"],
        ['Daily', f"{'✅' if result['rd']['signal'] else '❌'} ({result['rd']['pattern_name'] or 'None'})"],
        ['Weekly', f"{'✅' if result['rw']['signal'] else '❌'} ({result['rw']['pattern_name'] or 'None'})"],
        ['Monthly', f"{'✅' if result['rm']['signal'] else '❌'} ({result['rm']['pattern_name'] or 'None'})"],
    ]
    
    table = ax_table.table(cellText=table_data, loc='center', cellLoc='left', colWidths=[0.3, 0.6])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.5)
    
    for i, row in enumerate(table_data):
        if i == 0:
            for j in range(2):
                table[(i, j)].set_facecolor('#1a237e')
                table[(i, j)].set_text_props(color='white', weight='bold')
        elif row[0].startswith('----'):
            for j in range(2):
                table[(i, j)].set_facecolor('#e3f2fd')
                table[(i, j)].set_text_props(color='#0d47a1', weight='bold')
        elif '✅' in str(row[1]):
            table[(i, 1)].set_facecolor('#c8e6c9')
        elif '❌' in str(row[1]):
            table[(i, 1)].set_facecolor('#ffcdd2')
    
    charts.append(fig_table)
    return charts

# ======================================================
# 📊 PDF SUMMARY PAGE (WITH CURRENT PRICE)
# ======================================================
def create_summary_page(cat1, cat2, cat3, vol_stocks, all_results, date_str):
    fig, ax = plt.subplots(figsize=(16, 12))
    ax.axis('off')
    
    def build_cat_text(cat_list, title, emoji):
        if not cat_list:
            return f"{emoji} {title}: 0 stocks\n    (None)\n"
        lines = [f"{emoji} {title}: {len(cat_list)} stocks"]
        for s in cat_list:
            score = s.get('confluence_score', 'N/A')
            price = s.get('current_price', 0)
            lines.append(f"    - {s['ticker']} ({s['name']}) [{s['sector']}] Price: ₹{price} | Score:{score}/5")
        return "\n".join(lines) + "\n"
    
    cat1_text = build_cat_text(cat1, "STRONG BUY", "🔥")
    cat2_text = build_cat_text(cat2, "TECH WATCH", "📈")
    cat3_text = build_cat_text(cat3, "FUNDA WATCH", "💪")
    vol_text = build_cat_text(vol_stocks, "VOLUME SURGE", "🔊")
    
    stats = f"""
    📊 Total EMA Crossovers: {len([r for r in all_results if r['has_ema']])}
    🕯️ Patterns Detected: {len([r for r in all_results if r['has_pattern']])}
    📈 RSI Bullish: {len([r for r in all_results if r['has_rsi_bullish']])}
    📈 MACD Bullish: {len([r for r in all_results if r['has_macd_bullish']])}
    ⏱️ Timeframes: 4H, Daily, Weekly, Monthly
    """
    
    full_text = f"""
    📊 SPRZones Scan - EMA 200 ({date_str})
    ============================================================
    
    {cat1_text}
    {cat2_text}
    {cat3_text}
    {vol_text}
    ============================================================
    {stats}
    """
    
    ax.text(0.05, 0.95, full_text, fontsize=11, family='monospace', verticalalignment='top')
    return fig

# ======================================================
# 🚀 MAIN FUNCTION
# ======================================================
def main():
    print(f"\n🔄 Scanning {len(STOCKS)} stocks (4 Timeframes: 4H, Daily, Weekly, Monthly)...")
    print("⏱️ Estimated time: 30-45 minutes")
    
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
    
    cat1 = [r for r in all_results if r['cat_pattern_funda']]
    cat2 = [r for r in all_results if r['cat_pattern_nofunda']]
    cat3 = [r for r in all_results if r['cat_nopattern_funda']]
    cat4 = [r for r in all_results if r['cat_nopattern_nofunda']]
    vol_stocks = [r for r in all_results if r['has_pattern'] and r['has_ema'] and r['has_volume_surge']]
    
    print("\n" + "="*60)
    print("📊 QUADRANT ANALYSIS RESULTS (4 Timeframes)")
    print("="*60)
    print(f"🔥 STRONG BUY: {len(cat1)}")
    print(f"📈 TECH WATCH: {len(cat2)}")
    print(f"💪 FUNDA WATCH: {len(cat3)}")
    print(f"⛔ AVOID: {len(cat4)}")
    print(f"🔊 VOLUME SURGE: {len(vol_stocks)}")
    
    date_str = datetime.now().strftime('%d-%b-%Y')
    date_str_file = datetime.now().strftime('%Y%m%d')
    
    if not cat1 and not cat2 and not cat3 and not vol_stocks:
        send_email_with_pdf(
            pdf_path=None,
            subject=f"SPRZones Scan - EMA 200 ({date_str})",
            body_text=f"No significant signals found.\nScanned {len(STOCKS)} stocks.",
            html_table="<p>No significant signals found today.</p>"
        )
        print("No signals. Email sent without PDF.")
        return
    
    stocks_to_show = list({r['ticker']: r for r in (cat1 + cat2 + cat3 + vol_stocks)}.values())
    pdf_path = f"SPRZones_Scan_EMA200_{date_str_file}.pdf"
    
    with PdfPages(pdf_path) as pdf:
        summary_fig = create_summary_page(cat1, cat2, cat3, vol_stocks, all_results, date_str)
        pdf.savefig(summary_fig)
        plt.close(summary_fig)
        
        for idx, stock in enumerate(stocks_to_show):
            print(f"  Generating charts for {stock['ticker']} ({idx+1}/{len(stocks_to_show)})...")
            try:
                chart_data = create_stock_charts(stock)
                for i in range(4):
                    if i < len(chart_data) and chart_data[i]:
                        pdf.savefig(chart_data[i])
                        plt.close(chart_data[i])
                if len(chart_data) > 4:
                    pdf.savefig(chart_data[4])
                    plt.close(chart_data[4])
            except Exception as chart_err:
                print(f"    ⚠️ Warning: {stock['ticker']}: {chart_err}")
                continue
    
    print(f"✅ PDF generated: {pdf_path}")
    
    # 🔥 HTML Table with Price column
    html_table = f"""
    <h3>🔥 STRONG BUY ({len(cat1)} stocks)</h3>
    <table>
        <tr><th>Ticker</th><th>Name</th><th>Sector</th><th>Price</th><th>Score</th></tr>
        {"".join([f"<tr><td>{s['ticker']}</td><td>{s['name']}</td><td>{s['sector']}</td><td>₹{s['current_price']}</td><td>{s['confluence_score']}/5</td></tr>" for s in cat1]) if cat1 else "<tr><td colspan='5' style='text-align:center;color:#999;'>None</td></tr>"}
    </table>
    
    <h3>📈 TECH WATCH ({len(cat2)} stocks)</h3>
    <table>
        <tr><th>Ticker</th><th>Name</th><th>Sector</th><th>Price</th></tr>
        {"".join([f"<tr><td>{s['ticker']}</td><td>{s['name']}</td><td>{s['sector']}</td><td>₹{s['current_price']}</td></tr>" for s in cat2]) if cat2 else "<tr><td colspan='4' style='text-align:center;color:#999;'>None</td></tr>"}
    </table>
    
    <h3>💪 FUNDA WATCH ({len(cat3)} stocks)</h3>
    <table>
        <tr><th>Ticker</th><th>Name</th><th>Sector</th><th>Price</th></tr>
        {"".join([f"<tr><td>{s['ticker']}</td><td>{s['name']}</td><td>{s['sector']}</td><td>₹{s['current_price']}</td></tr>" for s in cat3]) if cat3 else "<tr><td colspan='4' style='text-align:center;color:#999;'>None</td></tr>"}
    </table>
    
    <h3>🔊 VOLUME SURGE ({len(vol_stocks)} stocks)</h3>
    <table>
        <tr><th>Ticker</th><th>Name</th><th>Sector</th><th>Price</th></tr>
        {"".join([f"<tr><td>{s['ticker']}</td><td>{s['name']}</td><td>{s['sector']}</td><td>₹{s['current_price']}</td></tr>" for s in vol_stocks]) if vol_stocks else "<tr><td colspan='4' style='text-align:center;color:#999;'>None</td></tr>"}
    </table>
    """
    
    body_text = f"""
    Scan complete with 4 Timeframes (4H, Daily, Weekly, Monthly)!
    
    STRONG BUY: {len(cat1)} stocks
    TECH WATCH: {len(cat2)} stocks
    FUNDA WATCH: {len(cat3)} stocks
    VOLUME SURGE: {len(vol_stocks)} stocks
    """
    
    subject = f"SPRZones Scan - EMA 200 ({date_str})"
    send_email_with_pdf(pdf_path, subject, body_text, html_table)

if __name__ == "__main__":
    main()
