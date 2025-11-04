import asyncio
import json

from kafka import KafkaProducer
from binance_common.configuration import ConfigurationWebSocketStreams
from binance_common.constants import SPOT_WS_STREAMS_PROD_URL
from binance_sdk_spot.spot import Spot

KAFKA_TOPIC = "crypto-topic"
KAFKA_SERVER = "localhost:9092"
SYMBOLS = ["btcusdt", "ethusdt", "solusdt"]


def build_producer():
    print(f"Connecting to Kafka server at {KAFKA_SERVER}...")
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_SERVER,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    print("Connected to Kafka.")
    return producer


def handle_message(raw_msg, producer: KafkaProducer):
    try:
        if hasattr(raw_msg, "s"):
            symbol = str(raw_msg.s)
            price = float(raw_msg.p)
            quantity = float(raw_msg.q)
            event_time = int(raw_msg.E)
        else:
            if isinstance(raw_msg, str):
                msg = json.loads(raw_msg)
            else:
                msg = raw_msg
            data = msg.get("data", msg)
            symbol = data["s"]
            price = float(data["p"])
            quantity = float(data["q"])
            event_time = int(data["E"])

        trade_data = {
            "symbol": symbol,
            "price": price,
            "quantity": quantity,
            "event_time": event_time,
        }

        producer.send(KAFKA_TOPIC, value=trade_data)
        print(f"Sent to Kafka: {trade_data}")
    except Exception as e:
        print(f"Error processing message: {e}")
        print(f"Raw message: {raw_msg}")


async def main():
    producer = build_producer()

    config_ws_streams = ConfigurationWebSocketStreams(
        stream_url=SPOT_WS_STREAMS_PROD_URL
    )
    client = Spot(config_ws_streams=config_ws_streams)

    connection = None
    streams = []

    try:
        print("Creating Binance WebSocket Streams connection...")
        connection = await client.websocket_streams.create_connection()
        print("Connection created.")

        for symbol in SYMBOLS:
            print(f"Subscribing aggTrade stream for {symbol}...")
            stream = await connection.agg_trade(symbol=symbol)
            stream.on(
                "message",
                lambda data, p=producer: handle_message(data, p),
            )
            streams.append(stream)

        print(f"Subscribed to aggTrade streams for: {SYMBOLS}")
        print("Collector is running. Press Ctrl+C to stop.")

        while True:
            await asyncio.sleep(1)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"Fatal error in main(): {e}")
    finally:
        print("Shutting down Binance WebSocket & Kafka...")
        try:
            for s in streams:
                try:
                    await s.unsubscribe()
                except Exception:
                    pass
            if connection:
                await connection.close_connection(close_session=True)
        except Exception as e:
            print(f"Error while closing Binance connection: {e}")

        try:
            producer.flush()
            producer.close()
        except Exception:
            pass

        print("Shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped by user.")
