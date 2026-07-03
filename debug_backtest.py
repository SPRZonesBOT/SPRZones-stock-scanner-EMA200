import yfinance as yf
import pandas as pd
import pandas_ta as ta
import warnings
warnings.filterwarnings('ignore')
from datetime import datetime, timedelta

print("="*60)
print("🔥 DEBUG: EMA 200 Crossover Check (RELIANCE.NS)")
print("="*60)

# Fetch 2 years daily data
end_date = datetime.now()
start_date = end_date - timedelta(days=730)

ticker = "RELIANCE.NS"
df = yf.download(ticker, start=start_date, end=end_date, interval='1d', progress=False)

print(f"\n📊 Data shape: {df.shape}")
print(f"📊 Columns: {df.columns.tolist()}")
print(f"📊 First 2 rows:\n{df.head(2)}")
print(f"📊 Last 2 rows:\n{df.tail(2)}")

# Calculate EMA 200
df['EMA_200'] = ta.ema(df['Close'], length=200)
print(f"\n📊 EMA_200 calculated. NaN count: {df['EMA_200'].isna().sum()}")

# Remove NaN rows
df_clean = df.dropna(subset=['EMA_200'])
print(f"📊 Clean rows (with EMA): {len(df_clean)}")

# Find crossovers
signals = []
crossovers = []

for i in range(1, len(df_clean)):
    prev_close = df_clean['Close'].iloc[i-1]
    curr_close = df_clean['Close'].iloc[i]
    prev_ema = df_clean['EMA_200'].iloc[i-1]
    curr_ema = df_clean['EMA_200'].iloc[i]
    
    # Crossover: Close was below EMA, now above EMA
    if (prev_close < prev_ema) and (curr_close > curr_ema):
        crossovers.append({
            'Date': df_clean.index[i],
            'Close': curr_close,
            'EMA_200': curr_ema,
            'Prev_Close': prev_close,
            'Prev_EMA': prev_ema
        })

print(f"\n✅ Total crossovers found: {len(crossovers)}")

if crossovers:
    print("\n📈 Crossover Details (Last 5):")
    for c in crossovers[-5:]:
        print(f"  {c['Date'].strftime('%Y-%m-%d')}: Close={c['Close']:.2f}, EMA={c['EMA_200']:.2f}, Prev Close={c['Prev_Close']:.2f}, Prev EMA={c['Prev_EMA']:.2f}")
    
    # Also show first 5
    print("\n📈 First 5 Crossovers:")
    for c in crossovers[:5]:
        print(f"  {c['Date'].strftime('%Y-%m-%d')}: Close={c['Close']:.2f}, EMA={c['EMA_200']:.2f}")
else:
    print("\n⚠️ No crossovers found. Check if data is correct.")
    print("💡 Tips:")
    print("   - Make sure you have at least 200 trading days of data")
    print("   - Try increasing years to 3 or 4")
    print("   - Check if ticker symbol is correct (e.g., RELIANCE.NS)")

# Save to CSV for inspection
if crossovers:
    pd.DataFrame(crossovers).to_csv('debug_crossovers.csv', index=False)
    print("\n✅ Crossovers saved to 'debug_crossovers.csv'")
