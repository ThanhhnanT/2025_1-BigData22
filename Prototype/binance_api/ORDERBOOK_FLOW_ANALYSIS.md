# Phân Tích Luồng Order Book - Prototype/binance_api

## 📊 Tổng Quan Luồng Dữ Liệu

```
Binance WebSocket → Producer (Kafka) → Consumer (Kafka) → Redis → Frontend/Backend
```

---

## 🔄 Các Component Trong Luồng

### 1. **ob_stream_producer.py** - WebSocket Producer
**Vai trò**: Nhận dữ liệu real-time từ Binance và gửi vào Kafka

**Luồng hoạt động**:
1. Kết nối WebSocket đến Binance Futures API
   - URL: `wss://fstream.binance.com/stream?streams={symbols}@depth`
   - Symbols: BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, ADAUSDT, XRPUSDT
   
2. Nhận message từ WebSocket (định dạng Binance depth stream)
   ```json
   {
     "data": {
       "s": "BTCUSDT",      // symbol
       "u": 123456789,      // update ID
       "b": [[price, qty]], // bids
       "a": [[price, qty]]  // asks
     }
   }
   ```

3. Gửi vào Kafka topic `orderbook_update`
   - Key: symbol (để partition theo symbol)
   - Value: payload từ Binance
   - Compression: LZ4
   - Linger: 10ms (batch messages)

**Cấu hình Kafka Producer**:
- Bootstrap servers: `localhost:9092`
- Serializer: JSON
- Compression: LZ4 (giảm bandwidth)
- Linger: 10ms (tối ưu throughput)

---

### 2. **ob_handler.py** - Order Book Handler & Consumer
**Vai trò**: Xử lý order book updates từ Kafka, maintain local order book, lưu vào Redis

#### 2.1. LocalOrderBook Class
**Chức năng**: Quản lý order book local cho mỗi symbol

**Cấu trúc dữ liệu**:
- `bids`: SortedDict (sắp xếp giảm dần theo price)
- `asks`: SortedDict (sắp xếp tăng dần theo price)
- `last_update_id`: ID update cuối cùng từ Binance
- `is_synced`: Trạng thái đã sync snapshot chưa

**Các phương thức**:
- `apply_update(data)`: Áp dụng update vào order book
- `update_levels(levels, book_side)`: Cập nhật bids/asks
  - Nếu qty = 0 → xóa level đó
  - Nếu qty > 0 → thêm/cập nhật level
- `get_payload()`: Lấy top 10 bids/asks để lưu Redis
- `display_top()`: Hiển thị top 3 bids/asks

#### 2.2. Kafka Consumer
**Luồng xử lý**:

1. **Kết nối Kafka**
   - Topic: `orderbook_update`
   - Group ID: `ob_consumers`
   - Auto offset reset: `latest`
   - Deserializer: JSON

2. **Xử lý message từ Kafka**:
   ```
   Nhận message → Kiểm tra symbol → Tạo LocalOrderBook nếu chưa có
   → Fetch snapshot từ Binance REST API (nếu chưa sync)
   → Buffer events trong khi chờ snapshot
   → Áp dụng updates vào order book
   → Lưu vào Redis mỗi 100ms (rate limiting)
   ```

3. **Snapshot Sync Process**:
   - Khi nhận symbol mới → tạo LocalOrderBook
   - Fetch snapshot từ: `https://fapi.binance.com/fapi/v1/depth?symbol={symbol}&limit=1000`
   - Buffer các events nhận được trong khi chờ snapshot
   - Sau khi có snapshot:
     - Áp dụng snapshot vào order book
     - Áp dụng các events đã buffer (nếu update_id > snapshot_id)
     - Đánh dấu `is_synced = True`

4. **Lưu vào Redis**:
   - Key: `LIVE_ORDERBOOK` (Hash)
   - Field: `{symbol}` (ví dụ: BTCUSDT)
   - Value: JSON payload với top 10 bids/asks
   - Rate limiting: Chỉ lưu mỗi 100ms (0.1s) để tránh spam Redis

**Cấu trúc dữ liệu Redis**:
```json
{
  "s": "BTCUSDT",
  "b": [[price, qty], ...],  // Top 10 bids
  "a": [[price, qty], ...],  // Top 10 asks
  "u": 123456789             // Last update ID
}
```

---

### 3. **redis_read_test.py** - Test Consumer
**Vai trò**: Test đọc order book từ Redis

**Hoạt động**:
- Đọc từ Redis key `LIVE_ORDERBOOK` field `ETHUSDT`
- In ra console mỗi 1 giây
- Kiểm tra dữ liệu có tồn tại không

---

## 🔀 Luồng Dữ Liệu Chi Tiết

### Phase 1: Initialization
```
1. Producer kết nối Binance WebSocket
2. Producer nhận depth stream updates
3. Producer gửi vào Kafka topic "orderbook_update"
```

### Phase 2: Consumer Processing
```
1. Consumer nhận message từ Kafka
2. Kiểm tra symbol có trong orderbooks dict chưa
3. Nếu chưa có:
   - Tạo LocalOrderBook mới
   - Tạo event buffer
   - Fetch snapshot từ Binance REST API (async)
   - Buffer events trong khi chờ snapshot
4. Nếu đã có:
   - Kiểm tra is_synced
   - Nếu chưa sync: buffer event
   - Nếu đã sync: apply update ngay
```

### Phase 3: Snapshot Sync
```
1. Fetch snapshot từ Binance REST API
2. Parse snapshot (bids, asks, lastUpdateId)
3. Update LocalOrderBook với snapshot data
4. Apply buffered events (nếu update_id > snapshot_id)
5. Set is_synced = True
```

### Phase 4: Real-time Updates
```
1. Nhận update từ Kafka
2. Kiểm tra update_id > last_update_id
3. Apply update vào LocalOrderBook
4. Rate limit: Chỉ lưu Redis mỗi 100ms
5. Lưu top 10 bids/asks vào Redis
```

---

## 🎯 Đặc Điểm Kỹ Thuật

### 1. **Snapshot Sync Pattern**
- **Vấn đề**: WebSocket stream chỉ gửi updates, không có full order book
- **Giải pháp**: Fetch snapshot từ REST API khi bắt đầu
- **Buffer events**: Lưu events nhận được trong khi chờ snapshot
- **Apply buffered**: Áp dụng events sau snapshot để đảm bảo tính nhất quán

### 2. **Rate Limiting**
- **Lý do**: Tránh spam Redis với quá nhiều writes
- **Cơ chế**: Chỉ lưu Redis mỗi 100ms (10 writes/giây)
- **Trade-off**: Giảm latency nhưng đảm bảo performance

### 3. **SortedDict cho Order Book**
- **Bids**: Sắp xếp giảm dần (giá cao nhất trước)
- **Asks**: Sắp xếp tăng dần (giá thấp nhất trước)
- **Lợi ích**: O(log n) cho insert/delete, O(1) cho top levels

### 4. **Update ID Validation**
- Kiểm tra `update_id > last_update_id` trước khi apply
- Đảm bảo không apply updates cũ (out-of-order)

### 5. **Error Handling**
- Retry kết nối Kafka nếu fail
- Exception handling cho snapshot fetch
- Graceful shutdown với producer.flush()

---

## 📈 Performance Considerations

### Throughput
- **WebSocket**: Real-time updates từ Binance (milliseconds)
- **Kafka**: Batch với linger 10ms, compression LZ4
- **Redis**: Rate limited 10 writes/second per symbol

### Latency
- **End-to-end**: ~100-200ms (WebSocket → Kafka → Consumer → Redis)
- **Snapshot sync**: ~500ms-1s (REST API call)

### Memory
- **LocalOrderBook**: Lưu full order book (1000 levels) trong memory
- **Event buffers**: Tạm thời lưu events trong khi chờ snapshot

---

## 🔧 Cấu Hình

### Kafka
- Topic: `orderbook_update`
- Partitions: Theo symbol (key-based partitioning)
- Compression: LZ4
- Producer linger: 10ms

### Redis
- Key: `LIVE_ORDERBOOK` (Hash)
- Field: `{SYMBOL}` (uppercase)
- Value: JSON với top 10 bids/asks
- TTL: Không có (persistent)

### Binance API
- WebSocket: `wss://fstream.binance.com/stream`
- REST API: `https://fapi.binance.com/fapi/v1/depth`
- Symbols: BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, ADAUSDT, XRPUSDT

---

## 🚀 Cách Chạy

### 1. Start Producer
```bash
python ob_stream_producer.py
```

### 2. Start Consumer/Handler
```bash
python ob_handler.py
```

### 3. Test Read from Redis
```bash
python redis_read_test.py
```

---

## 🔄 So Sánh Với Production Code

### Prototype (binance_api)
- LocalOrderBook trong memory
- Lưu vào Redis hash `LIVE_ORDERBOOK`
- Top 10 bids/asks
- Rate limit 100ms

### Production (Kafka/)
- Lưu full order book vào Redis
- Key: `orderbook:{symbol}:latest`
- Full order book (không giới hạn)
- Real-time updates qua Kafka consumer

---

## ⚠️ Lưu Ý

1. **Snapshot Sync**: Cần đảm bảo snapshot được fetch trước khi apply updates
2. **Update ID**: Phải validate để tránh out-of-order updates
3. **Rate Limiting**: Cân bằng giữa latency và Redis performance
4. **Error Recovery**: Cần retry mechanism cho snapshot fetch
5. **Memory**: LocalOrderBook lưu full book, cần monitor memory usage

---

## 📝 Tóm Tắt

Luồng order book prototype này minh họa:
- ✅ WebSocket streaming từ Binance
- ✅ Kafka làm message queue
- ✅ Snapshot sync pattern
- ✅ Local order book management
- ✅ Redis storage với rate limiting
- ✅ Event buffering trong khi sync

Đây là foundation tốt cho production system, nhưng cần thêm:
- Error recovery mechanisms
- Monitoring & logging
- Horizontal scaling
- Data persistence strategies

