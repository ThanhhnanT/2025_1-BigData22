# Troubleshooting: Consumer không nhận được messages

## Vấn đề: Chỉ có consumer cuối cùng nhận được messages

### Nguyên nhân: `auto_offset_reset='latest'`

Khi consumer group **mới** join lần đầu:
- `auto_offset_reset='latest'` → Chỉ đọc message **MỚI** từ thời điểm consumer join
- Nếu consumer join khi **không có message mới** → Không nhận gì
- Consumer join sau (khi có message mới) → Nhận được messages

### Giải pháp

#### Giải pháp 1: Dùng `earliest` để đọc từ đầu (cho testing)

```bash
# Terminal 1
AUTO_OFFSET_RESET=earliest CONSUMER_GROUP=crypto_group_1 CONSUMER_ID=consumer-1 python binance_consumer.py

# Terminal 2
AUTO_OFFSET_RESET=earliest CONSUMER_GROUP=crypto_group_2 CONSUMER_ID=consumer-2 python binance_consumer.py

# Terminal 3
AUTO_OFFSET_RESET=earliest CONSUMER_GROUP=crypto_group_3 CONSUMER_ID=consumer-3 python binance_consumer.py
```

**Lưu ý:** `earliest` sẽ đọc TẤT CẢ messages từ đầu topic (có thể rất nhiều!)

#### Giải pháp 2: Reset consumer group offset (khuyến nghị)

Xóa consumer group để reset offset:

```bash
# Xem các consumer groups
kubectl exec -it <kafka-pod> -n kafka -- bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --list

# Xóa consumer group để reset offset
kubectl exec -it <kafka-pod> -n kafka -- bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --delete --group crypto_group_1

kubectl exec -it <kafka-pod> -n kafka -- bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --delete --group crypto_group_2

kubectl exec -it <kafka-pod> -n kafka -- bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --delete --group crypto_group_3
```

Sau đó chạy lại consumer, chúng sẽ bắt đầu từ `latest` (message mới).

#### Giải pháp 3: Chạy tất cả consumer CÙNG LÚC

```bash
# Chạy cả 3 trong vòng vài giây
# Terminal 1
CONSUMER_GROUP=crypto_group_1 CONSUMER_ID=consumer-1 python binance_consumer.py &

# Terminal 2 (ngay sau)
CONSUMER_GROUP=crypto_group_2 CONSUMER_ID=consumer-2 python binance_consumer.py &

# Terminal 3 (ngay sau)
CONSUMER_GROUP=crypto_group_3 CONSUMER_ID=consumer-3 python binance_consumer.py &
```

#### Giải pháp 4: Đảm bảo producer đang chạy và có dữ liệu

```bash
# Kiểm tra producer có đang chạy không
kubectl get pods -n kafka | grep producer

# Xem logs producer
kubectl logs -f deployment/binance-producer -n kafka

# Kiểm tra topic có dữ liệu không
kubectl exec -it <kafka-pod> -n kafka -- bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic crypto_kline_1m \
  --from-beginning \
  --max-messages 5
```

## Debug: Kiểm tra consumer có hoạt động không

### 1. Kiểm tra consumer đã được assign partition chưa

Trong output của consumer, bạn sẽ thấy:
```
Assigned partitions: ['Partition 0', 'Partition 1', ...]
```

Nếu không thấy → Consumer chưa được assign partition (có thể do không có message mới).

### 2. Kiểm tra offset

```bash
# Xem offset của consumer groups
kubectl exec -it <kafka-pod> -n kafka -- bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe --group crypto_group_1

kubectl exec -it <kafka-pod> -n kafka -- bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe --group crypto_group_2

kubectl exec -it <kafka-pod> -n kafka -- bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe --group crypto_group_3
```

### 3. Kiểm tra topic có dữ liệu không

```bash
# Xem số messages trong topic
kubectl exec -it <kafka-pod> -n kafka -- bin/kafka-run-class.sh \
  kafka.tools.GetOffsetShell \
  --broker-list localhost:9092 \
  --topic crypto_kline_1m
```

## Test nhanh

### Test 1: Chạy consumer với earliest

```bash
AUTO_OFFSET_RESET=earliest CONSUMER_GROUP=test_group_1 python binance_consumer.py
```

Nếu nhận được messages → Topic có dữ liệu, vấn đề là ở offset.

### Test 2: Xem messages trực tiếp từ topic

```bash
# Đọc 10 messages từ topic (không qua consumer group)
kubectl exec -it <kafka-pod> -n kafka -- bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic crypto_kline_1m \
  --from-beginning \
  --max-messages 10
```

Nếu không thấy gì → Producer không gửi dữ liệu hoặc topic trống.

## Kết luận

**Vấn đề phổ biến nhất:** Consumer join khi không có message mới → Offset được set ở cuối → Không nhận được gì.

**Giải pháp tốt nhất:** 
1. Đảm bảo producer đang chạy và có dữ liệu
2. Reset consumer group offset
3. Chạy tất cả consumer cùng lúc
4. Hoặc dùng `earliest` cho testing (cẩn thận với dữ liệu cũ!)


