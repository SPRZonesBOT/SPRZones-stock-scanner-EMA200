import yfinance as yf
import pandas as pd
import pandas_ta as ta
import warnings
warnings.filterwarnings('ignore')
from datetime import datetime, timedelta

# ==============================================
# 🔥 NIFTY 100 STOCKS (Full List - Technical Only)
# ==============================================
NIFTY_100 = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "BAJFINANCE.NS", "WIPRO.NS", "HCLTECH.NS", "ASIANPAINT.NS", "AXISBANK.NS",
    "LT.NS", "MARUTI.NS", "TITAN.NS", "SUNPHARMA.NS", "ULTRACEMCO.NS",
    "ADANIPORTS.NS", "NTPC.NS", "POWERGRID.NS", "M&M.NS", "TATASTEEL.NS",
    "JSWSTEEL.NS", "TECHM.NS", "INDUSINDBK.NS", "BAJAJFINSV.NS", "HDFCLIFE.NS",
    "SBILIFE.NS", "DRREDDY.NS", "HINDALCO.NS", "EICHERMOT.NS", "COALINDIA.NS",
    "ONGC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "TATACONSUM.NS", "DIVISLAB.NS",
    "UPL.NS", "SHREECEM.NS", "GRASIM.NS", "APOLLOHOSP.NS", "HEROMOTOCO.NS",
    "BAJAJ-AUTO.NS", "ADANIENT.NS", "TATAMOTORS.NS", "VEDL.NS", "AMBUJACEM.NS",
    "CIPLA.NS", "PIDILITIND.NS", "ICICIPRULI.NS", "TATACOMM.NS", "HAL.NS",
    "SIEMENS.NS", "DLF.NS", "MCDOWELL-N.NS", "HAVELLS.NS", "BERGEPAINT.NS",
    "PAGEIND.NS", "COLPAL.NS", "MARICO.NS", "DABUR.NS", "GODREJCP.NS",
    "JUBLFOOD.NS", "MUTHOOTFIN.NS", "SRTRANSFIN.NS", "PEL.NS"
]

# ==============================================
# 📈 TECHNICAL ANALYSIS - ONLY EMA CROSSOVER (NO RESAMPLING)
# ==============================================
def analyze_df(df):
    """Check if price closes above 200 EMA (no pattern check)"""
    if len(df) < 50:
        return False
    
    df = df.copy()
    df['EMA_200'] = ta.ema(df['Close'], length=200)
    if df['EMA_200'].isna().all():
        return False
    
    prev_c = df['Close'].iloc[-2]
    curr_c = df['Close'].iloc[-1]
    prev_e = df['EMA_200'].iloc[-2]
    curr_e = df['EMA_200'].iloc[-1]
    
    # Crossover: previous close < EMA, current close > EMA
    return (prev_c < prev_e) and (curr_c > curr_e)

# ==============================================
# 📊 BACKTEST ENGINE - ONLY DAILY TIMEFRAME
# ==============================================
def backtest_stock(ticker, years=2, hold_days=[5, 10, 20]):
    print(f"📊 Backtesting {ticker} for {years} years...")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365 * years)
    
    # Fetch daily data
    df = yf.download(ticker, start=start_date, end=end_date, interval='1d', progress=False, auto_adjust=True)
    if df.empty or len(df) < 250:
        print(f"  ❌ Insufficient data for {ticker}")
        return None
    
    signals = []
    
    # Rolling window - check each day for signal
    for i in range(250, len(df) - max(hold_days)):
        slice_df = df.iloc[:i+1].copy()
        signal = analyze_df(slice_df)
        
        if signal:
            entry_price = df['Close'].iloc[i]
            entry_date = df.index[i]
            
            for days in hold_days:
                exit_idx = min(i + days, len(df) - 1)
                exit_price = df['Close'].iloc[exit_idx]
                return_pct = (exit_price / entry_price - 1) * 100
                signals.append({
                    'Ticker': ticker,
                    'Entry_Date': entry_date,
                    'Exit_Date': df.index[exit_idx],
                    'Hold_Days': days,
                    'Entry_Price': round(entry_price, 2),
                    'Exit_Price': round(exit_price, 2),
                    'Return_%': round(return_pct, 2),
                    'Win': return_pct > 0
                })
    
    if not signals:
        print(f"  ⚠️ No signals found for {ticker} in {years} years.")
        return None
    
    df_res = pd.DataFrame(signals)
    total_signals = len(df_res['Entry_Date'].unique())
    print(f"  ✅ {total_signals} signals found.")
    
    # Per holding period summary
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
    print("🔥 SPRZ Backtest Engine (Nifty 100 - Daily EMA Crossover Only)")
    print("="*70)
    print(f"📊 Scanning {len(NIFTY_100)} stocks for 2 years...")
    print("⏱️ Estimated time: 5-10 minutes\n")
    
    all_results = []
    
    for i, stock in enumerate(NIFTY_100):
        print(f"[{i+1}/{len(NIFTY_100)}] ", end="")
        res = backtest_stock(stock, years=2, hold_days=[5, 10, 20])
        if res is not None and not res.empty:
            all_results.append(res)
    
    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        
        print("\n" + "="*70)
        print("📈 OVERALL BACKTEST SUMMARY (2 Years, Nifty 100)")
        print("="*70)
        
        total_trades_all = len(final_df)
        print(f"\n📊 Total trades across all stocks: {total_trades_all}")
        
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
        
        # Save to CSV
        final_df.to_csv('backtest_results.csv', index=False)
        print("\n✅ Full results saved to 'backtest_results.csv'")
    else:
        print("❌ No backtest results generated. Try increasing years or different stocks.")
