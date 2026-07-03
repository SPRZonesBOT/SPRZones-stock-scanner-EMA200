
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import mplfinance as mpf
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import io
import os
import time
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import json

# ==================== CONFIG ====================
# 🔥 Email Config - GitHub Secrets se lein
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_SENDER = os.getenv("EMAIL_SENDER")        # GitHub Secret
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")    # GitHub Secret (App Password)
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT")  # GitHub Secret

# 🔥 Stock List (Nifty 100)
STOCKS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "BAJFINANCE.NS", "WIPRO.NS", "HCLTECH.NS", "ASIANPAINT.NS", "AXISBANK.NS",
    "LT.NS", "MARUTI.NS", "TITAN.NS", "SUNPHARMA.NS", "ULTRACEMCO.NS",
    "ADANIPORTS.NS", "NTPC.NS", "POWERGRID.NS", "M&M.NS", "TATASTEEL.NS"
]

# ==================== FUNDAMENTALS ====================
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
        return {
            'score': score,
            'pe': pe, 'roe': roe, 'debt': debt,
            'margin': margin, 'growth': growth
        }
    except:
        return None

# ==================== TECHNICAL SCANNER ====================
def analyze_df(df):
    """Returns dict with EMA cross and Pattern detection"""
    if len(df) < 50:
        return {'ema': False, 'pattern': False, 'signal': False, 'pattern_name': ''}
    
    df['EMA_200'] = ta.ema(df['Close'], length=200)
    if df['EMA_200'].isna().all():
        return {'ema': False, 'pattern': False, 'signal': False, 'pattern_name': ''}
    
    # Crossover check
    prev_c = df['Close'].iloc[-2]
    curr_c = df['Close'].iloc[-1]
    prev_e = df['EMA_200'].iloc[-2]
    curr_e = df['EMA_200'].iloc[-1]
    ema_cross = (prev_c < prev_e) and (curr_c > curr_e)
    
    # 🕯️ Bullish Patterns using pandas_ta
    pattern_name = ""
    pattern_detected = False
    
    engulf = ta.cdl_engulfing(df['Open'], df['High'], df['Low'], df['Close'])
    if engulf is not None and not engulf.empty and len(engulf) > 0 and engulf.iloc[-1] > 0:
        pattern_detected = True
        pattern_name = "Bullish Engulfing"
    
    if not pattern_detected:
        hammer = ta.cdl_hammer(df['Open'], df['High'], df['Low'], df['Close'])
        if hammer is not None and not hammer.empty and len(hammer) > 0 and hammer.iloc[-1] > 0:
            pattern_detected = True
            pattern_name = "Hammer"
    
    if not pattern_detected:
        dragon = ta.cdl_dragonfly_doji(df['Open'], df['High'], df['Low'], df['Close'])
        if dragon is not None and not dragon.empty and len(dragon) > 0 and dragon.iloc[-1] > 0:
            pattern_detected = True
            pattern_name = "Dragonfly Doji"
    
    # Morning Star etc. if needed
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

def scan_stock(ticker):
    try:
        # 1H Data
        df1 = yf.download(ticker, period='60d', interval='1h', progress=False, auto_adjust=True)
        if df1.empty or len(df1) < 200:
            return None
        r1 = analyze_df(df1)
        
        # 4H Data (Resample)
        df4 = df1.resample('4h').agg({'Open':'first','High':'max','Low':'min','Close':'last'}).dropna()
        r4 = analyze_df(df4)
        
        # Daily Data
        dfd = yf.download(ticker, period='60d', interval='1d', progress=False, auto_adjust=True)
        if dfd.empty or len(dfd) < 200:
            dfd = df1.resample('1d').agg({'Open':'first','High':'max','Low':'min','Close':'last'}).dropna()
        rd = analyze_df(dfd)
        
        funda = get_fundamentals(ticker)
        if funda is None:
            return None
        
        any_signal = r1['signal'] or r4['signal'] or rd['signal']
        buy_decision = any_signal and (funda['score'] >= 3)
        
        try:
            name = yf.Ticker(ticker).info.get('longName', ticker)[:30]
        except:
            name = ticker
            
        return {
            'ticker': ticker, 'name': name,
            'df_1h': df1, 'df_4h': df4, 'df_d': dfd,
            'r1': r1, 'r4': r4, 'rd': rd,
            'funda': funda,
            'buy': buy_decision
        }
    except Exception as e:
        print(f"Error in {ticker}: {e}")
        return None

# ==================== CHART + PDF GENERATOR ====================
def create_stock_charts(result):
    """Generate 3 charts (1H, 4H, Daily) for a stock and return figures"""
    ticker = result['ticker']
    name = result['name']
    r1, r4, rd = result['r1'], result['r4'], result['rd']
    df1, df4, dfd = result['df_1h'], result['df_4h'], result['df_d']
    funda = result['funda']
    
    # Last 90 candles for better visibility
    df1 = df1.tail(90)
    df4 = df4.tail(90)
    dfd = dfd.tail(90)
    
    charts = []
    
    # Helper to plot one timeframe
    def plot_tf(df, tf_name, cross_data, pattern_name):
        if df.empty:
            return None
        
        # Prepare EMA
        df['EMA_200'] = ta.ema(df['Close'], length=200)
        
        # Colors
        mc = mpf.make_marketcolors(up='#00ff00', down='#ff0000', wick='inherit')
        s = mpf.make_mpf_style(marketcolors=mc, gridstyle=':', y_on_right=True)
        
        # Create addplot for EMA
        ap_ema = mpf.make_addplot(df['EMA_200'], color='orange', width=1.5)
        
        # Plot
        fig, axes = mpf.plot(df, type='candle', style=s, addplot=ap_ema,
                             volume=False, figsize=(10, 6),
                             returnfig=True, tight_layout=True,
                             title=f"{ticker} - {name[:20]} ({tf_name})\nPattern: {pattern_name if pattern_name else 'None'}")
        
        # Annotate pattern on the last candle
        ax = axes[0]
        if pattern_name and cross_data['signal']:
            # Arrow pointing to the last candle
            last_x = len(df) - 1
            last_high = df['High'].iloc[-1]
            ax.annotate(f'🚀 {pattern_name}', 
                        xy=(last_x, last_high), 
                        xytext=(last_x - 15, last_high * 1.02),
                        arrowprops=dict(arrowstyle='->', color='yellow', lw=1.5),
                        color='yellow', fontsize=10, weight='bold',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7))
        
        # Mark 200 EMA crossover with a vertical line
        if cross_data['signal']:
            ax.axvline(x=len(df) - 1, color='cyan', linestyle='--', alpha=0.6, linewidth=2, label='Crossover Point')
            ax.legend()
        
        return fig
    
    # Generate 3 charts
    fig1 = plot_tf(df1, '1 Hour', r1, r1['pattern_name'])
    fig2 = plot_tf(df4, '4 Hour', r4, r4['pattern_name'])
    fig3 = plot_tf(dfd, 'Daily', rd, rd['pattern_name'])
    
    # Add fundamental info text on the last page
    info_text = f"""
    📊 {ticker} - {name}
    ----------------------------------------
    Fundamental Score: {funda['score']}/5
    PE: {funda['pe']:.2f}
    ROE: {funda['roe']*100:.2f}%
    Debt/Equity: {funda['debt']:.2f}
    Profit Margin: {funda['margin']*100:.2f}%
    Revenue Growth: {funda['growth']*100:.2f}%
    
    Signals:
    1H: {'✅' if r1['signal'] else '❌'} ({r1['pattern_name'] if r1['pattern_name'] else 'No Pattern'})
    4H: {'✅' if r4['signal'] else '❌'} ({r4['pattern_name'] if r4['pattern_name'] else 'No Pattern'})
    Daily: {'✅' if rd['signal'] else '❌'} ({rd['pattern_name'] if rd['pattern_name'] else 'No Pattern'})
    """
    
    return [fig1, fig2, fig3, info_text]

# ==================== EMAIL SENDER ====================
def send_email_with_pdf(pdf_path, subject, body):
    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT]):
        print("❌ Email config missing. Set GitHub Secrets.")
        return False
        
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECIPIENT
    msg['Subject'] = subject
    
    msg.attach(MIMEText(body, 'plain'))
    
    # Attach PDF
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
        print("✅ Email sent successfully!")
        return True
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False

# ==================== MAIN ====================
def main():
    print(f"🔄 Starting scan of {len(STOCKS)} stocks...")
    
    buy_stocks = []
    all_scanned = []
    
    for i, t in enumerate(STOCKS):
        print(f"  Scanning {i+1}/{len(STOCKS)}: {t}")
        res = scan_stock(t)
        if res:
            all_scanned.append(res)
            if res['buy']:
                buy_stocks.append(res)
        time.sleep(0.8)  # Rate limiting
    
    print(f"✅ Scan complete! Found {len(buy_stocks)} buy signals.")
    
    if not buy_stocks:
        # Send simple email that no signals found
        send_email_with_pdf(
            pdf_path=None,  # No attachment
            subject=f"📊 SPRZ Scanner - {datetime.now().strftime('%d-%b-%Y')}",
            body=f"No buy signals found today.\nScanned {len(STOCKS)} stocks."
        )
        print("No signals, email sent without PDF.")
        return
    
    # ==================== GENERATE PDF ====================
    pdf_path = f"SPRZ_Signals_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    with PdfPages(pdf_path) as pdf:
        for idx, stock in enumerate(buy_stocks):
            print(f"  Generating charts for {stock['ticker']}...")
            charts = create_stock_charts(stock)
            
            # Add charts (fig1, fig2, fig3)
            for i in range(3):
                if charts[i]:
                    pdf.savefig(charts[i])
                    plt.close(charts[i])
            
            # Add info text page
            info_str = charts[3] if len(charts) > 3 else "No Data"
            fig_info, ax_info = plt.subplots(figsize=(10, 6))
            ax_info.axis('off')
            ax_info.text(0.1, 0.9, info_str, fontsize=12, family='monospace', verticalalignment='top')
            pdf.savefig(fig_info)
            plt.close(fig_info)
    
    print(f"✅ PDF generated: {pdf_path}")
    
    # ==================== SEND EMAIL ====================
    subject = f"🚀 SPRZ Scanner - {len(buy_stocks)} Buy Signals Found! {datetime.now().strftime('%d-%b-%Y')}"
    body = f"""
    Hi,
    
    ✅ Scan complete. {len(buy_stocks)} stocks matched the criteria.
    Please find the detailed PDF report attached.
    
    Signals found in:
    {chr(10).join(['- ' + s['ticker'] + ' (' + s['name'] + ')' for s in buy_stocks])}
    
    Regards,
    SPRZ Scanner Bot
    """
    
    send_email_with_pdf(pdf_path, subject, body)
    
    # Cleanup
    # os.remove(pdf_path)  # Optional

if __name__ == "__main__":
    main()
