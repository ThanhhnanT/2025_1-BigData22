#!/usr/bin/env python3
"""
OHLC 5m Aggregator - Spark Batch Job
Aggregates 1m kline data from Redis into 5m OHLC candles and stores in MongoDB
"""

import os
import json
from datetime import datetime, timedelta, timezone
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, first, last, max as spark_max, min as spark_min, sum as spark_sum
import redis
from pymongo import MongoClient

# Environment variables
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://vuongthanhsaovang:9KviWHBS85W7i4j6@ai-tutor.k6sjnzc.mongodb.net")
MONGO_DB = os.getenv("MONGO_DB", "CRYPTO")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "5m_kline")

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT",
    "XRPUSDT", "DOGEUSDT", "DOTUSDT", "MATICUSDT", "AVAXUSDT",
    "LINKUSDT", "UNIUSDT", "LTCUSDT", "ATOMUSDT", "ETCUSDT"
]

def main():
    spark = SparkSession.builder \
        .appName("OHLC-5m-Aggregator") \
        .getOrCreate()
    
    print(f"🚀 Starting OHLC 5m Aggregator - Spark Job")
    print(f"📊 Symbols to process: {len(SYMBOLS)}")
    
    # Connect to Redis
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True
    )
    
    # Connect to MongoDB
    mongo_client = MongoClient(MONGO_URI)
    mongo_db = mongo_client[MONGO_DB]
    mongo_collection = mongo_db[MONGO_COLLECTION]
    
    # Create index
    mongo_collection.create_index([
        ("symbol", 1),
        ("interval", 1),
        ("openTime", 1)
    ], unique=True)
    
    # Calculate time window
    now = datetime.now(timezone.utc)
    current_minute = now.minute
    rounded_minute = (current_minute // 5) * 5
    window_end = now.replace(minute=rounded_minute, second=0, microsecond=0)
    window_start = window_end - timedelta(minutes=5)
    
    start_timestamp = int(window_start.timestamp() * 1000)
    end_timestamp = int(window_end.timestamp() * 1000)
    
    print(f"📅 Time window: {window_start} to {window_end}")
    print(f"   Timestamp: {start_timestamp} - {end_timestamp}")
    
    # Collect all kline data from Redis for all symbols
    all_klines = []
    
    for symbol in SYMBOLS:
        index_key = f"crypto:{symbol}:1m:index"
        
        # Get timestamps in range
        timestamps = redis_client.zrangebyscore(
            index_key,
            start_timestamp,
            end_timestamp
        )
        
        if not timestamps:
            print(f"  ⚠️  No data for {symbol}")
            continue
        
        # Fetch kline data
        for ts in sorted(timestamps):
            key = f"crypto:{symbol}:1m:{ts}"
            data = redis_client.get(key)
            if data:
                kline = json.loads(data)
                if kline.get("x", False):  # Only closed candles
                    kline["symbol"] = symbol
                    all_klines.append(kline)
    
    redis_client.close()
    
    if not all_klines:
        print("❌ No kline data found")
        spark.stop()
        mongo_client.close()
        return
    
    print(f"✅ Loaded {len(all_klines)} 1m klines from Redis")
    
    # Convert to Spark DataFrame
    df = spark.createDataFrame(all_klines)
    
    # Convert string columns to appropriate types
    df = df.withColumn("open", col("open").cast("double")) \
           .withColumn("high", col("high").cast("double")) \
           .withColumn("low", col("low").cast("double")) \
           .withColumn("close", col("close").cast("double")) \
           .withColumn("volume", col("volume").cast("double")) \
           .withColumn("quoteVolume", col("quoteVolume").cast("double")) \
           .withColumn("trades", col("trades").cast("integer")) \
           .withColumn("openTime", col("openTime").cast("long")) \
           .withColumn("closeTime", col("closeTime").cast("long"))
    
    # Calculate 5m window start time for grouping (floor to 5m intervals)
    df = df.withColumn(
        "window_start",
        (col("openTime") / 300000).cast("long") * 300000
    )
    
    # Group by symbol and 5m window, aggregate OHLC
    aggregated_df = df.groupBy("symbol", "window_start").agg(
        first("open").alias("open"),
        spark_max("high").alias("high"),
        spark_min("low").alias("low"),
        last("close").alias("close"),
        spark_sum("volume").alias("volume"),
        spark_sum("quoteVolume").alias("quoteVolume"),
        spark_sum("trades").alias("trades"),
        first("openTime").alias("openTime"),
        last("closeTime").alias("closeTime")
    )
    
    # Filter only complete 5m windows (should have 5 candles ideally, but we'll check count)
    # For now, we'll process all that we have
    
    # Convert to list of documents
    results = aggregated_df.collect()
    
    print(f"📊 Aggregated into {len(results)} 5m candles")
    
    # Write to MongoDB
    total_inserted = 0
    total_skipped = 0
    
    for row in results:
        # Check if already exists
        existing = mongo_collection.find_one({
            "symbol": row["symbol"],
            "interval": "5m",
            "openTime": row["openTime"]
        })
        
        if existing:
            print(f"  ℹ️  5m OHLC already exists for {row['symbol']} (openTime: {row['openTime']})")
            total_skipped += 1
            continue
        
        mongo_doc = {
            "symbol": row["symbol"],
            "interval": "5m",
            "openTime": row["openTime"],
            "closeTime": row["closeTime"],
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"],
            "volume": row["volume"],
            "quoteVolume": row["quoteVolume"],
            "trades": row["trades"],
            "createdAt": datetime.now(),
            "source": "spark_5m_aggregator"
        }
        
        try:
            mongo_collection.update_one(
                {
                    "symbol": mongo_doc["symbol"],
                    "interval": mongo_doc["interval"],
                    "openTime": mongo_doc["openTime"]
                },
                {"$set": mongo_doc},
                upsert=True
            )
            print(f"  ✅ {row['symbol']}: 5m OHLC saved (O:{row['open']:.4f}, H:{row['high']:.4f}, L:{row['low']:.4f}, C:{row['close']:.4f})")
            total_inserted += 1
        except Exception as e:
            print(f"  ❌ Error saving {row['symbol']}: {e}")
    
    print(f"\n✅ Completed! Inserted: {total_inserted}, Skipped: {total_skipped}")
    
    # Cleanup
    spark.stop()
    mongo_client.close()

if __name__ == "__main__":
    main()


