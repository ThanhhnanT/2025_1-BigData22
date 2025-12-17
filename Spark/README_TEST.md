# Testing Spark Jobs with Kubernetes Operator

## Vấn đề hiện tại

Khi chạy Spark job qua SparkApplication, pod driver có thể bị stuck ở trạng thái "ContainerCreating" và timeout. Nguyên nhân chính:

1. **File Python không có trong base image**: Base image `apache/spark:3.5.0` không chứa file Python của bạn tại `/opt/spark/jobs/test_spark_simple.py`

## Giải pháp

### Option 1: Build Custom Docker Image (Khuyến nghị)

Build custom image từ Dockerfile có sẵn:

```bash
cd Spark
docker build -t vvt/spark-crypto:3.5.0 -f Dockerfile .
docker push vvt/spark-crypto:3.5.0
```

Sau đó cập nhật `sparkConf` trong manifest:
```yaml
sparkConf:
  spark.kubernetes.container.image: your-registry/spark-crypto:3.5.0
```

### Option 2: Sử dụng ConfigMap

1. Tạo ConfigMap từ file Python:
```bash
kubectl create configmap spark-test-script -n crypto-infra \
  --from-file=test_spark_simple.py=Spark/batch/test_spark_simple.py
```

2. Cập nhật SparkApplication manifest để mount ConfigMap (cần thêm `driverSpec` với volume mount)

### Option 3: Test với file có sẵn trong image

Sử dụng file Python có sẵn trong Spark image để test:
- Ví dụ: `/opt/spark/examples/src/main/python/pi.py` (nếu có)

## Kiểm tra và Debug

1. **Kiểm tra SparkApplication status:**
```bash
kubectl get sparkapplication test-spark-simple -n crypto-infra -o yaml
```

2. **Kiểm tra driver pod:**
```bash
kubectl get pods -n crypto-infra | grep test-spark-simple
kubectl describe pod test-spark-simple-0-driver -n crypto-infra
```

3. **Xem logs từ operator:**
```bash
kubectl logs -n crypto-infra spark-kubernetes-operator-5f9d958469-gbkmt --tail=100
```

4. **Xem events:**
```bash
kubectl get events -n crypto-infra --sort-by='.lastTimestamp' | grep test-spark
```

## Cấu trúc SparkApplication đúng

Manifest hiện tại đã đúng cấu trúc CRD:
- `driverArgs`: Array chứa arguments cho spark-submit
- `pyFiles`: String (comma-separated nếu nhiều file)
- `sparkConf`: Object chứa tất cả Spark configurations
- `runtimeVersions`: Object với sparkVersion
- `deploymentMode`: ClusterMode
- `applicationTolerations`: Object với restart policy

## Lưu ý

- Pod name format: `{sparkapp-name}-{attempt-id}-driver` (ví dụ: `test-spark-simple-0-driver`)
- Status path: `.status.applicationState.currentStateSummary` (không phải `.status.applicationState.state`)
- Timeout mặc định: 5 phút cho driver start, có thể tăng trong `applicationTolerations.applicationTimeoutConfig`

