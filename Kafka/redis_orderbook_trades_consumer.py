import json
import os
from kafka import KafkaConsumer
import redis
from datetime import datetime

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "192.168.49.2:30995")
TOPIC_ORDERBOOK = os.getenv("KAFKA_TOPIC_ORDERBOOK", "crypto_orderbook")
TOPIC_TRADES = os.getenv("KAFKA_TOPIC_TRADES", "crypto_trades")
CONSUMER_GROUP = os.getenv("CONSUMER_GROUP", "redis_orderbook_trades_group")

#
# Redis configuration
# Mặc định trỏ tới Redis trên Minikube (my-redis-master NodePort).
# Có thể override bằng biến môi trường khi chạy trong cluster.
#
REDIS_HOST = os.getenv("REDIS_HOST", "192.168.49.2")
REDIS_PORT = int(os.getenv("REDIS_PORT", 31001))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "123456")

# TTL in seconds
ORDERBOOK_TTL = 3600  # 1 hour
TRADES_TTL = 1800     # 30 minutes
MAX_TRADES = 100      # Keep last 100 trades per symbol

# Create consumers for both topics
consumer_orderbook = KafkaConsumer(
    TOPIC_ORDERBOOK,
    bootstrap_servers=KAFKA_BROKER,
    auto_offset_reset='latest',
    enable_auto_commit=True,
    group_id=f"{CONSUMER_GROUP}_orderbook",
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

consumer_trades = KafkaConsumer(
    TOPIC_TRADES,
    bootstrap_servers=KAFKA_BROKER,
    auto_offset_reset='latest',
    enable_auto_commit=True,
    group_id=f"{CONSUMER_GROUP}_trades",
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True,
)

def save_orderbook_to_redis(orderbook_data):
    """Save Order Book snapshot to Redis"""
    symbol = orderbook_data.get("s", "UNKNOWN")
    if symbol == "UNKNOWN":
        return None
    
    # Format Order Book data
    formatted_data = {
        "symbol": symbol,
        "lastUpdateId": orderbook_data.get("lastUpdateId"),
        "bids": [[float(price), float(qty)] for price, qty in orderbook_data.get("bids", [])],
        "asks": [[float(price), float(qty)] for price, qty in orderbook_data.get("asks", [])],
        "timestamp": orderbook_data.get("received_at", int(datetime.now().timestamp() * 1000)),
        "updatedAt": datetime.now().isoformat()
    }
    
    # Save latest snapshot
    key = f"orderbook:{symbol}:latest"
    redis_client.setex(
        key,
        ORDERBOOK_TTL,
        json.dumps(formatted_data)
    )
    
    return key

def save_trade_to_redis(trade_data):
    """Save Market Trade to Redis (sorted set)"""
    symbol = trade_data.get("s", "UNKNOWN")
    if symbol == "UNKNOWN":
        return None
    
    # Format Trade data
    trade_time = trade_data.get("T", trade_data.get("received_at", int(datetime.now().timestamp() * 1000)))
    formatted_trade = {
        "symbol": symbol,
        "price": float(trade_data.get("p", 0)),
        "quantity": float(trade_data.get("q", 0)),
        "time": trade_time,
        "isBuyerMaker": trade_data.get("m", False),
        "tradeId": trade_data.get("t", 0),
        "updatedAt": datetime.now().isoformat()
    }
    
    # Use sorted set to keep trades sorted by time
    key = f"trades:{symbol}:list"
    trade_json = json.dumps(formatted_trade)
    
    # Add to sorted set with timestamp as score
    redis_client.zadd(key, {trade_json: trade_time})
    
    # Keep only last MAX_TRADES trades
    count = redis_client.zcard(key)
    if count > MAX_TRADES:
        # Remove oldest trades
        redis_client.zremrangebyrank(key, 0, count - MAX_TRADES - 1)
    
    # Set TTL
    redis_client.expire(key, TRADES_TTL)
    
    return key

def process_orderbook_messages():
    """Process Order Book messages from Kafka"""
    print("📊 Starting Order Book consumer...")
    try:
        for msg in consumer_orderbook:
            orderbook = msg.value
            symbol = orderbook.get("s", "UNKNOWN")
            
            key = save_orderbook_to_redis(orderbook)
            if key:
                bids_count = len(orderbook.get("bids", []))
                asks_count = len(orderbook.get("asks", []))
                last_update_id = orderbook.get("lastUpdateId", "N/A")
                
                print(f"✅ Order Book: {symbol} | Bids: {bids_count} | Asks: {asks_count} | Update ID: {last_update_id}")
                print(f"   Redis Key: {key} (TTL: {ORDERBOOK_TTL}s)")
            else:
                print(f"⚠️ Skipped Order Book (invalid symbol)")
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping Order Book consumer...")
    except Exception as e:
        print(f"❌ Order Book consumer error: {e}")
        import traceback
        traceback.print_exc()

def process_trades_messages():
    """Process Trade messages from Kafka"""
    print("💰 Starting Trades consumer...")
    try:
        for msg in consumer_trades:
            trade = msg.value
            symbol = trade.get("s", "UNKNOWN")
            
            key = save_trade_to_redis(trade)
            if key:
                price = float(trade.get("p", 0))
                quantity = float(trade.get("q", 0))
                is_buyer_maker = trade.get("m", False)
                side = "SELL" if is_buyer_maker else "BUY"
                trade_time = datetime.fromtimestamp(int(trade.get("T", 0)) / 1000).strftime("%H:%M:%S")
                
                print(f"✅ Trade: {symbol} | {side} | Price: ${price:.2f} | Qty: {quantity:.6f} | Time: {trade_time}")
                print(f"   Redis Key: {key} (TTL: {TRADES_TTL}s)")
            else:
                print(f"⚠️ Skipped Trade (invalid symbol)")
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping Trades consumer...")
    except Exception as e:
        print(f"❌ Trades consumer error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import threading
    
    print("=" * 80)
    print("Redis Order Book & Trades Consumer")
    print("=" * 80)
    print(f"Kafka Broker: {KAFKA_BROKER}")
    print(f"Order Book Topic: {TOPIC_ORDERBOOK}")
    print(f"Trades Topic: {TOPIC_TRADES}")
    print(f"Consumer Group: {CONSUMER_GROUP}")
    print(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
    print(f"Order Book TTL: {ORDERBOOK_TTL}s (1 hour)")
    print(f"Trades TTL: {TRADES_TTL}s (30 minutes)")
    print(f"Max Trades per Symbol: {MAX_TRADES}")
    print("=" * 80)
    print("Listening for messages from Kafka and saving to Redis...")
    print("=" * 80)
    
    # Run both consumers in separate threads
    thread_orderbook = threading.Thread(target=process_orderbook_messages, daemon=True)
    thread_trades = threading.Thread(target=process_trades_messages, daemon=True)
    
    thread_orderbook.start()
    thread_trades.start()
    
    try:
        # Keep main thread alive
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down consumers...")
    finally:
        consumer_orderbook.close()
        consumer_trades.close()
        redis_client.close()
        print("✅ Closed Kafka and Redis connections.")

