import yfinance as yf
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta

ticker = "RELIANCE.NS"
end = datetime.now()
start = end - timedelta(days=365*2)

df = yf.download(ticker, start=start, end=end, interval='1d', progress=False)

print(f"Total rows: {len(df)}")
print(df.head())
print(df.tail())

# EMA calculate karo
df['EMA_200'] = ta.ema(df['Close'], length=200)

# Crossover conditions check karo
crossover_dates = []
for i in range(200, len(df)):
    if (df['Close'].iloc[i-1] < df['EMA_200'].iloc[i-1]) and (df['Close'].iloc[i] > df['EMA_200'].iloc[i]):
        crossover_dates.append(df.index[i])

print(f"\nTotal crossovers found: {len(crossover_dates)}")
for d in crossover_dates[:5]:  # Pehle 5 show karo
    print(d)
