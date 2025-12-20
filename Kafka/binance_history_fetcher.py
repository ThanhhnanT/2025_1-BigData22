#!/usr/bin/env python3
"""
Binance History Fetcher
Fetch historical kline data from Binance API and save to MongoDB collections
"""

import os
import time
import json
import requests
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from pymongo.operations import UpdateOne
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import redis

MONGO_URI = os.getenv("MONGO_URI", "mongodb://root:8WcVPD9QHx@my-mongo-mongodb.crypto-infra.svc.cluster.local:27017/")
MONGO_DB = os.getenv("MONGO_DB", "CRYPTO")
YEARS_BACK = int(os.getenv("YEARS_BACK", "1"))
RESUME_FROM_EXISTING = os.getenv("RESUME_FROM_EXISTING", "true").lower() == "true"  # Continue from last saved data

REDIS_HOST = os.getenv("REDIS_HOST", "my-redis-master.crypto-infra.svc.cluster.local")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "123456")

# Base symbols from producer file (will be converted to full symbols)
BASE_SYMBOLS = [
    "BTC",   
    "ETH",   
    "BNB",  
    "SOL",   # Solana
    "ADA",   # Cardano
    "XRP",   # Ripple
    "DOGE",  # Dogecoin
    "DOT",   # Polkadot
    "MATIC", # Polygon
    "AVAX",  # Avalanche
    "LINK",  # Chainlink
    "UNI",   # Uniswap
    "LTC",   # Litecoin
    "ATOM",  # Cosmos
    "ETC",
]

SYMBOLS = [f"{symbol}USDT" for symbol in BASE_SYMBOLS]

INTERVALS = ["1m", "5m", "1h", "4h", "1d"]

# Collection mapping
# Note: 1m interval is saved to Redis, not MongoDB
COLLECTION_MAP = {
    "1m": None,  # Saved to Redis, not MongoDB
    "5m": "5m_kline",
    "1h": "1h_kline",
    "4h": "4h_kline",
    "1d": "1d_kline",
}

API_URL = "https://api.binance.com/api/v3/klines"
LIMIT = 1000 
RATE_LIMIT_DELAY = 0.1  # 100ms between requests (reduced for speed)
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
BATCH_SIZE = 1000  # MongoDB bulk write batch size
MAX_WORKERS = 4  # Number of parallel workers for fetching


def sleep(ms: int):
    """Sleep for specified milliseconds"""
    time.sleep(ms / 1000.0)


def fetch_candles(symbol: str, interval: str, start_time: int, end_time: int) -> List[List]:
    """
    Fetch candles from Binance API
    
    Args:
        symbol: Trading pair symbol (e.g., BTCUSDT)
        interval: Kline interval (5m, 1h, 5h, 1d)
        start_time: Start timestamp in milliseconds
        end_time: End timestamp in milliseconds
    
    Returns:
        List of kline data arrays
    """
    url = f"{API_URL}?symbol={symbol}&interval={interval}&limit={LIMIT}&startTime={start_time}&endTime={end_time}"
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                print(f"  ⚠️  Request error (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                time.sleep(RETRY_DELAY * (attempt + 1))  # Exponential backoff
            else:
                print(f"  ❌ Failed after {MAX_RETRIES} attempts: {e}")
                raise
    
    return []


def parse_candle(kline: List, symbol: str, interval: str) -> Dict:
    """
    Parse Binance kline array into MongoDB document
    
    Binance kline format:
    [
        0: openTime,
        1: open,
        2: high,
        3: low,
        4: close,
        5: volume,
        6: closeTime,
        7: quoteVolume,
        8: trades,
        9: takerBuyBaseVolume,
        10: takerBuyQuoteVolume,
        11: ignore
    ]
    """
    return {
        "symbol": symbol,
        "interval": interval,
        "openTime": kline[0],
        "closeTime": kline[6],
        "openTimeISO": datetime.fromtimestamp(kline[0] / 1000, tz=timezone.utc).isoformat(),
        "closeTimeISO": datetime.fromtimestamp(kline[6] / 1000, tz=timezone.utc).isoformat(),
        "open": float(kline[1]),
        "high": float(kline[2]),
        "low": float(kline[3]),
        "close": float(kline[4]),
        "volume": float(kline[5]),
        "quoteVolume": float(kline[7]),
        "trades": int(kline[8]),
        "savedAt": datetime.now(timezone.utc),
        "source": "binance_history_fetcher"
    }


def save_to_mongodb(collection, candles: List[Dict], symbol: str, interval: str) -> tuple:
    """
    Save candles to MongoDB with bulk upsert (much faster than individual updates)
    
    Returns:
        (inserted_count, skipped_count)
    """
    if not candles:
        return 0, 0
    
    inserted = 0
    skipped = 0
    
    try:
        # Prepare bulk operations using UpdateOne
        operations = []
        for candle in candles:
            operations.append(
                UpdateOne(
                    {
                        "symbol": candle["symbol"],
                        "interval": candle["interval"],
                        "openTime": candle["openTime"]
                    },
                    {"$set": candle},
                    upsert=True
                )
            )
        
        # Execute bulk write
        result = collection.bulk_write(operations, ordered=False)
        inserted = result.upserted_count + (result.modified_count if result.modified_count else 0)
        skipped = len(candles) - inserted
        
    except Exception as e:
        # Fallback to individual writes if bulk fails
        print(f"  ⚠️  Bulk write failed, falling back to individual writes: {e}")
        for candle in candles:
            try:
                result = collection.update_one(
                    {
                        "symbol": candle["symbol"],
                        "interval": candle["interval"],
                        "openTime": candle["openTime"]
                    },
                    {"$set": candle},
                    upsert=True
                )
                if result.upserted_id:
                    inserted += 1
                else:
                    skipped += 1
            except DuplicateKeyError:
                skipped += 1
            except Exception as e2:
                print(f"  ❌ Error saving candle for {symbol} {interval} (openTime: {candle['openTime']}): {e2}")
    
    return inserted, skipped


def get_latest_timestamp(collection, symbol: str, interval: str) -> Optional[int]:
    """
    Get the latest openTime timestamp for a symbol/interval in MongoDB
    
    Returns:
        Latest openTime timestamp in milliseconds, or None if no data exists
    """
    try:
        latest = collection.find_one(
            {"symbol": symbol, "interval": interval},
            sort=[("openTime", -1)]
        )
        if latest and "openTime" in latest:
            return latest["openTime"]
    except Exception as e:
        print(f"  ⚠️  Error checking existing data: {e}")
    return None


def get_latest_timestamp_from_redis(redis_client, symbol: str) -> Optional[int]:
    """
    Get the latest openTime timestamp for a symbol from Redis (1m interval)
    
    Returns:
        Latest openTime timestamp in milliseconds, or None if no data exists
    """
    try:
        index_key = f"crypto:{symbol}:1m:index"
        # Get the highest score (latest timestamp) from sorted set
        timestamps = redis_client.zrange(index_key, -1, -1, withscores=True)
        if timestamps:
            return int(timestamps[0][1])  # Return the score (timestamp)
    except Exception as e:
        print(f"  ⚠️  Error checking Redis data: {e}")
    return None


def save_to_redis(redis_client, candles: List[Dict], symbol: str) -> tuple:
    """
    Save 1m candles to Redis (same format as redis_consumer.py)
    
    Args:
        redis_client: Redis client instance
        candles: List of candle dictionaries
        symbol: Trading pair symbol
    
    Returns:
        (saved_count, skipped_count)
    """
    if not candles:
        return 0, 0
    
    saved = 0
    skipped = 0
    
    try:
        for candle in candles:
            open_time = candle["openTime"]
            close_time = candle["closeTime"]
            
            # Key format: crypto:{symbol}:1m:{openTime}
            key = f"crypto:{symbol}:1m:{open_time}"
            
            # Format value (same as redis_consumer.py)
            value = {
                "symbol": symbol,
                "interval": "1m",
                "openTime": open_time,
                "closeTime": close_time,
                "open": candle["open"],
                "high": candle["high"],
                "low": candle["low"],
                "close": candle["close"],
                "volume": candle["volume"],
                "quoteVolume": candle["quoteVolume"],
                "trades": candle["trades"],
                "x": True,  # Historical data is always closed
                "updatedAt": datetime.now().isoformat()
            }
            
            # Save candle with TTL 24h
            redis_client.setex(
                key,
                86400,  # 24 hours
                json.dumps(value)
            )
            
            # Add to index (sorted set)
            index_key = f"crypto:{symbol}:1m:index"
            redis_client.zadd(index_key, {str(open_time): open_time})
            redis_client.expire(index_key, 86400 * 7)  # 7 days TTL for index
            
            # Update latest
            latest_key = f"crypto:{symbol}:1m:latest"
            redis_client.setex(latest_key, 86400, json.dumps(value))
            
            saved += 1
        
    except Exception as e:
        print(f"  ❌ Error saving to Redis: {e}")
        skipped = len(candles)
        saved = 0
    
    return saved, skipped


def fetch_and_save_history(symbol: str, interval: str, collection=None, redis_client=None, years_back: int = 1, resume_from_existing: bool = True):
    """
    Fetch historical data for a symbol and interval, save to MongoDB or Redis
    
    Args:
        symbol: Trading pair symbol
        interval: Kline interval
        collection: MongoDB collection (None for 1m interval)
        redis_client: Redis client (required for 1m interval)
        years_back: Number of years of history to fetch (ignored for 1m, uses 1 day)
        resume_from_existing: If True, continue from last saved timestamp
    """
    print(f"\n📊 Fetching {symbol} ({interval})...")
    
    # Special handling for 1m interval: fetch 1 day and save to Redis
    if interval == "1m":
        if not redis_client:
            print(f"  ❌ Redis client required for 1m interval")
            return 0, 0, 0
        
        # Calculate time range: 1 day back
        now = datetime.now(timezone.utc)
        end_timestamp = int(now.timestamp() * 1000)
        start_date = now - timedelta(days=1)
        start_timestamp = int(start_date.timestamp() * 1000)
        
        # Check if we have existing data in Redis
        if resume_from_existing:
            latest_timestamp = get_latest_timestamp_from_redis(redis_client, symbol)
            if latest_timestamp and latest_timestamp >= start_timestamp:
                # Continue from the next candle after the latest one
                start_timestamp = latest_timestamp + 1
                start_date = datetime.fromtimestamp(start_timestamp / 1000, tz=timezone.utc)
                print(f"  ℹ️  Found existing data in Redis up to {datetime.fromtimestamp(latest_timestamp / 1000, tz=timezone.utc).isoformat()}")
                print(f"  📅 Resuming from: {start_date.isoformat()}")
            else:
                print(f"  📅 Starting fresh from: {start_date.isoformat()} (1 day back)")
        else:
            print(f"  📅 Fetching from: {start_date.isoformat()} (force mode, 1 day back)")
        
        # If we're already up to date, skip
        if start_timestamp >= end_timestamp:
            print(f"  ✅ {symbol} ({interval}) is already up to date!")
            return 0, 0, 0
        
        # Duration for 1m: 1 minute
        duration = 60 * 1000  # 1 minute in milliseconds
        window_size = LIMIT * duration
        
    else:
        # MongoDB intervals: use years_back
        # Calculate time range
        now = datetime.now(timezone.utc)
        end_timestamp = int(now.timestamp() * 1000)
        
        if resume_from_existing:
            latest_timestamp = get_latest_timestamp(collection, symbol, interval)
            if latest_timestamp:
                start_timestamp = latest_timestamp + 1
                start_date = datetime.fromtimestamp(start_timestamp / 1000, tz=timezone.utc)
                print(f"  ℹ️  Found existing data up to {datetime.fromtimestamp(latest_timestamp / 1000, tz=timezone.utc).isoformat()}")
                print(f"  📅 Resuming from: {start_date.isoformat()}")
            else:
                # No existing data, start from years_back
                start_date = now - timedelta(days=365 * years_back)
                start_timestamp = int(start_date.timestamp() * 1000)
                print(f"  📅 Starting fresh from: {start_date.isoformat()}")
        else:
            # Force fetch from years_back
            start_date = now - timedelta(days=365 * years_back)
            start_timestamp = int(start_date.timestamp() * 1000)
            print(f"  📅 Fetching from: {start_date.isoformat()} (force mode)")
        
        # If we're already up to date, skip
        if start_timestamp >= end_timestamp:
            print(f"  ✅ {symbol} ({interval}) is already up to date!")
            return 0, 0, 0
        
        # Calculate time window based on interval
        # For pagination, we'll fetch LIMIT candles at a time
        # Each interval has different duration:
        interval_durations = {
            "5m": 5 * 60 * 1000,      # 5 minutes in milliseconds
            "1h": 60 * 60 * 1000,     # 1 hour in milliseconds
            "5h": 5 * 60 * 60 * 1000, # 5 hours in milliseconds
            "1d": 24 * 60 * 60 * 1000 # 1 day in milliseconds
        }
        
        duration = interval_durations.get(interval, 60 * 60 * 1000)
        window_size = LIMIT * duration  # Time window for each request
    
    current_start = start_timestamp
    current_end = min(current_start + window_size, end_timestamp)
    
    total_inserted = 0
    total_skipped = 0
    total_fetched = 0
    batch_count = 0
    
    print(f"  📅 Time range: {start_date.isoformat()} to {now.isoformat()}")
    print(f"  📅 Timestamps: {start_timestamp} to {end_timestamp}")
    
    # Calculate expected number of candles for 1m interval
    if interval == "1m":
        time_range_ms = end_timestamp - start_timestamp
        expected_candles = time_range_ms / (60 * 1000)  # 1 minute per candle
        print(f"  📊 Expected candles for 24h: ~{int(expected_candles)} (1 candle per minute)")
    
    while current_start < end_timestamp:
        try:
            # Fetch candles
            klines = fetch_candles(symbol, interval, current_start, current_end)
            
            if len(klines) == 0:
                print(f"  ℹ️  No more data available for {symbol} ({interval})")
                break
            
            # Parse candles
            candles = [parse_candle(k, symbol, interval) for k in klines]
            
            # Save to Redis (1m) or MongoDB (other intervals)
            if interval == "1m":
                saved, skipped = save_to_redis(redis_client, candles, symbol)
                total_inserted += saved
                total_skipped += skipped
            else:
                inserted, skipped = save_to_mongodb(collection, candles, symbol, interval)
                total_inserted += inserted
                total_skipped += skipped
            
            total_fetched += len(candles)
            batch_count += 1
            
            # Print progress every 10 batches to reduce I/O overhead
            if batch_count % 10 == 0:
                print(f"  📊 {symbol} ({interval}): {total_fetched:,} candles fetched | Saved: {total_inserted:,}, Skipped: {total_skipped:,}")
            
            # Move to next window
            # For 1m interval, use openTime of last candle + 1 minute to ensure no gaps
            if len(klines) > 0:
                last_open_time = klines[-1][0]  # openTime
                if interval == "1m":
                    # For 1m: next candle starts 1 minute after last openTime
                    current_start = last_open_time + duration
                else:
                    # For other intervals: use closeTime + 1ms
                    last_close_time = klines[-1][6]
                    current_start = last_close_time + 1
            else:
                current_start = current_end + 1
            
            current_end = min(current_start + window_size, end_timestamp)
            
            # Rate limiting
            sleep(RATE_LIMIT_DELAY * 1000)
            
        except Exception as e:
            print(f"  ❌ Error fetching {symbol} {interval}: {e}")
            print(f"  ⏳ Retrying in {RETRY_DELAY} seconds...")
            time.sleep(RETRY_DELAY)
            # Advance to next window to avoid infinite loop
            current_start = current_end + 1
            current_end = min(current_start + window_size, end_timestamp)
    
    # Final validation for 1m interval
    if interval == "1m":
        time_range_ms = end_timestamp - start_timestamp
        expected_candles = time_range_ms / (60 * 1000)
        if total_fetched < expected_candles * 0.9:  # Allow 10% tolerance
            print(f"  ⚠️  Warning: Expected ~{int(expected_candles)} candles but only fetched {total_fetched}")
            print(f"  ⚠️  Missing ~{int(expected_candles - total_fetched)} candles")
        else:
            print(f"  ✅ Fetched {total_fetched} candles (expected ~{int(expected_candles)})")
    
    print(f"  ✅ Completed {symbol} ({interval}): Fetched {total_fetched}, Inserted {total_inserted}, Skipped {total_skipped}")
    return total_inserted, total_skipped, total_fetched


def main():
    """Main function"""
    print("=" * 80)
    print("🚀 Binance History Fetcher")
    print("=" * 80)
    print(f"📊 Symbols: {len(SYMBOLS)}")
    print(f"📈 Intervals: {', '.join(INTERVALS)}")
    print(f"📅 Years back: {YEARS_BACK} (1m interval: 1 day)")
    print(f"💾 MongoDB: {MONGO_DB}")
    print(f"🔴 Redis: {REDIS_HOST}:{REDIS_PORT} (for 1m interval)")
    print(f"🔄 Resume from existing: {RESUME_FROM_EXISTING}")
    print("=" * 80)
    
    # Connect to MongoDB (for non-1m intervals)
    mongo_client = None
    mongo_db = None
    try:
        mongo_client = MongoClient(MONGO_URI)
        mongo_db = mongo_client[MONGO_DB]
        print(f"✅ Connected to MongoDB: {MONGO_DB}")
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        return
    
    redis_client = None
    try:
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        # Test connection
        redis_client.ping()
        print(f"✅ Connected to Redis: {REDIS_HOST}:{REDIS_PORT}")
    except Exception as e:
        print(f"❌ Failed to connect to Redis: {e}")
        print(f"⚠️  1m interval will be skipped")
    
    # Create indexes for MongoDB collections (skip 1m)
    for interval in INTERVALS:
        if interval == "1m":
            continue  # Skip 1m, it's saved to Redis
        
        collection_name = COLLECTION_MAP[interval]
        if collection_name:
            collection = mongo_db[collection_name]
            try:
                collection.create_index(
                    [("symbol", 1), ("interval", 1), ("openTime", 1)],
                    unique=True,
                    name="symbol_interval_openTime_unique"
                )
                print(f"✅ Created/verified index for {collection_name}")
            except Exception as e:
                # Index already exists (possibly with different name) - this is fine
                error_msg = str(e)
                if "already exists" in error_msg.lower() or "IndexOptionsConflict" in error_msg:
                    print(f"ℹ️  Index already exists for {collection_name}")
                else:
                    print(f"⚠️  Index creation warning for {collection_name}: {e}")
    
    # Process each interval
    total_stats = {
        "inserted": 0,
        "skipped": 0,
        "fetched": 0
    }
    
    # Thread-safe lock for stats updates
    stats_lock = Lock()
    
    def process_symbol_interval(symbol: str, interval: str):
        """Process a single symbol-interval combination"""
        try:
            if interval == "1m":
                # Save to Redis
                if not redis_client:
                    return (symbol, interval, 0, 0, 0, "Redis client not available")
                inserted, skipped, fetched = fetch_and_save_history(
                    symbol, interval, collection=None, redis_client=redis_client,
                    years_back=YEARS_BACK, resume_from_existing=RESUME_FROM_EXISTING
                )
            else:
                # Save to MongoDB
                collection_name = COLLECTION_MAP[interval]
                if not collection_name:
                    return (symbol, interval, 0, 0, 0, f"No collection mapping for {interval}")
                collection = mongo_db[collection_name]
                inserted, skipped, fetched = fetch_and_save_history(
                    symbol, interval, collection=collection, redis_client=None,
                    years_back=YEARS_BACK, resume_from_existing=RESUME_FROM_EXISTING
                )
            
            with stats_lock:
                total_stats["inserted"] += inserted
                total_stats["skipped"] += skipped
                total_stats["fetched"] += fetched
            return (symbol, interval, inserted, skipped, fetched, None)
        except Exception as e:
            return (symbol, interval, 0, 0, 0, str(e))
    
    # Process intervals sequentially, but symbols in parallel within each interval
    for interval in INTERVALS:
        print(f"\n{'='*80}")
        print(f"📈 Processing interval: {interval}")
        print(f"{'='*80}")
        
        # Use ThreadPoolExecutor to process symbols in parallel
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit all symbol tasks for this interval
            futures = {
                executor.submit(process_symbol_interval, symbol, interval): (symbol, interval)
                for symbol in SYMBOLS
            }
            
            # Process completed tasks
            for future in as_completed(futures):
                symbol, interval, inserted, skipped, fetched, error = future.result()
                if error:
                    print(f"❌ Error processing {symbol} {interval}: {error}")
                else:
                    print(f"✅ Completed {symbol} ({interval}): Fetched {fetched}, Inserted {inserted}, Skipped {skipped}")
    
    # Summary
    print("\n" + "=" * 80)
    print("✅ FETCH COMPLETE")
    print("=" * 80)
    print(f"📊 Total candles fetched: {total_stats['fetched']}")
    print(f"💾 Total inserted: {total_stats['inserted']}")
    print(f"⏭️  Total skipped (duplicates): {total_stats['skipped']}")
    print("=" * 80)
    
    # Close connections
    if mongo_client:
        mongo_client.close()
        print("✅ MongoDB connection closed")
    if redis_client:
        redis_client.close()
        print("✅ Redis connection closed")


if __name__ == "__main__":
    main()

