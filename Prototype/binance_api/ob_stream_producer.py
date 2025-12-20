import websocket
import json
import time
from kafka import KafkaProducer

producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
    linger_ms=10, 
    compression_type='lz4'
)

TOPIC_NAME = "orderbook_update"

def on_message(ws, message):
    try:
        data = json.loads(message)
        payload = data.get('data', data)
        symbol = payload.get('s')
        u_id = payload.get('u')

        producer.send(TOPIC_NAME, key=symbol.encode('utf-8'), value=payload)
        
        print(f"Buffered update ID: {u_id}, symbol: {symbol}")
        
    except Exception as e:
        print(e)

def on_error(ws, error):
    print(f"Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("Connection closed")
    producer.flush() # Đảm bảo dữ liệu cuối cùng được gửi đi

def on_open(ws):
    print("Connection opened")

if __name__ == "__main__":
    symbols = ['btcusdt', 'ethusdt', 'bnbusdt', 'solusdt', 'adausdt', 'xrpusdt']
    streams = "/".join([f"{symbol}@depth" for symbol in symbols])
    socket_url = f"wss://fstream.binance.com/stream?streams={streams}"
    print(socket_url)
    
    ws = websocket.WebSocketApp(
        socket_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    ws.run_forever()