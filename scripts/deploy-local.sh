#!/bin/bash

# Local deployment script for quick updates
# This script deploys changes directly from your machine

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
KUBECONFIG_PATH="${KUBECONFIG:-$PROJECT_ROOT/kubeconfig.yaml}"
NAMESPACE="demo-app"

echo "🚀 Deploying to Rackspace Kubernetes..."
echo "   Project: $PROJECT_ROOT"
echo "   Kubeconfig: $KUBECONFIG_PATH"
echo ""

# Check if kubeconfig exists
if [ ! -f "$KUBECONFIG_PATH" ]; then
    echo "❌ Error: Kubeconfig not found at $KUBECONFIG_PATH"
    echo "Set KUBECONFIG environment variable or place kubeconfig at default location"
    exit 1
fi

export KUBECONFIG="$KUBECONFIG_PATH"

# Verify connection
echo "🔍 Verifying cluster connection..."
if ! kubectl cluster-info &>/dev/null; then
    echo "❌ Error: Cannot connect to Kubernetes cluster"
    exit 1
fi

# Apply manifests
echo "📦 Applying Kubernetes manifests..."

# Namespace first
kubectl apply -f "$PROJECT_ROOT/k8s/namespace.yaml"

# ConfigMaps
kubectl apply -f "$PROJECT_ROOT/k8s/configmap.yaml" 2>/dev/null || true
kubectl apply -f "$PROJECT_ROOT/k8s/configmap-nginx.yaml"

# Deployment
kubectl apply -f "$PROJECT_ROOT/k8s/deployment-nginx.yaml"

# Service
kubectl apply -f "$PROJECT_ROOT/k8s/service.yaml"

# HPA
kubectl apply -f "$PROJECT_ROOT/k8s/hpa.yaml"

# Restart deployment to pick up ConfigMap changes
echo "🔄 Restarting deployment..."
kubectl rollout restart deployment demo-app -n $NAMESPACE

# Wait for rollout
echo "⏳ Waiting for rollout to complete..."
kubectl rollout status deployment demo-app -n $NAMESPACE --timeout=300s

# Get status
echo ""
echo "✅ Deployment complete!"
echo ""
echo "📊 Current status:"
kubectl get pods -n $NAMESPACE
echo ""
kubectl get svc -n $NAMESPACE
echo ""

# Get access URL
NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
NODE_PORT=$(kubectl get svc demo-app-service -n $NAMESPACE -o jsonpath='{.spec.ports[0].nodePort}')

echo "🌐 Application URL: http://${NODE_IP}:${NODE_PORT}"
echo ""
echo "✨ Deployment successful!"