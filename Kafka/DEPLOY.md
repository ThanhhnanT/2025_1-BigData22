# Hướng dẫn Deploy lên Kubernetes

## Yêu cầu
- Kubernetes cluster đã cài đặt
- Kafka cluster đã chạy (dùng Strimzi)
- Docker hoặc container runtime
- kubectl đã cấu hình

## Bước 1: Build Docker Images

### Cách 1: Build local và load vào minikube
```bash
# Build images
docker build -t binance-producer:latest .
docker build -t binance-consumer:latest .

# Nếu dùng minikube
minikube image load binance-producer:latest
minikube image load binance-consumer:latest
```

### Cách 2: Push lên Docker Registry
```bash
# Tag images với registry của bạn
docker tag binance-producer:latest your-registry/binance-producer:latest
docker tag binance-consumer:latest your-registry/binance-consumer:latest

# Push
docker push your-registry/binance-producer:latest
docker push your-registry/binance-consumer:latest

# Sau đó cập nhật image name trong k8s-producer-deployment.yaml và k8s-consumer-deployment.yaml
```

## Bước 2: Tạo Topic (nếu chưa có)

```bash
# Cách 1: Dùng Python script (chạy local hoặc trong pod)
python create_topic.py

# Cách 2: Dùng Kubernetes (Strimzi)
kubectl apply -f kafka-topic.yaml -n kafka
```

## Bước 3: Kiểm tra Kafka Service Name

```bash
# Tìm service name của Kafka
kubectl get svc -n kafka | grep kafka

# Thường sẽ là: my-cluster-kafka-bootstrap
# Cập nhật trong k8s-configmap.yaml nếu khác
```

## Bước 4: Deploy lên Kubernetes

```bash
# Apply ConfigMap
kubectl apply -f k8s-configmap.yaml

# Deploy Producer
kubectl apply -f k8s-producer-deployment.yaml

# Deploy Consumer
kubectl apply -f k8s-consumer-deployment.yaml
```

Hoặc dùng script tự động:
```bash
chmod +x build-and-deploy.sh
./build-and-deploy.sh
```

## Bước 5: Kiểm tra

```bash
# Xem pods
kubectl get pods -n kafka

# Xem logs producer
kubectl logs -f deployment/binance-producer -n kafka

# Xem logs consumer
kubectl logs -f deployment/binance-consumer -n kafka

# Xem logs của một pod cụ thể
kubectl logs -f <pod-name> -n kafka
```

## Scale Consumer

```bash
# Scale consumer lên 5 instances
kubectl scale deployment binance-consumer --replicas=5 -n kafka
```

## Troubleshooting

### Pod không start
```bash
# Xem events
kubectl describe pod <pod-name> -n kafka

# Xem logs
kubectl logs <pod-name> -n kafka
```

### Không kết nối được Kafka
- Kiểm tra KAFKA_BROKER trong ConfigMap
- Kiểm tra Kafka service đã running: `kubectl get svc -n kafka`
- Kiểm tra network policy nếu có

### Image không tìm thấy
- Nếu dùng minikube: `minikube image load <image-name>`
- Hoặc push image lên registry và cập nhật image name trong deployment

## Xóa deployment

```bash
kubectl delete -f k8s-producer-deployment.yaml
kubectl delete -f k8s-consumer-deployment.yaml
kubectl delete -f k8s-configmap.yaml
```


