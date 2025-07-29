#!/bin/bash

# Direct access script for WSL environment
# No SSH tunnel needed - we're already on the same machine!

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
KUBECONFIG="$SCRIPT_DIR/kubeconfig.yaml"
export KUBECONFIG=$KUBECONFIG

echo "🚀 Starting Kubernetes port forward for WSL..."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Access the application at:"
echo ""
echo "From WSL:      http://localhost:8090"
echo "From Windows:  http://localhost:8090"
echo ""
echo "Note: This works because WSL2 shares localhost with Windows!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Press Ctrl+C to stop..."
echo ""

# Use 0.0.0.0 to bind to all interfaces, making it accessible from Windows host
kubectl port-forward -n demo-app svc/demo-app-service 8090:80 --address=0.0.0.0