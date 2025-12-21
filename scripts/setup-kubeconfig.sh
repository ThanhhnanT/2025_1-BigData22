#!/bin/bash
set -e

# Script to setup kubeconfig for EKS cluster
# Usage: ./setup-kubeconfig.sh [CLUSTER_NAME] [REGION]

CLUSTER_NAME="${1:-crypto-eks}"
REGION="${2:-ap-southeast-1}"

echo "=========================================="
echo "Setting up kubeconfig for EKS cluster"
echo "=========================================="
echo "Cluster Name: $CLUSTER_NAME"
echo "Region: $REGION"
echo ""

# Check if cluster exists
if ! aws eks describe-cluster --name $CLUSTER_NAME --region $REGION > /dev/null 2>&1; then
    echo "❌ Error: Cluster '$CLUSTER_NAME' not found in region '$REGION'"
    echo "   Make sure the cluster is created and the name is correct."
    exit 1
fi

# Update kubeconfig
echo "Updating kubeconfig..."
aws eks update-kubeconfig --region $REGION --name $CLUSTER_NAME

# Verify connection
echo ""
echo "Verifying cluster connection..."
if kubectl cluster-info > /dev/null 2>&1; then
    echo "✅ Successfully connected to cluster!"
    echo ""
    kubectl cluster-info
    echo ""
    echo "Current context:"
    kubectl config current-context
else
    echo "❌ Error: Failed to connect to cluster"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ Kubeconfig setup complete!"
echo "=========================================="

