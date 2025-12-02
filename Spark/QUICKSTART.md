# 🚀 Spark Operator - Quick Start Guide

Hướng dẫn nhanh để chạy Spark trên Kubernetes trong 5 phút.

## ✅ Yêu cầu

- Minikube đã chạy
- kubectl đã cấu hình
- Helm 3.0+ đã cài đặt
- Namespace `crypto-infra` đã tạo

## 📝 Bước 1: Thêm Helm Repository

```bash
# Thêm official Spark repo
helm repo add spark https://apache.github.io/spark-kubernetes-operator
helm repo update
```

## 🔧 Bước 2: Deploy Spark Operator

**Cách 1: Dùng script tự động (Khuyến nghị)**

```bash
cd Spark
./deploy-spark-operator.sh minikube
```

**Cách 2: Deploy thủ công**

```bash
helm install crypto-spark-operator spark/spark-kubernetes-operator \
  --namespace crypto-infra \
  --version 1.4.0 \
  --values config/operator-values-minikube.yaml \
  --wait
```

## ✅ Bước 3: Kiểm tra Operator

```bash
# Xem pods
kubectl get pods -n crypto-infra -l app.kubernetes.io/name=spark-kubernetes-operator

# Xem CRDs
kubectl get crd | grep spark

# Xem logs
kubectl logs -n crypto-infra -l app.kubernetes.io/name=spark-kubernetes-operator
```

Output mong đợi:
```
NAME                                                   READY   STATUS    RESTARTS   AGE
crypto-spark-operator-spark-kubernetes-operator-xxx    1/1     Running   0          1m
```

## 🧪 Bước 4: Test với Spark Pi

```bash
# Deploy test app
./deploy-spark-app.sh test minikube

# Hoặc thủ công
kubectl apply -f apps/spark-pi-test.yaml

# Xem status
kubectl get sparkapplication -n crypto-infra

# Xem logs
kubectl logs -n crypto-infra spark-pi-test-driver
```

Output cuối cùng sẽ có:
```
Pi is roughly 3.14159...
```

## 📊 Bước 5: Deploy Streaming Application

```bash
# Đảm bảo Kafka đã chạy
kubectl get kafka -n crypto-infra

# Deploy streaming app
./deploy-spark-app.sh streaming minikube

# Monitor status
kubectl get sparkapplication crypto-streaming-10m -n crypto-infra -w
```

## 🔍 Bước 6: Access Spark UI

```bash
# Port-forward to Spark UI
kubectl port-forward -n crypto-infra crypto-streaming-10m-driver 4040:4040

# Mở browser: http://localhost:4040
```

## 📈 Bước 7: Setup Monitoring (Optional)

```bash
# Deploy ServiceMonitors
kubectl apply -f config/servicemonitor.yaml

# Deploy Prometheus Rules
kubectl apply -f config/prometheus-rules.yaml

# Import Grafana Dashboard
# File: config/grafana-dashboard.json
```

## 🎯 Các lệnh hữu ích

```bash
# Xem tất cả Spark applications
kubectl get sparkapplication -n crypto-infra

# Xem chi tiết application
kubectl describe sparkapplication crypto-streaming-10m -n crypto-infra

# Xem logs driver
kubectl logs -n crypto-infra crypto-streaming-10m-driver -f

# Xem logs executor
kubectl logs -n crypto-infra -l spark-role=executor --tail=100

# Xóa application
kubectl delete sparkapplication crypto-streaming-10m -n crypto-infra

# Restart application (xóa và tạo lại)
kubectl delete sparkapplication crypto-streaming-10m -n crypto-infra
./deploy-spark-app.sh streaming minikube
```

## 🐛 Troubleshooting

### Operator không start

```bash
# Kiểm tra events
kubectl get events -n crypto-infra --sort-by='.lastTimestamp'

# Xem chi tiết pod
kubectl describe pod -n crypto-infra -l app.kubernetes.io/name=spark-kubernetes-operator

# Xem logs chi tiết
kubectl logs -n crypto-infra -l app.kubernetes.io/name=spark-kubernetes-operator --tail=200
```

### Application failed

```bash
# Xem status
kubectl get sparkapplication -n crypto-infra

# Xem chi tiết
kubectl describe sparkapplication <app-name> -n crypto-infra

# Xem logs
kubectl logs -n crypto-infra <app-name>-driver
```

### Không connect được Kafka

```bash
# Kiểm tra Kafka service
kubectl get svc -n crypto-infra | grep kafka

# Test connection từ pod
kubectl run -it --rm test-kafka --image=ubuntu --restart=Never -- bash
apt update && apt install -y telnet
telnet my-cluster-kafka-bootstrap.crypto-infra.svc.cluster.local 9092
```

## 🔄 Update/Upgrade

### Upgrade Operator

```bash
./deploy-spark-operator.sh minikube
```

### Update Application

```bash
# Sửa file yaml, sau đó:
kubectl apply -f apps/streaming/crypto-streaming-minikube.yaml

# Hoặc dùng script:
./deploy-spark-app.sh streaming minikube
```

## 📚 Tài liệu

- [README.md](README.md) - Tài liệu đầy đủ
- [Official Docs](https://apache.github.io/spark-kubernetes-operator/)
- [Spark on K8s](https://spark.apache.org/docs/latest/running-on-kubernetes.html)

## 💡 Tips

1. **Development**: Dùng `minikube` environment với resources thấp
2. **Testing**: Test với `spark-pi-test` trước khi deploy app thật
3. **Monitoring**: Setup Prometheus/Grafana để theo dõi
4. **Logs**: Luôn check logs khi có vấn đề
5. **Resources**: Điều chỉnh CPU/memory trong manifest nếu cần

## ✨ Next Steps

Sau khi setup thành công:

1. ✅ Customize streaming application trong `spark_streaming_10m.py`
2. ✅ Setup persistent storage cho checkpoints (production)
3. ✅ Configure Prometheus alerting rules
4. ✅ Import Grafana dashboards
5. ✅ Document runbooks cho operations

---

**Câu hỏi?** Xem [README.md](README.md) hoặc check [official docs](https://apache.github.io/spark-kubernetes-operator/)

