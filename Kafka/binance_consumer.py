from kafka import KafkaConsumer
import json
from datetime import datetime
from pprint import pprint

KAFKA_BROKER = "192.168.49.2:30599"
TOPIC = "crypto_kline_1m"

consumer = KafkaConsumer(
    TOPIC,
    bootstrap_servers=KAFKA_BROKER,
    auto_offset_reset='latest',
    enable_auto_commit=True,
    group_id='crypto_group',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

print("Listening for messages from multiple cryptocurrencies...")
print("-" * 80)

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
    
    price_change = ((close_price - open_price) / open_price * 100) if open_price > 0 else 0
    change_symbol = "📈" if price_change >= 0 else "📉"
    
    open_time = datetime.fromtimestamp(int(kline.get("t", 0)) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    
    partition_info = f"Partition: {msg.partition}, Offset: {msg.offset}"
    
    print(f"\n[{open_time}] {symbol} ({interval}) | {partition_info}")
    print(f"  Open:  ${open_price:.4f}  |  Close: ${close_price:.4f}  |  {change_symbol} {price_change:+.2f}%")
    print(f"  High:  ${high_price:.4f}  |  Low:   ${low_price:.4f}")
    print(f"  Volume: {volume:.2f}  |  Closed: {'Yes' if is_closed else 'No'}")
    print("-" * 80)
