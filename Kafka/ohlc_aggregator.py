"""
OHLC Aggregator: Tính OHLC 5 phút từ dữ liệu 1 phút
- Đọc từ Redis hoặc Kafka
- Aggregate 5 kline 1m thành 1 kline 5m
- Lưu vào Redis và MongoDB
"""
import json
import os
import time
from datetime import datetime, timedelta
import redis
from pymongo import MongoClient
from collections import defaultdict

# Config
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "crypto_history")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "candles")

# Redis Client
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True
)

# MongoDB Client
mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client[MONGO_DB]
mongo_collection = mongo_db[MONGO_COLLECTION]

# Tạo index
mongo_collection.create_index([
    ("symbol", 1),
    ("interval", 1),
    ("openTime", 1)
], unique=True)

def get_klines_from_redis(symbol, start_time, end_time):
    """
    Lấy klines từ Redis trong khoảng thời gian
    """
    index_key = f"crypto:{symbol}:1m:index"
    
    # Lấy timestamps trong range
    timestamps = redis_client.zrangebyscore(
        index_key,
        start_time,
        end_time
    )
    
    klines = []
    for ts in timestamps:
        key = f"crypto:{symbol}:1m:{ts}"
        data = redis_client.get(key)
        if data:
            kline = json.loads(data)
            # Chỉ lấy kline đã đóng
            if kline.get("is_closed", False):
                klines.append(kline)
    
    # Sort theo open_time
    klines.sort(key=lambda x: x["open_time"])
    return klines

def aggregate_ohlc_5m(klines_1m):
    """
    Aggregate 5 kline 1m thành 1 kline 5m
    """
    if len(klines_1m) < 5:
        return None
    
    # Lấy 5 kline đầu tiên
    klines = klines_1m[:5]
    
    # Tính OHLC
    open_price = klines[0]["open"]
    close_price = klines[-1]["close"]
    high_price = max(k["high"] for k in klines)
    low_price = min(k["low"] for k in klines)
    volume = sum(float(k["volume"]) for k in klines)
    quote_volume = sum(float(k.get("quote_volume", 0)) for k in klines)
    trades = sum(int(k.get("trades", 0)) for k in klines)
    
    # Thời gian
    open_time = klines[0]["open_time"]
    close_time = klines[-1]["close_time"]
    
    return {
        "symbol": klines[0]["symbol"],
        "interval": "5m",
        "open_time": open_time,
        "close_time": close_time,
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
        "volume": volume,
        "quote_volume": quote_volume,
        "trades": trades,
        "is_closed": True,
        "aggregated_from": "1m",
        "created_at": datetime.now().isoformat()
    }

def save_ohlc_5m(ohlc_data):
    """
    Lưu OHLC 5m vào Redis và MongoDB
    """
    symbol = ohlc_data["symbol"]
    open_time = ohlc_data["open_time"]
    
    # Lưu vào Redis
    redis_key = f"crypto:{symbol}:5m:{open_time}"
    redis_client.setex(
        redis_key,
        86400 * 7,  # 7 ngày
        json.dumps(ohlc_data)
    )
    
    # Lưu vào index
    index_key = f"crypto:{symbol}:5m:index"
    redis_client.zadd(index_key, {str(open_time): open_time})
    redis_client.expire(index_key, 86400 * 30)  # 30 ngày
    
    # Lưu latest
    latest_key = f"crypto:{symbol}:5m:latest"
    redis_client.setex(latest_key, 86400, json.dumps(ohlc_data))
    
    # Lưu vào MongoDB
    mongo_doc = {
        "symbol": ohlc_data["symbol"],
        "interval": "5m",
        "openTime": ohlc_data["open_time"],
        "closeTime": ohlc_data["close_time"],
        "open": ohlc_data["open"],
        "high": ohlc_data["high"],
        "low": ohlc_data["low"],
        "close": ohlc_data["close"],
        "volume": ohlc_data["volume"],
        "quoteVolume": ohlc_data.get("quote_volume", 0),
        "trades": ohlc_data.get("trades", 0),
        "createdAt": datetime.now()
    }
    
    mongo_collection.update_one(
        {
            "symbol": mongo_doc["symbol"],
            "interval": mongo_doc["interval"],
            "openTime": mongo_doc["openTime"]
        },
        {"$set": mongo_doc},
        upsert=True
    )
    
    return redis_key

def process_symbol(symbol):
    """
    Xử lý aggregate OHLC 5m cho một symbol
    """
    # Lấy klines 1m gần nhất (5 phút = 5 klines)
    index_key = f"crypto:{symbol}:1m:index"
    
    # Lấy 10 klines gần nhất để đảm bảo có đủ 5 klines đã đóng
    timestamps = redis_client.zrevrange(index_key, 0, 9)
    
    if len(timestamps) < 5:
        return None
    
    # Lấy klines
    klines = []
    for ts in reversed(timestamps):  # Từ cũ đến mới
        key = f"crypto:{symbol}:1m:{ts}"
        data = redis_client.get(key)
        if data:
            kline = json.loads(data)
            if kline.get("is_closed", False):
                klines.append(kline)
    
    if len(klines) < 5:
        return None
    
    # Kiểm tra xem đã aggregate chưa
    # Lấy open_time của kline 5m đầu tiên (5 kline 1m đầu)
    first_5m_open_time = klines[0]["open_time"]
    
    # Kiểm tra xem đã có OHLC 5m chưa
    check_key = f"crypto:{symbol}:5m:{first_5m_open_time}"
    if redis_client.exists(check_key):
        return None  # Đã aggregate rồi
    
    # Aggregate
    ohlc_5m = aggregate_ohlc_5m(klines)
    if ohlc_5m:
        save_ohlc_5m(ohlc_5m)
        return ohlc_5m
    
    return None

def main():
    """
    Main loop: Chạy mỗi 5 phút để aggregate OHLC
    """
    # Danh sách symbols (có thể lấy từ Redis hoặc config)
    symbols = [
        "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT",
        "XRPUSDT", "DOGEUSDT", "DOTUSDT", "MATICUSDT", "AVAXUSDT",
        "LINKUSDT", "UNIUSDT", "LTCUSDT", "ATOMUSDT", "ETCUSDT"
    ]
    
    print("=" * 80)
    print("OHLC Aggregator 5m đã khởi động")
    print(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
    print(f"MongoDB: {MONGO_URI}/{MONGO_DB}")
    print(f"Symbols: {len(symbols)}")
    print("=" * 80)
    
    while True:
        try:
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Bắt đầu aggregate OHLC 5m...")
            
            aggregated_count = 0
            for symbol in symbols:
                result = process_symbol(symbol)
                if result:
                    aggregated_count += 1
                    print(f"  ✅ {symbol}: OHLC 5m đã được tạo (Open: {result['open']}, Close: {result['close']})")
            
            if aggregated_count == 0:
                print("  ℹ️  Không có kline mới để aggregate")
            
            print(f"  Tổng: {aggregated_count}/{len(symbols)} symbols đã được aggregate")
            
            # Đợi 5 phút
            print("  Đợi 5 phút trước khi aggregate tiếp...")
            time.sleep(300)  # 5 phút
            
        except KeyboardInterrupt:
            print("\n\nĐang dừng aggregator...")
            break
        except Exception as e:
            print(f"\n❌ Lỗi: {e}")
            time.sleep(60)  # Đợi 1 phút trước khi retry

if __name__ == "__main__":
    main()

