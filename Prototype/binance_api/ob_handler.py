from typing import Dict
import redis.asyncio as redis
import json
import time
from sortedcontainers import SortedDict
import aiohttp
import asyncio
from aiokafka import AIOKafkaConsumer

REDIS_URL = "redis://localhost:6379"

class LocalOrderBook:
    def __init__(self, symbol):
        self.symbol = symbol
        self.bids = SortedDict(lambda val: -float(val))
        self.asks = SortedDict(lambda val: float(val))

        self.last_push_time = 0
        self.last_updated_id = 0
        self.is_synced = False

    def apply_update(self, data):
        self.update_levels(data['b'], self.bids)
        self.update_levels(data['a'], self.asks)
        self.last_updated_id = data['u']

    def update_levels(self, levels, book_side : SortedDict):
        for price, qty in levels:
            if float(qty) == 0:
                book_side.pop(price, None)
            else:
                book_side[price] = qty
    
    # def get_top_n(self, n=10):
    #     top_bids = [[p, q] for p, q in list(self.bids.items())[:n]]
    #     top_asks = [[p, q] for p, q in list(self.asks.items())[:n]]

    #     return {
    #         "s": self.symbol,
    #         "b": top_bids,
    #         "a": top_asks,
    #         "u": self.last_update_id
    #     }
    
    def get_payload(self):
        return json.dumps({
            "s": self.symbol,
            "b": list(self.bids.items())[:10],
            "a": list(self.asks.items())[:10],
            "u": self.last_update_id
        })
    
    def display_top(self):
        top_bids = list(self.bids.items())[:3]
        top_asks = list(self.asks.items())[:3]
        
        print(f"\n--- {self.symbol} | ID: {self.last_update_id} ---")
        print(f"ASKS: {top_asks[::-1]}") 
        print(f"BIDS: {top_bids}")
        print("-" * 30)

    def clear(self):
        self.bids.clear()
        self.asks.clear()
        self.is_synced = False

orderbooks: Dict[str, LocalOrderBook] = {}
event_buffers = {}

async def fetch_snapshot(symbol: str, limit=1000):
    url = f"https://fapi.binance.com/fapi/v1/depth?symbol={symbol.upper()}&limit={limit}"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    snapshot = await resp.json()
                    book = orderbooks[symbol]

                    book.update_levels(snapshot['bids'], book.bids)
                    book.update_levels(snapshot['asks'], book.asks)
                    book.last_update_id = snapshot['lastUpdateId']

                    if symbol in event_buffers:
                        buffer_count = 0
                        for event in event_buffers[symbol]: 
                            if event['u'] > book.last_update_id:
                                book.apply_update(event)
                                buffer_count += 1
                        del event_buffers[symbol]

                    book.is_synced = True
        except Exception as e:
            print(e)

async def run_consumer():
    r = redis.from_url(REDIS_URL, decode_responses=True)

    consumer = AIOKafkaConsumer('orderbook_update',
                                bootstrap_servers=['localhost:9092'],
                                group_id='ob_consumers',
                                auto_offset_reset='latest',
                                value_deserializer=lambda x: json.loads(x.decode('utf-8')))
    connected = False
    while not connected:
        try:
            print("Đang thử kết nối với Kafka...")
            await consumer.start()
            connected = True
            print("Kết nối thành công!")
        except Exception as e:
            print(f"Chưa tìm thấy Coordinator: {e}. Thử lại sau 2s...")
            await asyncio.sleep(2)
    print("Consumer đã khởi động. Đang đợi tin nhắn từ Kafka...")

    try:
        async for msg in consumer:
            data = msg.value
            symbol = data['s']

            if symbol not in orderbooks:
                orderbooks[symbol] = LocalOrderBook(symbol)
                event_buffers[symbol] = []
                asyncio.create_task(fetch_snapshot(symbol))

            book = orderbooks[symbol]

            if not book.is_synced:
                event_buffers[symbol].append(data)
            else:
                if data['u'] > book.last_update_id:
                    book.apply_update(data)

                    now = time.time()
                    if now - book.last_push_time > 0.1:
                        await r.hset("LIVE_ORDERBOOK", symbol, book.get_payload())
                        book.last_push_time = now
    finally:
        await consumer.stop()

def main():
    asyncio.run(run_consumer())

if __name__ == "__main__":
    main()