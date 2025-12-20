import requests
import json
import time
from kafka import KafkaProducer, KafkaConsumer

TOPIC = "orderbook"

base_url =  "https://fapi.binance.com"
endpoint = "/fapi/v1/depth"
symbol = "BTCUSDT"

def main():
    producer = KafkaProducer(bootstrap_servers='localhost:9092',
                             value_serializer=lambda v: json.dumps(v).encode('utf-8'))

    url = f"{base_url}{endpoint}"
    params = {
        "symbol": symbol,
        "limit": 5
    }

    while True:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            future = producer.send(TOPIC, key=symbol.encode(), value=data)
            record_metadata = future.get(timeout=10)

            print(f"Message sent! {record_metadata.partition}")
        else:
            print(f"ERROR! Status code: {response.status_code}")
        
        producer.flush()
        time.sleep(1.5)

if __name__ == '__main__':
    main()
    
