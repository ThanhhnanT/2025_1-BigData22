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

# Check if ServiceMonitor CRD exists (required for ServiceMonitor resources)
echo ""
echo "🔍 Checking ServiceMonitor CRD..."
if ! kubectl get crd servicemonitors.monitoring.coreos.com > /dev/null 2>&1; then
    echo ""
    echo "❌ ServiceMonitor CRD not found."
    echo "   This means Prometheus Operator is not installed."
    echo ""
    echo "   📋 To fix this, please deploy the monitoring stack first:"
    echo ""
    echo "   1. Navigate to helm directory:"
    echo "      cd $(dirname "${SCRIPT_DIR}")/helm"
    echo ""
    echo "   2. Deploy monitoring stack:"
    echo "      ./deploy-monitoring.sh"
    echo ""
    echo "   The monitoring stack will install:"
    echo "   - Prometheus Operator (provides ServiceMonitor CRD)"
    echo "   - Prometheus"
    echo "   - Grafana"
    echo ""
    echo "   After deployment, wait for pods to be ready, then run this script again."
    exit 1
fi
echo "✅ ServiceMonitor CRD found"

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
# First, create the metrics service if it doesn't exist
if ! kubectl get service spark-operator-metrics -n crypto-infra > /dev/null 2>&1; then
    if kubectl get deployment spark-kubernetes-operator -n crypto-infra > /dev/null 2>&1; then
        echo "  📦 Creating Spark Operator metrics service..."
        kubectl apply -f "${SCRIPT_DIR}/spark-operator-metrics-service.yaml"
    fi
fi

if kubectl get service spark-operator-metrics -n crypto-infra > /dev/null 2>&1; then
    echo "  ✓ Applying Spark Operator ServiceMonitor..."
    kubectl apply -f "${SCRIPT_DIR}/spark-operator-servicemonitor.yaml"
else
    echo "  ⚠️  Spark Operator deployment not found, skipping Spark ServiceMonitor"
    echo "     Note: Spark Operator must be deployed first"
fi

# Airflow StatsD ServiceMonitor
if kubectl get service -n crypto-infra | grep -q airflow-statsd; then
    echo "  ✓ Applying Airflow StatsD ServiceMonitor..."
    kubectl apply -f "${SCRIPT_DIR}/airflow-statsd-servicemonitor.yaml"
else
    echo "  ⚠️  Airflow StatsD service not found, skipping Airflow ServiceMonitor"
fi

# MongoDB ServiceMonitor
if kubectl get service -n crypto-infra | grep -q mongodb.*metrics; then
    echo "  ✓ Applying MongoDB ServiceMonitor..."
    kubectl apply -f "${SCRIPT_DIR}/mongodb-servicemonitor.yaml"
else
    echo "  ⚠️  MongoDB metrics service not found, skipping MongoDB ServiceMonitor"
    echo "     📋 To enable MongoDB metrics, run:"
    echo "        helm upgrade mongodb oci://registry-1.docker.io/bitnamicharts/mongodb \\"
    echo "          -n crypto-infra --set metrics.enabled=true"
fi

# Redis ServiceMonitor
if kubectl get service -n crypto-infra | grep -q redis.*metrics; then
    echo "  ✓ Applying Redis ServiceMonitor..."
    kubectl apply -f "${SCRIPT_DIR}/redis-servicemonitor.yaml"
else
    echo "  ⚠️  Redis metrics service not found, skipping Redis ServiceMonitor"
    echo "     📋 To enable Redis metrics, run:"
    echo "        helm upgrade redis oci://registry-1.docker.io/bitnamicharts/redis \\"
    echo "          -n crypto-infra --set metrics.enabled=true"
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

