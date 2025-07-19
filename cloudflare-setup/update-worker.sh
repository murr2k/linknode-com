#!/bin/bash

echo "🚀 Updating Cloudflare Worker for Power Monitoring..."
echo ""
echo "This script will update your Cloudflare Worker to support:"
echo "- Power monitoring API endpoints (/api/power-data/*)"
echo "- Grafana dashboard routing (/grafana)"
echo "- CORS headers for API access"
echo ""

# Check if worker.js exists
if [ ! -f "worker.js" ]; then
    echo "❌ Error: worker.js not found in current directory"
    echo "Please run this script from the cloudflare-setup directory"
    exit 1
fi

echo "📋 Instructions to update your Cloudflare Worker:"
echo "------------------------------------------------"
echo ""
echo "1. Go to Cloudflare Dashboard: https://dash.cloudflare.com"
echo ""
echo "2. Navigate to: Workers & Pages → Your Worker (linknode.com)"
echo ""
echo "3. Click 'Quick Edit' or 'Edit Code'"
echo ""
echo "4. Replace the entire worker code with the contents of worker.js"
echo ""
echo "5. Click 'Save and Deploy'"
echo ""
echo "6. Test the endpoints:"
echo "   - API Test: https://linknode.com/api/power-data/test"
echo "   - Landing Page: https://linknode.com/"
echo ""
echo "📝 Note: The worker has been updated locally in worker.js"
echo "You need to manually deploy it to Cloudflare."
echo ""
echo "Would you like to see the updated worker code? (y/n)"
read -r response

if [[ "$response" =~ ^[Yy]$ ]]; then
    echo ""
    echo "========== UPDATED WORKER CODE =========="
    cat worker.js
    echo ""
    echo "========================================="
    echo ""
    echo "Copy the above code and paste it into your Cloudflare Worker editor."
fi

echo ""
echo "✅ After updating the worker, your EAGLE device should be able to POST to:"
echo "   https://linknode.com/api/power-data"
echo ""
echo "🧪 Test with curl:"
echo "   curl https://linknode.com/api/power-data/test"