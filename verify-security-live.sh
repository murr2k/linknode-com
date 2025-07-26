#!/bin/bash
# Live Security Verification Script
# Date: 2025-07-25

echo "==================================="
echo "Live Security Verification"
echo "Target: https://linknode.com"
echo "Time: $(date)"
echo "==================================="

echo -e "\n1. Checking Security Headers:"
echo "-----------------------------------"
curl -sI https://linknode.com | grep -E "(Content-Security-Policy|X-Frame-Options|X-Content-Type-Options|Strict-Transport-Security|X-XSS-Protection|Referrer-Policy|Permissions-Policy)" | sed 's/^/  ✓ /'

echo -e "\n2. Testing Cloud Metadata Blocking:"
echo "-----------------------------------"
CODE=$(curl -s -o /dev/null -w "%{http_code}" https://linknode.com/opc/v1/instance/)
if [ "$CODE" == "403" ]; then
    echo "  ✓ /opc/v1/instance/ returns 403 (BLOCKED)"
else
    echo "  ✗ /opc/v1/instance/ returns $CODE (NOT BLOCKED)"
fi

echo -e "\n3. Testing Admin Endpoints:"
echo "-----------------------------------"
for endpoint in admin private api; do
    CODE=$(curl -s -o /dev/null -w "%{http_code}" https://linknode.com/$endpoint)
    if [ "$CODE" == "404" ]; then
        echo "  ✓ /$endpoint returns 404 (PROTECTED)"
    else
        echo "  ✗ /$endpoint returns $CODE (NOT PROTECTED)"
    fi
done

echo -e "\n4. Testing CORS Headers:"
echo "-----------------------------------"
CORS=$(curl -sI https://linknode.com -H "Origin: https://example.com" | grep -i "access-control-allow-origin")
if [[ $CORS == *"*"* ]]; then
    echo "  ✗ CORS uses wildcard (INSECURE)"
else
    echo "  ✓ CORS properly configured (no wildcard)"
    echo "    $CORS"
fi

echo -e "\n5. Server Version Check:"
echo "-----------------------------------"
SERVER=$(curl -sI https://linknode.com | grep -i "^server:")
echo "  Server header: $SERVER"
if [[ $SERVER == *"nginx"* ]]; then
    echo "  ✗ Nginx version exposed"
else
    echo "  ✓ Nginx version hidden"
fi

echo -e "\n==================================="
echo "Verification Complete"
echo "==================================="