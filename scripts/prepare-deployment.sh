#!/bin/bash

echo "=== Preparing Grafana Dashboard for CI/CD Deployment ==="
echo ""

# Ensure we have the latest stable dashboard
if [ ! -f "k8s/grafana-dashboard-stable.yaml" ]; then
  echo "ERROR: k8s/grafana-dashboard-stable.yaml not found!"
  echo "Please ensure you have the dashboard ConfigMap ready."
  exit 1
fi

# Copy stable dashboard as the main one
echo "1. Setting stable dashboard as main..."
cp k8s/grafana-dashboard-stable.yaml k8s/grafana-dashboard-power.yaml

# Check git status
echo ""
echo "2. Current git status:"
git status --short

echo ""
echo "3. Files ready for deployment:"
ls -la k8s/grafana-dashboard-*.yaml
ls -la .github/workflows/deploy*.yml

echo ""
echo "=== Next Steps ==="
echo "1. Add and commit the changes:"
echo "   git add k8s/grafana-dashboard-*.yaml .github/workflows/deploy*.yml"
echo "   git commit -m 'feat: Add automated Grafana dashboard deployment'"
echo ""
echo "2. Push to trigger deployment:"
echo "   git push origin main"
echo ""
echo "3. The pipeline will:"
echo "   - Deploy all monitoring components"
echo "   - Update Grafana dashboards LIVE (no restart)"
echo "   - Show deployment status in GitHub Actions"
echo ""
echo "Dashboard will auto-update when you push changes to:"
echo "- k8s/grafana-dashboard-*.yaml files"
echo "- monitoring/* files"
echo "- app/* files"