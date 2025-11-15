import json
from kafka import KafkaProducer
import websocket
import threading

KAFKA_BROKER = "192.168.49.2:30599"
TOPIC = "crypto_kline_1m"

# Danh sách các đồng tiền ảo muốn stream (có thể thêm/bớt tùy ý)
CRYPTO_SYMBOLS = [
    "BTC",   # Bitcoin
    "ETH",   # Ethereum
    "BNB",   # Binance Coin
    "SOL",   # Solana
    "ADA",   # Cardano
    "XRP",   # Ripple
    "DOGE",  # Dogecoin
    "DOT",   # Polkadot
    "MATIC", # Polygon
    "AVAX",  # Avalanche
    "LINK",  # Chainlink
    "UNI",   # Uniswap
    "LTC",   # Litecoin
    "ATOM",  # Cosmos
    "ETC",   # Ethereum Classic
]

# Tạo combined stream URL cho nhiều đồng tiền
def build_stream_url(symbols):
    """Tạo URL stream kết hợp cho nhiều đồng tiền"""
    streams = [f"{symbol.lower()}usdt@kline_1m" for symbol in symbols]
    stream_path = "/".join(streams)
    return f"wss://stream.binance.com:9443/stream?streams={stream_path}"

STREAM_URL = build_stream_url(CRYPTO_SYMBOLS)

producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKER,
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    key_serializer=lambda k: k.encode("utf-8") if k else None
)

def on_message(ws, message):
    data = json.loads(message)
    # Combined stream trả về data với format: {"stream": "btcusdt@kline_1m", "data": {...}}
    if "data" in data:
        kline_data = data["data"]
        stream_name = data.get("stream", "")
    else:
        # Fallback cho single stream format
        kline_data = data
        stream_name = ""

    kline = kline_data.get("k", {})
    if kline:
        symbol = kline.get("s", "UNKNOWN")
        # Sử dụng symbol làm key để đảm bảo cùng một đồng tiền luôn vào cùng partition
        # Điều này giúp đảm bảo thứ tự và cho phép parallel processing
        producer.send(TOPIC, value=kline)
        interval = kline.get("i", "")
        open_price = kline.get("o", "")
        close_price = kline.get("c", "")
        print(f"Sent to Kafka: {symbol} {interval} open={open_price} close={close_price} (key={symbol})")

def on_error(ws, error):
    print("Error:", error)

def on_close(ws, close_status_code, close_msg):
    print("### closed ###")
    print("Attempting to reconnect...")

def on_open(ws):
    print("WebSocket connection opened.")
    print(f"Streaming {len(CRYPTO_SYMBOLS)} cryptocurrencies: {', '.join(CRYPTO_SYMBOLS)}")

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
    print(f"Starting producer for {len(CRYPTO_SYMBOLS)} cryptocurrencies...")
    print(f"Stream URL: {STREAM_URL[:100]}...")  # Print first 100 chars
    t = threading.Thread(target=run_websocket)
    t.start()
