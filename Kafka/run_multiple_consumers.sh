#!/bin/bash

# Script để chạy nhiều consumer với consumer group ID khác nhau
# Mỗi consumer sẽ nhận TẤT CẢ dữ liệu (không chia sẻ)

echo "Chạy 3 consumer với consumer group khác nhau..."
echo "Mỗi consumer sẽ nhận TẤT CẢ messages (không chia sẻ partition)"
echo ""

# Terminal 1
echo "Consumer 1 - Group: crypto_group_1"
CONSUMER_GROUP=crypto_group_1 CONSUMER_ID=consumer-1 python binance_consumer.py &

# Terminal 2  
echo "Consumer 2 - Group: crypto_group_2"
CONSUMER_GROUP=crypto_group_2 CONSUMER_ID=consumer-2 python binance_consumer.py &

# Terminal 3
echo "Consumer 3 - Group: crypto_group_3"
CONSUMER_GROUP=crypto_group_3 CONSUMER_ID=consumer-3 python binance_consumer.py &

echo ""
echo "Đã khởi động 3 consumer. Nhấn Ctrl+C để dừng tất cả."
wait


