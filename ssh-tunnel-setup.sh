#!/bin/bash

# SSH Tunnel Setup for Kubernetes Application Access
# This script sets up secure SSH-only access to the demo application

echo "🔒 Setting up SSH-only access to Kubernetes application..."

# Configuration
KUBECONFIG="/home/murr2k/projects/rackspace/kubeconfig.yaml"
NAMESPACE="demo-app"
SERVICE="demo-app-service"
LOCAL_PORT="8081"
SERVICE_PORT="80"

# Export kubeconfig
export KUBECONFIG=$KUBECONFIG

# Function to start port forwarding
start_port_forward() {
    echo "📡 Starting kubectl port-forward..."
    echo "   Namespace: $NAMESPACE"
    echo "   Service: $SERVICE"
    echo "   Local Port: $LOCAL_PORT -> Service Port: $SERVICE_PORT"
    
    kubectl port-forward -n $NAMESPACE svc/$SERVICE $LOCAL_PORT:$SERVICE_PORT
}

# Function to show SSH tunnel instructions
show_ssh_instructions() {
    echo ""
    echo "🚀 SSH Tunnel Instructions:"
    echo "=================================="
    echo ""
    echo "From your LOCAL machine, create an SSH tunnel:"
    echo ""
    echo "ssh -L 8081:localhost:8081 $(whoami)@$(hostname -I | awk '{print $1}')"
    echo ""
    echo "Or if you're using a specific SSH key:"
    echo "ssh -i ~/.ssh/your-key.pem -L 8081:localhost:8081 $(whoami)@$(hostname -I | awk '{print $1}')"
    echo ""
    echo "Then access the application at:"
    echo "http://localhost:8081"
    echo ""
    echo "=================================="
}

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl is not installed or not in PATH"
    exit 1
fi

# Check if the service exists
if ! kubectl get svc $SERVICE -n $NAMESPACE &> /dev/null; then
    echo "❌ Service $SERVICE not found in namespace $NAMESPACE"
    exit 1
fi

# Show instructions
show_ssh_instructions

# Start port forwarding
echo ""
echo "✅ Starting port forward (Press Ctrl+C to stop)..."
start_port_forward