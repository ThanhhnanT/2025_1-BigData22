# Hướng dẫn chạy tất cả Kafka Producers và Consumers

## Tổng quan

Có 2 cách để chạy tất cả 4 file Kafka cùng lúc:

1. **Shell Script** (`run_all.sh`) - Đơn giản, dễ sử dụng
2. **Python Script** (`run_all.py`) - Có thêm tính năng monitoring

## Các file sẽ được chạy

1. `binance_producer.py` - Producer cho Kline data (candlestick)
2. `binance_orderbook_trades_producer.py` - Producer cho Order Book và Market Trades
3. `redis_consumer.py` - Consumer lưu Kline data vào Redis
4. `redis_orderbook_trades_consumer.py` - Consumer lưu Order Book và Trades vào Redis

## Cách sử dụng

### Cách 1: Shell Script (Khuyến nghị)

```bash
cd Kafka
./run_all.sh
```

Hoặc:

```bash
bash run_all.sh
```

### Cách 2: Python Script

```bash
cd Kafka
python3 run_all.py
```

## Dừng tất cả processes

### Cách 1: Nhấn Ctrl+C
Khi đang chạy script, nhấn `Ctrl+C` để dừng tất cả processes.

### Cách 2: Sử dụng stop script

```bash
cd Kafka
./stop_all.sh
```

Hoặc:

```bash
bash stop_all.sh
```

## Logs

Tất cả logs được lưu trong thư mục `logs/`:

- `logs/kline_producer.log` - Log của Kline Producer
- `logs/orderbook_trades_producer.log` - Log của OrderBook Producer
- `logs/kline_consumer.log` - Log của Kline Consumer
- `logs/orderbook_trades_consumer.log` - Log của OrderBook Consumer

## Kiểm tra processes đang chạy

```bash
# Xem các processes Python đang chạy
ps aux | grep python

# Xem các processes cụ thể
ps aux | grep binance_producer
ps aux | grep redis_consumer
```

## Troubleshooting

### Processes không khởi động được

1. Kiểm tra Python đã được cài đặt:
   ```bash
   python3 --version
   ```

2. Kiểm tra các dependencies:
   ```bash
   pip3 install kafka-python websocket-client redis
   ```

3. Kiểm tra Kafka broker có đang chạy không:
   ```bash
   # Kiểm tra Kafka port
   netstat -tuln | grep 30995
   ```

4. Kiểm tra Redis có đang chạy không:
   ```bash
   redis-cli ping
   ```

### Processes tự động dừng

1. Kiểm tra logs trong thư mục `logs/` để xem lỗi
2. Kiểm tra kết nối đến Kafka và Redis
3. Kiểm tra WebSocket connection đến Binance

### Dừng processes thủ công

Nếu script không dừng được, có thể dừng thủ công:

```bash
# Tìm và dừng theo tên
pkill -f binance_producer.py
pkill -f redis_consumer.py

# Hoặc dừng theo PID
kill <PID>
```

## Lưu ý

- Đảm bảo Kafka broker đang chạy trước khi start các producers/consumers
- Đảm bảo Redis đang chạy trước khi start các consumers
- Các processes sẽ tự động reconnect nếu mất kết nối
- Logs sẽ được ghi vào file, không hiển thị trên terminal (trừ khi dùng Python script với output)

