# Recommended Slack Setup - GitHub Native Integration

## Quick Setup (5 minutes)

The easiest and most reliable way to get Slack notifications for your CI/CD pipelines is using GitHub's official Slack integration.

### Step 1: Install GitHub Slack App

1. Go to: https://slack.com/apps/A01BP7R4KNY-github
   - Or visit https://slack.github.com/ and click "Add to Slack"
2. Sign in to your Slack workspace
3. Authorize the GitHub app
4. The app will be added to your workspace

### Step 2: Connect Your GitHub Account

In any Slack channel:
```
/github signin
```

This will open a browser window to connect your GitHub account.

### Step 3: Subscribe to Your Repository

In your desired channel (e.g., #deployments), type:
```
/github subscribe murr2k/rackspace-k8s-demo workflows
```

That's it! You'll now receive notifications for:
- ✅ Successful workflow runs
- ❌ Failed workflow runs
- ⏱️ In-progress status updates

### Customize Notifications (Optional)

Filter by workflow name:
```
/github subscribe murr2k/rackspace-k8s-demo workflows:{name:"deploy-fly"}
```

Filter by branch:
```
/github subscribe murr2k/rackspace-k8s-demo workflows:{branch:"main"}
```

Filter by event:
```
/github subscribe murr2k/rackspace-k8s-demo workflows:{event:"push"}
```

Combine filters:
```
/github subscribe murr2k/rackspace-k8s-demo workflows:{name:"deploy-fly" branch:"main"}
```

### Available Commands

List subscriptions:
```
/github subscribe list
```

Unsubscribe:
```
/github unsubscribe murr2k/rackspace-k8s-demo workflows
```

Get help:
```
/github help
```

## Benefits of GitHub Native Integration

✅ **No configuration required** - Works immediately  
✅ **No secrets to manage** - Uses OAuth, not tokens  
✅ **Rich formatting** - Native GitHub cards with context  
✅ **Real-time updates** - Status changes as they happen  
✅ **Thread support** - Related notifications group together  
✅ **Multiple channels** - Different subscriptions per channel  
✅ **Always up-to-date** - Maintained by GitHub  

## Example Notifications

### Success
```
✅ deploy-fly.yml #123 (main)
Deployment successful by @murr2k
Duration: 3m 24s
```

### Failure
```
❌ e2e-tests.yml #124 (feature/new-feature)
Tests failed by @developer
Failed job: API Tests
Duration: 5m 12s
[View logs]
```

## Advanced Usage

### Multiple Repositories
Subscribe to multiple repos in one channel:
```
/github subscribe org/repo1 workflows
/github subscribe org/repo2 workflows
```

### Different Channels for Different Workflows
In #deployments:
```
/github subscribe murr2k/rackspace-k8s-demo workflows:{name:"deploy-*"}
```

In #testing:
```
/github subscribe murr2k/rackspace-k8s-demo workflows:{name:"e2e-tests"}
```

## Fallback: Custom Webhooks

If you need custom formatting or have specific requirements, the workflows support an optional webhook URL. Simply add `SLACK_WEBHOOK_URL` to your GitHub secrets, and custom notifications will be sent in addition to the GitHub native ones.

However, we strongly recommend using the GitHub native integration as it requires no maintenance and provides better functionality.

## Troubleshooting

**Not receiving notifications?**
1. Verify the subscription: `/github subscribe list`
2. Check the bot has channel access
3. Ensure workflows are running on the subscribed branch

**Too many notifications?**
- Use filters to limit notifications
- Create separate channels for different notification types
- Unsubscribe from less important workflows

---

This is the recommended approach for 2024 and beyond. The deprecated Incoming Webhooks are not needed!