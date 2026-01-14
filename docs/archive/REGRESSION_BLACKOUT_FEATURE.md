# Regression Blackout Feature Documentation

## Overview
This feature provides a structured way to blackout dynamic content during visual regression testing, preventing false positives from time-based changes.

## Implementation

### Core Utility
`/e2e/utils/regression-blackout.ts` - Provides blackout functionality:
- CSS-based element blackouts with labels
- Standard configurations for common dynamic elements
- Debug mode support for development

### Test Suite
`/e2e/tests/regression/power-monitoring-regression.spec.ts` - Comprehensive test scenarios:
- Standard testing with blackouts applied
- Debug mode for viewing without blackouts
- Environment variable control via `REGRESSION_DEBUG`

### HTML Viewer
`/grafana-viewer-no-blackout.html` - Interactive dashboard control:
- Toggle blackout overlay
- Reload dashboard functionality
- Backend render image viewing
- Panel data inspection

## Usage

### Running Tests with Blackouts
```bash
npm run test:regression
```

### Running Tests in Debug Mode (No Blackouts)
```bash
REGRESSION_DEBUG=true npm run test:regression
```

### Blackout Configuration Example
```typescript
const blackouts = [
  {
    selector: '[data-testid="data-testid Panel header Current Power Demand"]',
    label: 'Power Gauge'
  },
  {
    selector: '.timeseries-panel',
    label: 'Time Series Graph'
  }
];
```

## Important Discovery
During implementation, we discovered that the "blackout" preventing dashboard visibility was actually a Grafana frontend loading error, not an intentional test mechanism. The error "Invalid language tag: en-US@posix" prevents the Grafana UI from initializing properly.

## Benefits
1. Prevents regression test failures from dynamic data
2. Maintains visual testing for static UI elements
3. Provides debug mode for development
4. Documents which elements are expected to change