#!/bin/bash

# Script để dừng tất cả các Kafka processes
# Usage: ./stop_all.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/kafka_processes.pid"

echo "🛑 Đang dừng tất cả Kafka processes..."

if [ ! -f "$PID_FILE" ]; then
    echo "⚠️  Không tìm thấy PID file. Có thể các processes đã được dừng."
    echo "   Đang tìm và dừng các processes theo tên..."
    
    # Tìm và dừng các processes theo tên
    pkill -f "binance_producer.py" 2>/dev/null
    pkill -f "binance_orderbook_trades_producer.py" 2>/dev/null
    pkill -f "redis_consumer.py" 2>/dev/null
    pkill -f "redis_orderbook_trades_consumer.py" 2>/dev/null
    
    echo "✅ Đã thử dừng các processes theo tên"
    exit 0
fi

# Đọc và dừng từng process
count=0
while read pid; do
    if ps -p $pid > /dev/null 2>&1; then
        echo "  Killing process $pid"
        kill $pid 2>/dev/null
        count=$((count + 1))
    fi
done < "$PID_FILE"

if [ $count -eq 0 ]; then
    echo "⚠️  Không có process nào đang chạy"
else
    echo "✅ Đã dừng $count process(es)"
fi

# Xóa PID file
rm -f "$PID_FILE"
echo "✅ Đã xóa PID file"

