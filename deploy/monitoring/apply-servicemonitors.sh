#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'
echo "📊 Applying ServiceMonitor resources for Prometheus"
echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'

# Check if monitoring namespace exists
if ! kubectl get namespace crypto-monitoring > /dev/null 2>&1; then
    echo "❌ Namespace crypto-monitoring does not exist."
    echo "   Please deploy monitoring stack first:"
    echo "   cd ../helm && ./deploy-monitoring.sh"
    exit 1
fi

# Apply ServiceMonitors
echo ""
echo "📋 Applying ServiceMonitor resources..."

# Backend FastAPI ServiceMonitor
if kubectl get service backend-fastapi-service -n crypto-app > /dev/null 2>&1; then
    echo "  ✓ Applying backend-fastapi ServiceMonitor..."
    kubectl apply -f "${SCRIPT_DIR}/backend-servicemonitor.yaml"
else
    echo "  ⚠️  Backend service not found, skipping backend ServiceMonitor"
fi

# Kafka ServiceMonitor
if kubectl get kafka my-cluster -n crypto-infra > /dev/null 2>&1; then
    echo "  ✓ Applying Kafka ServiceMonitor..."
    kubectl apply -f "${SCRIPT_DIR}/kafka-servicemonitor.yaml"
else
    echo "  ⚠️  Kafka cluster not found, skipping Kafka ServiceMonitor"
fi

# Spark Operator ServiceMonitor
if kubectl get service -n crypto-infra | grep -q spark-operator; then
    echo "  ✓ Applying Spark Operator ServiceMonitor..."
    kubectl apply -f "${SCRIPT_DIR}/spark-operator-servicemonitor.yaml"
else
    echo "  ⚠️  Spark Operator service not found, skipping Spark ServiceMonitor"
fi

# Airflow StatsD ServiceMonitor
if kubectl get service -n crypto-infra | grep -q airflow-statsd; then
    echo "  ✓ Applying Airflow StatsD ServiceMonitor..."
    kubectl apply -f "${SCRIPT_DIR}/airflow-statsd-servicemonitor.yaml"
else
    echo "  ⚠️  Airflow StatsD service not found, skipping Airflow ServiceMonitor"
fi

echo ""
echo "✅ ServiceMonitor resources applied"
echo ""
echo "🔍 Verify ServiceMonitors:"
echo "   kubectl get servicemonitors -A"
echo ""
echo "📊 Check Prometheus targets:"
echo "   kubectl port-forward svc/crypto-monitoring-kube-prometheus-prometheus 9090:9090 -n crypto-monitoring"
echo "   Then open: http://localhost:9090/targets"
echo ""

