#!/bin/bash
# Deploy monitoring configuration for Spark on Kubernetes
# Usage: ./deploy-monitoring.sh [deploy|delete]

set -e

ACTION=${1:-deploy}
NAMESPACE="crypto-infra"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Spark Monitoring Configuration${NC}"
echo -e "${GREEN}Action: ${ACTION}${NC}"
echo -e "${GREEN}========================================${NC}"

if [ "$ACTION" = "deploy" ]; then
    echo -e "${YELLOW}Deploying ServiceMonitors...${NC}"
    kubectl apply -f config/servicemonitor.yaml
    echo -e "${GREEN}✓ ServiceMonitors deployed${NC}"
    
    echo -e "\n${YELLOW}Deploying Prometheus Rules...${NC}"
    kubectl apply -f config/prometheus-rules.yaml
    echo -e "${GREEN}✓ Prometheus Rules deployed${NC}"
    
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}Monitoring Deployed Successfully!${NC}"
    echo -e "${GREEN}========================================${NC}"
    
    echo -e "\n${YELLOW}Resources created:${NC}"
    kubectl get servicemonitor -n ${NAMESPACE}
    kubectl get prometheusrule -n ${NAMESPACE}
    
    echo -e "\n${YELLOW}Next steps:${NC}"
    echo -e "1. Verify Prometheus is scraping targets:"
    echo -e "   kubectl port-forward -n crypto-monitoring svc/crypto-monitoring-prometheus 9090:9090"
    echo -e "   Open: http://localhost:9090/targets"
    echo -e ""
    echo -e "2. Import Grafana dashboard:"
    echo -e "   kubectl port-forward -n crypto-monitoring svc/crypto-monitoring-grafana 3000:80"
    echo -e "   Open: http://localhost:3000"
    echo -e "   Import: config/grafana-dashboard.json"
    echo -e ""
    echo -e "3. Check alerts:"
    echo -e "   Open: http://localhost:9090/alerts"
    
elif [ "$ACTION" = "delete" ]; then
    echo -e "${YELLOW}Deleting monitoring resources...${NC}"
    kubectl delete -f config/servicemonitor.yaml --ignore-not-found=true
    kubectl delete -f config/prometheus-rules.yaml --ignore-not-found=true
    echo -e "${GREEN}✓ Monitoring resources deleted${NC}"
else
    echo -e "${RED}Error: Invalid action. Use 'deploy' or 'delete'${NC}"
    exit 1
fi

