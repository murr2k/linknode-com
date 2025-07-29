#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🛠️ Fixing EAGLE 404 Error"
echo "========================"
echo ""

echo "This script will guide you through fixing the 404 error."
echo ""

echo "📋 Step 1: Deploy the Monitoring Stack"
echo "-------------------------------------"
echo "The monitoring service is not currently running."
echo ""
echo "To deploy it, you need to:"
echo "1. Connect to your Kubernetes cluster"
echo "2. Run the deployment script"
echo ""
echo "Commands to run:"
echo ""
echo "# First, connect to your cluster:"
echo "cd $PROJECT_ROOT/scripts"
echo "./rackspace-connect.sh"
echo ""
echo "# Then deploy the monitoring stack:"
echo "cd $PROJECT_ROOT/demo-app/monitoring"
echo "./deploy-monitoring.sh"
echo ""
echo "Press Enter when you've completed this step..."
read -r

echo ""
echo "📋 Step 2: Update Cloudflare Worker"
echo "----------------------------------"
echo "The Cloudflare Worker needs to be updated to route API requests."
echo ""
echo "1. Go to: https://dash.cloudflare.com"
echo "2. Navigate to: Workers & Pages → linknode.com"
echo "3. Click 'Quick Edit' or 'Edit Code'"
echo "4. Copy the ENTIRE contents from the file below:"
echo "   $PROJECT_ROOT/demo-app/cloudflare-setup/worker.js"
echo "5. Paste it into the Cloudflare editor (replacing ALL existing code)"
echo "6. Click 'Save and Deploy'"
echo ""
echo "Would you like to see the worker code now? (y/n)"
read -r show_code

if [[ "$show_code" =~ ^[Yy]$ ]]; then
    echo ""
    echo "========== COPY THIS ENTIRE CODE =========="
    cat "$PROJECT_ROOT/demo-app/cloudflare-setup/worker.js"
    echo ""
    echo "=========================================="
fi

echo ""
echo "Press Enter when you've updated the Cloudflare Worker..."
read -r

echo ""
echo "📋 Step 3: Verify Everything Works"
echo "---------------------------------"
echo "Running verification tests..."
echo ""

# Test direct access
echo "Testing direct access..."
direct_test=$(curl -s -w "%{http_code}" -o /dev/null http://119.9.118.22:30500/api/power-data/test)
if [ "$direct_test" = "200" ]; then
    echo "✅ Direct access works!"
else
    echo "❌ Direct access still failing (HTTP $direct_test)"
    echo "   Make sure you deployed the monitoring stack in Step 1"
fi

# Test Cloudflare
echo "Testing Cloudflare route..."
cf_test=$(curl -s -w "%{http_code}" -o /dev/null https://linknode.com/api/power-data/test)
if [ "$cf_test" = "200" ]; then
    echo "✅ Cloudflare route works!"
else
    echo "❌ Cloudflare route still failing (HTTP $cf_test)"
    echo "   Make sure you updated the worker in Step 2"
fi

echo ""
echo "📋 Step 4: Configure EAGLE"
echo "-------------------------"
echo "If both tests passed above, configure your EAGLE with:"
echo ""
echo "Protocol: HTTPS"
echo "Hostname: linknode.com"
echo "URL: /api/power-data"
echo "Port: 443"
echo "Format: JSON"
echo ""
echo "🔧 If EAGLE still shows 404, try these alternatives:"
echo ""
echo "Option 1 - Direct HTTP:"
echo "  Protocol: HTTP"
echo "  Hostname: 119.9.118.22"
echo "  URL: /api/power-data"
echo "  Port: 30500"
echo "  Format: JSON"
echo ""
echo "Option 2 - Via Tunnel:"
echo "  Protocol: HTTPS"
echo "  Hostname: daniel-holidays-diesel-gross.trycloudflare.com"
echo "  URL: /api/power-data"
echo "  Port: 443"
echo "  Format: JSON"