# Đánh giá Kiến trúc: Crypto Data Collection Pipeline

## Kiến trúc đề xuất của bạn

```
Binance API (WebSocket)
    ↓
Kafka Producer (1 phút kline)
    ↓
Kafka Topic
    ↓
Kafka Consumer → Khi x=true → Redis Cache
    ↓
OHLC Aggregator (mỗi 5 phút) → Tính OHLC 5 phút
    ↓
Airflow (cuối ngày) → Lưu vào lịch sử
```

## ✅ Điểm tốt

1. **Tách biệt streaming và batch** - Đúng hướng
2. **Kafka làm message queue** - Phù hợp cho real-time data
3. **Redis cache** - Tốt cho dữ liệu nóng (hot data)
4. **Airflow cho batch** - Phù hợp cho ETL cuối ngày
5. **Chỉ lưu khi x=true** - Đúng, chỉ lưu kline đã đóng

## ⚠️ Điểm cần cải thiện

### 1. **Redis Cache Strategy**
- **Vấn đề**: Chỉ lưu khi x=true → Mất dữ liệu real-time (chưa đóng)
- **Đề xuất**: 
  - Lưu cả kline chưa đóng (x=false) vào Redis với TTL
  - Khi x=true → Update và set TTL dài hơn
  - Dùng Redis Streams hoặc Sorted Sets để quản lý time-series

### 2. **OHLC Aggregation 5 phút**
- **Vấn đề**: Tính lại mỗi 5 phút từ đâu? Từ Redis hay Kafka?
- **Đề xuất**:
  - Dùng Kafka Streams hoặc Spark Streaming để aggregate
  - Hoặc consumer riêng đọc từ Redis và tính OHLC
  - Lưu OHLC 5 phút vào Redis và MongoDB

### 3. **Data Loss Risk**
- **Vấn đề**: Nếu Redis down → Mất dữ liệu
- **Đề xuất**: 
  - Kafka retention đủ dài (7 ngày)
  - Có thể replay từ Kafka nếu Redis mất dữ liệu
  - Hoặc lưu backup vào Kafka topic khác

### 4. **Airflow Schedule**
- **Vấn đề**: "Hết ngày" - Cần define rõ timezone và thời điểm
- **Đề xuất**: 
  - Schedule: `0 0 * * *` (00:00 UTC) hoặc `0 1 * * *` (00:00 VN)
  - Đọc từ Redis hoặc Kafka để lưu vào MongoDB/PostgreSQL

### 5. **Multiple Symbols**
- **Vấn đề**: Hiện tại chỉ có BTC, cần scale cho nhiều đồng
- **Đề xuất**: 
  - Redis key pattern: `crypto:{symbol}:{interval}:{timestamp}`
  - OHLC aggregation theo từng symbol
  - Airflow DAG có thể parallelize theo symbol

## 🎯 Kiến trúc đề xuất (Cải thiện)

```
┌─────────────────────────────────────────────────────────────┐
│                    Binance WebSocket API                   │
│              (15 cryptocurrencies, 1m kline)                 │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  Kafka Producer (Streaming)                  │
│              Topic: crypto_kline_1m (5 partitions)          │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                                 │
        ▼                                 ▼
┌──────────────────┐          ┌──────────────────────┐
│  Kafka Consumer  │          │  Kafka Streams/      │
│  (Redis Writer)  │          │  Spark Streaming      │
│                  │          │  (OHLC Aggregator)    │
│  - Filter x=true │          │                      │
│  - Write Redis   │          │  - Aggregate 1m → 5m │
│  - Write x=false │          │  - Write Redis       │
│    với TTL       │          │  - Write MongoDB     │
└────────┬─────────┘          └──────────┬──────────┘
         │                                │
         ▼                                ▼
┌─────────────────────────────────────────────────────────────┐
│                    Redis Cache                              │
│  - crypto:{symbol}:1m:{timestamp} → Kline data             │
│  - crypto:{symbol}:5m:{timestamp} → OHLC 5m                │
│  - TTL: 24h cho 1m, 7d cho 5m                              │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              Airflow DAG (Daily Batch)                      │
│  Schedule: 0 1 * * * (00:00 VN time)                       │
│                                                              │
│  Tasks:                                                      │
│  1. Read từ Redis (hoặc Kafka)                              │
│  2. Aggregate daily OHLC                                    │
│  3. Write to MongoDB/PostgreSQL                             │
│  4. Archive old Redis data                                  │
└─────────────────────────────────────────────────────────────┘
```

## 📋 Implementation Plan

### Phase 1: Redis Consumer
- Consumer đọc từ Kafka
- Filter x=true và x=false
- Lưu vào Redis với structure phù hợp

### Phase 2: OHLC Aggregator
- Đọc từ Redis hoặc Kafka
- Aggregate 1m → 5m
- Lưu vào Redis và MongoDB

### Phase 3: Airflow Integration
- DAG đọc từ Redis/Kafka
- Lưu daily data vào MongoDB
- Cleanup Redis data cũ

## 🔧 Tech Stack Recommendations

1. **Redis**: 
   - Redis Streams cho time-series
   - Hoặc Sorted Sets với timestamp làm score
   - RedisJSON cho structured data

2. **OHLC Aggregation**:
   - Kafka Streams (lightweight, real-time)
   - Spark Streaming (nếu cần complex processing)
   - Python với pandas (đơn giản, dễ maintain)

3. **Storage**:
   - MongoDB: Lịch sử dài hạn
   - PostgreSQL: Nếu cần ACID và queries phức tạp
   - MinIO/S3: Archive data cũ

## ✅ Kết luận

Kiến trúc của bạn **tốt và hợp lý**, chỉ cần:
1. ✅ Bổ sung Redis consumer
2. ✅ Implement OHLC aggregator
3. ✅ Cải thiện Redis strategy (lưu cả x=false)
4. ✅ Airflow DAG đọc từ Redis/Kafka thay vì CoinGecko API
5. ✅ Xử lý multiple symbols

Tôi sẽ tạo code mẫu cho các components này!

