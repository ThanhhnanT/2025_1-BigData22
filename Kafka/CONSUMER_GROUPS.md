# Hiểu về Consumer Groups trong Kafka

## Vấn đề bạn gặp

Khi chạy 3 consumer cùng lúc, dữ liệu chỉ đến consumer cuối cùng. Đây là hành vi bình thường của Kafka Consumer Groups.

## Cách Kafka Consumer Groups hoạt động

### Trường hợp 1: Cùng Consumer Group (chia sẻ partition)

Khi nhiều consumer trong **cùng một consumer group**:
- Kafka sẽ **phân phối partition** cho các consumer
- Mỗi partition chỉ được xử lý bởi **1 consumer** trong group
- Khi consumer mới join → Kafka **rebalance** và phân phối lại partition

**Ví dụ với 5 partition và 3 consumer:**
```
Consumer 1 (crypto_group) → Partition 0, 1
Consumer 2 (crypto_group) → Partition 2, 3
Consumer 3 (crypto_group) → Partition 4
```

**Vấn đề:** Nếu consumer 3 join sau, nó có thể nhận hết partition do rebalancing.

### Trường hợp 2: Khác Consumer Group (mỗi consumer nhận tất cả)

Khi mỗi consumer dùng **consumer group khác nhau**:
- Mỗi consumer sẽ nhận **TẤT CẢ messages** từ tất cả partition
- Không chia sẻ, mỗi consumer xử lý độc lập

**Ví dụ:**
```
Consumer 1 (crypto_group_1) → Tất cả partition (0,1,2,3,4)
Consumer 2 (crypto_group_2) → Tất cả partition (0,1,2,3,4)
Consumer 3 (crypto_group_3) → Tất cả partition (0,1,2,3,4)
```

## Giải pháp

### Cách 1: Dùng Consumer Group khác nhau (mỗi consumer nhận tất cả)

Chạy mỗi consumer với group ID khác nhau:

```bash
# Terminal 1
CONSUMER_GROUP=crypto_group_1 CONSUMER_ID=consumer-1 python binance_consumer.py

# Terminal 2
CONSUMER_GROUP=crypto_group_2 CONSUMER_ID=consumer-2 python binance_consumer.py

# Terminal 3
CONSUMER_GROUP=crypto_group_3 CONSUMER_ID=consumer-3 python binance_consumer.py
```

Hoặc dùng script:
```bash
chmod +x run_multiple_consumers.sh
./run_multiple_consumers.sh
```

### Cách 2: Đợi Consumer Group Rebalance (chia sẻ partition)

Chạy tất cả consumer **cùng lúc** với cùng group ID:

```bash
# Terminal 1
python binance_consumer.py

# Terminal 2 (chạy ngay sau terminal 1)
python binance_consumer.py

# Terminal 3 (chạy ngay sau terminal 2)
python binance_consumer.py
```

Kafka sẽ tự động rebalance và phân phối partition cho cả 3 consumer.

### Cách 3: Dùng Consumer ID khác nhau

```bash
# Terminal 1
CONSUMER_ID=consumer-1 python binance_consumer.py

# Terminal 2
CONSUMER_ID=consumer-2 python binance_consumer.py

# Terminal 3
CONSUMER_ID=consumer-3 python binance_consumer.py
```

## Kiểm tra Consumer Group

```bash
# Xem các consumer trong group
kubectl exec -it <kafka-pod> -n kafka -- bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe --group crypto_group

# Hoặc nếu chạy local
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --describe --group crypto_group
```

## Khi nào dùng cách nào?

### Dùng cùng Consumer Group (chia sẻ):
- ✅ Khi muốn **load balancing** - chia tải xử lý
- ✅ Khi muốn **parallel processing** - xử lý song song
- ✅ Khi muốn **scale horizontally** - thêm consumer để tăng throughput

### Dùng khác Consumer Group (mỗi consumer nhận tất cả):
- ✅ Khi muốn **multiple processing** - xử lý cùng dữ liệu theo cách khác
- ✅ Khi muốn **backup processing** - có consumer dự phòng
- ✅ Khi muốn **different logic** - mỗi consumer xử lý logic khác nhau

## Lưu ý

1. **Rebalancing** có thể mất vài giây khi consumer join/leave
2. **Offset** được lưu theo consumer group → mỗi group có offset riêng
3. **Số consumer tối đa hiệu quả = số partition**


