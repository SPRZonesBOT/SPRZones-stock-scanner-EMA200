import yfinance as yf
import pandas as pd
import pandas_ta as ta
import warnings
warnings.filterwarnings('ignore')
from datetime import datetime, timedelta

# ==============================================
# 🔥 SAHI SYMBOLS (DOT .NS ke saath)
# ==============================================
TEST_STOCKS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS"
]

# ==============================================
# 📈 TECHNICAL LOGIC (EMA 200 Crossover Only)
# ==============================================
def analyze_df(df):
    if len(df) < 50:
        return False
    
    df = df.copy()
    df['EMA_200'] = ta.ema(df['Close'], length=200)
    if df['EMA_200'].isna().all():
        return False
    
    # Crossover: Close was below EMA yesterday, Close is above EMA today
    prev_c = df['Close'].iloc[-2]
    curr_c = df['Close'].iloc[-1]
    prev_e = df['EMA_200'].iloc[-2]
    curr_e = df['EMA_200'].iloc[-1]
    
    return (prev_c < prev_e) and (curr_c > curr_e)

# ==============================================
# 📊 BACKTEST ENGINE
# ==============================================
def backtest_stock(ticker, years=2, hold_days=[5, 10, 20]):
    print(f"  Backtesting {ticker} for {years} years...")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365 * years)
    
    # Daily data fetch
    df = yf.download(ticker, start=start_date, end=end_date, 
                     interval='1d', progress=False, auto_adjust=True)
    
    if df.empty or len(df) < 250:
        print(f"    ❌ Insufficient data (got {len(df)} candles)")
        return None
    
    results = []
    
    # Rolling window simulation
    for i in range(250, len(df) - max(hold_days)):
        slice_df = df.iloc[:i+1].copy()
        
        if analyze_df(slice_df):
            entry_price = df['Close'].iloc[i]
            entry_date = df.index[i]
            
            for days in hold_days:
                exit_idx = min(i + days, len(df) - 1)
                exit_price = df['Close'].iloc[exit_idx]
                exit_date = df.index[exit_idx]
                
                return_pct = (exit_price / entry_price - 1) * 100
                results.append({
                    'Ticker': ticker,
                    'Entry_Date': entry_date,
                    'Exit_Date': exit_date,
                    'Hold_Days': days,
                    'Entry_Price': round(entry_price, 2),
                    'Exit_Price': round(exit_price, 2),
                    'Return_%': round(return_pct, 2),
                    'Win': return_pct > 0
                })
    
    if not results:
        print(f"    ⚠️ No signals found")
        return None
    
    print(f"    ✅ Total signals: {len(results)}")
    
    # Summary per holding period
    df_res = pd.DataFrame(results)
    for days in hold_days:
        subset = df_res[df_res['Hold_Days'] == days]
        if len(subset) > 0:
            win_rate = (subset['Win'].sum() / len(subset)) * 100
            avg_return = subset['Return_%'].mean()
            print(f"      Hold {days} days: {len(subset)} trades, Win Rate: {win_rate:.1f}%, Avg Return: {avg_return:.2f}%")
    
    return df_res

# ==============================================
# 🚀 MAIN
# ==============================================
if __name__ == "__main__":
    print("="*60)
    print("🔥 SPRZ Backtest (Daily EMA 200 Crossover)")
    print("📊 Testing 10 Nifty 50 stocks for 2 years")
    print("="*60)
    
    all_results = []
    for stock in TEST_STOCKS:
        res = backtest_stock(stock, years=2, hold_days=[5, 10, 20])
        if res is not None:
            all_results.append(res)
    
    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        
        print("\n" + "="*60)
        print("📈 OVERALL SUMMARY (2 Years, 10 Nifty Stocks)")
        print("="*60)
        
        total_trades = len(final_df)
        print(f"\n📊 Total Trades: {total_trades}")
        
        for days in [5, 10, 20]:
            subset = final_df[final_df['Hold_Days'] == days]
            if not subset.empty:
                win_rate = (subset['Win'].sum() / len(subset)) * 100
                avg_return = subset['Return_%'].mean()
                max_return = subset['Return_%'].max()
                min_return = subset['Return_%'].min()
                print(f"\n📊 Hold {days} days:")
                print(f"   Trades: {len(subset)}")
                print(f"   Win Rate: {win_rate:.1f}%")
                print(f"   Avg Return: {avg_return:.2f}%")
                print(f"   Max Return: {max_return:.2f}%")
                print(f"   Min Return: {min_return:.2f}%")
        
        # Save CSV
        final_df.to_csv('backtest_results_fixed.csv', index=False)
        print("\n✅ Full results saved to 'backtest_results_fixed.csv'")
    else:
        print("❌ No backtest results. Try increasing years or different stocks.")
