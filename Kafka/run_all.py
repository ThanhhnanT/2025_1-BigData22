#!/usr/bin/env python3
"""
Script để chạy tất cả các Kafka producers và consumers cùng lúc
Usage: python3 run_all.py
"""

import os
import sys
import subprocess
import signal
import time
from pathlib import Path

# Đường dẫn thư mục hiện tại
SCRIPT_DIR = Path(__file__).parent.absolute()
LOG_DIR = SCRIPT_DIR / "logs"
PID_FILE = SCRIPT_DIR / "kafka_processes.pid"

# Tạo thư mục logs nếu chưa có
LOG_DIR.mkdir(exist_ok=True)

# Danh sách các processes
processes = []

def cleanup(signum=None, frame=None):
    """Cleanup function khi script bị dừng"""
    print("\n🛑 Đang dừng tất cả các processes...")
    
    # Dừng tất cả processes
    for proc in processes:
        if proc.poll() is None:  # Process vẫn đang chạy
            print(f"  Killing process {proc.pid} ({proc.args[1]})")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    
    # Xóa PID file
    if PID_FILE.exists():
        PID_FILE.unlink()
    
    print("✅ Đã dừng tất cả processes")
    sys.exit(0)

# Đăng ký signal handlers
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

def start_process(name, script_name, log_file):
    """Khởi động một process"""
    log_path = LOG_DIR / log_file
    script_path = SCRIPT_DIR / script_name
    
    print(f"🚀 Starting {name}...")
    
    try:
        # Mở log file
        log_handle = open(log_path, "w")
        
        # Khởi động process
        proc = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            cwd=str(SCRIPT_DIR)
        )
        
        processes.append(proc)
        
        # Lưu PID vào file
        with open(PID_FILE, "a") as f:
            f.write(f"{proc.pid}\n")
        
        print(f"  ✅ PID: {proc.pid} | Log: {log_path}")
        time.sleep(2)  # Đợi một chút trước khi start process tiếp theo
        
        return proc
    except Exception as e:
        print(f"  ❌ Lỗi khi khởi động {name}: {e}")
        return None

def main():
    """Hàm main"""
    print("=" * 80)
    print("🚀 Starting all Kafka Producers and Consumers")
    print("=" * 80)
    print()
    
    # Xóa PID file cũ nếu có
    if PID_FILE.exists():
        PID_FILE.unlink()
    
    # 1. Binance Kline Producer
    start_process(
        "Binance Kline Producer",
        "binance_producer.py",
        "kline_producer.log"
    )
    
    # 2. Binance OrderBook & Trades Producer
    start_process(
        "Binance OrderBook & Trades Producer",
        "binance_orderbook_trades_producer.py",
        "orderbook_trades_producer.log"
    )
    
    # 3. Redis Kline Consumer
    start_process(
        "Redis Kline Consumer",
        "redis_consumer.py",
        "kline_consumer.log"
    )
    
    # 4. Redis OrderBook & Trades Consumer
    start_process(
        "Redis OrderBook & Trades Consumer",
        "redis_orderbook_trades_consumer.py",
        "orderbook_trades_consumer.log"
    )
    
    print()
    print("=" * 80)
    print("✅ Tất cả processes đã được khởi động!")
    print("=" * 80)
    print()
    print("📋 Process IDs:")
    for i, proc in enumerate(processes, 1):
        if proc:
            print(f"  {i}. PID {proc.pid}")
    print()
    print(f"📁 Logs được lưu tại: {LOG_DIR}/")
    print()
    print("💡 Nhấn Ctrl+C để dừng tất cả processes")
    print()
    
    # Monitor các processes
    try:
        while True:
            time.sleep(5)
            
            # Kiểm tra xem các processes còn chạy không
            running_count = sum(1 for p in processes if p.poll() is None)
            
            if running_count < len(processes):
                stopped = [p for p in processes if p.poll() is not None]
                for proc in stopped:
                    print(f"⚠️  Warning: Process {proc.pid} ({proc.args[1]}) đã dừng")
                    print(f"   Kiểm tra log tại: {LOG_DIR}/{proc.args[1].replace('.py', '.log')}")
    
    except KeyboardInterrupt:
        cleanup()

if __name__ == "__main__":
    main()

