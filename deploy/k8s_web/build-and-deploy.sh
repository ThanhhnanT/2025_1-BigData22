#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE="crypto-app"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'
echo "🚀 Building and deploying Frontend & Backend to minikube"
echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'

# Check if minikube is running
if ! minikube status > /dev/null 2>&1; then
    echo "❌ Minikube is not running. Please start minikube first:"
    echo "   minikube start"
    exit 1
fi

# Check if namespace exists
if ! kubectl get namespace ${NAMESPACE} > /dev/null 2>&1; then
    echo "📦 Creating namespace ${NAMESPACE}..."
    kubectl apply -f "${SCRIPT_DIR}/namespace.yaml"
fi

# Function to build and deploy backend
deploy_backend() {
    echo ""
    echo -e "${BLUE}📦 Building Backend Docker image...${NC}"
    cd "${SCRIPT_DIR}/../../backend_fastapi"
    
    BACKEND_IMAGE="crypto-backend-fastapi:latest"
    docker build -t ${BACKEND_IMAGE} .
    
    echo ""
    echo -e "${BLUE}📥 Loading Backend image into minikube...${NC}"
    minikube image load ${BACKEND_IMAGE}
    
    echo ""
    echo -e "${BLUE}📋 Applying Backend Kubernetes manifests...${NC}"
    cd "${SCRIPT_DIR}"
    
    # Apply ConfigMap and Secret first
    kubectl apply -f configmap.yaml
    kubectl apply -f secret.yaml || echo "⚠️  Secret may already exist"
    
    # Apply Service
    kubectl apply -f backend-service.yaml
    
    # Apply Deployment
    kubectl apply -f backend-deployment.yaml
    
    # Restart deployment to use new image
    echo ""
    echo -e "${BLUE}🔄 Restarting Backend deployment...${NC}"
    kubectl rollout restart deployment/backend-fastapi -n ${NAMESPACE}
    
    echo ""
    echo -e "${GREEN}✅ Backend deployment complete!${NC}"
}

# Function to build and deploy frontend
deploy_frontend() {
    echo ""
    echo -e "${BLUE}📦 Building Frontend Docker image...${NC}"
    cd "${SCRIPT_DIR}/../../frontend"
    
    FRONTEND_IMAGE="crypto-frontend-next:local"
    docker build -t ${FRONTEND_IMAGE} .
    
    echo ""
    echo -e "${BLUE}📥 Loading Frontend image into minikube...${NC}"
    minikube image load ${FRONTEND_IMAGE}
    
    echo ""
    echo -e "${BLUE}📋 Applying Frontend Kubernetes manifests...${NC}"
    cd "${SCRIPT_DIR}"
    
    # Apply Service
    kubectl apply -f frontend-service.yaml
    
    # Apply Deployment
    kubectl apply -f frontend-deployment.yaml
    
    # Restart deployment to use new image
    echo ""
    echo -e "${BLUE}🔄 Restarting Frontend deployment...${NC}"
    kubectl rollout restart deployment/frontend-next -n ${NAMESPACE}
    
    echo ""
    echo -e "${GREEN}✅ Frontend deployment complete!${NC}"
}

# Function to deploy ingress
deploy_ingress() {
    echo ""
    echo -e "${BLUE}📋 Applying Ingress...${NC}"
    cd "${SCRIPT_DIR}"
    
    # Check if ingress controller is available
    if ! kubectl get ingressclass nginx > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  NGINX Ingress Controller not found. Installing...${NC}"
        minikube addons enable ingress
        echo "⏳ Waiting for ingress controller to be ready..."
        sleep 10
    fi
    
    # Apply Ingress
    kubectl apply -f ingress.yaml
    
    echo ""
    echo -e "${GREEN}✅ Ingress deployment complete!${NC}"
    
    # Get ingress IP
    echo ""
    echo -e "${BLUE}🌐 Getting Ingress information...${NC}"
    sleep 5
    INGRESS_IP=$(kubectl get ingress -n ${NAMESPACE} -o jsonpath='{.items[0].status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
    
    if [ -z "$INGRESS_IP" ]; then
        # Try to get from minikube
        INGRESS_IP=$(minikube ip)
    fi
    
    if [ -n "$INGRESS_IP" ]; then
        echo ""
        echo -e "${GREEN}📍 Ingress is available at:${NC}"
        echo "   Frontend: http://crypto.local (add to /etc/hosts: ${INGRESS_IP} crypto.local)"
        echo "   Backend API: http://crypto.local/api (add to /etc/hosts: ${INGRESS_IP} crypto.local)"
        echo ""
        echo "   To add to /etc/hosts, run:"
        echo "   echo '${INGRESS_IP} crypto.local' | sudo tee -a /etc/hosts"
    fi
}

# Parse arguments
DEPLOY_BACKEND=false
DEPLOY_FRONTEND=false
DEPLOY_INGRESS_ONLY=false

if [ $# -eq 0 ]; then
    # No arguments, deploy both
    DEPLOY_BACKEND=true
    DEPLOY_FRONTEND=true
else
    for arg in "$@"; do
        case $arg in
            --backend|-b)
                DEPLOY_BACKEND=true
                ;;
            --frontend|-f)
                DEPLOY_FRONTEND=true
                ;;
            --both|-a)
                DEPLOY_BACKEND=true
                DEPLOY_FRONTEND=true
                ;;
            --ingress|-i)
                DEPLOY_INGRESS_ONLY=true
                ;;
            *)
                echo "Unknown option: $arg"
                echo "Usage: $0 [--backend|--frontend|--both|--ingress]"
                echo "  --backend, -b    Deploy only backend"
                echo "  --frontend, -f   Deploy only frontend"
                echo "  --both, -a       Deploy both (default)"
                echo "  --ingress, -i    Deploy only ingress"
                exit 1
                ;;
        esac
    done
fi

# If only ingress is requested, deploy it and exit
if [ "$DEPLOY_INGRESS_ONLY" = true ] && [ "$DEPLOY_BACKEND" = false ] && [ "$DEPLOY_FRONTEND" = false ]; then
    deploy_ingress
    exit 0
fi

# Deploy based on flags
if [ "$DEPLOY_BACKEND" = true ]; then
    deploy_backend
fi

if [ "$DEPLOY_FRONTEND" = true ]; then
    deploy_frontend
fi

# Always deploy ingress if either backend or frontend is deployed
if [ "$DEPLOY_BACKEND" = true ] || [ "$DEPLOY_FRONTEND" = true ]; then
    deploy_ingress
fi

# Summary
echo ""
echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'
echo -e "${GREEN}✅ Deployment Summary${NC}"
echo "=" | awk '{for(i=0;i<80;i++)printf "=";print ""}'

if [ "$DEPLOY_BACKEND" = true ]; then
    echo ""
    echo "📊 Backend Status:"
    echo "   kubectl get pods -n ${NAMESPACE} | grep backend"
    echo "   kubectl logs -f deployment/backend-fastapi -n ${NAMESPACE}"
    echo ""
    echo "🌐 Access Backend:"
    echo "   kubectl port-forward svc/backend-fastapi-service 8000:8000 -n ${NAMESPACE}"
    echo "   Then open: http://localhost:8000"
fi

if [ "$DEPLOY_FRONTEND" = true ]; then
    echo ""
    echo "📊 Frontend Status:"
    echo "   kubectl get pods -n ${NAMESPACE} | grep frontend"
    echo "   kubectl logs -f deployment/frontend-next -n ${NAMESPACE}"
    echo ""
    echo "🌐 Access Frontend:"
    echo "   kubectl port-forward svc/frontend-next-service 3000:3000 -n ${NAMESPACE}"
    echo "   Then open: http://localhost:3000"
fi

echo ""
echo "🌐 Access via Ingress:"
INGRESS_IP=$(kubectl get ingress -n ${NAMESPACE} -o jsonpath='{.items[0].status.loadBalancer.ingress[0].ip}' 2>/dev/null || minikube ip 2>/dev/null || echo "")
if [ -n "$INGRESS_IP" ]; then
    echo "   Frontend: http://crypto.local"
    echo "   Backend API: http://crypto.local/api"
    echo ""
    echo "   Add to /etc/hosts: ${INGRESS_IP} crypto.local"
    echo "   Run: echo '${INGRESS_IP} crypto.local' | sudo tee -a /etc/hosts"
else
    echo "   kubectl get ingress -n ${NAMESPACE}"
fi

echo ""
echo "📋 Check all resources:"
echo "   kubectl get all -n ${NAMESPACE}"
echo "   kubectl get ingress -n ${NAMESPACE}"

