set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="crypto-binance"
IMAGE_TAG="latest"
NAMESPACE="crypto-infra"

echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'
echo "🚀 Building and deploying Kafka apps to minikube"
echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'

# 1. Build Docker image
echo ""
echo "📦 Building Docker image..."
cd "$SCRIPT_DIR"
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .

# 2. Load image into minikube
echo ""
echo "📥 Loading image into minikube..."
minikube image load ${IMAGE_NAME}:${IMAGE_TAG}

# 3. Apply Kubernetes manifests
echo ""
echo "📋 Applying Kubernetes manifests..."
kubectl apply -f configYaml/configMap.yaml
kubectl apply -f configYaml/binance-producer-deployment.yaml
kubectl apply -f configYaml/binance-orderbook-producer-deployment.yaml
kubectl apply -f configYaml/redis-consumer-deployment.yaml
kubectl apply -f configYaml/redis-order-book.yaml

# Clear Redis before fetching history
echo ""
echo "🗑️  Cleaning up existing clear-redis job (if any)..."
kubectl delete job clear-redis -n ${NAMESPACE} --ignore-not-found=true

echo ""
echo "🗑️  Running clear-redis job..."
kubectl apply -f configYaml/clear-redis-job.yaml

# Wait for clear-redis job to complete
echo ""
echo "⏳ Waiting for clear-redis job to complete..."
kubectl wait --for=condition=complete --timeout=300s job/clear-redis -n ${NAMESPACE} || echo "⚠️  Clear Redis job may still be running or failed"

# Clean up and run history fetcher
echo ""
echo "🔄 Cleaning up existing history fetcher job (if any)..."
kubectl delete job binance-history-fetcher -n ${NAMESPACE} --ignore-not-found=true

echo ""
echo "📥 Running history fetcher job..."
kubectl apply -f configYaml/history-fetcher-job.yaml

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📊 Check status with:"
echo "  kubectl get pods -n ${NAMESPACE} | grep -E 'binance|redis-consumer'"
echo ""
echo "📝 View logs with:"
echo "  kubectl logs -f deployment/binance-producer -n ${NAMESPACE}"
echo "  kubectl logs -f deployment/binance-orderbook-producer -n ${NAMESPACE}"
echo "  kubectl logs -f deployment/redis-consumer -n ${NAMESPACE}"
echo "  kubectl logs -f deployment/redis-orderbook-consumer -n ${NAMESPACE}"
echo "  kubectl logs -f job/clear-redis -n ${NAMESPACE}"
echo "  kubectl logs -f job/binance-history-fetcher -n ${NAMESPACE}"