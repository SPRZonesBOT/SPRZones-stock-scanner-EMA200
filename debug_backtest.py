import yfinance as yf
import pandas as pd
import pandas_ta as ta
import warnings
warnings.filterwarnings('ignore')
from datetime import datetime, timedelta

# ==============================================
# 🔥 TOP 10 STOCKS
# ==============================================
TEST_STOCKS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS"
]

# ==============================================
# 📈 SIMPLE EMA ANALYSIS (No patterns)
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
        return False
    
    df = flatten_multiindex(df.copy())
    
    # EMA 200 with fallback
    try:
        df['EMA_200'] = ta.ema(df['Close'], length=200)
    except:
        df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    if df['EMA_200'].isna().all():
        return False
    
    # Crossover
    prev_c = df['Close'].iloc[-2]
    curr_c = df['Close'].iloc[-1]
    prev_e = df['EMA_200'].iloc[-2]
    curr_e = df['EMA_200'].iloc[-1]
    return (prev_c < prev_e) and (curr_c > curr_e)

# ==============================================
# 📊 BACKTEST
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
    trades = []
    
    for i in range(250, len(df) - max(hold_days)):
        slice_df = df.iloc[:i+1].copy()
        if analyze_df(slice_df):
            entry_price = df['Close'].iloc[i]
            entry_date = df.index[i]
            for days in hold_days:
                exit_idx = min(i + days, len(df) - 1)
                exit_price = df['Close'].iloc[exit_idx]
                return_pct = (exit_price / entry_price - 1) * 100
                trades.append({
                    'Ticker': ticker,
                    'Entry_Date': entry_date,
                    'Hold_Days': days,
                    'Return_%': return_pct,
                    'Win': return_pct > 0
                })
    
    print(f" ✅ {len(trades)//len(hold_days)} signals")
    return pd.DataFrame(trades) if trades else None

# ==============================================
# 🚀 MAIN
# ==============================================
if __name__ == "__main__":
    print("="*70)
    print("🔥 SIMPLE BACKTEST: EMA Crossover Only")
    print(f"📊 Testing {len(TEST_STOCKS)} stocks for 3 years")
    print("="*70)
    
    all_dfs = []
    for i, stock in enumerate(TEST_STOCKS):
        print(f"[{i+1}/{len(TEST_STOCKS)}] ", end="")
        res = backtest_stock(stock, years=3, hold_days=[5, 10, 20])
        if res is not None:
            all_dfs.append(res)
    
    if all_dfs:
        df = pd.concat(all_dfs, ignore_index=True)
        total_trades = len(df)
        print(f"\n📊 Total Trades: {total_trades}")
        for days in [5, 10, 20]:
            subset = df[df['Hold_Days'] == days]
            if not subset.empty:
                win_rate = (subset['Win'].sum() / len(subset)) * 100
                avg_return = subset['Return_%'].mean()
                print(f"   Hold {days}d: {len(subset)} trades, Win Rate: {win_rate:.1f}%, Avg: {avg_return:.2f}%")
        df.to_csv('backtest_ema_simple.csv', index=False)
        print("\n✅ Results saved to 'backtest_ema_simple.csv'")
    else:
        print("❌ No results.")
