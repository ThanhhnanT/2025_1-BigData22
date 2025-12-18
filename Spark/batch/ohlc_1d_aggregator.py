#!/usr/bin/env python3
"""
OHLC 1d Aggregator - Spark Batch Job
Aggregates 1h kline data from MongoDB into 1d OHLC candles
"""

import os
from datetime import datetime, timedelta, timezone
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, first, last, max as spark_max, min as spark_min, sum as spark_sum
from pymongo import MongoClient
from pymongo.errors import OperationFailure

# Environment variables (local MongoDB)
MONGO_URI = os.getenv("MONGO_URI", "mongodb://root:8WcVPD9QHx@192.168.49.2:30376/")
MONGO_DB = os.getenv("MONGO_DB", "CRYPTO")
SOURCE_COLLECTION = "1h_kline"
TARGET_COLLECTION = "1d_kline"

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT",
    "XRPUSDT", "DOGEUSDT", "DOTUSDT", "MATICUSDT", "AVAXUSDT",
    "LINKUSDT", "UNIUSDT", "LTCUSDT", "ATOMUSDT", "ETCUSDT"
]

def main():
    # Initialize Spark Session
    spark = SparkSession.builder \
        .appName("OHLC-1d-Aggregator") \
        .getOrCreate()
    
    print(f"🚀 Starting OHLC 1d Aggregator - Spark Job")
    print(f"📊 Symbols to process: {len(SYMBOLS)}")
    
    # Connect to MongoDB
    mongo_client = MongoClient(MONGO_URI)
    mongo_db = mongo_client[MONGO_DB]
    source_collection = mongo_db[SOURCE_COLLECTION]
    target_collection = mongo_db[TARGET_COLLECTION]
    
    # Create index (handle case where index already exists)
    index_fields = [("symbol", 1), ("interval", 1), ("openTime", 1)]
    existing_indexes = target_collection.list_indexes()
    index_exists = False
    
    for idx in existing_indexes:
        idx_key = idx.get("key", {})
        if (
            idx_key.get("symbol") == 1 and
            idx_key.get("interval") == 1 and
            idx_key.get("openTime") == 1
        ):
            index_exists = True
            print(f"  ℹ️  1d index already exists: {idx.get('name', 'unnamed')}")
            break
    
    if not index_exists:
        try:
            target_collection.create_index(
                index_fields,
                unique=True,
                name="symbol_interval_openTime_unique"
            )
            print("  ✅ 1d index created successfully")
        except OperationFailure as e:
            if e.code == 85:
                print("  ℹ️  1d index already exists with different name, skipping creation")
            else:
                print(f"  ⚠️  MongoDB 1d index creation error (code {e.code}): {e}")
        except Exception as e:
            print(f"  ⚠️  Unexpected error creating 1d index: {e}")
    
    # Calculate time window (last complete day)
    now = datetime.now(timezone.utc)
    window_end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_start = window_end - timedelta(days=1)
    
    start_timestamp = int(window_start.timestamp() * 1000)
    end_timestamp = int(window_end.timestamp() * 1000)
    
    print(f"📅 Time window: {window_start} to {window_end}")
    print(f"   Timestamp: {start_timestamp} - {end_timestamp}")
    
    # Load 1h data from MongoDB for all symbols
    query = {
        "symbol": {"$in": SYMBOLS},
        "interval": "1h",
        "openTime": {"$gte": start_timestamp, "$lt": end_timestamp}
    }
    
    klines = list(source_collection.find(query))
    
    if not klines:
        print("❌ No 1h kline data found")
        spark.stop()
        mongo_client.close()
        return
    
    print(f"✅ Loaded {len(klines)} 1h klines from MongoDB")
    
    # Convert to Spark DataFrame
    df = spark.createDataFrame(klines)
    
    # Ensure proper types
    df = df.withColumn("open", col("open").cast("double")) \
           .withColumn("high", col("high").cast("double")) \
           .withColumn("low", col("low").cast("double")) \
           .withColumn("close", col("close").cast("double")) \
           .withColumn("volume", col("volume").cast("double")) \
           .withColumn("quoteVolume", col("quoteVolume").cast("double")) \
           .withColumn("trades", col("trades").cast("integer")) \
           .withColumn("openTime", col("openTime").cast("long")) \
           .withColumn("closeTime", col("closeTime").cast("long"))
    
    # Calculate 1d window start time for grouping (floor to 1d intervals)
    df = df.withColumn(
        "window_start",
        (col("openTime") / 86400000).cast("long") * 86400000
    )
    
    # Group by symbol and 1d window, aggregate OHLC
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
    
    # Convert to list of documents
    results = aggregated_df.collect()
    
    print(f"📊 Aggregated into {len(results)} 1d candles")
    
    # Write to MongoDB
    total_inserted = 0
    total_skipped = 0
    
    for row in results:
        # Check if already exists
        existing = target_collection.find_one({
            "symbol": row["symbol"],
            "interval": "1d",
            "openTime": row["openTime"]
        })
        
        if existing:
            print(f"  ℹ️  1d OHLC already exists for {row['symbol']} (openTime: {row['openTime']})")
            total_skipped += 1
            continue
        
        mongo_doc = {
            "symbol": row["symbol"],
            "interval": "1d",
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
            "source": "spark_1d_aggregator"
        }
        
        try:
            target_collection.update_one(
                {
                    "symbol": mongo_doc["symbol"],
                    "interval": mongo_doc["interval"],
                    "openTime": mongo_doc["openTime"]
                },
                {"$set": mongo_doc},
                upsert=True
            )
            print(f"  ✅ {row['symbol']}: 1d OHLC saved (O:{row['open']:.4f}, H:{row['high']:.4f}, L:{row['low']:.4f}, C:{row['close']:.4f})")
            total_inserted += 1
        except Exception as e:
            print(f"  ❌ Error saving {row['symbol']}: {e}")
    
    print(f"\n✅ Completed! Inserted: {total_inserted}, Skipped: {total_skipped}")
    
    # Cleanup
    spark.stop()
    mongo_client.close()

if __name__ == "__main__":
    main()


