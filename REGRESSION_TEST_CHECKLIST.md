# Regression Testing Checklist for Linknode.com

## Pre-Release Regression Testing

This checklist should be completed before every release to ensure no regressions have been introduced.

### 🔍 Visual Regression
- [ ] Desktop view (1920x1080) matches baseline
- [ ] Tablet view (768x1024) matches baseline  
- [ ] Mobile view (375x667) matches baseline
- [ ] Component screenshots match baselines:
  - [ ] Power widget
  - [ ] API status widget
  - [ ] Build status section
  - [ ] Metrics section
- [ ] No unexpected layout shifts
- [ ] Fonts render correctly
- [ ] Colors and themes are consistent

### ⚡ Performance Regression
- [ ] Page load time < 3 seconds
- [ ] First Contentful Paint < 1.8s
- [ ] Largest Contentful Paint < 2.5s
- [ ] Cumulative Layout Shift < 0.1
- [ ] Total page size < baseline + 10%
- [ ] JavaScript bundle size hasn't increased significantly
- [ ] No memory leaks detected
- [ ] API response times < 1 second

### 🔧 Functional Regression
- [ ] Power monitoring displays current usage
- [ ] Power statistics (min/avg/max) update correctly
- [ ] API status indicators show correct states:
  - [ ] InfluxDB status
  - [ ] Eagle Monitor status
  - [ ] Web Interface status
- [ ] Build information displays:
  - [ ] Version number
  - [ ] Build date
  - [ ] Commit SHA
  - [ ] Environment
- [ ] Grafana dashboard iframe loads
- [ ] All navigation links work
- [ ] No JavaScript console errors

### 🌐 API Regression
- [ ] `/api/stats` endpoint returns 200
- [ ] `/api/current` endpoint returns valid data
- [ ] `/health` endpoint returns healthy status
- [ ] `/build-info.json` returns current build info
- [ ] CORS headers are present
- [ ] API response formats unchanged
- [ ] No new 4XX or 5XX errors

### 📱 Cross-Browser Regression
- [ ] Chrome/Chromium rendering correct
- [ ] Firefox rendering correct
- [ ] Safari/WebKit rendering correct
- [ ] Mobile Chrome working
- [ ] Mobile Safari working
- [ ] No browser-specific errors

### ♿ Accessibility Regression
- [ ] All interactive elements keyboard accessible
- [ ] Screen reader announcements work
- [ ] Color contrast ratios maintained
- [ ] Focus indicators visible
- [ ] No new accessibility violations

### 🔒 Security Regression
- [ ] No sensitive data in build artifacts
- [ ] HTTPS enforced
- [ ] Security headers present
- [ ] No exposed API keys or tokens
- [ ] CSP policy unchanged

## Automated Regression Testing

### Running Baseline Capture
```bash
# Capture current state as baseline
npx ts-node scripts/capture-baseline.ts
```

### Running Regression Tests
```bash
# Run all regression tests against baseline
npm test -- regression-baseline.spec.ts

# Run with specific tags
npm test -- --grep @regression
```

### Running Phase 3 Tests
```bash
# Comprehensive visual and performance testing
npm run test:phase3
```

## Manual Testing Steps

### 1. Visual Inspection
1. Open https://linknode.com in Chrome
2. Verify header and branding
3. Check power monitoring widget displays data
4. Verify API status indicators
5. Scroll to footer
6. Resize browser to test responsiveness

### 2. Functional Testing
1. Wait for power data to update (should pulse)
2. Check that metrics show reasonable values
3. Verify Grafana dashboard loads in iframe
4. Check build status shows current deployment

### 3. Performance Check
1. Open DevTools Network tab
2. Hard refresh (Ctrl+Shift+R)
3. Check total load time < 3s
4. Verify no failed requests
5. Check total page size

### 4. Mobile Testing
1. Open Chrome DevTools
2. Toggle device toolbar
3. Test on iPhone 12 preset
4. Test on Pixel 5 preset
5. Verify touch interactions work

## Post-Release Verification

After deployment, verify:
- [ ] Production URL loads correctly
- [ ] Build info shows new version
- [ ] No deployment errors in logs
- [ ] Monitoring shows normal metrics
- [ ] No spike in error rates

## Baseline Management

### When to Update Baseline
- After intentional UI changes
- After performance optimizations
- After adding new features
- Quarterly for drift correction

### How to Update Baseline
```bash
# Capture new baseline
npx ts-node scripts/capture-baseline.ts

# Review changes
git diff test-baselines/

# Commit if changes are intentional
git add test-baselines/
git commit -m "chore: Update regression testing baseline"
```

## Regression Prevention

### Best Practices
1. Run regression tests in CI/CD pipeline
2. Review visual diffs before approving PRs
3. Monitor performance metrics continuously
4. Keep baselines up to date
5. Document intentional changes

### CI/CD Integration
All PRs should pass:
- Visual regression tests
- Performance budgets
- Functional tests
- API contract tests

## Issue Reporting

If regression is found:
1. Document the regression with screenshots
2. Compare with baseline
3. Identify the commit that introduced it
4. Create GitHub issue with:
   - Description of regression
   - Steps to reproduce
   - Expected vs actual behavior
   - Screenshots/metrics
   - Affected browsers/devices

## Contact

For questions about regression testing:
- Check [E2E Testing Documentation](./E2E_TESTING_README.md)
- Review [Phase 3 Testing Guide](./E2E_PHASE3_GUIDE.md)
- Create issue in GitHub repository