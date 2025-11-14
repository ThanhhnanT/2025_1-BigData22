# Hướng dẫn Scale Producer và Consumer

## Cấu hình hiện tại

- **Producer**: 1 replica (chỉ cần 1)
- **Consumer**: 3 replicas (có thể scale lên)

## Producer - Tại sao chỉ cần 1?

Producer stream dữ liệu từ Binance WebSocket API. Nếu chạy nhiều producer:
- ❌ Sẽ nhận duplicate data (cùng một stream từ Binance)
- ❌ Tốn tài nguyên không cần thiết
- ✅ **Chỉ cần 1 producer** là đủ

### Nếu muốn chạy nhiều producer (không khuyến nghị)

```bash
# Scale producer lên 2 (sẽ có duplicate data)
kubectl scale deployment binance-producer --replicas=2 -n kafka
```

## Consumer - Scale để xử lý song song

Consumer có thể scale để xử lý nhiều partition song song.

### Kiểm tra số partition hiện tại

```bash
# Xem topic có bao nhiêu partition
kubectl exec -it <kafka-pod> -n kafka -- bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --describe --topic crypto_kline_1m
```

### Scale Consumer

```bash
# Scale lên 5 consumer (nếu có 5 partition)
kubectl scale deployment binance-consumer --replicas=5 -n kafka

# Scale xuống 2 consumer
kubectl scale deployment binance-consumer --replicas=2 -n kafka

# Scale về 1 consumer
kubectl scale deployment binance-consumer --replicas=1 -n kafka
```

### Lưu ý quan trọng

- **Số consumer tối đa = số partition**
  - Nếu có 5 partition → tối đa 5 consumer hiệu quả
  - Nếu có 10 consumer nhưng chỉ 5 partition → 5 consumer sẽ idle

- **Consumer trong cùng consumer group** sẽ tự động chia partition:
  - Consumer 1 → Partition 0, 1
  - Consumer 2 → Partition 2, 3
  - Consumer 3 → Partition 4

### Xem consumer đang xử lý partition nào

```bash
# Xem logs của từng consumer pod
kubectl logs <consumer-pod-name> -n kafka | grep "Partition:"

# Hoặc xem tất cả consumer
kubectl logs -l app=binance-consumer -n kafka | grep "Partition:"
```

## Auto-scaling với HPA (Horizontal Pod Autoscaler)

Có thể setup auto-scaling dựa trên CPU/Memory:

```bash
# Tạo HPA cho consumer (scale từ 2-10 pods, dựa trên CPU > 70%)
kubectl autoscale deployment binance-consumer \
  --cpu-percent=70 \
  --min=2 \
  --max=10 \
  -n kafka

# Xem HPA status
kubectl get hpa -n kafka

# Xóa HPA
kubectl delete hpa binance-consumer -n kafka
```

## Best Practices

1. **Producer**: Giữ ở 1 replica
2. **Consumer**: 
   - Bắt đầu với 3-5 replicas
   - Monitor throughput và latency
   - Scale dựa trên số partition và workload
3. **Partition**: 
   - Nên có partition >= số consumer muốn chạy
   - Có thể tăng partition sau (nhưng không thể giảm)

## Monitoring

```bash
# Xem tất cả pods
kubectl get pods -n kafka

# Xem resource usage
kubectl top pods -n kafka

# Xem deployment status
kubectl get deployments -n kafka

# Xem replica status
kubectl describe deployment binance-consumer -n kafka
```


