import yfinance as yf
import pandas as pd
import pandas as ta
import warnings
warnings.filterwarnings('ignore')
from datetime import datetime, timedelta

# ==============================================
# 🔥 NIFTY 50 STOCKS (Fast test ke liye)
# ==============================================
NIFTY_50 = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "BAJFINANCE.NS", "WIPRO.NS", "HCLTECH.NS", "ASIANPAINT.NS", "AXISBANK.NS",
    "LT.NS", "MARUTI.NS", "TITAN.NS", "SUNPHARMA.NS", "ULTRACEMCO.NS",
    "ADANIPORTS.NS", "NTPC.NS", "POWERGRID.NS", "M&M.NS", "TATASTEEL.NS",
    "JSWSTEEL.NS", "TECHM.NS", "INDUSINDBK.NS", "BAJAJFINSV.NS", "HDFCLIFE.NS",
    "SBILIFE.NS", "DRREDDY.NS", "HINDALCO.NS", "EICHERMOT.NS", "COALINDIA.NS",
    "ONGC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "TATACONSUM.NS", "HDFC.NS",
    "DIVISLAB.NS", "UPL.NS", "SHREECEM.NS", "GRASIM.NS", "APOLLOHOSP.NS",
    "HEROMOTOCO.NS", "BAJAJ-AUTO.NS", "ADANIENT.NS", "TATAMOTORS.NS", "VEDL.NS"
]

# ==============================================
# 📈 TECHNICAL LOGIC (Same as scanner)
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
        return {'ema': False, 'pattern': False, 'volume_surge': False}
    
    df = flatten_multiindex(df.copy())
    df['EMA_200'] = ta.ema(df['Close'], length=200)
    if df['EMA_200'].isna().all():
        return {'ema': False, 'pattern': False, 'volume_surge': False}
    
    # 1. EMA Crossover
    prev_c = df['Close'].iloc[-2]
    curr_c = df['Close'].iloc[-1]
    prev_e = df['EMA_200'].iloc[-2]
    curr_e = df['EMA_200'].iloc[-1]
    ema_cross = (prev_c < prev_e) and (curr_c > curr_e)
    
    # 2. Pattern Detection (Sirf crossover pe check karo, time bachane ke liye)
    pattern_detected = False
    if ema_cross:
        engulf = ta.cdl_engulfing(df['Open'], df['High'], df['Low'], df['Close'])
        if engulf is not None and not engulf.empty and len(engulf) > 0 and engulf.iloc[-1] > 0:
            pattern_detected = True
        if not pattern_detected:
            hammer = ta.cdl_hammer(df['Open'], df['High'], df['Low'], df['Close'])
            if hammer is not None and not hammer.empty and len(hammer) > 0 and hammer.iloc[-1] > 0:
                pattern_detected = True
        if not pattern_detected:
            dragon = ta.cdl_dragonfly_doji(df['Open'], df['High'], df['Low'], df['Close'])
            if dragon is not None and not dragon.empty and len(dragon) > 0 and dragon.iloc[-1] > 0:
                pattern_detected = True
        if not pattern_detected:
            ms = ta.cdl_morning_star(df['Open'], df['High'], df['Low'], df['Close'])
            if ms is not None and not ms.empty and len(ms) > 0 and ms.iloc[-1] > 0:
                pattern_detected = True
    
    # 3. Volume Surge (Last candle volume > 1.5x 20-period avg)
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
    
    if df.empty or len(df) < 300:
        print(" ❌ Insufficient data")
        return None
    
    df = flatten_multiindex(df)
    
    # Store trades for 3 strategies
    trades_ema = []      # Strategy A: Sirf EMA
    trades_pattern = []  # Strategy B: EMA + Pattern
    trades_volume = []   # Strategy C: EMA + Pattern + Volume
    
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
    print("🔥 ADVANCED BACKTEST: EMA vs Pattern vs Volume Surge")
    print(f"📊 Testing {len(NIFTY_50)} stocks for 3 years (Daily timeframe)")
    print("⏱️ Estimated time: 10-15 minutes")
    print("="*70)
    
    all_ema = []
    all_pattern = []
    all_volume = []
    
    for i, stock in enumerate(NIFTY_50):
        print(f"[{i+1}/{len(NIFTY_50)}] ", end="")
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
    print("📈 BACKTEST COMPARISON RESULTS (3 Years, Nifty 50)")
    print("="*70)
    
    summary_ema = print_summary(df_ema, "🔵 STRATEGY A: EMA Crossover Only")
    summary_pattern = print_summary(df_pattern, "🟢 STRATEGY B: EMA + Pattern")
    summary_volume = print_summary(df_volume, "🔴 STRATEGY C: EMA + Pattern + Volume Surge (>1.5x Avg)")
    
    # ================= FINAL INTERPRETATION =================
    print("\n" + "="*70)
    print("💡 FINAL INTERPRETATION")
    print("="*70)
    
    if summary_ema and summary_pattern and summary_volume:
        reduction = ((summary_ema['total_trades'] - summary_pattern['total_trades']) / summary_ema['total_trades']) * 100
        reduction_vol = ((summary_ema['total_trades'] - summary_volume['total_trades']) / summary_ema['total_trades']) * 100
        
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
