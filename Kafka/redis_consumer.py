"""
Kafka Consumer để lưu dữ liệu vào Redis
- Lọc kline khi x=true (đã đóng)
- Lưu vào Redis với TTL
- Cũng lưu kline chưa đóng (x=false) với TTL ngắn hơn
"""
import json
import os
from kafka import KafkaConsumer
import redis
from datetime import datetime, timedelta

# Config
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "192.168.49.2:30113")
TOPIC = os.getenv("KAFKA_TOPIC", "crypto_kline_1m")
CONSUMER_GROUP = os.getenv("CONSUMER_GROUP", "redis_writer_group")

# Redis config
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

# Kafka Consumer
consumer = KafkaConsumer(
    TOPIC,
    bootstrap_servers=KAFKA_BROKER,
    auto_offset_reset='latest',
    enable_auto_commit=True,
    group_id=CONSUMER_GROUP,
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

# Redis Client
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True
)

def save_to_redis(kline_data):
    """
    Lưu kline vào Redis
    Key pattern: crypto:{symbol}:1m:{open_time}
    """
    symbol = kline_data.get("s", "UNKNOWN")
    open_time = kline_data.get("t")  # Open time in milliseconds
    is_closed = kline_data.get("x", False)
    
    # Tạo key
    key = f"crypto:{symbol}:1m:{open_time}"
    
    # Tạo value (JSON)
    value = {
        "symbol": symbol,
        "interval": "1m",
        "open_time": open_time,
        "close_time": kline_data.get("T"),
        "open": float(kline_data.get("o", 0)),
        "high": float(kline_data.get("h", 0)),
        "low": float(kline_data.get("l", 0)),
        "close": float(kline_data.get("c", 0)),
        "volume": float(kline_data.get("v", 0)),
        "quote_volume": float(kline_data.get("q", 0)),
        "trades": int(kline_data.get("n", 0)),
        "is_closed": is_closed,
        "updated_at": datetime.now().isoformat()
    }
    
    # TTL: 24h cho kline đã đóng, 5 phút cho kline chưa đóng
    ttl_seconds = 86400 if is_closed else 300  # 24h hoặc 5 phút
    
    # Lưu vào Redis
    redis_client.setex(
        key,
        ttl_seconds,
        json.dumps(value)
    )
    
    # Lưu vào sorted set để query theo time range
    # Key: crypto:{symbol}:1m:index
    index_key = f"crypto:{symbol}:1m:index"
    redis_client.zadd(index_key, {str(open_time): open_time})
    redis_client.expire(index_key, 86400 * 7)  # 7 ngày
    
    # Lưu latest kline cho mỗi symbol
    latest_key = f"crypto:{symbol}:1m:latest"
    redis_client.setex(latest_key, 86400, json.dumps(value))
    
    return key, is_closed

def get_recent_klines(symbol, count=5):
    """Lấy kline gần nhất từ Redis"""
    index_key = f"crypto:{symbol}:1m:index"
    # Lấy top N timestamps
    timestamps = redis_client.zrevrange(index_key, 0, count - 1)
    
    klines = []
    for ts in timestamps:
        key = f"crypto:{symbol}:1m:{ts}"
        data = redis_client.get(key)
        if data:
            klines.append(json.loads(data))
    
    return klines

print("=" * 80)
print("Redis Consumer đã khởi động")
print(f"Kafka Broker: {KAFKA_BROKER}")
print(f"Topic: {TOPIC}")
print(f"Consumer Group: {CONSUMER_GROUP}")
print(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
print("=" * 80)
print("Đang lắng nghe messages từ Kafka...")
print("=" * 80)

try:
    for msg in consumer:
        kline = msg.value
        
        # Lưu vào Redis
        key, is_closed = save_to_redis(kline)
        
        symbol = kline.get("s", "UNKNOWN")
        status = "✅ CLOSED" if is_closed else "⏳ OPEN"
        
        print(f"\n[{status}] {symbol} | Key: {key}")
        print(f"  OHLC: O={kline.get('o')} H={kline.get('h')} L={kline.get('l')} C={kline.get('c')}")
        print(f"  Volume: {kline.get('v')} | Trades: {kline.get('n')}")
        
        # Nếu kline đã đóng, có thể trigger OHLC aggregation
        if is_closed:
            print(f"  → Kline đã đóng, có thể tính OHLC 5m")
            
except KeyboardInterrupt:
    print("\n\nĐang dừng consumer...")
except Exception as e:
    print(f"\n❌ Lỗi: {e}")
finally:
    consumer.close()
    redis_client.close()
    print("Đã đóng kết nối.")

