#!/bin/bash

# This script prepares the kubeconfig for GitHub Actions secret
# Run this locally to generate the base64 encoded kubeconfig

KUBECONFIG_PATH="${1:-/home/murr2k/projects/rackspace/kubeconfig.yaml}"

if [ ! -f "$KUBECONFIG_PATH" ]; then
    echo "❌ Error: Kubeconfig file not found at $KUBECONFIG_PATH"
    echo "Usage: $0 [path-to-kubeconfig]"
    exit 1
fi

echo "📋 Preparing kubeconfig for GitHub Actions..."
echo ""
echo "1. Copy this base64 encoded string:"
echo "================================="
cat "$KUBECONFIG_PATH" | base64 -w 0
echo ""
echo "================================="
echo ""
echo "2. Go to: https://github.com/murr2k/rackspace-k8s-demo/settings/secrets/actions"
echo ""
echo "3. Click 'New repository secret'"
echo ""
echo "4. Add secret:"
echo "   Name: KUBECONFIG"
echo "   Value: [paste the base64 string from step 1]"
echo ""
echo "✅ Done! Your pipeline will now be able to deploy to Rackspace."