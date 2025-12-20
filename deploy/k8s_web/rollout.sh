#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE="crypto-app"

echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'
echo "🔄 Rolling out all Kubernetes resources in k8s_web"
echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'

# Check if namespace exists
if ! kubectl get namespace ${NAMESPACE} > /dev/null 2>&1; then
    echo "📦 Creating namespace ${NAMESPACE}..."
    kubectl apply -f "${SCRIPT_DIR}/namespace.yaml"
else
    echo "✅ Namespace ${NAMESPACE} exists"
fi

echo ""
echo "📋 Applying Kubernetes manifests..."

# Apply in order: namespace -> configmap -> secret -> services -> deployments -> ingress
echo ""
echo "1. Applying namespace..."
kubectl apply -f "${SCRIPT_DIR}/namespace.yaml"

echo ""
echo "2. Applying ConfigMap..."
kubectl apply -f "${SCRIPT_DIR}/configmap.yaml"

echo ""
echo "3. Applying Secret..."
kubectl apply -f "${SCRIPT_DIR}/secret.yaml" || echo "⚠️  Secret may already exist or need manual update"

echo ""
echo "4. Applying Services..."
kubectl apply -f "${SCRIPT_DIR}/backend-service.yaml"
kubectl apply -f "${SCRIPT_DIR}/frontend-service.yaml"

echo ""
echo "5. Applying Deployments..."
kubectl apply -f "${SCRIPT_DIR}/backend-deployment.yaml"
kubectl apply -f "${SCRIPT_DIR}/frontend-deployment.yaml"

echo ""
echo "6. Applying Ingress..."
kubectl apply -f "${SCRIPT_DIR}/ingress.yaml"

echo ""
echo "🔄 Restarting deployments to apply changes..."

# Restart backend deployment
if kubectl get deployment backend-fastapi -n ${NAMESPACE} > /dev/null 2>&1; then
    echo "   Restarting backend-fastapi..."
    kubectl rollout restart deployment/backend-fastapi -n ${NAMESPACE}
    echo "   ⏳ Waiting for backend rollout..."
    kubectl rollout status deployment/backend-fastapi -n ${NAMESPACE} --timeout=300s || echo "⚠️  Backend rollout may still be in progress"
else
    echo "   ⚠️  Backend deployment not found"
fi

# Restart frontend deployment
if kubectl get deployment frontend-next -n ${NAMESPACE} > /dev/null 2>&1; then
    echo "   Restarting frontend-next..."
    kubectl rollout restart deployment/frontend-next -n ${NAMESPACE}
    echo "   ⏳ Waiting for frontend rollout..."
    kubectl rollout status deployment/frontend-next -n ${NAMESPACE} --timeout=300s || echo "⚠️  Frontend rollout may still be in progress"
else
    echo "   ⚠️  Frontend deployment not found"
fi

echo ""
echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'
echo "✅ Rollout complete!"
echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'
echo ""
echo "📊 Check pod status:"
echo "   kubectl get pods -n ${NAMESPACE}"
echo ""
echo "📋 Check services:"
echo "   kubectl get svc -n ${NAMESPACE}"
echo ""
echo "🔍 View logs:"
echo "   Backend: kubectl logs -f deployment/backend-fastapi -n ${NAMESPACE}"
echo "   Frontend: kubectl logs -f deployment/frontend-next -n ${NAMESPACE}"
echo ""

