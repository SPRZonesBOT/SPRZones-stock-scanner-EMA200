import yfinance as yf
import pandas as pd
import pandas_ta as ta
import warnings
warnings.filterwarnings('ignore')
from datetime import datetime, timedelta

# ==============================================
# 🔥 NIFTY 50 STOCKS
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
# 📈 TECHNICAL ANALYSIS (Returns EMA and Pattern flags)
# ==============================================
def analyze_df(df):
    if len(df) < 50:
        return {'ema': False, 'pattern': False}
    
    # Flatten MultiIndex
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ['_'.join(col).strip() for col in df.columns.values]
        df.columns = [col.split('_')[0] for col in df.columns]
    
    df = df.copy()
    df['EMA_200'] = ta.ema(df['Close'], length=200)
    if df['EMA_200'].isna().all():
        return {'ema': False, 'pattern': False}
    
    # EMA Crossover
    prev_c = df['Close'].iloc[-2]
    curr_c = df['Close'].iloc[-1]
    prev_e = df['EMA_200'].iloc[-2]
    curr_e = df['EMA_200'].iloc[-1]
    ema_cross = (prev_c < prev_e) and (curr_c > curr_e)
    
    # Pattern Detection
    pattern_detected = False
    if ema_cross:  # Sirf pattern tab check karo jab crossover ho (time bachane ke liye)
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
    
    return {'ema': ema_cross, 'pattern': pattern_detected}

# ==============================================
# 📊 BACKTEST ENGINE
# ==============================================
def backtest_stock(ticker, years=2, hold_days=[5, 10, 20]):
    print(f"  Backtesting {ticker}...", end="")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365 * years)
    
    df = yf.download(ticker, start=start_date, end=end_date, 
                     interval='1d', progress=False, auto_adjust=True)
    
    if df.empty or len(df) < 250:
        print(" ❌ Insufficient data")
        return None
    
    # Flatten MultiIndex
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ['_'.join(col).strip() for col in df.columns.values]
        df.columns = [col.split('_')[0] for col in df.columns]
    
    results_ema = []      # Strategy A: Sirf EMA (Loose)
    results_pattern = []  # Strategy B: EMA + Pattern (Strict)
    
    for i in range(250, len(df) - max(hold_days)):
        slice_df = df.iloc[:i+1].copy()
        signals = analyze_df(slice_df)
        
        if signals['ema']:
            entry_price = df['Close'].iloc[i]
            entry_date = df.index[i]
            
            # 🟡 Strategy A: Sirf EMA (Pattern ignore)
            for days in hold_days:
                exit_idx = min(i + days, len(df) - 1)
                exit_price = df['Close'].iloc[exit_idx]
                return_pct = (exit_price / entry_price - 1) * 100
                results_ema.append({
                    'Ticker': ticker,
                    'Entry_Date': entry_date,
                    'Hold_Days': days,
                    'Return_%': return_pct,
                    'Win': return_pct > 0
                })
            
            # 🔥 Strategy B: EMA + Pattern (Strict)
            if signals['pattern']:
                for days in hold_days:
                    exit_idx = min(i + days, len(df) - 1)
                    exit_price = df['Close'].iloc[exit_idx]
                    return_pct = (exit_price / entry_price - 1) * 100
                    results_pattern.append({
                        'Ticker': ticker,
                        'Entry_Date': entry_date,
                        'Hold_Days': days,
                        'Return_%': return_pct,
                        'Win': return_pct > 0
                    })
    
    print(f" ✅ EMA: {len(results_ema)//len(hold_days)} signals, Pattern: {len(results_pattern)//len(hold_days)} signals")
    
    return {'ema': pd.DataFrame(results_ema) if results_ema else None, 
            'pattern': pd.DataFrame(results_pattern) if results_pattern else None}

# ==============================================
# 🚀 MAIN
# ==============================================
if __name__ == "__main__":
    print("="*70)
    print("🔥 QUADRANT BACKTEST: EMA Only vs EMA + Pattern")
    print(f"📊 Testing {len(NIFTY_50)} stocks for 2 years")
    print("⏱️ Estimated time: 15-20 minutes")
    print("="*70)
    
    all_ema = []
    all_pattern = []
    
    for i, stock in enumerate(NIFTY_50):
        print(f"[{i+1}/{len(NIFTY_50)}] ", end="")
        res = backtest_stock(stock, years=2, hold_days=[5, 10, 20])
        if res:
            if res['ema'] is not None:
                all_ema.append(res['ema'])
            if res['pattern'] is not None:
                all_pattern.append(res['pattern'])
    
    # ================= COMBINE RESULTS =================
    if not all_ema and not all_pattern:
        print("\n❌ No results generated.")
        exit()
    
    print("\n" + "="*70)
    print("📈 BACKTEST COMPARISON RESULTS")
    print("="*70)
    
    # Strategy A: EMA Only
    if all_ema:
        df_ema = pd.concat(all_ema, ignore_index=True)
        total_trades_ema = len(df_ema)
        print(f"\n📊 STRATEGY A: EMA Crossover Only (Loose - Cat 3 & 4)")
        print(f"   Total Trades: {total_trades_ema}")
        for days in [5, 10, 20]:
            subset = df_ema[df_ema['Hold_Days'] == days]
            if not subset.empty:
                win_rate = (subset['Win'].sum() / len(subset)) * 100
                avg_return = subset['Return_%'].mean()
                max_return = subset['Return_%'].max()
                min_return = subset['Return_%'].min()
                print(f"   Hold {days}d: {len(subset)} trades, Win Rate: {win_rate:.1f}%, Avg: {avg_return:.2f}%, Max: {max_return:.2f}%, Min: {min_return:.2f}%")
    
    # Strategy B: EMA + Pattern
    if all_pattern:
        df_pattern = pd.concat(all_pattern, ignore_index=True)
        total_trades_pattern = len(df_pattern)
        print(f"\n📊 STRATEGY B: EMA + Pattern (Strict - Cat 1 & 2)")
        print(f"   Total Trades: {total_trades_pattern}")
        for days in [5, 10, 20]:
            subset = df_pattern[df_pattern['Hold_Days'] == days]
            if not subset.empty:
                win_rate = (subset['Win'].sum() / len(subset)) * 100
                avg_return = subset['Return_%'].mean()
                max_return = subset['Return_%'].max()
                min_return = subset['Return_%'].min()
                print(f"   Hold {days}d: {len(subset)} trades, Win Rate: {win_rate:.1f}%, Avg: {avg_return:.2f}%, Max: {max_return:.2f}%, Min: {min_return:.2f}%")
    
    # ================= FINAL COMPARISON =================
    print("\n" + "="*70)
    print("💡 INTERPRETATION")
    print("="*70)
    if all_ema and all_pattern:
        trades_ema = len(df_ema)
        trades_pattern = len(df_pattern)
        reduction = ((trades_ema - trades_pattern) / trades_ema) * 100 if trades_ema > 0 else 0
        print(f"📌 Pattern filter ne {reduction:.1f}% trades reduce kar diye.")
        print("   - Agar Win Rate aur Avg Return PATTERN strategy mein HIGHER hai, toh pattern add karna faydemand hai.")
        print("   - Agar Win Rate PATTERN strategy mein LOWER hai, toh pattern strict condition trade ko miss kar raha hai.")
        print("\n💡 Real Entry (Cat 1): Pattern + Funda (Live scanner me aap already use kar rahe ho).")
    else:
        print("❌ Insufficient data for comparison.")
    
    # Save results
    if all_ema:
        df_ema.to_csv('backtest_ema_only.csv', index=False)
        print("\n✅ EMA Only results saved to 'backtest_ema_only.csv'")
    if all_pattern:
        df_pattern.to_csv('backtest_ema_pattern.csv', index=False)
        print("✅ EMA + Pattern results saved to 'backtest_ema_pattern.csv'")
