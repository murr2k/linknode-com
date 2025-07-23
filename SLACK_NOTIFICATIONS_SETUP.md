# Slack Notifications Setup Guide

This guide explains how to set up Slack notifications for the GitHub Actions CI/CD pipelines in the Linknode project.

## Overview

The project includes Slack notifications for the following workflows:
- **deploy-fly.yml** - Fly.io deployment status
- **e2e-tests.yml** - E2E test results  
- **deploy.yml** - Kubernetes deployment status
- **deploy-monitoring.yml** - Monitoring stack deployment status

## Notification Types

### Success Notifications ✅
- Deployment URL links
- Service health status
- Test coverage summary
- Deployment details (branch, commit, author)

### Failure Notifications ❌
- Error indication
- Link to workflow logs
- Failed job/test details
- Troubleshooting information

## Setup Instructions

### Step 1: Create Slack Webhook

1. Go to your Slack workspace
2. Navigate to **Apps** → **Add Apps**
3. Search for "Incoming WebHooks"
4. Click **Add to Slack**
5. Choose a channel (e.g., #ci-cd-alerts, #deployments)
6. Click **Add Incoming WebHooks integration**
7. Copy the Webhook URL (starts with `https://hooks.slack.com/services/`)

### Step 2: Add Webhook to GitHub Secrets

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `SLACK_WEBHOOK_URL`
5. Value: Paste your Slack webhook URL
6. Click **Add secret**

### Step 3: Verify Setup

The Slack notifications are already configured in the workflow files. Once you've added the webhook secret, notifications will automatically be sent on:
- Successful deployments
- Failed deployments
- Test passes/failures

## Notification Examples

### Deployment Success
```
✅ Fly.io Deployment Successful

Service: all
Branch: main
Commit: abc1234
Author: murr2k

Live URLs:
• Main Site: https://linknode.com
• Grafana: https://linknode-grafana.fly.dev
• API Health: https://linknode-eagle-monitor.fly.dev/health
```

### Test Failure
```
❌ E2E Tests Failed

Branch: feature/new-feature
Commit: def5678
Author: developer

Failed Jobs:
• ✅ Browser Tests
• ❌ API Tests
• ✅ Visual Tests
• ❌ Performance Tests
• ✅ Accessibility Tests
• ✅ Mobile Tests

View failed tests
```

## Customization

### Changing the Channel

To send notifications to a different channel, create a new webhook for that channel and update the `SLACK_WEBHOOK_URL` secret.

### Modifying Notification Content

Edit the notification text in the workflow files:
```yaml
- name: Slack Notification - Success
  uses: 8398a7/action-slack@v3
  with:
    status: success
    text: |
      Your custom message here
    webhook_url: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### Adding to New Workflows

To add Slack notifications to a new workflow:

```yaml
- name: Slack Notification - Success
  if: success()
  uses: 8398a7/action-slack@v3
  with:
    status: success
    text: |
      ✅ *Your Workflow Succeeded*
      
      *Details:* ${{ github.ref_name }} by ${{ github.actor }}
    webhook_url: ${{ secrets.SLACK_WEBHOOK_URL }}
    
- name: Slack Notification - Failure
  if: failure()
  uses: 8398a7/action-slack@v3
  with:
    status: failure
    text: |
      ❌ *Your Workflow Failed*
      
      *Error:* Check the <${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}|logs>
    webhook_url: ${{ secrets.SLACK_WEBHOOK_URL }}
```

## Troubleshooting

### Notifications Not Sending

1. Verify the `SLACK_WEBHOOK_URL` secret is set correctly
2. Check the webhook URL is valid and not expired
3. Ensure the Slack app has permissions for the channel
4. Check GitHub Actions logs for any errors

### Webhook URL Expired

Slack webhooks don't expire, but if the integration is removed:
1. Re-add the Incoming WebHooks app
2. Generate a new webhook URL
3. Update the GitHub secret

### Rate Limits

Slack webhooks have rate limits:
- Burst: 1 per second
- Sustained: 60 per minute

The current setup should not hit these limits under normal usage.

## Security Notes

- Never commit the webhook URL to your repository
- Use GitHub Secrets for storing sensitive data
- Webhook URLs are channel-specific - they can only post to the configured channel
- Regularly audit your webhooks in Slack admin settings

## Advanced Features

The `8398a7/action-slack@v3` action supports additional features:
- Custom usernames and icons
- Attachments and fields
- Conditional notifications
- Multiple webhook support

See the [action documentation](https://github.com/8398a7/action-slack) for more options.

---

Last updated: 2025-07-23