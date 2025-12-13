import os
import json
from datetime import datetime, timedelta, timezone
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from dotenv import load_dotenv
import redis
from pymongo import MongoClient

load_dotenv()

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

def aggregate_ohlc_5m(**context):
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True
    )
    
    mongo_client = MongoClient(MONGO_URI)
    mongo_db = mongo_client[MONGO_DB]
    mongo_collection = mongo_db[MONGO_COLLECTION]
    
    mongo_collection.create_index([
        ("symbol", 1),
        ("interval", 1),
        ("openTime", 1)
    ], unique=True)
    
    now = datetime.now(timezone.utc)
    current_minute = now.minute
    rounded_minute = (current_minute // 5) * 5
    window_end = now.replace(minute=rounded_minute, second=0, microsecond=0)
    window_start = window_end - timedelta(minutes=5)
    
    start_timestamp = int(window_start.timestamp() * 1000)
    end_timestamp = int(window_end.timestamp() * 1000)
    
    print(f"📅 Aggregate OHLC 5m từ {window_start} đến {window_end}")
    print(f"   Timestamp: {start_timestamp} - {end_timestamp}")
    
    total_aggregated = 0
    
    for symbol in SYMBOLS:
        print(f"\n📊 Xử lý {symbol}...")
        
        index_key = f"crypto:{symbol}:1m:index"
        
        timestamps = redis_client.zrangebyscore(
            index_key,
            start_timestamp,
            end_timestamp
        )
        
        if not timestamps:
            print(f"  ⚠️  Không có dữ liệu cho {symbol}")
            continue
        
        klines = []
        for ts in sorted(timestamps):
            key = f"crypto:{symbol}:1m:{ts}"
            data = redis_client.get(key)
            if data:
                kline = json.loads(data)
                if kline.get("x", False):
                    klines.append(kline)
        
        if len(klines) < 5:
            print(f"  ⚠️  Chỉ có {len(klines)}/5 klines đã đóng cho {symbol}")
            continue

        klines_5m = klines[:5]

        first_5m_open_time = klines_5m[0]["openTime"]
        existing = mongo_collection.find_one({
            "symbol": symbol,
            "interval": "5m",
            "openTime": first_5m_open_time
        })
        
        if existing:
            print(f"  ℹ️  OHLC 5m đã tồn tại trong MongoDB cho {symbol} (open_time: {first_5m_open_time})")
            continue
        
        open_price = float(klines_5m[0]["open"])
        close_price = float(klines_5m[-1]["close"])
        high_price = max(float(k["high"]) for k in klines_5m)
        low_price = min(float(k["low"]) for k in klines_5m)
        volume = sum(float(k["volume"]) for k in klines_5m)
        quote_volume = sum(float(k.get("quoteVolume", 0)) for k in klines_5m)
        trades = sum(int(k.get("trades", 0)) for k in klines_5m)
        
        open_time = klines_5m[0]["openTime"]
        close_time = klines_5m[-1]["closeTime"]
        
        mongo_doc = {
            "symbol": symbol,
            "interval": "5m",
            "openTime": open_time,
            "closeTime": close_time,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": volume,
            "quoteVolume": quote_volume,
            "trades": trades,
            "createdAt": datetime.now(),
            "source": "airflow_5m_aggregator"
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
            print(f"  ✅ {symbol}: OHLC 5m đã được tạo và lưu vào MongoDB")
            print(f"     Open: {open_price:.4f}, High: {high_price:.4f}, Low: {low_price:.4f}, Close: {close_price:.4f}")
            total_aggregated += 1
        except Exception as e:
            print(f"  ❌ Lỗi khi lưu {symbol} vào MongoDB: {e}")
            total_aggregated += 0
    
    print(f"\n✅ Hoàn thành! Tổng cộng đã aggregate {total_aggregated}/{len(SYMBOLS)} symbols")
    
    redis_client.close()
    mongo_client.close()
    
    return total_aggregated


def aggregate_ohlc_1h(**context):
    mongo_client = MongoClient(MONGO_URI)
    mongo_db = mongo_client[MONGO_DB]
    source_collection = mongo_db["5m_kline"]
    target_collection = mongo_db["1h_kline"]
    
    target_collection.create_index([
        ("symbol", 1),
        ("interval", 1),
        ("openTime", 1)
    ], unique=True)
    
    now = datetime.now(timezone.utc)
    window_end = now.replace(minute=0, second=0, microsecond=0)
    window_start = window_end - timedelta(hours=1)
    
    start_timestamp = int(window_start.timestamp() * 1000)
    end_timestamp = int(window_end.timestamp() * 1000)
    
    print(f"📅 Aggregate OHLC 1h từ {window_start} đến {window_end}")
    print(f"   Timestamp: {start_timestamp} - {end_timestamp}")
    
    total_aggregated = 0
    
    for symbol in SYMBOLS:
        print(f"\n📊 Xử lý {symbol}...")
        
        klines = list(source_collection.find({
            "symbol": symbol,
            "interval": "5m",
            "openTime": {"$gte": start_timestamp, "$lt": end_timestamp}
        }).sort("openTime", 1))
        
        if len(klines) < 12:
            print(f"  ⚠️  Chỉ có {len(klines)}/12 klines 5m cho {symbol}")
            continue
        
        klines_1h = klines[:12]
        
        first_1h_open_time = klines_1h[0]["openTime"]
        existing = target_collection.find_one({
            "symbol": symbol,
            "interval": "1h",
            "openTime": first_1h_open_time
        })
        
        if existing:
            print(f"  ℹ️  OHLC 1h đã tồn tại cho {symbol} (open_time: {first_1h_open_time})")
            continue
        
        open_price = float(klines_1h[0]["open"])
        close_price = float(klines_1h[-1]["close"])
        high_price = max(float(k["high"]) for k in klines_1h)
        low_price = min(float(k["low"]) for k in klines_1h)
        volume = sum(float(k["volume"]) for k in klines_1h)
        quote_volume = sum(float(k.get("quoteVolume", 0)) for k in klines_1h)
        trades = sum(int(k.get("trades", 0)) for k in klines_1h)
        
        open_time = klines_1h[0]["openTime"]
        close_time = klines_1h[-1]["closeTime"]
        
        mongo_doc = {
            "symbol": symbol,
            "interval": "1h",
            "openTime": open_time,
            "closeTime": close_time,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": volume,
            "quoteVolume": quote_volume,
            "trades": trades,
            "createdAt": datetime.now(),
            "source": "airflow_1h_aggregator"
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
            print(f"  ✅ {symbol}: OHLC 1h đã được tạo và lưu vào MongoDB")
            print(f"     Open: {open_price:.4f}, High: {high_price:.4f}, Low: {low_price:.4f}, Close: {close_price:.4f}")
            total_aggregated += 1
        except Exception as e:
            print(f"  ❌ Lỗi khi lưu {symbol} vào MongoDB: {e}")
            total_aggregated += 0
    
    print(f"\n✅ Hoàn thành! Tổng cộng đã aggregate {total_aggregated}/{len(SYMBOLS)} symbols")
    mongo_client.close()
    return total_aggregated


def aggregate_ohlc_5h(**context):
    mongo_client = MongoClient(MONGO_URI)
    mongo_db = mongo_client[MONGO_DB]
    source_collection = mongo_db["1h_kline"]
    target_collection = mongo_db["5h_kline"]
    
    target_collection.create_index([
        ("symbol", 1),
        ("interval", 1),
        ("openTime", 1)
    ], unique=True)
    
    now = datetime.now(timezone.utc)
    current_hour = now.hour
    rounded_hour = (current_hour // 5) * 5
    window_end = now.replace(hour=rounded_hour, minute=0, second=0, microsecond=0)
    window_start = window_end - timedelta(hours=5)
    
    start_timestamp = int(window_start.timestamp() * 1000)
    end_timestamp = int(window_end.timestamp() * 1000)
    
    print(f"📅 Aggregate OHLC 5h từ {window_start} đến {window_end}")
    print(f"   Timestamp: {start_timestamp} - {end_timestamp}")
    
    total_aggregated = 0
    
    for symbol in SYMBOLS:
        print(f"\n📊 Xử lý {symbol}...")
        
        # Lấy klines 1h từ MongoDB
        klines = list(source_collection.find({
            "symbol": symbol,
            "interval": "1h",
            "openTime": {"$gte": start_timestamp, "$lt": end_timestamp}
        }).sort("openTime", 1))
        
        if len(klines) < 5:
            print(f"  ⚠️  Chỉ có {len(klines)}/5 klines 1h cho {symbol}")
            continue
        
        klines_5h = klines[:5]
        
        first_5h_open_time = klines_5h[0]["openTime"]
        existing = target_collection.find_one({
            "symbol": symbol,
            "interval": "5h",
            "openTime": first_5h_open_time
        })
        
        if existing:
            print(f"  ℹ️  OHLC 5h đã tồn tại cho {symbol} (open_time: {first_5h_open_time})")
            continue
        
        open_price = float(klines_5h[0]["open"])
        close_price = float(klines_5h[-1]["close"])
        high_price = max(float(k["high"]) for k in klines_5h)
        low_price = min(float(k["low"]) for k in klines_5h)
        volume = sum(float(k["volume"]) for k in klines_5h)
        quote_volume = sum(float(k.get("quoteVolume", 0)) for k in klines_5h)
        trades = sum(int(k.get("trades", 0)) for k in klines_5h)
        
        open_time = klines_5h[0]["openTime"]
        close_time = klines_5h[-1]["closeTime"]
        
        mongo_doc = {
            "symbol": symbol,
            "interval": "5h",
            "openTime": open_time,
            "closeTime": close_time,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": volume,
            "quoteVolume": quote_volume,
            "trades": trades,
            "createdAt": datetime.now(),
            "source": "airflow_5h_aggregator"
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
            print(f"  ✅ {symbol}: OHLC 5h đã được tạo và lưu vào MongoDB")
            print(f"     Open: {open_price:.4f}, High: {high_price:.4f}, Low: {low_price:.4f}, Close: {close_price:.4f}")
            total_aggregated += 1
        except Exception as e:
            print(f"  ❌ Lỗi khi lưu {symbol} vào MongoDB: {e}")
            total_aggregated += 0
    
    print(f"\n✅ Hoàn thành! Tổng cộng đã aggregate {total_aggregated}/{len(SYMBOLS)} symbols")
    mongo_client.close()
    return total_aggregated


def aggregate_ohlc_1d(**context):
    mongo_client = MongoClient(MONGO_URI)
    mongo_db = mongo_client[MONGO_DB]
    source_collection = mongo_db["1h_kline"]
    target_collection = mongo_db["1d_kline"]
    
    target_collection.create_index([
        ("symbol", 1),
        ("interval", 1),
        ("openTime", 1)
    ], unique=True)
    
    now = datetime.now(timezone.utc)
    window_end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_start = window_end - timedelta(days=1)
    
    start_timestamp = int(window_start.timestamp() * 1000)
    end_timestamp = int(window_end.timestamp() * 1000)
    
    print(f"📅 Aggregate OHLC 1d từ {window_start} đến {window_end}")
    print(f"   Timestamp: {start_timestamp} - {end_timestamp}")
    
    total_aggregated = 0
    
    for symbol in SYMBOLS:
        print(f"\n📊 Xử lý {symbol}...")
        
        # Lấy klines 1h từ MongoDB
        klines = list(source_collection.find({
            "symbol": symbol,
            "interval": "1h",
            "openTime": {"$gte": start_timestamp, "$lt": end_timestamp}
        }).sort("openTime", 1))
        
        if len(klines) < 24:
            print(f"  ⚠️  Chỉ có {len(klines)}/24 klines 1h cho {symbol}")
            continue
        
        klines_1d = klines[:24]
        
        first_1d_open_time = klines_1d[0]["openTime"]
        existing = target_collection.find_one({
            "symbol": symbol,
            "interval": "1d",
            "openTime": first_1d_open_time
        })
        
        if existing:
            print(f"  ℹ️  OHLC 1d đã tồn tại cho {symbol} (open_time: {first_1d_open_time})")
            continue
        
        open_price = float(klines_1d[0]["open"])
        close_price = float(klines_1d[-1]["close"])
        high_price = max(float(k["high"]) for k in klines_1d)
        low_price = min(float(k["low"]) for k in klines_1d)
        volume = sum(float(k["volume"]) for k in klines_1d)
        quote_volume = sum(float(k.get("quoteVolume", 0)) for k in klines_1d)
        trades = sum(int(k.get("trades", 0)) for k in klines_1d)
        
        open_time = klines_1d[0]["openTime"]
        close_time = klines_1d[-1]["closeTime"]
        
        mongo_doc = {
            "symbol": symbol,
            "interval": "1d",
            "openTime": open_time,
            "closeTime": close_time,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": volume,
            "quoteVolume": quote_volume,
            "trades": trades,
            "createdAt": datetime.now(),
            "source": "airflow_1d_aggregator"
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
            print(f"  ✅ {symbol}: OHLC 1d đã được tạo và lưu vào MongoDB")
            print(f"     Open: {open_price:.4f}, High: {high_price:.4f}, Low: {low_price:.4f}, Close: {close_price:.4f}")
            total_aggregated += 1
        except Exception as e:
            print(f"  ❌ Lỗi khi lưu {symbol} vào MongoDB: {e}")
            total_aggregated += 0
    
    print(f"\n✅ Hoàn thành! Tổng cộng đã aggregate {total_aggregated}/{len(SYMBOLS)} symbols")
    mongo_client.close()
    return total_aggregated


default_args = {
    "owner": "crypto_team",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
}

with DAG(
    dag_id="ohlc_5m_aggregator",
    default_args=default_args,
    description="Aggregate OHLC 5 phút từ Redis mỗi 5 phút",
    schedule="*/5 * * * *",
    catchup=False,
    tags=["crypto", "ohlc", "redis", "5m"],
    start_date=datetime(2024, 1, 1),
    max_active_runs=1,
) as dag_5m:
    
    aggregate_5m_task = PythonOperator(
        task_id="aggregate_ohlc_5m_from_redis",
        python_callable=aggregate_ohlc_5m,
    )
    
    aggregate_5m_task

# DAG 1h
with DAG(
    dag_id="ohlc_1h_aggregator",
    default_args=default_args,
    description="Aggregate OHLC 1 giờ từ MongoDB 5m mỗi giờ",
    schedule="0 * * * *",  # Mỗi giờ (vào phút 0)
    catchup=False,
    tags=["crypto", "ohlc", "mongodb", "1h"],
    start_date=datetime(2024, 1, 1),
    max_active_runs=1,
) as dag_1h:
    
    aggregate_1h_task = PythonOperator(
        task_id="aggregate_ohlc_1h_from_5m",
        python_callable=aggregate_ohlc_1h,
    )
    
    aggregate_1h_task

# DAG 5h
with DAG(
    dag_id="ohlc_5h_aggregator",
    default_args=default_args,
    description="Aggregate OHLC 5 giờ từ MongoDB 1h mỗi 5 giờ",
    schedule="0 */5 * * *",  # Mỗi 5 giờ (vào phút 0)
    catchup=False,
    tags=["crypto", "ohlc", "mongodb", "5h"],
    start_date=datetime(2024, 1, 1),
    max_active_runs=1,
) as dag_5h:
    
    aggregate_5h_task = PythonOperator(
        task_id="aggregate_ohlc_5h_from_1h",
        python_callable=aggregate_ohlc_5h,
    )
    
    aggregate_5h_task

# DAG 1d
with DAG(
    dag_id="ohlc_1d_aggregator",
    default_args=default_args,
    description="Aggregate OHLC 1 ngày từ MongoDB 1h mỗi ngày",
    schedule="0 0 * * *",  # Mỗi ngày lúc 00:00 UTC
    catchup=False,
    tags=["crypto", "ohlc", "mongodb", "1d"],
    start_date=datetime(2024, 1, 1),
    max_active_runs=1,
) as dag_1d:
    
    aggregate_1d_task = PythonOperator(
        task_id="aggregate_ohlc_1d_from_1h",
        python_callable=aggregate_ohlc_1d,
    )
    
    aggregate_1d_task

