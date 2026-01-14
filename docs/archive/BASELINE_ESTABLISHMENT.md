# Regression Testing Baseline Establishment

## Overview

A comprehensive regression testing baseline has been established for linknode.com to ensure future releases maintain quality and performance standards.

## What Was Created

### 1. Baseline Capture System
- **Script**: `scripts/capture-baseline.ts`
- Captures current website state including:
  - Visual snapshots (4 viewport sizes)
  - Component screenshots
  - Performance metrics (Core Web Vitals, navigation timing)
  - Feature availability
  - API endpoint status
  - Build information

### 2. Baseline Comparison Tool
- **Script**: `scripts/compare-baseline.ts`
- Compares current state against baseline
- Generates detailed reports
- Identifies regressions with pass/warning/fail status
- Tolerances: 20% for performance, 10% for resources

### 3. Regression Test Suite
- **Test**: `e2e/tests/regression/regression-baseline.spec.ts`
- Automated regression tests including:
  - Feature availability checks
  - Visual regression testing
  - Performance regression testing
  - API contract validation
  - Critical user flow verification

### 4. Documentation
- **Checklist**: `REGRESSION_TEST_CHECKLIST.md`
- Pre-release regression testing checklist
- Manual testing steps
- Baseline management procedures

### 5. CI/CD Integration
- **Workflow**: `.github/workflows/regression-tests.yml`
- Automatic regression testing on PRs
- Baseline artifact management
- PR comments with results

## How to Use

### Initial Baseline Capture
```bash
# First time setup - capture baseline
npm run baseline:capture

# This creates:
# - test-baselines/baseline.json
# - test-baselines/visual/*.png
# - test-baselines/BASELINE_REPORT.md
```

### Running Regression Tests

#### Quick Comparison
```bash
# Compare current state to baseline
npm run baseline:compare
```

#### Full Regression Suite
```bash
# Run comprehensive regression tests
npm run test:regression
```

#### CI/CD
- Automatically runs on all PRs
- Compares against stored baseline
- Reports results in PR comments

### Updating Baseline

When intentional changes are made:
```bash
# Capture new baseline
npm run baseline:capture

# Review changes
git diff test-baselines/

# Commit if correct
git add test-baselines/
git commit -m "chore: Update regression baseline after [feature]"
```

## Baseline Contents

### Visual Baselines
- Desktop (1920x1080)
- Desktop (1440x900)
- Tablet (768x1024)
- Mobile (375x667)
- Component screenshots

### Performance Baselines
- DOM Content Loaded time
- Page load complete time
- First Contentful Paint
- Largest Contentful Paint
- Total resource size
- Request count

### Feature Baselines
- Page structure elements
- Power monitoring features
- API status indicators
- Build information display
- Grafana integration

### API Baselines
- `/api/stats` - Power statistics
- `/api/current` - Current power
- `/health` - Health check
- `/build-info.json` - Build metadata

## Regression Tolerances

### Performance
- Navigation timing: 20% tolerance
- Paint timing: 20% tolerance
- Resource size: 10% tolerance
- API response time: < 1 second

### Visual
- Pixel difference threshold: 0.2 (20%)
- Max different pixels: 100

### Functional
- All features must be present
- API status codes must match
- Critical user flows must work

## Benefits

1. **Quality Assurance**: Catch regressions before deployment
2. **Performance Monitoring**: Prevent performance degradation
3. **Visual Consistency**: Maintain UI appearance
4. **API Stability**: Ensure backward compatibility
5. **Automated Validation**: Reduce manual testing

## Next Steps

1. Run initial baseline capture
2. Integrate into deployment process
3. Monitor regression trends
4. Update baselines quarterly
5. Add more specific test scenarios

## Maintenance

### Quarterly Review
- Update baselines to account for drift
- Review and adjust tolerances
- Add new features to baseline
- Remove deprecated features

### On Major Changes
- Capture new baseline before deployment
- Document what changed and why
- Update regression tests accordingly

## Summary

The regression testing baseline is now established and ready to protect linknode.com from unintended changes. All future releases should pass regression tests before deployment.