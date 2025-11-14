# Kiến trúc với PySpark

## Tổng quan

Pipeline sử dụng PySpark để xử lý streaming và batch data:

```
┌─────────────────────────────────────────────────────────────┐
│                    Binance WebSocket API                   │
│              (15 cryptocurrencies, 1m kline)                 │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  Kafka Producer (Python)                    │
│              Topic: crypto_kline_1m (5 partitions)          │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
        ▼                               ▼
┌──────────────────┐          ┌──────────────────────┐
│  PySpark Redis   │          │  PySpark OHLC 5m      │
│     Writer       │          │    Aggregator        │
│  (Streaming)     │          │   (Streaming)        │
│                  │          │                      │
│  - Filter x=true │          │  - Window 5 minutes     │
│  - Write Redis   │          │  - Aggregate OHLC     │
│  - TTL 24h       │          │  - Write Redis + Mongo│
└────────┬─────────┘          └──────────┬──────────┘
         │                                │
         ▼                                ▼
┌─────────────────────────────────────────────────────────────┐
│                    Redis Cache                              │
│  - crypto:{symbol}:1m:{timestamp} → Kline 1m               │
│  - crypto:{symbol}:5m:{timestamp} → OHLC 5m               │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│         PySpark Batch MongoDB Writer (Airflow)              │
│  Schedule: 0 1 * * * (00:00 VN time)                       │
│                                                              │
│  - Read from Kafka (yesterday's data)                       │
│  - Batch write to MongoDB                                   │
│  - Daily backup                                             │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Spark Redis Writer (Streaming)

**File**: `spark_redis_writer.py`

**Chức năng**:
- Đọc từ Kafka topic `crypto_kline_1m`
- Filter kline đã đóng (x=true)
- Lưu vào Redis với TTL 24h
- Tạo index và latest key

**Tính năng**:
- Structured Streaming với checkpoint
- Custom ForeachWriter để ghi vào Redis
- Trigger mỗi 10 giây

**Chạy**:
```bash
spark-submit spark_redis_writer.py
```

### 2. Spark OHLC 5m Aggregator (Streaming)

**File**: `spark_ohlc_5m_aggregator.py`

**Chức năng**:
- Đọc từ Kafka topic `crypto_kline_1m`
- Filter kline đã đóng (x=true)
- Window aggregation 5 phút
- Tính OHLC 5m
- Lưu vào Redis và MongoDB

**Tính năng**:
- Watermark để xử lý late data
- Window function với 5 phút
- Dual write: Redis + MongoDB
- Trigger mỗi 1 phút

**Chạy**:
```bash
spark-submit spark_ohlc_5m_aggregator.py
```

### 3. Spark Batch MongoDB Writer (Batch)

**File**: `spark_batch_mongodb_writer.py`

**Chức năng**:
- Đọc từ Kafka với time range (yesterday)
- Filter kline đã đóng
- Batch write vào MongoDB
- Chạy từ Airflow mỗi ngày

**Tính năng**:
- Batch processing (không streaming)
- Time range filtering
- MongoDB connector

**Chạy từ Airflow**:
```python
SparkSubmitOperator(
    task_id="spark_batch_mongodb",
    application="spark_batch_mongodb_writer.py"
)
```

## Lợi ích của PySpark

### 1. Scalability
- Có thể scale trên Spark cluster
- Distributed processing
- Parallel execution

### 2. Fault Tolerance
- Checkpoint và recovery tự động
- Exactly-once semantics với Kafka
- Retry mechanism

### 3. Window Aggregation
- Time-based window functions
- Watermark cho late data
- Efficient aggregation

### 4. Integration
- Kafka connector tích hợp sẵn
- MongoDB connector
- Redis qua custom writer

### 5. Monitoring
- Spark UI để monitor
- Metrics và logging
- Query progress tracking

## So sánh: PySpark vs Python thuần

| Feature | PySpark | Python thuần |
|---------|---------|--------------|
| Scalability | ✅ Cluster | ❌ Single node |
| Fault Tolerance | ✅ Checkpoint | ❌ Manual |
| Window Aggregation | ✅ Built-in | ❌ Manual |
| Late Data | ✅ Watermark | ❌ Complex |
| Monitoring | ✅ Spark UI | ❌ Custom |
| Resource Usage | ⚠️ Higher | ✅ Lower |

## Deployment

### Local Development
```bash
# Terminal 1: Redis Writer
python spark_redis_writer.py

# Terminal 2: OHLC Aggregator
python spark_ohlc_5m_aggregator.py
```

### Production (Kubernetes)
```yaml
# Spark Operator để deploy lên K8s
apiVersion: sparkoperator.k8s.io/v1beta2
kind: SparkApplication
metadata:
  name: crypto-redis-writer
spec:
  type: Python
  pythonVersion: "3"
  mode: cluster
  image: spark:3.5.0
  mainApplicationFile: spark_redis_writer.py
  ...
```

### Airflow Integration
Xem `airflow/dags/spark_crypto_pipeline.py`

## Monitoring

### Spark UI
- URL: `http://localhost:4040`
- Xem streaming queries
- Monitor processing time
- Check errors

### Checkpoint
- Location: `/tmp/spark_*_checkpoint`
- Recovery từ checkpoint nếu restart
- Cleanup old checkpoints

## Best Practices

1. **Checkpoint Location**: Dùng persistent storage
2. **Watermark**: Set phù hợp với data latency
3. **Trigger**: Balance latency và throughput
4. **Partitioning**: Đảm bảo đủ partitions
5. **Resource**: Allocate đủ memory/cores
6. **Monitoring**: Monitor Spark UI và logs

## Troubleshooting

### Job không start
- Kiểm tra Spark packages
- Kiểm tra Kafka connection
- Kiểm tra checkpoint location

### Slow processing
- Tăng executor memory
- Tăng số partitions
- Optimize window size

### Data loss
- Kiểm tra watermark
- Kiểm tra checkpoint
- Kiểm tra Kafka retention

