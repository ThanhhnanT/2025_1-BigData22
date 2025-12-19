import requests
import json
import time
from kafka import KafkaProducer, KafkaConsumer

TOPIC = "orderbook"

base_url =  "https://fapi.binance.com"
endpoint = "/fapi/v1/depth"
symbol = "BTCUSDT"

def main():
    producer = KafkaProducer(bootstrap_servers='localhost:9092')

    url = f"{base_url}{endpoint}"
    params = {
        "symbol": symbol,
        "limit": 5
    }

    while True:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            producer.send(TOPIC, data)
            producer.flush()
        else:
            print(f"ERROR! Status code: {response.status_code}")
        time.sleep(1.5)

if __name__ == '__main__':
    main()
    
