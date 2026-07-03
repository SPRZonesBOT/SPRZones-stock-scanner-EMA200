import yfinance as yf
import pandas as pd
import pandas_ta as ta
import warnings
warnings.filterwarnings('ignore')
from datetime import datetime, timedelta

# ==============================================
# 🔥 NIFTY 50 STOCKS (Full List)
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
# 📈 TECHNICAL ANALYSIS (EMA CROSSOVER + PATTERN OPTIONAL)
# ==============================================
def analyze_df(df, check_pattern=False):
    if len(df) < 50:
        return False, ''
    
    df = df.copy()
    df['EMA_200'] = ta.ema(df['Close'], length=200)
    if df['EMA_200'].isna().all():
        return False, ''
    
    prev_c = df['Close'].iloc[-2]
    curr_c = df['Close'].iloc[-1]
    prev_e = df['EMA_200'].iloc[-2]
    curr_e = df['EMA_200'].iloc[-1]
    ema_cross = (prev_c < prev_e) and (curr_c > curr_e)
    
    if check_pattern and ema_cross:
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
        
        return ema_cross and pattern_detected, pattern_name
    
    return ema_cross, "EMA Crossover"

# ==============================================
# 📊 BACKTEST ENGINE (MULTI-TIMEFRAME)
# ==============================================
def backtest_stock(ticker, years=2, hold_days=[5, 10, 20]):
    print(f"\n📊 Backtesting {ticker} for {years} years...")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365 * years)
    
    # Daily data
    df_daily = yf.download(ticker, start=start_date, end=end_date, interval='1d', progress=False, auto_adjust=True)
    if df_daily.empty or len(df_daily) < 250:
        print(f"  ❌ Insufficient daily data for {ticker}")
        return None
    
    # 1H data
    try:
        df_1h = yf.download(ticker, period='60d', interval='1h', progress=False, auto_adjust=True)
        if df_1h.empty or len(df_1h) < 100:
            df_1h = None
    except:
        df_1h = None
    
    # Resample 1H -> 4H (FIXED: dynamic column handling)
    df_4h = None
    if df_1h is not None and not df_1h.empty:
        try:
            # Ensure column names are clean
            df_1h.columns = df_1h.columns.str.strip()
            # Resample using column indices to avoid KeyError
            df_4h = df_1h.resample('4h').agg({
                df_1h.columns[0]: 'first',
                df_1h.columns[1]: 'max',
                df_1h.columns[2]: 'min',
                df_1h.columns[3]: 'last'
            }).dropna()
            df_4h.columns = ['Open', 'High', 'Low', 'Close']
        except Exception as e:
            print(f"  ⚠️ Could not resample to 4H: {e}")
            df_4h = None
    
    all_signals = []
    
    # Daily signals
    for i in range(250, len(df_daily) - max(hold_days)):
        slice_df = df_daily.iloc[:i+1].copy()
        signal, pattern = analyze_df(slice_df, check_pattern=False)
        if signal:
            entry_price = df_daily['Close'].iloc[i]
            entry_date = df_daily.index[i]
            for days in hold_days:
                exit_idx = min(i + days, len(df_daily) - 1)
                exit_price = df_daily['Close'].iloc[exit_idx]
                return_pct = (exit_price / entry_price - 1) * 100
                all_signals.append({
                    'Ticker': ticker,
                    'Timeframe': 'Daily',
                    'Entry_Date': entry_date,
                    'Exit_Date': df_daily.index[exit_idx],
                    'Pattern': pattern,
                    'Hold_Days': days,
                    'Entry_Price': round(entry_price, 2),
                    'Exit_Price': round(exit_price, 2),
                    'Return_%': round(return_pct, 2),
                    'Win': return_pct > 0
                })
    
    # 4H signals
    if df_4h is not None and not df_4h.empty and len(df_4h) > 50:
        for i in range(50, len(df_4h) - max(hold_days)*4):
            slice_df = df_4h.iloc[:i+1].copy()
            signal, pattern = analyze_df(slice_df, check_pattern=False)
            if signal:
                entry_price = df_4h['Close'].iloc[i]
                entry_date = df_4h.index[i]
                for days in hold_days:
                    exit_idx = min(i + days*4, len(df_4h) - 1)
                    exit_price = df_4h['Close'].iloc[exit_idx]
                    return_pct = (exit_price / entry_price - 1) * 100
                    all_signals.append({
                        'Ticker': ticker,
                        'Timeframe': '4H',
                        'Entry_Date': entry_date,
                        'Exit_Date': df_4h.index[exit_idx],
                        'Pattern': pattern,
                        'Hold_Days': days,
                        'Entry_Price': round(entry_price, 2),
                        'Exit_Price': round(exit_price, 2),
                        'Return_%': round(return_pct, 2),
                        'Win': return_pct > 0
                    })
    
    if not all_signals:
        print(f"  ⚠️ No signals found for {ticker} in {years} years.")
        return pd.DataFrame()
    
    df_res = pd.DataFrame(all_signals)
    print(f"  ✅ Total signals found: {len(all_signals)}")
    
    for days in hold_days:
        subset = df_res[df_res['Hold_Days'] == days]
        if len(subset) > 0:
            win_rate = (subset['Win'].sum() / len(subset)) * 100
            avg_return = subset['Return_%'].mean()
            print(f"    Hold {days} days: {len(subset)} trades, Win Rate: {win_rate:.1f}%, Avg Return: {avg_return:.2f}%")
    
    return df_res

# ==============================================
# 🚀 MAIN
# ==============================================
if __name__ == "__main__":
    print("="*70)
    print("🔥 SPRZ Backtest Engine (Nifty 50 + 4H + Daily - EMA Crossover Only)")
    print("="*70)
    print(f"📊 Scanning {len(NIFTY_50)} stocks for 2 years...")
    print("⏱️ Estimated time: 10-15 minutes\n")
    
    all_results = []
    
    for i, stock in enumerate(NIFTY_50):
        print(f"[{i+1}/{len(NIFTY_50)}] ", end="")
        res = backtest_stock(stock, years=2, hold_days=[5, 10, 20])
        if res is not None and not res.empty:
            all_results.append(res)
    
    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        
        print("\n" + "="*70)
        print("📈 OVERALL BACKTEST SUMMARY (2 Years, Nifty 50)")
        print("="*70)
        
        total_trades_all = len(final_df)
        print(f"\n📊 Total trades across all stocks & timeframes: {total_trades_all}")
        
        for days in [5, 10, 20]:
            subset = final_df[final_df['Hold_Days'] == days]
            if not subset.empty:
                win_rate = (subset['Win'].sum() / len(subset)) * 100
                avg_return = subset['Return_%'].mean()
                max_return = subset['Return_%'].max()
                min_return = subset['Return_%'].min()
                total_trades = len(subset)
                print(f"\n📊 Hold {days} days:")
                print(f"   Total Trades: {total_trades}")
                print(f"   Win Rate: {win_rate:.1f}%")
                print(f"   Avg Return: {avg_return:.2f}%")
                print(f"   Max Return: {max_return:.2f}%")
                print(f"   Min Return: {min_return:.2f}%")
        
        print("\n📊 Timeframe-wise breakdown:")
        for tf in final_df['Timeframe'].unique():
            tf_subset = final_df[final_df['Timeframe'] == tf]
            win_rate = (tf_subset['Win'].sum() / len(tf_subset)) * 100
            avg_return = tf_subset['Return_%'].mean()
            print(f"   {tf}: {len(tf_subset)} trades, Win Rate: {win_rate:.1f}%, Avg Return: {avg_return:.2f}%")
        
        final_df.to_csv('backtest_results.csv', index=False)
        print("\n✅ Full results saved to 'backtest_results.csv'")
    else:
        print("❌ No backtest results generated. Try increasing years or different stocks.")
