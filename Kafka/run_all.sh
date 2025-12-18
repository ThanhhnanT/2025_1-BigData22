#!/bin/bash

# Script để chạy tất cả các Kafka producers và consumers cùng lúc
# Usage: ./run_all.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
PID_FILE="$SCRIPT_DIR/kafka_processes.pid"

# Tạo thư mục logs nếu chưa có
mkdir -p "$LOG_DIR"

# Hàm cleanup khi script bị dừng
cleanup() {
    echo ""
    echo "🛑 Đang dừng tất cả các processes..."
    if [ -f "$PID_FILE" ]; then
        while read pid; do
            if ps -p $pid > /dev/null 2>&1; then
                echo "  Killing process $pid"
                kill $pid 2>/dev/null
            fi
        done < "$PID_FILE"
        rm -f "$PID_FILE"
    fi
    echo "✅ Đã dừng tất cả processes"
    exit 0
}

# Đăng ký signal handlers
trap cleanup SIGINT SIGTERM

echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'
echo "🚀 Starting all Kafka Producers and Consumers"
echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'
echo ""

# Xóa PID file cũ nếu có
rm -f "$PID_FILE"

# 0. Clear Redis data (optional - uncomment if you want to clear Redis on startup)
# echo "🗑️  Clearing Redis data..."
# cd "$SCRIPT_DIR"
# python3 clear_redis.py
# echo "✅ Redis cleared"
# sleep 1

# # 0.1. Fetch historical 1m data into Redis
# echo "📥 Fetching historical 1m data into Redis..."
# python3 binance_history_fetcher.py > "$LOG_DIR/history_fetcher.log" 2>&1
# echo "✅ Historical data fetched"
# sleep 2

# 1. Binance Kline Producer
echo "📊 Starting Binance Kline Producer..."
cd "$SCRIPT_DIR"
python3 binance_producer.py > "$LOG_DIR/kline_producer.log" 2>&1 &
KLINE_PRODUCER_PID=$!
echo "$KLINE_PRODUCER_PID" >> "$PID_FILE"
echo "  PID: $KLINE_PRODUCER_PID | Log: $LOG_DIR/kline_producer.log"
sleep 2

# 2. Binance OrderBook & Trades Producer
echo "📈 Starting Binance OrderBook & Trades Producer..."
python3 binance_orderbook_trades_producer.py > "$LOG_DIR/orderbook_trades_producer.log" 2>&1 &
ORDERBOOK_PRODUCER_PID=$!
echo "$ORDERBOOK_PRODUCER_PID" >> "$PID_FILE"
echo "  PID: $ORDERBOOK_PRODUCER_PID | Log: $LOG_DIR/orderbook_trades_producer.log"
sleep 2

# 3. Redis Kline Consumer
echo "💾 Starting Redis Kline Consumer..."
python3 redis_consumer.py > "$LOG_DIR/kline_consumer.log" 2>&1 &
KLINE_CONSUMER_PID=$!
echo "$KLINE_CONSUMER_PID" >> "$PID_FILE"
echo "  PID: $KLINE_CONSUMER_PID | Log: $LOG_DIR/kline_consumer.log"
sleep 2

# 4. Redis OrderBook & Trades Consumer
echo "💾 Starting Redis OrderBook & Trades Consumer..."
python3 redis_orderbook_trades_consumer.py > "$LOG_DIR/orderbook_trades_consumer.log" 2>&1 &
ORDERBOOK_CONSUMER_PID=$!
echo "$ORDERBOOK_CONSUMER_PID" >> "$PID_FILE"
echo "  PID: $ORDERBOOK_CONSUMER_PID | Log: $LOG_DIR/orderbook_trades_consumer.log"
sleep 2

echo ""
echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'
echo "✅ Tất cả processes đã được khởi động!"
echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'
echo ""
echo "📋 Process IDs:"
echo "  - Kline Producer:      $KLINE_PRODUCER_PID"
echo "  - OrderBook Producer:  $ORDERBOOK_PRODUCER_PID"
echo "  - Kline Consumer:       $KLINE_CONSUMER_PID"
echo "  - OrderBook Consumer:   $ORDERBOOK_CONSUMER_PID"
echo ""
echo "📁 Logs được lưu tại: $LOG_DIR/"
echo ""
echo "💡 Nhấn Ctrl+C để dừng tất cả processes"
echo ""

# Giữ script chạy và monitor các processes
while true; do
    sleep 5
    # Kiểm tra xem các processes còn chạy không
    all_running=true
    while read pid; do
        if ! ps -p $pid > /dev/null 2>&1; then
            echo "⚠️  Warning: Process $pid đã dừng"
            all_running=false
        fi
    done < "$PID_FILE"
    
    if [ "$all_running" = false ]; then
        echo "⚠️  Một số processes đã dừng. Kiểm tra logs tại $LOG_DIR/"
    fi
done

