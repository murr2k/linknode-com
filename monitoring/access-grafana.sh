#!/bin/bash

echo "📊 Grafana Access Information"
echo "============================"
echo ""
echo "Direct URL: http://119.9.118.22:30300"
echo ""
echo "Login Credentials:"
echo "Username: admin"
echo "Password: admin"
echo ""
echo "Testing Grafana accessibility..."

# Test if Grafana is responding
response=$(curl -s -o /dev/null -w "%{http_code}" http://119.9.118.22:30300/api/health)
if [ "$response" = "200" ]; then
    echo "✅ Grafana is accessible and healthy!"
else
    echo "❌ Grafana returned HTTP $response"
fi

echo ""
echo "Dashboard Location:"
echo "After logging in, look for 'Power Line Monitoring' in the dashboards list"
echo ""
echo "Quick Links:"
echo "- Home: http://119.9.118.22:30300"
echo "- Dashboards: http://119.9.118.22:30300/dashboards"
echo "- Data Sources: http://119.9.118.22:30300/datasources"
echo ""
echo "If you still see redirect issues:"
echo "1. Clear your browser cache"
echo "2. Try an incognito/private window"
echo "3. Use a different browser"