#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
NAMESPACE="crypto-infra"

# Paths to YAML files
CLEAR_REDIS_JOB="${PROJECT_ROOT}/Kafka/configYaml/clear-redis-job.yaml"
HISTORY_FETCHER_JOB="${PROJECT_ROOT}/Kafka/configYaml/history-fetcher-job.yaml"
BINANCE_PRODUCER_DEPLOYMENT="${PROJECT_ROOT}/Kafka/configYaml/binance-producer-deployment.yaml"
BINANCE_ORDERBOOK_PRODUCER_DEPLOYMENT="${PROJECT_ROOT}/Kafka/configYaml/binance-orderbook-producer-deployment.yaml"
REDIS_CONSUMER_DEPLOYMENT="${PROJECT_ROOT}/Kafka/configYaml/redis-consumer-deployment.yaml"
REDIS_ORDERBOOK_CONSUMER_DEPLOYMENT="${PROJECT_ROOT}/Kafka/configYaml/redis-order-book.yaml"

echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'
echo "🔄 Rolling out all Kafka Python pods"
echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'

# Check if namespace exists
if ! kubectl get namespace ${NAMESPACE} > /dev/null 2>&1; then
    echo "❌ Namespace ${NAMESPACE} does not exist."
    exit 1
fi

# Check if YAML files exist
YAML_FILES=(
    "${CLEAR_REDIS_JOB}"
    "${HISTORY_FETCHER_JOB}"
    "${BINANCE_PRODUCER_DEPLOYMENT}"
    "${BINANCE_ORDERBOOK_PRODUCER_DEPLOYMENT}"
    "${REDIS_CONSUMER_DEPLOYMENT}"
    "${REDIS_ORDERBOOK_CONSUMER_DEPLOYMENT}"
)

for file in "${YAML_FILES[@]}"; do
    if [ ! -f "${file}" ]; then
        echo "❌ File not found: ${file}"
        exit 1
    fi
done

# Rollout Deployments
echo ""
echo "📦 Rolling out Deployments..."
echo ""

# 1. binance-producer
echo "1. Rolling out binance-producer deployment..."
kubectl rollout restart deployment/binance-producer -n ${NAMESPACE} 2>/dev/null || {
    echo "   ⚠️  Deployment not found, applying from YAML..."
    kubectl apply -f "${BINANCE_PRODUCER_DEPLOYMENT}"
}
echo "   ⏳ Waiting for rollout to complete..."
kubectl rollout status deployment/binance-producer -n ${NAMESPACE} --timeout=300s || echo "   ⚠️  Rollout may still be in progress"

# 2. binance-orderbook-producer
echo ""
echo "2. Rolling out binance-orderbook-producer deployment..."
kubectl rollout restart deployment/binance-orderbook-producer -n ${NAMESPACE} 2>/dev/null || {
    echo "   ⚠️  Deployment not found, applying from YAML..."
    kubectl apply -f "${BINANCE_ORDERBOOK_PRODUCER_DEPLOYMENT}"
}
echo "   ⏳ Waiting for rollout to complete..."
kubectl rollout status deployment/binance-orderbook-producer -n ${NAMESPACE} --timeout=300s || echo "   ⚠️  Rollout may still be in progress"

# 3. redis-consumer
echo ""
echo "3. Rolling out redis-consumer deployment..."
kubectl rollout restart deployment/redis-consumer -n ${NAMESPACE} 2>/dev/null || {
    echo "   ⚠️  Deployment not found, applying from YAML..."
    kubectl apply -f "${REDIS_CONSUMER_DEPLOYMENT}"
}
echo "   ⏳ Waiting for rollout to complete..."
kubectl rollout status deployment/redis-consumer -n ${NAMESPACE} --timeout=300s || echo "   ⚠️  Rollout may still be in progress"

# 4. redis-orderbook-consumer
echo ""
echo "4. Rolling out redis-orderbook-consumer deployment..."
kubectl rollout restart deployment/redis-orderbook-consumer -n ${NAMESPACE} 2>/dev/null || {
    echo "   ⚠️  Deployment not found, applying from YAML..."
    kubectl apply -f "${REDIS_ORDERBOOK_CONSUMER_DEPLOYMENT}"
}
echo "   ⏳ Waiting for rollout to complete..."
kubectl rollout status deployment/redis-orderbook-consumer -n ${NAMESPACE} --timeout=300s || echo "   ⚠️  Rollout may still be in progress"

# Rollout Jobs
echo ""
echo "📋 Rolling out Jobs..."
echo ""

# 5. clear-redis job
echo "5. Rolling out clear-redis job..."
echo "   🗑️  Deleting existing clear-redis job (if any)..."
kubectl delete job clear-redis -n ${NAMESPACE} --ignore-not-found=true

echo "   ⏳ Waiting for job to be fully deleted..."
sleep 3

echo "   📋 Applying clear-redis job..."
kubectl apply -f "${CLEAR_REDIS_JOB}"

echo "   ⏳ Waiting for clear-redis job to complete..."
if kubectl wait --for=condition=complete --timeout=300s job/clear-redis -n ${NAMESPACE} 2>/dev/null; then
    echo "   ✅ clear-redis job completed successfully"
else
    echo "   ⚠️  clear-redis job may still be running or failed"
    echo "   Check status: kubectl get job clear-redis -n ${NAMESPACE}"
    echo "   View logs: kubectl logs job/clear-redis -n ${NAMESPACE}"
fi

# 6. binance-history-fetcher job
echo ""
echo "6. Rolling out binance-history-fetcher job..."
echo "   🗑️  Deleting existing binance-history-fetcher job (if any)..."
kubectl delete job binance-history-fetcher -n ${NAMESPACE} --ignore-not-found=true

echo "   ⏳ Waiting for job to be fully deleted..."
sleep 3

echo "   📋 Applying binance-history-fetcher job..."
kubectl apply -f "${HISTORY_FETCHER_JOB}"

echo "   ⏳ Waiting for binance-history-fetcher job to start..."
sleep 5

echo ""
echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'
echo "✅ All Kafka Python pods rollout complete!"
echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'
echo ""
echo "📊 Check deployment status:"
echo "   kubectl get deployments -n ${NAMESPACE} | grep -E 'binance-producer|binance-orderbook-producer|redis-consumer|redis-orderbook-consumer'"
echo ""
echo "📊 Check job status:"
echo "   kubectl get jobs -n ${NAMESPACE} | grep -E 'clear-redis|binance-history-fetcher'"
echo ""
echo "📊 Check pod status:"
echo "   kubectl get pods -n ${NAMESPACE} | grep -E 'binance-producer|binance-orderbook-producer|redis-consumer|redis-orderbook-consumer|clear-redis|binance-history-fetcher'"
echo ""
echo "🔍 View logs:"
echo "   Binance Producer: kubectl logs deployment/binance-producer -n ${NAMESPACE}"
echo "   Binance Orderbook Producer: kubectl logs deployment/binance-orderbook-producer -n ${NAMESPACE}"
echo "   Redis Consumer: kubectl logs deployment/redis-consumer -n ${NAMESPACE}"
echo "   Redis Orderbook Consumer: kubectl logs deployment/redis-orderbook-consumer -n ${NAMESPACE}"
echo "   Clear Redis: kubectl logs job/clear-redis -n ${NAMESPACE}"
echo "   History Fetcher: kubectl logs job/binance-history-fetcher -n ${NAMESPACE}"
echo ""

