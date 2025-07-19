#!/bin/bash

# Cloudflare Tunnel Service Manager
# Manages the tunnel as a background service

CLOUDFLARED_BIN="$HOME/bin/cloudflared"
PID_FILE="$HOME/.cloudflared/tunnel.pid"
LOG_FILE="$HOME/.cloudflared/tunnel.log"

start_tunnel() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "✅ Tunnel is already running (PID: $PID)"
            echo "View logs: tail -f $LOG_FILE"
            return
        fi
    fi
    
    echo "🚀 Starting Cloudflare Tunnel in background..."
    nohup $CLOUDFLARED_BIN tunnel --url http://119.9.118.22:32304 > "$LOG_FILE" 2>&1 &
    PID=$!
    echo $PID > "$PID_FILE"
    
    sleep 5
    
    # Extract the URL from logs
    TUNNEL_URL=$(grep -o 'https://[^[:space:]]*\.trycloudflare\.com' "$LOG_FILE" | tail -1)
    
    if [ -n "$TUNNEL_URL" ]; then
        echo "✅ Tunnel started successfully!"
        echo "🔗 Tunnel URL: $TUNNEL_URL"
        echo ""
        echo "📝 To update linknode.com with this URL:"
        echo "   1. Edit worker.js and update the tunnelUrl variable"
        echo "   2. Run: ./upload-worker.sh"
        echo ""
        echo "📊 View logs: tail -f $LOG_FILE"
        echo "🛑 Stop tunnel: $0 stop"
    else
        echo "❌ Failed to start tunnel. Check logs: $LOG_FILE"
    fi
}

stop_tunnel() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "🛑 Stopping tunnel (PID: $PID)..."
            kill $PID
            rm -f "$PID_FILE"
            echo "✅ Tunnel stopped"
        else
            echo "⚠️  Tunnel not running (stale PID file)"
            rm -f "$PID_FILE"
        fi
    else
        echo "⚠️  Tunnel is not running"
    fi
}

status_tunnel() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "✅ Tunnel is running (PID: $PID)"
            TUNNEL_URL=$(grep -o 'https://[^[:space:]]*\.trycloudflare\.com' "$LOG_FILE" | tail -1)
            if [ -n "$TUNNEL_URL" ]; then
                echo "🔗 URL: $TUNNEL_URL"
            fi
            echo "📊 Logs: tail -f $LOG_FILE"
        else
            echo "❌ Tunnel is not running (stale PID file)"
            rm -f "$PID_FILE"
        fi
    else
        echo "❌ Tunnel is not running"
    fi
}

restart_tunnel() {
    stop_tunnel
    sleep 2
    start_tunnel
}

case "$1" in
    start)
        start_tunnel
        ;;
    stop)
        stop_tunnel
        ;;
    status)
        status_tunnel
        ;;
    restart)
        restart_tunnel
        ;;
    logs)
        if [ -f "$LOG_FILE" ]; then
            tail -f "$LOG_FILE"
        else
            echo "No log file found"
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|status|restart|logs}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the tunnel in background"
        echo "  stop    - Stop the running tunnel"
        echo "  status  - Check if tunnel is running"
        echo "  restart - Restart the tunnel"
        echo "  logs    - Follow tunnel logs"
        exit 1
        ;;
esac