#!/bin/bash

# Quick start script for secure SSH-only access

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
KUBECONFIG="$SCRIPT_DIR/kubeconfig.yaml"
export KUBECONFIG=$KUBECONFIG

echo "🔒 Starting secure SSH-only access to demo application..."
echo ""
echo "This window will handle the Kubernetes port forwarding."
echo "You'll need to create an SSH tunnel from your local machine."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "From your LOCAL machine, run:"
echo ""
echo "ssh -L 8081:localhost:8081 $(whoami)@$(hostname -I | awk '{print $1}')"
echo ""
echo "Then access: http://localhost:8081"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Press Ctrl+C to stop the port forwarding..."
echo ""

kubectl port-forward -n demo-app svc/demo-app-service 8081:80