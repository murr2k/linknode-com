# Baseline Comparison Report

Generated: 7/23/2025, 8:30:45 AM
Baseline Date: 7/23/2025, 8:29:39 AM

## Summary
- **Total Checks**: 34
- **✅ Passed**: 30 (88.2%)
- **⚠️  Warnings**: 0 (0.0%)
- **❌ Failed**: 4 (11.8%)


## ❌ Failures
- **Navigation Timing > domContentLoaded**: NaN% change
  - Baseline: 0ms
  - Current: 0ms

- **Navigation Timing > loadComplete**: NaN% change
  - Baseline: 0ms
  - Current: 0ms

- **Navigation Timing > dnsLookup**: NaN% change
  - Baseline: 0ms
  - Current: 0ms

- **Navigation Timing > tcpConnection**: NaN% change
  - Baseline: 0ms
  - Current: 0ms




## Detailed Results

### Page Structure
- ✅ header
- ✅ mainHeading
- ✅ metricsSection
- ✅ powerWidget
- ✅ apiStatusWidget
- ✅ grafanaPreview
- ✅ buildStatus
- ✅ footer

### Functionality
- ✅ Functionality - powerMonitoring > currentPower
- ✅ Functionality - powerMonitoring > powerStats
- ✅ Functionality - powerMonitoring > metricsDisplay
- ✅ Functionality - apiStatus > influxStatus
- ✅ Functionality - apiStatus > eagleStatus
- ✅ Functionality - apiStatus > webStatus
- ✅ Functionality - buildInfo > version
- ✅ Functionality - buildInfo > buildDate
- ✅ Functionality - buildInfo > commit
- ✅ Functionality - buildInfo > environment
- ✅ Functionality - grafana > iframe

### Performance
- ❌ Navigation Timing > domContentLoaded: 0ms (NaN% change)
- ❌ Navigation Timing > loadComplete: 0ms (NaN% change)
- ✅ Navigation Timing > totalDuration: 86.29999999701977ms (2.0% change)
- ❌ Navigation Timing > dnsLookup: 0ms (NaN% change)
- ❌ Navigation Timing > tcpConnection: 0ms (NaN% change)
- ✅ Navigation Timing > serverResponse: 72.70000000298023ms (3.9% change)
- ✅ Navigation Timing > domInteractive: 10.600000001490116ms (-9.4% change)
- ✅ Navigation Timing > domComplete: 2.1999999955296516ms (4.8% change)
- ✅ Paint Timing > firstPaint: 148ms (2.8% change)
- ✅ Paint Timing > firstContentfulPaint: 148ms (2.8% change)
- ✅ Resources > Total Size: 0.00MB (0.0% change)
- ✅ Resources > Request Count: 5 (0 requests)

### API Endpoints
- ✅ /api/stats: Status 200
- ✅ /health: Status 200
- ✅ /build-info.json: Status 200

## Recommendations
- Review and fix failing checks before deployment


