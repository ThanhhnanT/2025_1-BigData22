import redis
import time
import json

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

while True:
    # Lấy thử một con coin
    data = r.hget("LIVE_ORDERBOOK", "ETHUSDT")
    if data:
        book = json.loads(data)
        print(book)
    else:
        print("Empty")
    time.sleep(1)