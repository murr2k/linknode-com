# GitHub Actions Slack Integration Guide

## Setting up Slack Notifications for GitHub Pipeline

### 1. Create Slack Webhook

1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Name it "GitHub Actions Bot" and select your workspace
4. Go to "Incoming Webhooks" → Enable it
5. Click "Add New Webhook to Workspace"
6. Select the #github channel
7. Copy the webhook URL (looks like: https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX)

### 2. Add Webhook to GitHub Secrets

```bash
# Add the webhook URL as a repository secret
gh secret set SLACK_WEBHOOK_URL --body "YOUR_WEBHOOK_URL_HERE"
```

### 3. Update GitHub Actions Workflow

Add Slack notifications to `.github/workflows/deploy.yml`:

```yaml
  notify-slack:
    name: Notify Slack
    runs-on: ubuntu-latest
    needs: deploy
    if: always()
    steps:
      - name: Send Slack notification
        uses: 8398a7/action-slack@v3
        with:
          status: ${{ job.status }}
          text: |
            Pipeline Status: ${{ job.status }}
            Workflow: ${{ github.workflow }}
            Commit: ${{ github.sha }}
            Branch: ${{ github.ref }}
            Author: ${{ github.actor }}
          webhook_url: ${{ secrets.SLACK_WEBHOOK_URL }}
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### 4. Alternative: Using Slack GitHub App

1. Install the Slack GitHub app: https://slack.github.com/
2. In Slack, type: `/github subscribe murr2k/linknode-com`
3. Select notification preferences:
   - `/github subscribe murr2k/linknode-com workflows:{name:"Deploy to Rackspace Kubernetes"}`

### 5. Testing the Integration

```bash
# Trigger a test deployment
echo "# Test" >> README.md
git add README.md
git commit -m "Test Slack integration"
git push
```

### 6. Notification Format

The notifications will include:
- ✅ Success/❌ Failure status
- Commit message and author
- Link to the workflow run
- Duration and timestamp
- Branch information