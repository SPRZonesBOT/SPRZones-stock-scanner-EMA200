
import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import time
from datetime import datetime

# ------------------- PAGE CONFIG -------------------
st.set_page_config(
    page_title="SPRZones - EMA200 Scanner",
    page_icon="📈",
    layout="wide"
)

# Custom CSS for mobile
st.markdown("""
<style>
    .main > div { padding-top: 1rem; }
    .stButton button { width: 100%; }
    .buy-signal { background-color: #00ff0044; }
    .stDataFrame { overflow-x: auto; }
</style>
""", unsafe_allow_html=True)

st.title("⚡ SPRZones - EMA200 Breakout Scanner")
st.markdown("**Indian Stocks** | **1H / 4H / Daily** | **200 EMA Crossover + Bullish Patterns + Strong Fundamentals**")

# ------------------- SIDEBAR (Controls) -------------------
st.sidebar.header("⚙️ Settings")

@st.cache_data
def get_stock_list():
    """Top 100 Nifty stocks for fast scanning"""
    return [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
        "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
        "BAJFINANCE.NS", "WIPRO.NS", "HCLTECH.NS", "ASIANPAINT.NS", "AXISBANK.NS",
        "LT.NS", "MARUTI.NS", "TITAN.NS", "SUNPHARMA.NS", "ULTRACEMCO.NS",
        "ADANIPORTS.NS", "NTPC.NS", "POWERGRID.NS", "M&M.NS", "TATASTEEL.NS",
        "JSWSTEEL.NS", "TECHM.NS", "INDUSINDBK.NS", "BAJAJFINSV.NS", "HDFCLIFE.NS",
        "SBILIFE.NS", "DRREDDY.NS", "HINDALCO.NS", "EICHERMOT.NS", "COALINDIA.NS",
        "ONGC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "TATACONSUM.NS", "HDFC.NS",
        "DIVISLAB.NS", "UPL.NS", "SHREECEM.NS", "GRASIM.NS", "APOLLOHOSP.NS",
        "HEROMOTOCO.NS", "BAJAJ-AUTO.NS", "ADANIENT.NS", "TATAMOTORS.NS", "VEDL.NS",
        "AMBUJACEM.NS", "CIPLA.NS", "PIDILITIND.NS", "ICICIPRULI.NS", "TATACOMM.NS",
        "HAL.NS", "SIEMENS.NS", "DLF.NS", "MCDOWELL-N.NS", "HAVELLS.NS",
        "BERGEPAINT.NS", "PAGEIND.NS", "COLPAL.NS", "MARICO.NS", "DABUR.NS",
        "GODREJCP.NS", "JUBLFOOD.NS", "MUTHOOTFIN.NS", "SRTRANSFIN.NS", "PEL.NS",
        "BANKBARODA.NS", "CANBK.NS", "PNB.NS", "UNIONBANK.NS", "IOB.NS",
        "NAM-INDIA.NS", "MOTHERSON.NS", "ASHOKLEY.NS", "ESCORTS.NS", "TVSMOTOR.NS",
        "BIOCON.NS", "LUPIN.NS", "TORNTPHARM.NS", "AUROPHARMA.NS", "DIVISLAB.NS",
        "DIXON.NS", "VOLTAS.NS", "WHIRLPOOL.NS", "BLUESTAR.NS", "AMBER.NS"
    ]

mode = st.sidebar.radio("Select Mode", ["Top 100 Stocks (Fast)", "Custom Tickers"])
min_score = st.sidebar.slider("Min Fundamental Score (out of 5)", 2, 5, 3, 
                             help="PE<30, ROE>15%, Debt<1.5, Margin>10%, Growth>10%")

if mode == "Custom Tickers":
    custom_input = st.sidebar.text_area("Enter Tickers (comma separated)", "RELIANCE.NS, TCS.NS, HDFCBANK.NS")
    stock_list = [t.strip() for t in custom_input.split(",") if t.strip()]
else:
    stock_list = get_stock_list()

run_scan = st.sidebar.button("🚀 Start Scan", type="primary", use_container_width=True)
st.sidebar.caption(f"📊 Total Stocks: {len(stock_list)}")

# ------------------- SCANNER ENGINE -------------------
@st.cache_data(ttl=3600, show_spinner=False)
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
        details = {}
        if pe < 30: score += 1; details['PE'] = '✅'
        else: details['PE'] = f'{pe:.1f}x'
        if roe > 0.15: score += 1; details['ROE'] = '✅'
        else: details['ROE'] = f'{roe*100:.1f}%'
        if debt < 1.5: score += 1; details['Debt'] = '✅'
        else: details['Debt'] = f'{debt:.1f}x'
        if margin > 0.10: score += 1; details['Margin'] = '✅'
        else: details['Margin'] = f'{margin*100:.1f}%'
        if growth > 0.10: score += 1; details['Growth'] = '✅'
        else: details['Growth'] = f'{growth*100:.1f}%'
        
        return {'score': score, 'details': details}
    except:
        return None

def analyze_df(df):
    if len(df) < 50:
        return {'ema': False, 'pattern': False, 'signal': False}
    
    df['EMA_200'] = ta.ema(df['Close'], length=200)
    if df['EMA_200'].isna().all():
        return {'ema': False, 'pattern': False, 'signal': False}
    
    # Crossover
    prev_c = df['Close'].iloc[-2]; curr_c = df['Close'].iloc[-1]
    prev_e = df['EMA_200'].iloc[-2]; curr_e = df['EMA_200'].iloc[-1]
    ema_cross = (prev_c < prev_e) and (curr_c > curr_e)
    
    # Patterns
    engulf = ta.cdl_engulfing(df['Open'], df['High'], df['Low'], df['Close'])
    bull_eng = False
    if engulf is not None and not engulf.empty and len(engulf) > 0:
        bull_eng = engulf.iloc[-1] > 0
    
    hammer = ta.cdl_hammer(df['Open'], df['High'], df['Low'], df['Close'])
    bull_ham = False
    if hammer is not None and not hammer.empty and len(hammer) > 0:
        bull_ham = hammer.iloc[-1] > 0
    
    dragon = ta.cdl_dragonfly_doji(df['Open'], df['High'], df['Low'], df['Close'])
    bull_drag = False
    if dragon is not None and not dragon.empty and len(dragon) > 0:
        bull_drag = dragon.iloc[-1] > 0
    
    pattern = bull_eng or bull_ham or bull_drag
    return {'ema': ema_cross, 'pattern': pattern, 'signal': ema_cross and pattern}

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
        
        # Fundamentals
        funda = get_fundamentals(ticker)
        if funda is None:
            return None
        
        any_signal = r1['signal'] or r4['signal'] or rd['signal']
        buy = any_signal and (funda['score'] >= min_score)
        
        try:
            name = yf.Ticker(ticker).info.get('longName', ticker)[:25]
        except:
            name = ticker
        
        return {
            'Ticker': ticker, 'Name': name,
            '1H': r1['signal'], '4H': r4['signal'], 'Daily': rd['signal'],
            'Funda_Score': funda['score'],
            'Funda_Details': str(funda['details']),
            'BUY': buy
        }
    except:
        return None

# ------------------- EXECUTION -------------------
if run_scan:
    start = time.time()
    progress = st.progress(0)
    status = st.empty()
    output = st.empty()
    
    results = []
    total = len(stock_list)
    
    status.info(f"🔄 Scanning {total} stocks... Estimated time: {total // 20} min.")
    
    for i, t in enumerate(stock_list):
        status.text(f"⏳ {i+1}/{total}: {t}")
        res = scan_stock(t)
        if res:
            results.append(res)
        progress.progress((i+1)/total)
        time.sleep(0.6)
    
    status.success("✅ Scan Complete!")
    progress.empty()
    
    if not results:
        st.warning("⚠️ No data fetched. Check internet connection.")
    else:
        df = pd.DataFrame(results)
        buy_df = df[df['BUY'] == True]
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader("🚀 Buy Signals")
            if buy_df.empty:
                st.info("😴 No BUY signals today. Try lowering the score threshold or check tomorrow.")
            else:
                st.metric("🔥 Total Opportunities", len(buy_df))
                display_cols = ['Ticker', 'Name', '1H', '4H', 'Daily', 'Funda_Score']
                st.dataframe(buy_df[display_cols].style.map(
                    lambda x: 'background-color: #00ff0044; font-weight: bold' if x == True else '',
                    subset=['1H', '4H', 'Daily']
                ), use_container_width=True)
                
                csv = buy_df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download BUY List", csv, "buy_signals.csv", "text/csv")
        
        with col2:
            st.subheader("📊 All Scanned")
            st.dataframe(df, use_container_width=True, height=300)
            csv_all = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Full Report", csv_all, "full_scan.csv", "text/csv")
        
        elapsed = time.time() - start
        st.caption(f"⏱️ Completed in {elapsed:.1f} seconds. Stocks: {len(results)}")
        st.balloons()

else:
    st.info("👈 Click **'Start Scan'** in the sidebar to run the scanner.")
    with st.expander("ℹ️ Strategy Explained"):
        st.markdown("""
        **Entry Conditions (Strict):**
        1. Price closes **above** 200 EMA (was below in previous candle).
        2. Bullish pattern detected (Engulfing, Hammer, or Dragonfly Doji).
        3. Fundamentals score >= selected threshold.
        
        **Fundamental Score (Max 5):**
        - PE < 30
        - ROE > 15%
        - Debt/Equity < 1.5
        - Profit Margin > 10%
        - Revenue Growth > 10%
        """)

st.divider()
st.caption(f"🕒 Last refresh: {datetime.now().strftime('%I:%M:%S %p')} IST")
