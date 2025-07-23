# Modern Slack Notifications Setup Guide

This guide provides two modern approaches for setting up Slack notifications for GitHub Actions, replacing the deprecated Incoming Webhooks.

## Option 1: GitHub's Native Slack Integration (Recommended)

This is the simplest approach using GitHub's official Slack app.

### Setup Steps

1. **Install GitHub Slack App**
   - Go to: https://slack.com/apps/A01BP7R4KNY-github
   - Or visit: https://slack.github.com/
   - Click "Add to Slack"
   - Authorize the app for your workspace

2. **Connect Your GitHub Account**
   - In Slack, type: `/github signin`
   - Complete the OAuth flow in your browser

3. **Subscribe to Your Repository**
   - In your desired channel, type: `/github subscribe owner/repo`
   - Example: `/github subscribe murr2k/rackspace-k8s-demo`

3. **Configure Notifications**
   - Subscribe to workflow runs: `/github subscribe owner/repo workflows`
   - Or customize: `/github subscribe owner/repo workflows:{event:"push" branch:"main"}`

4. **Available Events**
   - `workflows` - All workflow runs
   - `workflows:{name:"deploy-fly"}` - Specific workflow
   - `workflows:{event:"push"}` - Push events only
   - `workflows:{actor:"username"}` - Specific user

### Benefits
- No code changes required
- No secrets to manage
- Rich GitHub-native formatting
- Easy to enable/disable
- Supports multiple channels

## Option 2: Slack App with Bot Token

For custom notifications with full control over formatting.

### Prerequisites
1. **Create a Slack App**
   - Go to: https://api.slack.com/apps
   - Click "Create New App" → "From scratch"
   - Name: "CI/CD Bot" (or your preference)
   - Select your workspace

2. **Configure Bot Permissions**
   - Go to "OAuth & Permissions"
   - Add Bot Token Scopes:
     - `chat:write` - Send messages
     - `chat:write.public` - Send to public channels
   - Click "Install to Workspace"
   - Copy the "Bot User OAuth Token" (starts with `xoxb-`)

3. **Get Channel ID**
   - Right-click the channel in Slack
   - Select "View channel details"
   - Copy the Channel ID at the bottom

### GitHub Setup

1. **Add Secrets**
   - Go to: `https://github.com/owner/repo/settings/secrets/actions`
   - Add two secrets:
     - `SLACK_BOT_TOKEN`: Your bot token (xoxb-...)
     - `SLACK_CHANNEL_ID`: Your channel ID (C0123456789)

2. **Workflow Configuration**
   The workflows are already configured to use these secrets with the official Slack GitHub Action.

### Custom Message Format

The workflows use Slack's Block Kit for rich formatting:

```json
{
  "text": "✅ Deployment Successful",
  "blocks": [
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "✅ *Deployment Successful*"
      }
    },
    {
      "type": "section",
      "fields": [
        {
          "type": "mrkdwn",
          "text": "*Service:*\nall"
        },
        {
          "type": "mrkdwn",
          "text": "*Branch:*\nmain"
        }
      ]
    }
  ]
}
```

## Option 3: Simplified Webhook Approach

If you prefer a simpler approach without Slack Apps, you can use Discord-style webhooks or other services that provide Slack-compatible webhooks.

### Using Discord Webhooks
1. Create a Discord webhook
2. Use a service like [discord-slack-webhook-proxy](https://github.com/coderabbitai/discord-slack-webhook-proxy)
3. Update the workflow to use the proxy URL

### Using Other Services
- **Zapier**: Create a webhook trigger that posts to Slack
- **IFTTT**: Webhook to Slack applet
- **Make (Integromat)**: HTTP webhook to Slack scenario

## Comparison

| Feature | GitHub Native | Slack App | Webhook Proxy |
|---------|--------------|-----------|---------------|
| Setup Complexity | ⭐ Easy | ⭐⭐ Moderate | ⭐⭐ Moderate |
| Customization | Limited | Full | Full |
| Maintenance | None | Low | Low |
| Security | Best | Good | Varies |
| Cost | Free | Free | May have limits |

## Recommendations

1. **For most teams**: Use GitHub's native Slack integration
2. **For custom formatting**: Use Slack App with bot token
3. **For simplicity**: Use a webhook proxy service

## Troubleshooting

### GitHub Native Integration
- Ensure the GitHub app has access to your repository
- Check subscription settings with `/github subscribe list`
- Verify channel permissions for the app

### Slack App
- Verify bot token starts with `xoxb-`
- Ensure bot is added to the channel
- Check OAuth scopes include `chat:write`
- Test with Slack's API tester: https://api.slack.com/methods/chat.postMessage/test

### Common Issues
- **No notifications**: Check workflow logs for errors
- **Permission denied**: Ensure bot/app is in the channel
- **Invalid channel**: Use channel ID, not name

## Security Best Practices

1. Use GitHub Secrets for all tokens
2. Rotate tokens periodically
3. Limit bot permissions to minimum required
4. Use private channels for sensitive notifications
5. Audit app installations regularly

---

Last updated: 2025-07-23