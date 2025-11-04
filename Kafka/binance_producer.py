import json
from kafka import KafkaProducer
import websocket
import threading

KAFKA_BROKER = "192.168.49.2:30113"
TOPIC = "crypto_kline_1m"
STREAM_URL = "wss://stream.binance.com:9443/ws/btcusdt@kline_1m"


producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKER,
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

def on_message(ws, message):
    data = json.loads(message)
    kline = data.get("k", {})
    producer.send(TOPIC, kline)
    print(f"Sent to Kafka: {kline['s']} {kline['i']} open={kline['o']} close={kline['c']}")

def on_error(ws, error):
    print("Error:", error)

def on_close(ws, close_status_code, close_msg):
    print("### closed ###")

def on_open(ws):
    print("WebSocket connection opened.")

def run_websocket():
    ws = websocket.WebSocketApp(
        STREAM_URL,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open
    )
    ws.run_forever()

if __name__ == "__main__":
    t = threading.Thread(target=run_websocket)
    t.start()
