import yfinance as yf
import pandas as pd
import pandas_ta as ta
import warnings
warnings.filterwarnings('ignore')
from datetime import datetime, timedelta

# ==============================================
# 🔥 TOP 10 STOCKS (Fast test ke liye)
# ==============================================
TEST_STOCKS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS"
]

# ==============================================
# 📈 CUSTOM PATTERN DETECTION (No pandas_ta dependency)
# ==============================================
def detect_patterns(df):
    """Bullish patterns detect karo WITHOUT pandas_ta"""
    if len(df) < 3:
        return False, ""
    
    # Current candle
    open_c = df['Open'].iloc[-1]
    high_c = df['High'].iloc[-1]
    low_c = df['Low'].iloc[-1]
    close_c = df['Close'].iloc[-1]
    body_c = abs(close_c - open_c)
    
    # Previous candle
    open_p = df['Open'].iloc[-2]
    high_p = df['High'].iloc[-2]
    low_p = df['Low'].iloc[-2]
    close_p = df['Close'].iloc[-2]
    body_p = abs(close_p - open_p)
    
    # Bullish Engulfing
    is_bullish_engulf = False
    if (open_c < close_c) and (open_p > close_p):  # Current bullish, Previous bearish
        if (open_c < close_p) and (close_c > open_p):  # Current engulfs previous
            if body_c > (body_p * 1.2):  # Body zyada ho
                is_bullish_engulf = True
    
    # Hammer (Lower wick > 2x body, Upper wick < 0.3x body)
    is_hammer = False
    if body_c > 0:
        upper_wick = high_c - max(open_c, close_c)
        lower_wick = min(open_c, close_c) - low_c
        if (lower_wick > (body_c * 2)) and (upper_wick < (body_c * 0.3)):
            is_hammer = True
    
    # Dragonfly Doji (body < 0.1x range, lower wick > 2x body)
    is_dragonfly = False
    candle_range = high_c - low_c
    if candle_range > 0 and body_c < (candle_range * 0.1):
        if (min(open_c, close_c) - low_c) > (candle_range * 0.7):
            is_dragonfly = True
    
    if is_bullish_engulf:
        return True, "Bullish Engulfing"
    elif is_hammer:
        return True, "Hammer"
    elif is_dragonfly:
        return True, "Dragonfly Doji"
    return False, ""

# ==============================================
# 📈 TECHNICAL ANALYSIS (WITHOUT pandas_ta patterns)
# ==============================================
def flatten_multiindex(df):
    if df is None or df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ['_'.join(col).strip() for col in df.columns.values]
        df.columns = [col.split('_')[0] for col in df.columns]
    return df

def analyze_df(df):
    if df is None or df.empty or len(df) < 50:
        return {'ema': False, 'pattern': False, 'signal': False, 'pattern_name': '', 'volume_surge': False}
    
    df = flatten_multiindex(df.copy())
    
    # EMA 200 (pandas_ta only for EMA)
    try:
        df['EMA_200'] = ta.ema(df['Close'], length=200)
    except:
        # Fallback: agar pandas_ta fail ho toh manually calculate
        df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    if df['EMA_200'].isna().all():
        return {'ema': False, 'pattern': False, 'signal': False, 'pattern_name': '', 'volume_surge': False}
    
    # 1. Crossover
    prev_c = df['Close'].iloc[-2]
    curr_c = df['Close'].iloc[-1]
    prev_e = df['EMA_200'].iloc[-2]
    curr_e = df['EMA_200'].iloc[-1]
    ema_cross = (prev_c < prev_e) and (curr_c > curr_e)
    
    # 2. Pattern Detection (Custom, no pandas_ta)
    pattern_name = ""
    pattern_detected = False
    if ema_cross:
        pattern_detected, pattern_name = detect_patterns(df)
    
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
        'signal': ema_cross and pattern_detected,
        'pattern_name': pattern_name,
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
    trades_volume = []   # Strategy C: EMA + Pattern + Volume Surge
    
    for i in range(250, len(df) - max(hold_days)):
        slice_df = df.iloc[:i+1].copy()
        signals = analyze_df(slice_df)
        
        if signals['ema']:
            entry_price = df['Close'].iloc[i]
            entry_date = df.index[i]
            
            # --- Strategy A: Sirf EMA ---
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
            
            # --- Strategy B: EMA + Pattern ---
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
                
                # --- Strategy C: EMA + Pattern + Volume Surge ---
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
# 📊 SUMMARY PRINTER
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
            max_return = subset['Return_%'].max()
            min_return = subset['Return_%'].min()
            print(f"   Hold {days}d: {len(subset)} trades, Win Rate: {win_rate:.1f}%, Avg: {avg_return:.2f}%, Max: {max_return:.2f}%, Min: {min_return:.2f}%")
    
    return {
        'total_trades': total_trades,
        'win_rate_5d': (df[df['Hold_Days']==5]['Win'].sum() / len(df[df['Hold_Days']==5])) * 100 if len(df[df['Hold_Days']==5]) > 0 else 0,
        'win_rate_10d': (df[df['Hold_Days']==10]['Win'].sum() / len(df[df['Hold_Days']==10])) * 100 if len(df[df['Hold_Days']==10]) > 0 else 0,
        'win_rate_20d': (df[df['Hold_Days']==20]['Win'].sum() / len(df[df['Hold_Days']==20])) * 100 if len(df[df['Hold_Days']==20]) > 0 else 0,
        'avg_return_5d': df[df['Hold_Days']==5]['Return_%'].mean() if len(df[df['Hold_Days']==5]) > 0 else 0,
    }

# ==============================================
# 🚀 MAIN
# ==============================================
if __name__ == "__main__":
    print("="*70)
    print("🔥 FINAL BACKTEST: EMA vs Pattern vs Volume Surge")
    print(f"📊 Testing {len(TEST_STOCKS)} stocks for 3 years (Daily timeframe)")
    print("⏱️ Estimated time: 5-10 minutes")
    print("="*70)
    
    all_ema = []
    all_pattern = []
    all_volume = []
    
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
    
    # Combine results
    df_ema = pd.concat(all_ema, ignore_index=True) if all_ema else None
    df_pattern = pd.concat(all_pattern, ignore_index=True) if all_pattern else None
    df_volume = pd.concat(all_volume, ignore_index=True) if all_volume else None
    
    print("\n" + "="*70)
    print("📈 BACKTEST COMPARISON RESULTS (3 Years, 10 Nifty Stocks)")
    print("="*70)
    
    summary_ema = print_summary(df_ema, "🔵 STRATEGY A: EMA Crossover Only")
    summary_pattern = print_summary(df_pattern, "🟢 STRATEGY B: EMA + Pattern")
    summary_volume = print_summary(df_volume, "🔴 STRATEGY C: EMA + Pattern + Volume Surge (>1.5x Avg)")
    
    # ================= FINAL INTERPRETATION =================
    print("\n" + "="*70)
    print("💡 FINAL INTERPRETATION")
    print("="*70)
    
    if summary_ema and summary_pattern and summary_volume:
        reduction = ((summary_ema['total_trades'] - summary_pattern['total_trades']) / summary_ema['total_trades']) * 100 if summary_ema['total_trades'] > 0 else 0
        reduction_vol = ((summary_ema['total_trades'] - summary_volume['total_trades']) / summary_ema['total_trades']) * 100 if summary_ema['total_trades'] > 0 else 0
        
        print(f"📌 Pattern filter ne {reduction:.1f}% trades reduce kar diye.")
        print(f"📌 Volume Surge filter ne {reduction_vol:.1f}% trades reduce kar diye.")
        print()
        print("🔍 Win Rate Comparison (20 Days Hold):")
        print(f"   EMA Only        : {summary_ema['win_rate_20d']:.1f}%")
        print(f"   EMA + Pattern   : {summary_pattern['win_rate_20d']:.1f}%")
        print(f"   EMA + Pattern + Volume : {summary_volume['win_rate_20d']:.1f}%")
        print()
        
        if summary_pattern['win_rate_20d'] > summary_ema['win_rate_20d']:
            print("✅ PATTERN add karne se Win Rate IMPROVE hui hai — isko compulsory rakho.")
        else:
            print("⚠️ PATTERN add karne se Win Rate GIR gaya hai — isko optional rakh sakte ho.")
        
        if summary_volume['win_rate_20d'] > summary_pattern['win_rate_20d']:
            print("✅ VOLUME SURGE add karne se Win Rate aur IMPROVE hui hai — isko 'Strong Buy' filter rakho.")
        elif summary_volume['win_rate_20d'] > summary_ema['win_rate_20d']:
            print("✅ VOLUME SURGE ne EMA se toh better kiya, lekin Pattern se kam — useful hai.")
        else:
            print("⚠️ VOLUME SURGE ne performance degrade kardi — isko optional rakh sakte ho.")
    
    # Save CSVs
    if df_ema is not None:
        df_ema.to_csv('backtest_ema_only.csv', index=False)
        print("\n✅ EMA Only results saved to 'backtest_ema_only.csv'")
    if df_pattern is not None:
        df_pattern.to_csv('backtest_ema_pattern.csv', index=False)
        print("✅ EMA + Pattern results saved to 'backtest_ema_pattern.csv'")
    if df_volume is not None:
        df_volume.to_csv('backtest_ema_pattern_volume.csv', index=False)
        print("✅ EMA + Pattern + Volume results saved to 'backtest_ema_pattern_volume.csv'")
    
    print("\n" + "="*70)
    print("🔔 NOTE: Fundamentals (PE/ROE) is backtest mein include nahi hain.")
    print("   Live scanner mein Fundamentals filter apply hota hai (Score >= 3).")
    print("   Ye backtest sirf TECHNICAL EDGE (EMA, Pattern, Volume) ka test hai.")
