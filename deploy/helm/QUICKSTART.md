# Quick Start: Deploy Prometheus & Grafana Monitoring

## Tóm tắt nhanh

Triển khai monitoring stack cho hệ thống CRYPTO trên minikube chỉ với 2 bước:

## Bước 1: Triển khai Monitoring Stack

```bash
cd deploy/helm
./deploy-monitoring.sh
```

Chờ khoảng 2-5 phút để tất cả pods khởi động.

## Bước 2: Áp dụng ServiceMonitors

```bash
cd ../k8s_web/monitoring
./apply-servicemonitors.sh
```

## Truy cập Grafana

```bash
# Cách 1: NodePort (khuyến nghị)
minikube service crypto-monitoring-grafana -n crypto-monitoring

# Cách 2: Port Forward
kubectl port-forward svc/crypto-monitoring-grafana 3000:80 -n crypto-monitoring
# Mở: http://localhost:3000
```

**Đăng nhập:**
- Username: `admin`
- Password: Lấy bằng lệnh:
  ```bash
  kubectl get secret crypto-monitoring-grafana -n crypto-monitoring -o jsonpath="{.data.admin-password}" | base64 -d
  ```

## Truy cập Prometheus

```bash
kubectl port-forward svc/crypto-monitoring-kube-prometheus-prometheus 9090:9090 -n crypto-monitoring
# Mở: http://localhost:9090
```

## Kiểm tra trạng thái

```bash
cd deploy/helm
./verify-monitoring.sh
```

## Scripts tiện ích

- `deploy-monitoring.sh`: Triển khai monitoring stack
- `access-monitoring.sh`: Xem thông tin truy cập
- `verify-monitoring.sh`: Kiểm tra trạng thái
- `apply-servicemonitors.sh`: Áp dụng ServiceMonitors (trong `deploy/k8s_web/monitoring/`)

## Xem thêm

Chi tiết đầy đủ: [MONITORING_README.md](./MONITORING_README.md)


