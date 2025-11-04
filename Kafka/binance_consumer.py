from kafka import KafkaConsumer
import json
from pprint import pprint

KAFKA_BROKER = "192.168.49.2:30113"
TOPIC = "crypto_kline_1m"

consumer = KafkaConsumer(
    TOPIC,
    bootstrap_servers=KAFKA_BROKER,
    auto_offset_reset='latest',
    enable_auto_commit=True,
    group_id='crypto_group',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

print("Listening for messages...")
for msg in consumer:
    kline = msg.value
    symbol = kline.get("s")
    open_price = kline.get("o")
    close_price = kline.get("c")
    print(f"{symbol}: open={open_price} close={close_price}")
    pprint(kline)