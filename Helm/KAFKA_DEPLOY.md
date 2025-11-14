# Hướng dẫn Deploy Kafka bằng Helm

## Tổng quan

Sử dụng Helm để deploy Strimzi Kafka Operator và Kafka Cluster trên Kubernetes.

## Kiến trúc

```
Strimzi Kafka Operator (Helm Chart)
    ↓
Kafka Cluster (CRD)
    ↓
Kafka Topics (CRD)
```

## Yêu cầu

- Kubernetes cluster
- Helm 3.x
- kubectl
- Đủ storage (100Gi per broker)
- Đủ resources (CPU, Memory)

## Quick Start

### Deploy tự động

```bash
cd Helm
./deploy-kafka.sh
```

Script sẽ:
1. Tạo namespace `kafka`
2. Thêm Helm repo
3. Deploy Strimzi Operator
4. Deploy Kafka Cluster
5. Deploy Kafka Topics

## Manual Deploy

### Bước 1: Tạo Namespace

```bash
kubectl create namespace kafka
```

### Bước 2: Thêm Helm Repo

```bash
helm repo add strimzi https://strimzi.io/charts/
helm repo update
```

### Bước 3: Deploy Strimzi Operator

```bash
helm install strimzi-kafka-operator strimzi/strimzi-kafka-operator \
  --namespace kafka \
  --create-namespace \
  --values kafka-operator-values.yaml
```

### Bước 4: Kiểm tra Operator

```bash
# Kiểm tra pods
kubectl get pods -n kafka

# Kiểm tra CRD
kubectl get crd | grep kafka

# Xem logs
kubectl logs -f deployment/strimzi-cluster-operator -n kafka
```

### Bước 5: Deploy Kafka Cluster

```bash
kubectl apply -f kafka-cluster.yaml
```

### Bước 6: Kiểm tra Kafka Cluster

```bash
# Kiểm tra cluster
kubectl get kafka -n kafka

# Kiểm tra pods
kubectl get pods -n kafka

# Đợi cluster ready
kubectl wait --for=condition=Ready kafka/my-cluster -n kafka --timeout=600s
```

### Bước 7: Deploy Kafka Topics

```bash
kubectl apply -f kafka-topics.yaml
```

### Bước 8: Kiểm tra Topics

```bash
# Kiểm tra topics
kubectl get kafkatopic -n kafka

# List topics từ Kafka
kubectl run kafka-client -it --rm \
  --image=quay.io/strimzi/kafka:0.40.0-kafka-3.7.0 \
  --restart=Never \
  -- bin/kafka-topics.sh \
  --bootstrap-server my-cluster-kafka-bootstrap:9092 \
  --list
```

## Configuration

### Kafka Operator

File: `kafka-operator-values.yaml`

- Operator image và version
- Resource limits
- Service account và RBAC
- Watch namespaces

### Kafka Cluster

File: `kafka-cluster.yaml` hoặc `kafka-cluster-values.yaml`

- Cluster name: `my-cluster`
- Replicas: 3 brokers
- Listeners:
  - Plain (internal): 9092
  - TLS (internal): 9093
  - External (NodePort): 9094
- Storage: 100Gi per broker
- KRaft mode: Enabled (no Zookeeper)

### Kafka Topics

File: `kafka-topics.yaml`

- Topic: `crypto-kline-1m`
- Partitions: 5
- Replicas: 3
- Retention: 7 days
- Compression: snappy

## Access Kafka

### Internal (trong cluster)

```bash
# Bootstrap server
my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092
```

### External (từ ngoài cluster)

```bash
# Lấy NodePort
kubectl get svc my-cluster-kafka-external-bootstrap -n kafka

# Hoặc port forward
kubectl port-forward svc/my-cluster-kafka-bootstrap 9092:9092 -n kafka
```

## Test Kafka

### Tạo Producer

```bash
kubectl run kafka-producer -it --rm \
  --image=quay.io/strimzi/kafka:0.40.0-kafka-3.7.0 \
  --restart=Never \
  -- bin/kafka-console-producer.sh \
  --bootstrap-server my-cluster-kafka-bootstrap:9092 \
  --topic crypto-kline-1m
```

### Tạo Consumer

```bash
kubectl run kafka-consumer -it --rm \
  --image=quay.io/strimzi/kafka:0.40.0-kafka-3.7.0 \
  --restart=Never \
  -- bin/kafka-console-consumer.sh \
  --bootstrap-server my-cluster-kafka-bootstrap:9092 \
  --topic crypto-kline-1m \
  --from-beginning
```

## Monitoring

### Check Status

```bash
# Operator
kubectl get pods -n kafka -l name=strimzi-cluster-operator

# Kafka brokers
kubectl get pods -n kafka -l strimzi.io/cluster=my-cluster

# Topics
kubectl get kafkatopic -n kafka
```

### Logs

```bash
# Operator logs
kubectl logs -f deployment/strimzi-cluster-operator -n kafka

# Kafka broker logs
kubectl logs -f <kafka-broker-pod> -n kafka
```

### Describe Resources

```bash
# Describe cluster
kubectl describe kafka my-cluster -n kafka

# Describe topic
kubectl describe kafkatopic crypto-kline-1m -n kafka
```

## Upgrade

### Upgrade Operator

```bash
helm upgrade strimzi-kafka-operator strimzi/strimzi-kafka-operator \
  --namespace kafka \
  --values kafka-operator-values.yaml
```

### Upgrade Cluster

```bash
# Cập nhật kafka-cluster.yaml
# Sau đó apply
kubectl apply -f kafka-cluster.yaml
```

## Scale

### Scale Brokers

```bash
# Cập nhật replicas trong kafka-cluster.yaml
# Sau đó apply
kubectl apply -f kafka-cluster.yaml
```

### Scale Partitions

```bash
# Cập nhật partitions trong kafka-topics.yaml
# Sau đó apply
kubectl apply -f kafka-topics.yaml
```

## Troubleshooting

### Operator không start

```bash
# Kiểm tra logs
kubectl logs -f deployment/strimzi-cluster-operator -n kafka

# Kiểm tra RBAC
kubectl get clusterrole strimzi-cluster-operator
kubectl get clusterrolebinding strimzi-cluster-operator
```

### Kafka pods không start

```bash
# Kiểm tra events
kubectl describe pod <kafka-pod> -n kafka

# Kiểm tra PVC
kubectl get pvc -n kafka

# Kiểm tra storage class
kubectl get storageclass
```

### Topics không tạo được

```bash
# Kiểm tra topic operator
kubectl get pods -n kafka -l strimzi.io/kind=topic-operator

# Kiểm tra logs
kubectl logs -f <topic-operator-pod> -n kafka
```

## Uninstall

### Uninstall Topics

```bash
kubectl delete kafkatopic crypto-kline-1m -n kafka
```

### Uninstall Cluster

```bash
kubectl delete kafka my-cluster -n kafka
```

### Uninstall Operator

```bash
helm uninstall strimzi-kafka-operator -n kafka
```

### Delete Namespace

```bash
kubectl delete namespace kafka
```

## Best Practices

1. **Storage**: Dùng persistent storage với đủ dung lượng
2. **Replication**: Set replication factor phù hợp với số brokers
3. **Retention**: Cấu hình retention dựa trên use case
4. **Monitoring**: Setup monitoring cho Kafka metrics
5. **Backup**: Backup Kafka data và configurations
6. **Security**: Enable TLS và authentication cho production

## Integration với các services khác

### Spark

```yaml
env:
  - name: KAFKA_BROKER
    value: "my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092"
```

### Airflow

```python
KAFKA_BROKER = "my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092"
```

### Producer/Consumer

```python
KAFKA_BROKER = "my-cluster-kafka-bootstrap:9092"
```

