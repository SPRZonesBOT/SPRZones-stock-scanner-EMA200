import yfinance as yf
import pandas as pd
import pandas_ta as ta
import warnings
warnings.filterwarnings('ignore')
from datetime import datetime, timedelta

# ==============================================
# 🔥 TEST STOCKS (10 Nifty stocks - Fast)
# ==============================================
TEST_STOCKS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS"
]

# ==============================================
# 📈 MANUAL PATTERN DETECTION (No pandas_ta dependency)
# ==============================================
def flatten_multiindex(df):
    if df is None or df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ['_'.join(col).strip() for col in df.columns.values]
        df.columns = [col.split('_')[0] for col in df.columns]
    return df

def detect_bullish_engulfing(df, i):
    """Manual Bullish Engulfing detection"""
    if i < 1:
        return False
    prev_open = df['Open'].iloc[i-1]
    prev_close = df['Close'].iloc[i-1]
    curr_open = df['Open'].iloc[i]
    curr_close = df['Close'].iloc[i]
    # Bearish candle (prev) -> Bullish candle (curr) with engulf
    if prev_close < prev_open and curr_close > curr_open:
        if curr_open < prev_close and curr_close > prev_open:
            return True
    return False

def detect_hammer(df, i):
    """Manual Hammer detection"""
    if i < 1:
        return False
    open_price = df['Open'].iloc[i]
    high = df['High'].iloc[i]
    low = df['Low'].iloc[i]
    close = df['Close'].iloc[i]
    body = abs(close - open_price)
    lower_wick = min(open_price, close) - low
    upper_wick = high - max(open_price, close)
    # Hammer: lower wick >= 2*body, upper wick <= body/2, body > 0
    if body > 0 and lower_wick >= 2*body and upper_wick <= body/2:
        return True
    return False

def detect_dragonfly_doji(df, i):
    """Manual Dragonfly Doji detection"""
    if i < 1:
        return False
    open_price = df['Open'].iloc[i]
    high = df['High'].iloc[i]
    low = df['Low'].iloc[i]
    close = df['Close'].iloc[i]
    body = abs(close - open_price)
    lower_wick = min(open_price, close) - low
    upper_wick = high - max(open_price, close)
    # Doji: body <= 0.1 * (high-low), lower wick >= 2*body, upper wick <= body
    if (high - low) > 0 and body <= 0.1 * (high - low) and lower_wick >= 2*body and upper_wick <= body:
        return True
    return False

def detect_morning_star(df, i):
    """Manual Morning Star detection (simplified)"""
    if i < 2:
        return False
    # Candle 1: Bearish (prev day)
    c1_open = df['Open'].iloc[i-2]
    c1_close = df['Close'].iloc[i-2]
    c1_bearish = c1_close < c1_open
    
    # Candle 2: Doji / Small body (middle)
    c2_open = df['Open'].iloc[i-1]
    c2_close = df['Close'].iloc[i-1]
    c2_range = df['High'].iloc[i-1] - df['Low'].iloc[i-1]
    c2_body = abs(c2_close - c2_open)
    c2_doji = (c2_range > 0 and c2_body <= 0.1 * c2_range)
    
    # Candle 3: Bullish (current)
    c3_open = df['Open'].iloc[i]
    c3_close = df['Close'].iloc[i]
    c3_bullish = c3_close > c3_open
    
    # Gap between c1 and c2 (c2 low > c1 close) and c2 to c3 (c3 open > c2 close)
    if c1_bearish and c2_doji and c3_bullish:
        if df['Low'].iloc[i-1] > c1_close and c3_open > df['High'].iloc[i-1]:
            return True
    return False

def analyze_df(df):
    if df is None or df.empty or len(df) < 50:
        return {'ema': False, 'pattern': False, 'volume_surge': False}
    
    df = flatten_multiindex(df.copy())
    df['EMA_200'] = ta.ema(df['Close'], length=200)
    if df['EMA_200'].isna().all():
        return {'ema': False, 'pattern': False, 'volume_surge': False}
    
    # 1. Crossover
    prev_c = df['Close'].iloc[-2]
    curr_c = df['Close'].iloc[-1]
    prev_e = df['EMA_200'].iloc[-2]
    curr_e = df['EMA_200'].iloc[-1]
    ema_cross = (prev_c < prev_e) and (curr_c > curr_e)
    
    # 2. Pattern Detection (Manual)
    pattern_detected = False
    if ema_cross:
        last_idx = len(df) - 1
        if detect_bullish_engulfing(df, last_idx):
            pattern_detected = True
        elif detect_hammer(df, last_idx):
            pattern_detected = True
        elif detect_dragonfly_doji(df, last_idx):
            pattern_detected = True
        elif detect_morning_star(df, last_idx):
            pattern_detected = True
    
    # 3. Volume Surge
    volume_surge = False
    if ema_cross and 'Volume' in df.columns and len(df) >= 20:
        avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
        curr_vol = df['Volume'].iloc[-1]
        if avg_vol > 0 and curr_vol > (avg_vol * 1.5):
            volume_surge = True
    
    return {
        'ema': ema_cross,
        'pattern': pattern_detected,
        'volume_surge': volume_surge
    }

# ==============================================
# 📊 BACKTEST ENGINE
# ==============================================
def backtest_stock(ticker, years=3, hold_days=[5, 10, 20]):
    print(f"  Backtesting {ticker}...", end="")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365 * years)
    
    df = yf.download(ticker, start=start_date, end=end_date, 
                     interval='1d', progress=False, auto_adjust=True)
    
    if df.empty or len(df) < 250:
        print(" ❌ Insufficient data")
        return None
    
    df = flatten_multiindex(df)
    
    trades_ema = []      # Strategy A: Sirf EMA
    trades_pattern = []  # Strategy B: EMA + Pattern
    trades_volume = []   # Strategy C: EMA + Pattern + Volume
    
    for i in range(250, len(df) - max(hold_days)):
        slice_df = df.iloc[:i+1].copy()
        signals = analyze_df(slice_df)
        
        if signals['ema']:
            entry_price = df['Close'].iloc[i]
            entry_date = df.index[i]
            
            # --- A: Sirf EMA ---
            for days in hold_days:
                exit_idx = min(i + days, len(df) - 1)
                exit_price = df['Close'].iloc[exit_idx]
                return_pct = (exit_price / entry_price - 1) * 100
                trades_ema.append({
                    'Ticker': ticker,
                    'Entry_Date': entry_date,
                    'Hold_Days': days,
                    'Return_%': return_pct,
                    'Win': return_pct > 0
                })
            
            # --- B: EMA + Pattern ---
            if signals['pattern']:
                for days in hold_days:
                    exit_idx = min(i + days, len(df) - 1)
                    exit_price = df['Close'].iloc[exit_idx]
                    return_pct = (exit_price / entry_price - 1) * 100
                    trades_pattern.append({
                        'Ticker': ticker,
                        'Entry_Date': entry_date,
                        'Hold_Days': days,
                        'Return_%': return_pct,
                        'Win': return_pct > 0
                    })
                
                # --- C: EMA + Pattern + Volume Surge ---
                if signals['volume_surge']:
                    for days in hold_days:
                        exit_idx = min(i + days, len(df) - 1)
                        exit_price = df['Close'].iloc[exit_idx]
                        return_pct = (exit_price / entry_price - 1) * 100
                        trades_volume.append({
                            'Ticker': ticker,
                            'Entry_Date': entry_date,
                            'Hold_Days': days,
                            'Return_%': return_pct,
                            'Win': return_pct > 0
                        })
    
    print(f" ✅ EMA:{len(trades_ema)//len(hold_days)} | Pat:{len(trades_pattern)//len(hold_days)} | Vol:{len(trades_volume)//len(hold_days)}")
    
    return {
        'ema': pd.DataFrame(trades_ema) if trades_ema else None,
        'pattern': pd.DataFrame(trades_pattern) if trades_pattern else None,
        'volume': pd.DataFrame(trades_volume) if trades_volume else None
    }

# ==============================================
# 📊 SUMMARY
# ==============================================
def print_summary(df, strategy_name):
    if df is None or df.empty:
        print(f"\n📊 {strategy_name}: No trades")
        return None
    
    total_trades = len(df)
    print(f"\n📊 {strategy_name}")
    print(f"   Total Trades: {total_trades}")
    
    for days in [5, 10, 20]:
        subset = df[df['Hold_Days'] == days]
        if not subset.empty:
            win_rate = (subset['Win'].sum() / len(subset)) * 100
            avg_return = subset['Return_%'].mean()
            print(f"   Hold {days}d: {len(subset)} trades, Win Rate: {win_rate:.1f}%, Avg: {avg_return:.2f}%")
    
    return {
        'total_trades': total_trades,
        'win_rate_20d': (df[df['Hold_Days']==20]['Win'].sum() / len(df[df['Hold_Days']==20])) * 100 if len(df[df['Hold_Days']==20]) > 0 else 0,
    }

# ==============================================
# 🚀 MAIN
# ==============================================
if __name__ == "__main__":
    print("="*70)
    print("🔥 SAFE BACKTEST: EMA vs Pattern vs Volume Surge (No pandas_ta dependency)")
    print(f"📊 Testing {len(TEST_STOCKS)} stocks for 3 years")
    print("⏱️ Estimated time: 5-10 minutes")
    print("="*70)
    
    all_ema = []; all_pattern = []; all_volume = []
    
    for i, stock in enumerate(TEST_STOCKS):
        print(f"[{i+1}/{len(TEST_STOCKS)}] ", end="")
        res = backtest_stock(stock, years=3, hold_days=[5, 10, 20])
        if res:
            if res['ema'] is not None:
                all_ema.append(res['ema'])
            if res['pattern'] is not None:
                all_pattern.append(res['pattern'])
            if res['volume'] is not None:
                all_volume.append(res['volume'])
    
    df_ema = pd.concat(all_ema, ignore_index=True) if all_ema else None
    df_pattern = pd.concat(all_pattern, ignore_index=True) if all_pattern else None
    df_volume = pd.concat(all_volume, ignore_index=True) if all_volume else None
    
    print("\n" + "="*70)
    print("📈 BACKTEST COMPARISON RESULTS (3 Years, 10 Nifty Stocks)")
    print("="*70)
    
    s_ema = print_summary(df_ema, "🔵 STRATEGY A: EMA Crossover Only")
    s_pattern = print_summary(df_pattern, "🟢 STRATEGY B: EMA + Pattern")
    s_volume = print_summary(df_volume, "🔴 STRATEGY C: EMA + Pattern + Volume Surge")
    
    print("\n" + "="*70)
    print("💡 FINAL INTERPRETATION")
    print("="*70)
    
    if s_ema and s_pattern and s_volume:
        print(f"📌 Pattern filter ne {((s_ema['total_trades'] - s_pattern['total_trades'])/s_ema['total_trades']*100):.1f}% trades reduce kar diye.")
        print(f"📌 Volume Surge filter ne {((s_ema['total_trades'] - s_volume['total_trades'])/s_ema['total_trades']*100):.1f}% trades reduce kar diye.")
        print()
        print("🔍 Win Rate Comparison (20 Days Hold):")
        print(f"   EMA Only        : {s_ema['win_rate_20d']:.1f}%")
        print(f"   EMA + Pattern   : {s_pattern['win_rate_20d']:.1f}%")
        print(f"   EMA + Pattern + Volume : {s_volume['win_rate_20d']:.1f}%")
    
    if df_ema is not None:
        df_ema.to_csv('backtest_ema_only.csv', index=False)
    if df_pattern is not None:
        df_pattern.to_csv('backtest_ema_pattern.csv', index=False)
    if df_volume is not None:
        df_volume.to_csv('backtest_ema_pattern_volume.csv', index=False)
    
    print("\n✅ CSVs saved. Done!")
