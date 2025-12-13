import yfinance as yf
import pandas as pd
import time
import os
from datetime import datetime, timezone
import random

TICKERS = ['BTC-USD', 'ETH-USD', 'XRP-USD', 'LTC-USD', 'BCH-USD', 'ADA-USD', 'DOT-USD', 'LINK-USD', 'XLM-USD', 'DOGE-USD']
OUTPUT_DIR = "streaming_test_data"
SLEEP_INTERVAL = 10
NUM_FILES = 60
os.makedirs(OUTPUT_DIR, exist_ok=True)

try:
    for i in range(NUM_FILES):
        rows = []
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        for ticker in TICKERS:
            try:
                stock_info = yf.Ticker(ticker).info
                price = stock_info.get('regularMarketPrice', 0.0)
                if price == 0.0:
                    price = stock_info.get('currentPrice', 0.0)
                volume = stock_info.get('volume', None)
                if volume is None:
                    volume = random.uniform(1000, 5000)

                rows.append({
                    'timestamp': timestamp,
                    'ticker': ticker,
                    'price': price,
                    'volume': volume
                })
            except Exception as e:
                print(f"Error fetching data for {ticker}: {e}")
        
        if not rows:
            print("No data fetched for any ticker. Skipping this iteration.")
            time.sleep(SLEEP_INTERVAL)
            continue

        df = pd.DataFrame(rows)
        df = df[['timestamp', 'ticker', 'price', 'volume']]
        filename = f"crypto_data_{int(time.time())}.csv"
        full_path = os.path.join(OUTPUT_DIR, filename)
        df.to_csv(full_path, index=False, header=True)

        if i < NUM_FILES - 1:
            time.sleep(SLEEP_INTERVAL)

except KeyboardInterrupt:
    print("Data generation interrupted by user.")

print("Data generation completed.")

        