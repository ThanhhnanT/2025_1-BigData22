#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE="crypto-infra"

echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'
echo "🔄 Rolling out Jobs: clear-redis and binance-history-fetcher"
echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'

# Check if namespace exists
if ! kubectl get namespace ${NAMESPACE} > /dev/null 2>&1; then
    echo "❌ Namespace ${NAMESPACE} does not exist."
    exit 1
fi

# Rollout clear-redis job
echo ""
echo "1. Rolling out clear-redis job..."
echo "   🗑️  Deleting existing clear-redis job (if any)..."
kubectl delete job clear-redis -n ${NAMESPACE} --ignore-not-found=true

echo "   ⏳ Waiting for job to be fully deleted..."
sleep 3

echo "   📋 Applying clear-redis job..."
kubectl apply -f "${SCRIPT_DIR}/clear-redis-job.yaml"

echo "   ⏳ Waiting for clear-redis job to complete..."
if kubectl wait --for=condition=complete --timeout=300s job/clear-redis -n ${NAMESPACE} 2>/dev/null; then
    echo "   ✅ clear-redis job completed successfully"
else
    echo "   ⚠️  clear-redis job may still be running or failed"
    echo "   Check status: kubectl get job clear-redis -n ${NAMESPACE}"
    echo "   View logs: kubectl logs job/clear-redis -n ${NAMESPACE}"
fi

# Rollout binance-history-fetcher job
echo ""
echo "2. Rolling out binance-history-fetcher job..."
echo "   🗑️  Deleting existing binance-history-fetcher job (if any)..."
kubectl delete job binance-history-fetcher -n ${NAMESPACE} --ignore-not-found=true

echo "   ⏳ Waiting for job to be fully deleted..."
sleep 3

echo "   📋 Applying binance-history-fetcher job..."
kubectl apply -f "${SCRIPT_DIR}/history-fetcher-job.yaml"

echo "   ⏳ Waiting for binance-history-fetcher job to start..."
sleep 5

echo ""
echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'
echo "✅ Jobs rollout complete!"
echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'
echo ""
echo "📊 Check job status:"
echo "   kubectl get jobs -n ${NAMESPACE} | grep -E 'clear-redis|binance-history-fetcher'"
echo ""
echo "📊 Check pod status:"
echo "   kubectl get pods -n ${NAMESPACE} | grep -E 'clear-redis|binance-history-fetcher'"
echo ""
echo "📝 View logs:"
echo "   clear-redis: kubectl logs job/clear-redis -n ${NAMESPACE}"
echo "   history-fetcher: kubectl logs job/binance-history-fetcher -n ${NAMESPACE}"
echo ""
echo "ℹ️  Note: binance-history-fetcher may take a long time to complete."
echo "   Monitor progress with: kubectl logs -f job/binance-history-fetcher -n ${NAMESPACE}"
echo ""

