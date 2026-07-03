import yfinance as yf
import pandas as pd
import pandas as ta
import warnings
warnings.filterwarnings('ignore')
from datetime import datetime, timedelta

# ==============================================
# 🔥 SAME TECHNICAL LOGIC (Jo scanner mein hai)
# ==============================================
def analyze_df(df):
    if len(df) < 50:
        return False, ''
    
    df = df.copy()
    df['EMA_200'] = ta.ema(df['Close'], length=200)
    if df['EMA_200'].isna().all():
        return False, ''
    
    # Crossover
    prev_c = df['Close'].iloc[-2]
    curr_c = df['Close'].iloc[-1]
    prev_e = df['EMA_200'].iloc[-2]
    curr_e = df['EMA_200'].iloc[-1]
    ema_cross = (prev_c < prev_e) and (curr_c > curr_e)
    
    # Pattern
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
    
    return (ema_cross and pattern_detected), pattern_name

# ==============================================
# 📊 BACKTEST ENGINE
# ==============================================
def backtest_stock(ticker, years=3, hold_days=[5, 10, 20]):
    print(f"\n📊 Backtesting {ticker} for {years} years...")
    
    # Data fetch
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365 * years)
    df = yf.download(ticker, start=start_date, end=end_date, interval='1d', progress=False, auto_adjust=True)
    
    if df.empty or len(df) < 250:
        print(f"  ❌ Insufficient data for {ticker}")
        return None
    
    results = []
    total_signals = 0
    
    # Rolling window simulation
    for i in range(250, len(df) - max(hold_days)):
        slice_df = df.iloc[:i+1].copy()
        signal, pattern = analyze_df(slice_df)
        
        if signal:
            total_signals += 1
            entry_price = df['Close'].iloc[i]
            entry_date = df.index[i]
            
            # Check returns for different holding periods
            for days in hold_days:
                exit_idx = min(i + days, len(df) - 1)
                exit_price = df['Close'].iloc[exit_idx]
                exit_date = df.index[exit_idx]
                
                return_pct = (exit_price / entry_price - 1) * 100
                results.append({
                    'Ticker': ticker,
                    'Entry_Date': entry_date,
                    'Exit_Date': exit_date,
                    'Pattern': pattern,
                    'Hold_Days': days,
                    'Entry_Price': round(entry_price, 2),
                    'Exit_Price': round(exit_price, 2),
                    'Return_%': round(return_pct, 2),
                    'Win': return_pct > 0
                })
    
    if not results:
        print(f"  ⚠️ No signals found for {ticker} in {years} years.")
        return pd.DataFrame()
    
    df_res = pd.DataFrame(results)
    
    # Summary
    print(f"  ✅ Total signals found: {total_signals}")
    for days in hold_days:
        subset = df_res[df_res['Hold_Days'] == days]
        win_rate = (subset['Win'].sum() / len(subset)) * 100 if len(subset) > 0 else 0
        avg_return = subset['Return_%'].mean() if len(subset) > 0 else 0
        print(f"    Hold {days} days: {len(subset)} trades, Win Rate: {win_rate:.1f}%, Avg Return: {avg_return:.2f}%")
    
    return df_res

# ==============================================
# 🚀 RUN BACKTEST (Top 5 Nifty Stocks)
# ==============================================
if __name__ == "__main__":
    # 🔥 Test ke liye top 5 stocks (Nifty 50 se)
    test_stocks = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "HINDUNILVR.NS"]
    
    all_results = []
    
    for stock in test_stocks:
        res = backtest_stock(stock, years=3, hold_days=[5, 10, 20])
        if res is not None and not res.empty:
            all_results.append(res)
    
    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        
        print("\n" + "="*50)
        print("📈 OVERALL BACKTEST SUMMARY (3 Years)")
        print("="*50)
        
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
        
        # Export to CSV
        final_df.to_csv('backtest_results.csv', index=False)
        print("\n✅ Full results saved to 'backtest_results.csv'")
    else:
        print("❌ No backtest results generated.")
