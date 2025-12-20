#!/bin/bash

NAMESPACE="crypto-monitoring"
RELEASE_NAME="crypto-monitoring"

echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'
echo "🔍 Verifying Monitoring Stack"
echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'

# Check namespace
echo ""
echo "1. Checking namespace..."
if kubectl get namespace ${NAMESPACE} > /dev/null 2>&1; then
    echo "   ✅ Namespace ${NAMESPACE} exists"
else
    echo "   ❌ Namespace ${NAMESPACE} does not exist"
    exit 1
fi

# Check Helm release
echo ""
echo "2. Checking Helm release..."
if helm list -n ${NAMESPACE} | grep -q ${RELEASE_NAME}; then
    echo "   ✅ Helm release ${RELEASE_NAME} exists"
    helm list -n ${NAMESPACE} | grep ${RELEASE_NAME}
else
    echo "   ❌ Helm release ${RELEASE_NAME} not found"
    exit 1
fi

# Check pods
echo ""
echo "3. Checking pods..."
PODS=$(kubectl get pods -n ${NAMESPACE} --no-headers 2>/dev/null | wc -l)
if [ "$PODS" -gt 0 ]; then
    echo "   ✅ Found $PODS pod(s)"
    kubectl get pods -n ${NAMESPACE}
    
    # Check if all pods are ready
    READY_PODS=$(kubectl get pods -n ${NAMESPACE} --no-headers 2>/dev/null | grep -c "Running\|Completed" || echo "0")
    TOTAL_PODS=$(kubectl get pods -n ${NAMESPACE} --no-headers 2>/dev/null | wc -l)
    if [ "$READY_PODS" -eq "$TOTAL_PODS" ]; then
        echo "   ✅ All pods are ready"
    else
        echo "   ⚠️  Some pods are not ready ($READY_PODS/$TOTAL_PODS)"
    fi
else
    echo "   ❌ No pods found"
    exit 1
fi

# Check services
echo ""
echo "4. Checking services..."
SERVICES=$(kubectl get svc -n ${NAMESPACE} --no-headers 2>/dev/null | wc -l)
if [ "$SERVICES" -gt 0 ]; then
    echo "   ✅ Found $SERVICES service(s)"
    kubectl get svc -n ${NAMESPACE}
else
    echo "   ❌ No services found"
fi

# Check ServiceMonitors
echo ""
echo "5. Checking ServiceMonitors..."
SERVICEMONITORS=$(kubectl get servicemonitors -A --no-headers 2>/dev/null | wc -l)
if [ "$SERVICEMONITORS" -gt 0 ]; then
    echo "   ✅ Found $SERVICEMONITORS ServiceMonitor(s)"
    kubectl get servicemonitors -A
else
    echo "   ⚠️  No ServiceMonitors found (this is OK if you haven't applied them yet)"
fi

# Check Prometheus targets (if Prometheus is accessible)
echo ""
echo "6. Checking Prometheus configuration..."
PROMETHEUS_POD=$(kubectl get pods -n ${NAMESPACE} -l app.kubernetes.io/name=prometheus --no-headers 2>/dev/null | head -1 | awk '{print $1}')
if [ -n "$PROMETHEUS_POD" ]; then
    echo "   ✅ Prometheus pod found: $PROMETHEUS_POD"
    echo ""
    echo "   To check Prometheus targets, run:"
    echo "   kubectl port-forward svc/${RELEASE_NAME}-kube-prometheus-prometheus 9090:9090 -n ${NAMESPACE}"
    echo "   Then open: http://localhost:9090/targets"
else
    echo "   ⚠️  Prometheus pod not found"
fi

# Check Grafana
echo ""
echo "7. Checking Grafana..."
GRAFANA_POD=$(kubectl get pods -n ${NAMESPACE} -l app.kubernetes.io/name=grafana --no-headers 2>/dev/null | head -1 | awk '{print $1}')
if [ -n "$GRAFANA_POD" ]; then
    echo "   ✅ Grafana pod found: $GRAFANA_POD"
    GRAFANA_SVC=$(kubectl get svc -n ${NAMESPACE} -l app.kubernetes.io/name=grafana --no-headers 2>/dev/null | head -1)
    if echo "$GRAFANA_SVC" | grep -q "NodePort"; then
        NODEPORT=$(echo "$GRAFANA_SVC" | awk '{print $5}' | cut -d: -f2 | cut -d/ -f1)
        echo "   ✅ Grafana NodePort: $NODEPORT"
        echo ""
        echo "   Access Grafana:"
        echo "   minikube service ${RELEASE_NAME}-grafana -n ${NAMESPACE}"
    fi
else
    echo "   ⚠️  Grafana pod not found"
fi

echo ""
echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'
echo "✅ Verification complete"
echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'
echo ""
echo "📚 For more information, see: deploy/helm/MONITORING_README.md"
echo ""


