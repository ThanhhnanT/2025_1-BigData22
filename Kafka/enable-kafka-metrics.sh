#!/bin/bash

# Script để bật Kafka metrics cho Prometheus
# Thứ tự apply:
# 1. ConfigMap cho JMX exporter
# 2. Cập nhật Kafka cluster với metricsConfig
# 3. ServiceMonitor (đã có sẵn)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE="crypto-infra"

echo "🚀 Bật Kafka Metrics cho Prometheus"
echo "=================================="

# Bước 1: Apply ConfigMap
echo ""
echo "📝 Bước 1: Tạo ConfigMap cho JMX Exporter..."
kubectl apply -f "${SCRIPT_DIR}/kafka-metrics-config.yaml"

# Bước 2: Apply Kafka cluster với metricsConfig
echo ""
echo "📝 Bước 2: Cập nhật Kafka cluster với metricsConfig..."
kubectl apply -f "${SCRIPT_DIR}/kafka-helm.yaml"

# Bước 3: Kiểm tra ServiceMonitor
echo ""
echo "📝 Bước 3: Kiểm tra ServiceMonitor..."
if kubectl get servicemonitor kafka-cluster -n "${NAMESPACE}" &>/dev/null; then
    echo "✅ ServiceMonitor đã tồn tại"
else
    echo "⚠️  ServiceMonitor chưa tồn tại, đang apply..."
    kubectl apply -f "${SCRIPT_DIR}/../deploy/monitoring/kafka-servicemonitor.yaml"
fi

# Bước 4: Đợi Kafka pods restart
echo ""
echo "⏳ Đợi Kafka pods restart với metrics enabled..."
echo "   (Có thể mất 2-5 phút để pods restart)"
kubectl wait --for=condition=ready pod -l strimzi.io/cluster=my-cluster -n "${NAMESPACE}" --timeout=300s || true

# Bước 5: Kiểm tra metrics endpoint
echo ""
echo "🔍 Bước 4: Kiểm tra metrics endpoint..."
KAFKA_POD=$(kubectl get pods -n "${NAMESPACE}" -l strimzi.io/cluster=my-cluster -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

if [ -n "$KAFKA_POD" ]; then
    echo "   Pod: $KAFKA_POD"
    echo "   Đang kiểm tra port 9404 (metrics endpoint)..."
    
    # Port-forward trong background để test
    kubectl port-forward "pod/${KAFKA_POD}" 9404:9404 -n "${NAMESPACE}" > /dev/null 2>&1 &
    PF_PID=$!
    sleep 2
    
    if curl -s http://localhost:9404/metrics | grep -q "kafka"; then
        echo "   ✅ Metrics endpoint hoạt động!"
        curl -s http://localhost:9404/metrics | grep -i "kafka" | head -5
    else
        echo "   ⚠️  Metrics endpoint chưa sẵn sàng (có thể cần đợi thêm)"
    fi
    
    kill $PF_PID 2>/dev/null || true
else
    echo "   ⚠️  Không tìm thấy Kafka pod"
fi

# Bước 6: Kiểm tra Prometheus targets
echo ""
echo "🔍 Bước 5: Kiểm tra Prometheus targets..."
echo "   Chạy lệnh sau để kiểm tra Prometheus có scrape được Kafka không:"
echo ""
echo "   kubectl port-forward svc/crypto-monitoring-kube-prometheus-prometheus 9090:9090 -n crypto-monitoring"
echo "   # Sau đó mở: http://localhost:9090/targets"
echo "   # Tìm target có tên chứa 'kafka' hoặc 'my-cluster'"
echo ""

echo "✅ Hoàn tất!"
echo ""
echo "📊 Để verify metrics đang hoạt động:"
echo "   1. Kiểm tra Prometheus targets (xem hướng dẫn trên)"
echo "   2. Trong Prometheus UI, thử query: {__name__=~\"kafka.*\"}"
echo "   3. Kiểm tra Grafana dashboard Kafka"
echo ""

