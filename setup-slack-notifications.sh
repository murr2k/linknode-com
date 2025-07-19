#!/bin/bash

echo "🔔 Setting up Slack notifications for GitHub Actions"
echo ""
echo "Prerequisites:"
echo "1. Create a Slack app at https://api.slack.com/apps"
echo "2. Enable Incoming Webhooks"
echo "3. Add webhook to #github channel"
echo ""
read -p "Enter your Slack webhook URL: " WEBHOOK_URL

if [ -z "$WEBHOOK_URL" ]; then
    echo "❌ No webhook URL provided"
    exit 1
fi

# Test the webhook
echo "Testing webhook..."
RESPONSE=$(curl -s -X POST "$WEBHOOK_URL" \
  -H 'Content-Type: application/json' \
  -d '{"text":"🎉 GitHub Actions Slack integration test successful!"}')

if [ "$RESPONSE" = "ok" ]; then
    echo "✅ Webhook test successful!"
    
    # Add to GitHub secrets
    echo ""
    echo "Adding webhook to GitHub secrets..."
    gh secret set SLACK_WEBHOOK_URL --body "$WEBHOOK_URL"
    
    echo "✅ Slack webhook added to repository secrets"
    echo ""
    echo "Next steps:"
    echo "1. Copy .github/workflows/deploy-with-slack.yml to .github/workflows/deploy.yml"
    echo "2. Commit and push to trigger a deployment"
    echo ""
    echo "Or use Slack GitHub App (recommended):"
    echo "1. Install: https://slack.github.com/"
    echo "2. In Slack: /github subscribe murr2k/rackspace-k8s-demo"
else
    echo "❌ Webhook test failed. Please check your URL."
    exit 1
fi