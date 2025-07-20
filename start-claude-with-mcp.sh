#!/bin/bash

# Start Claude CLI with MCP support
echo "Starting Claude with MCP claude-flow support..."

# Export environment variables if needed
export CLAUDE_FLOW_LOG_LEVEL="info"
export NODE_ENV="production"

# Check if claude-flow is installed
if ! command -v claude-flow &> /dev/null; then
    echo "Installing claude-flow@alpha..."
    npm install -g claude-flow@alpha
fi

# Start Claude with MCP configuration
# Option 1: If using the official Claude CLI
if command -v claude &> /dev/null; then
    claude --mcp-config ./claude-mcp-config.json "$@"
else
    echo "Claude CLI not found. Please install it first."
    echo ""
    echo "For Claude Desktop App:"
    echo "1. Close Claude Desktop App completely"
    echo "2. The configuration has been saved to: ~/.config/claude/claude_desktop_config.json"
    echo "3. Restart Claude Desktop App"
    echo "4. The MCP claude-flow tools should now be available"
    echo ""
    echo "To verify MCP is working, look for tools starting with 'mcp__claude-flow__' in the tools list"
fi