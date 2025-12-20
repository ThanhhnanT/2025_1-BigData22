import json
from kafka import KafkaConsumer

TOPIC = "orderbook"

def main():
    consumer = KafkaConsumer(bootstrap_servers=['localhost:9092'],
                             group_id='test_group_0',
                             auto_offset_reset='latest',
                             value_deserializer=lambda x: json.loads(x.decode('utf-8')))
    consumer.subscribe([TOPIC])
    
    for message in consumer:
        symbol = message.key.decode()
        data = message.value
        print(data)

if __name__ == '__main__':
    main()