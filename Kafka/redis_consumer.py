import json
import os
from kafka import KafkaConsumer
import redis
from datetime import datetime

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "192.168.49.2:30995")
TOPIC = os.getenv("KAFKA_TOPIC", "crypto_kline_1m")
CONSUMER_GROUP = os.getenv("CONSUMER_GROUP", "redis_writer_group")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

consumer = KafkaConsumer(
    TOPIC,
    bootstrap_servers=KAFKA_BROKER,
    auto_offset_reset='latest',
    enable_auto_commit=True,
    group_id=CONSUMER_GROUP,
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True
)

def save_to_redis(kline_data):
    symbol = kline_data.get("s", "UNKNOWN")
    open_time = kline_data.get("t")  # Open time in milliseconds
    close_time = kline_data.get("T")  # Close time in milliseconds
    is_closed = kline_data.get("x", False)
    
    # Chỉ lưu trữ khi candle đã đóng (x=true)
    if not is_closed:
        return None, False
    
    key = f"crypto:{symbol}:1m:{open_time}"
    
    value = {
        "symbol": symbol,
        "interval": kline_data.get("i", "1m"),
        "openTime": open_time,
        "closeTime": close_time,
        "open": float(kline_data.get("o", 0)),
        "high": float(kline_data.get("h", 0)),
        "low": float(kline_data.get("l", 0)),
        "close": float(kline_data.get("c", 0)),
        "volume": float(kline_data.get("v", 0)),
        "quoteVolume": float(kline_data.get("q", 0)),
        "trades": int(kline_data.get("n", 0)),
        "x": is_closed,
        "updatedAt": datetime.now().isoformat()
    }
    
    # Lưu candle đã đóng với TTL 24h
    redis_client.setex(
        key,
        86400,  # 24 hours
        json.dumps(value)
    )
    
    # Thêm vào index (chỉ candles đã đóng)
    index_key = f"crypto:{symbol}:1m:index"
    redis_client.zadd(index_key, {str(open_time): open_time})
    redis_client.expire(index_key, 86400 * 7)
    
    # Cập nhật latest (chỉ candles đã đóng)
    latest_key = f"crypto:{symbol}:1m:latest"
    redis_client.setex(latest_key, 86400, json.dumps(value))
    
    return key, is_closed

print("=" * 80)
print("Redis Consumer đã khởi động")
print(f"Kafka Broker: {KAFKA_BROKER}")
print(f"Topic: {TOPIC}")
print(f"Consumer Group: {CONSUMER_GROUP}")
print(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
print("=" * 80)
print("Đang lắng nghe messages từ Kafka và lưu vào Redis...")
print("=" * 80)

try:
    for msg in consumer:
        kline = msg.value
        
        symbol = kline.get("s", "UNKNOWN")
        interval = kline.get("i", "")
        open_price = float(kline.get("o", 0))
        close_price = float(kline.get("c", 0))
        high_price = float(kline.get("h", 0))
        low_price = float(kline.get("l", 0))
        volume = float(kline.get("v", 0))
        is_closed = kline.get("x", False)
        
        open_time = datetime.fromtimestamp(int(kline.get("t", 0)) / 1000).strftime("%Y-%m-%d %H:%M:%S")
        status = "✅ CLOSED" if is_closed else "⏳ OPEN"
        
        print(f"\n[{open_time}] {symbol} ({interval}) | {status}")
        
        # Chỉ lưu vào Redis khi candle đã đóng (x=true)
        if is_closed:
            key, _ = save_to_redis(kline)
            print(f"  Redis Key: {key}")
            print(f"  → Kline đã đóng, đã lưu vào Redis (TTL: 24h)")
        else:
            print(f"  ⏭️  Kline đang mở (x=false), không lưu vào Redis")
        
        price_change = ((close_price - open_price) / open_price * 100) if open_price > 0 else 0
        change_symbol = "📈" if price_change >= 0 else "📉"
        print(f"  OHLC: O=${open_price:.4f} H=${high_price:.4f} L=${low_price:.4f} C=${close_price:.4f} {change_symbol} {price_change:+.2f}%")
        print(f"  Volume: {volume:.2f} | Trades: {kline.get('n', 0)}")
        print(f"  Partition: {msg.partition}, Offset: {msg.offset}")
        
        print("-" * 80)
            
except KeyboardInterrupt:
    print("\n\nĐang dừng consumer...")
except Exception as e:
    print(f"\n❌ Lỗi: {e}")
    import traceback
    traceback.print_exc()
finally:
    consumer.close()
    redis_client.close()
    print("✅ Đã đóng kết nối Kafka và Redis.")

