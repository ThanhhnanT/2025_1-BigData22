#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART_PATH="${SCRIPT_DIR}/../../Prometheus"
MONITORING_DIR="${SCRIPT_DIR}/../monitoring"
NAMESPACE="crypto-monitoring"
RELEASE_NAME="crypto-monitoring"

# Parse command line arguments
FORCE_REINSTALL=false
if [ "$1" == "--force" ] || [ "$1" == "-f" ]; then
    FORCE_REINSTALL=true
fi

echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'
echo "🚀 Deploying Prometheus and Grafana monitoring stack"
echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'

# 1. Check if minikube is running
echo ""
echo "📋 Checking minikube status..."
if ! minikube status > /dev/null 2>&1; then
    echo "❌ Minikube is not running. Please start minikube first:"
    echo "   minikube start --cpus=4 --memory=8192 --driver=docker"
    exit 1
fi
echo "✅ Minikube is running"

# 2. Create namespace if it doesn't exist
echo ""
echo "📦 Creating namespace ${NAMESPACE}..."
kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -
echo "✅ Namespace ${NAMESPACE} ready"

# 3. Check if local chart exists
echo ""
echo "📦 Checking local Prometheus chart..."
if [ ! -d "${CHART_PATH}" ]; then
    echo "❌ Prometheus chart not found at: ${CHART_PATH}"
    echo "   Please ensure the Prometheus folder exists in the project root"
    exit 1
fi

if [ ! -f "${CHART_PATH}/Chart.yaml" ]; then
    echo "❌ Chart.yaml not found in ${CHART_PATH}"
    exit 1
fi

echo "✅ Found local Prometheus chart at: ${CHART_PATH}"

# 4. Check if pods already exist and are running
echo ""
echo "🔍 Checking if monitoring pods already exist..."
GRAFANA_PODS=$(kubectl get pods -n ${NAMESPACE} -l app.kubernetes.io/name=grafana --no-headers 2>/dev/null | grep -c "Running\|Pending" || echo "0")
PROMETHEUS_PODS=$(kubectl get pods -n ${NAMESPACE} -l app.kubernetes.io/name=prometheus --no-headers 2>/dev/null | grep -c "Running\|Pending" || echo "0")

if [ "$GRAFANA_PODS" -gt 0 ] || [ "$PROMETHEUS_PODS" -gt 0 ]; then
    echo "✅ Found existing monitoring pods:"
    echo "   Grafana pods: $GRAFANA_PODS"
    echo "   Prometheus pods: $PROMETHEUS_PODS"
    echo ""
    echo "📋 Current pod status:"
    kubectl get pods -n ${NAMESPACE} -l 'app.kubernetes.io/name in (grafana,prometheus)' 2>/dev/null || true
    echo ""
    
    if [ "$FORCE_REINSTALL" = false ]; then
        echo "ℹ️  Monitoring pods already exist. Skipping installation."
        echo "   (Use --force to reinstall anyway)"
        SKIP_INSTALL=true
    else
        echo "🔄 Force reinstall requested. Will proceed with installation..."
        SKIP_INSTALL=false
    fi
else
    echo "ℹ️  No existing monitoring pods found. Proceeding with installation..."
    SKIP_INSTALL=false
fi

if [ "$SKIP_INSTALL" = true ]; then
    echo "⏭️  Skipping Helm installation/upgrade as pods already exist"
else
    # 5. Check if release already exists
    RELEASE_EXISTS=$(helm list -n ${NAMESPACE} -q | grep -x ${RELEASE_NAME} || echo "")
    if [ -n "$RELEASE_EXISTS" ]; then
        if [ "$FORCE_REINSTALL" = true ]; then
            echo "🔄 Force reinstall requested. Uninstalling existing release..."
            helm uninstall ${RELEASE_NAME} -n ${NAMESPACE} || true
            echo "⏳ Waiting for resources to be cleaned up..."
            sleep 5
            echo "📦 Installing fresh ${RELEASE_NAME}..."
        else
            echo "⚠️  Release ${RELEASE_NAME} already exists. Upgrading..."
            echo "   (Use --force to uninstall and reinstall instead)"
        fi
        
        if [ "$FORCE_REINSTALL" = false ]; then
            if helm upgrade ${RELEASE_NAME} ${CHART_PATH} \
                --namespace ${NAMESPACE} \
                --wait \
                --timeout 10m; then
                echo "✅ Monitoring stack upgraded"
            else
                echo "❌ Upgrade failed. Try force reinstall:"
                echo "   ./deploy-monitoring.sh --force"
                echo ""
                echo "Or manually uninstall and retry:"
                echo "   helm uninstall ${RELEASE_NAME} -n ${NAMESPACE}"
                exit 1
            fi
        fi
    fi

    if [ -z "$RELEASE_EXISTS" ] || [ "$FORCE_REINSTALL" = true ]; then
        echo "📦 Installing ${RELEASE_NAME}..."
        if helm install ${RELEASE_NAME} ${CHART_PATH} \
            --namespace ${NAMESPACE} \
            --wait \
            --timeout 10m; then
            echo "✅ Monitoring stack installed"
        else
            echo "❌ Installation failed. Checking if release was partially created..."
            # Check if release exists now (might have been created but failed)
            if helm list -n ${NAMESPACE} -q | grep -x ${RELEASE_NAME} > /dev/null 2>&1; then
                echo "⚠️  Release exists but installation failed. Try upgrading instead:"
                echo "   helm upgrade ${RELEASE_NAME} ${CHART_PATH} \\"
                echo "     --namespace ${NAMESPACE}"
                echo ""
                echo "Or uninstall and retry:"
                echo "   helm uninstall ${RELEASE_NAME} -n ${NAMESPACE}"
            fi
            exit 1
        fi
    fi
fi

# 6. Wait for pods to be ready
echo ""
echo "⏳ Waiting for pods to be ready..."
kubectl wait --for=condition=ready pod \
    -l app.kubernetes.io/name=grafana \
    -n ${NAMESPACE} \
    --timeout=300s || echo "⚠️  Grafana pod may still be starting"

kubectl wait --for=condition=ready pod \
    -l app.kubernetes.io/name=prometheus \
    -n ${NAMESPACE} \
    --timeout=300s || echo "⚠️  Prometheus pod may still be starting"

# 7. Get Grafana credentials
echo ""
echo "🔐 Getting Grafana admin credentials..."
GRAFANA_SECRET=$(kubectl get secret -n ${NAMESPACE} ${RELEASE_NAME}-grafana -o jsonpath="{.data.admin-password}" 2>/dev/null || echo "")
if [ -z "$GRAFANA_SECRET" ]; then
    echo "⚠️  Could not retrieve Grafana password. Default credentials:"
    echo "   Username: admin"
    echo "   Password: admin (you will be prompted to change it)"
else
    GRAFANA_PASSWORD=$(echo ${GRAFANA_SECRET} | base64 -d)
    echo "   Username: admin"
    echo "   Password: ${GRAFANA_PASSWORD}"
fi

# 8. Display access information
echo ""
echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'
echo "✅ Monitoring stack deployment complete!"
echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'
echo ""
echo "📊 Access Grafana:"
echo "   Method 1 (NodePort):"
echo "     minikube service ${RELEASE_NAME}-grafana -n ${NAMESPACE}"
echo ""
echo "   Method 2 (Port Forward):"
echo "     kubectl port-forward svc/${RELEASE_NAME}-grafana 3000:80 -n ${NAMESPACE}"
echo "     Then open: http://localhost:3000"
echo ""
echo "📈 Access Prometheus:"
echo "     kubectl port-forward svc/${RELEASE_NAME}-kube-prometheus-prometheus 9090:9090 -n ${NAMESPACE}"
echo "     Then open: http://localhost:9090"
echo ""
echo "🔍 Check pod status:"
echo "     kubectl get pods -n ${NAMESPACE}"
echo ""
echo "📋 Check services:"
echo "     kubectl get svc -n ${NAMESPACE}"
echo ""
echo "📊 Apply ServiceMonitors (optional):"
echo "     cd ${MONITORING_DIR} && ./apply-servicemonitors.sh"
echo ""


