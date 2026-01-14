# Instructions to Remove Grafana Blackout

## Background
The Grafana regression blackout mechanism has been removed from the codebase as it was causing more problems than it solved. However, the REGRESSION_BLACKOUT secret may still be set in production.

## Steps to Clean Up

### 1. Remove the Secret from Fly.io
```bash
fly secrets unset REGRESSION_BLACKOUT -a linknode-grafana
```

### 2. Verify Removal
```bash
fly secrets list -a linknode-grafana | grep BLACKOUT
# Should return nothing
```

### 3. The App Will Restart Automatically
- Fly.io will restart the Grafana service when the secret is removed
- This should take 1-2 minutes

### 4. Verify Grafana is Working
```bash
# Check API health
curl https://linknode-grafana.fly.dev/api/health

# Check if dashboard loads (should return HTML, not blackout message)
curl -s https://linknode-grafana.fly.dev/d/power-monitoring/power-monitoring | head -20
```

## What This Fixes

- Visual regression tests will see actual Grafana content
- E2E tests can verify dashboard functionality
- No more confusion about whether Grafana is actually working

## Better Testing Strategies

Instead of a blackout mechanism, use these approaches:

1. **Playwright Screenshot Options**
   ```javascript
   await expect(page).toHaveScreenshot('dashboard.png', {
     maxDiffPixels: 100,
     mask: [page.locator('.timestamp-element')]
   });
   ```

2. **Fixed Time Ranges**
   - Configure Grafana dashboards to use "Last 24 hours" instead of "now"
   - Use URL parameters to set specific time ranges in tests

3. **Mock at Test Level**
   - Mock API responses in E2E tests
   - Use Playwright's route interception for consistent data

## Files Removed
- `fly/grafana/blackout.sh` - The blackout script
- `fly/grafana/BLACKOUT_SWITCH_README.md` - Blackout documentation
- `GRAFANA_BLACKOUT_STATUS.md` - Status tracking
- `GRAFANA_BLACKOUT_WARNING.md` - Warning about test interference