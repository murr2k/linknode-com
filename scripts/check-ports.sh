#!/bin/bash

# Check for available ports and suggest alternatives

echo "🔍 Checking port availability..."
echo ""

# Common ports to check
PORTS=(8080 8081 8082 8090 9090 9080 8888 3000 3001 5000)

echo "Port Status:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
for port in "${PORTS[@]}"; do
    if ss -tuln | grep -q ":$port "; then
        echo "❌ Port $port: IN USE"
    else
        echo "✅ Port $port: AVAILABLE"
    fi
done
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Find first available port
SELECTED_PORT=""
for port in "${PORTS[@]}"; do
    if ! ss -tuln | grep -q ":$port "; then
        SELECTED_PORT=$port
        break
    fi
done

if [ -n "$SELECTED_PORT" ]; then
    echo ""
    echo "📌 Recommended port: $SELECTED_PORT"
    echo ""
    echo "To use this port, update LOCAL_PORT in ssh-tunnel-setup.sh:"
    echo "LOCAL_PORT=\"$SELECTED_PORT\""
else
    echo ""
    echo "⚠️  All common ports are in use!"
    echo "Try a random high port: $((RANDOM + 10000))"
fi