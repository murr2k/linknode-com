# Workflow Notifications Setup

## Overview

This project uses GitHub's native Slack integration for workflow notifications. This provides automatic notifications for workflow failures, deployments, and status changes without requiring any secrets or webhook configuration.

## Current Setup

- **Slack Channel**: `#linknode-com`
- **Integration**: GitHub Slack App
- **Subscription**: All workflows in `murr2k/linknode-com`

## Features

The GitHub Slack integration provides:

- ✅ Workflow failure notifications
- ✅ Deployment status updates
- ✅ Pull request activity
- ✅ Rich formatting with links
- ✅ Thread-based discussions
- ✅ No maintenance required

## Setup Instructions

### For New Team Members

1. **Join the Slack channel**: `#linknode-com`

2. **Connect your GitHub account** (one-time setup):
   ```
   /github signin
   ```

3. **You're done!** You'll now receive notifications in the channel.

### For Repository Admins

To modify the subscription:

```bash
# View current subscriptions
/github subscribe list

# Subscribe to all workflows (current setup)
/github subscribe murr2k/linknode-com workflows

# Subscribe to specific workflows only
/github subscribe murr2k/linknode-com workflows:{name:"Deploy to Fly.io"}

# Add additional event types
/github subscribe murr2k/linknode-com issues pulls deployments

# Unsubscribe from specific events
/github unsubscribe murr2k/linknode-com issues
```

## Notification Types

### Workflow Notifications

- **Failed workflows**: Immediate notification with error details
- **Successful deployments**: Confirmation when deployments complete
- **Cancelled workflows**: When workflows are cancelled (e.g., by new commits)

### Example Notifications

1. **Deployment Success**:
   ```
   ✅ Deploy to Fly.io #123 (main) successful
   Murray Kopit: feat: Add new dashboard feature
   ```

2. **Test Failure**:
   ```
   ❌ E2E Tests #124 (main) failed
   Murray Kopit: fix: Update API endpoint
   View logs → [link]
   ```

## Benefits Over Webhook Approach

1. **No secrets management**: No `SLACK_WEBHOOK_URL` to maintain
2. **Richer notifications**: Better formatting and context
3. **Two-way integration**: Can trigger actions from Slack
4. **Maintained by GitHub**: Always up-to-date with new features
5. **Thread discussions**: Team can discuss failures in threads

## Troubleshooting

### Not receiving notifications?

1. Ensure you've signed in: `/github signin`
2. Check subscription: `/github subscribe list`
3. Verify you're in the `#linknode-com` channel

### Too many notifications?

You can filter by:
- Workflow name
- Event type
- Branch

Example:
```
/github unsubscribe murr2k/linknode-com workflows
/github subscribe murr2k/linknode-com workflows:{name:"Deploy to Fly.io"}
```

### Need help?

- GitHub Slack App documentation: https://github.com/integrations/slack
- In Slack: `/github help`

## Migration from Webhooks

We've removed the custom webhook code from all workflows in favor of the native integration. The old webhook-based notifications required:
- Managing `SLACK_WEBHOOK_URL` secret
- Custom formatting in each workflow
- Maintenance of notification code

All of this is now handled automatically by GitHub's Slack integration.

## Related Documentation

- [GitHub Actions Workflows](../.github/workflows/README.md)
- [CI/CD Improvement Roadmap](https://github.com/murr2k/linknode-com/issues/33)