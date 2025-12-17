import json
from kafka import KafkaProducer
import websocket
import threading
import time

KAFKA_BROKER = "192.168.49.2:30995"
TOPIC_ORDERBOOK = "crypto_orderbook"
TOPIC_TRADES = "crypto_trades"

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
    "ETC",
]

def build_stream_url(symbols):
    """
    Build WebSocket URL for Order Book depth and Trade streams.
    Format: {symbol}@depth@100ms and {symbol}@trade
    """
    streams = []
    for symbol in symbols:
        symbol_lower = symbol.lower()
        streams.append(f"{symbol_lower}usdt@depth@1000ms")  # Order Book updates every 100ms
        streams.append(f"{symbol_lower}usdt@trade")        # Market Trades
    stream_path = "/".join(streams)
    return f"wss://stream.binance.com:9443/stream?streams={stream_path}"

STREAM_URL = build_stream_url(CRYPTO_SYMBOLS)

producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKER,
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    key_serializer=lambda k: k.encode("utf-8") if k else None
)

def on_message(ws, message):
    try:
        data = json.loads(message)
        
        # Binance WebSocket format: {"stream": "btcusdt@depth@100ms", "data": {...}}
        if "stream" in data and "data" in data:
            stream_name = data["stream"]
            stream_data = data["data"]
            
            # Determine stream type and symbol
            if "@depth" in stream_name:
                # Order Book depth update
                symbol = stream_data.get("s", "").upper()
                if symbol:
                    # Add timestamp and stream info
                    enriched_data = {
                        **stream_data,
                        "stream": stream_name,
                        "received_at": int(time.time() * 1000)  # milliseconds
                    }
                    producer.send(TOPIC_ORDERBOOK, key=symbol, value=enriched_data)
                    print(f"📊 Order Book: {symbol} | Last update ID: {stream_data.get('lastUpdateId', 'N/A')}")
            
            elif "@trade" in stream_name:
                # Market Trade
                symbol = stream_data.get("s", "").upper()
                if symbol:
                    # Add timestamp and stream info
                    enriched_data = {
                        **stream_data,
                        "stream": stream_name,
                        "received_at": int(time.time() * 1000)  # milliseconds
                    }
                    producer.send(TOPIC_TRADES, key=symbol, value=enriched_data)
                    price = float(stream_data.get("p", 0))
                    quantity = float(stream_data.get("q", 0))
                    is_buyer_maker = stream_data.get("m", False)
                    side = "SELL" if is_buyer_maker else "BUY"
                    print(f"💰 Trade: {symbol} | {side} | Price: {price:.2f} | Qty: {quantity:.6f}")
        else:
            # Fallback: direct data (shouldn't happen with Binance format)
            print(f"⚠️ Unexpected message format: {data.keys()}")
    
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
    except Exception as e:
        print(f"❌ Error processing message: {e}")

def on_error(ws, error):
    print(f"❌ WebSocket error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("### WebSocket closed ###")
    print(f"Close status code: {close_status_code}")
    print(f"Close message: {close_msg}")
    print("Attempting to reconnect in 5 seconds...")
    time.sleep(5)
    run_websocket()

def on_open(ws):
    print("✅ WebSocket connection opened.")
    print(f"Streaming Order Book and Trades for {len(CRYPTO_SYMBOLS)} cryptocurrencies")
    print(f"Symbols: {', '.join(CRYPTO_SYMBOLS)}")
    print(f"Topics: {TOPIC_ORDERBOOK}, {TOPIC_TRADES}")

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
    print("=" * 80)
    print("Starting Binance Order Book & Trades Producer")
    print("=" * 80)
    print(f"Kafka Broker: {KAFKA_BROKER}")
    print(f"Order Book Topic: {TOPIC_ORDERBOOK}")
    print(f"Trades Topic: {TOPIC_TRADES}")
    print(f"Stream URL: {STREAM_URL[:150]}...")
    print("=" * 80)
    
    t = threading.Thread(target=run_websocket, daemon=True)
    t.start()
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down producer...")
        producer.close()

