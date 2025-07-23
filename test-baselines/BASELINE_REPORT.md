# Regression Testing Baseline Report
Generated: 7/23/2025, 8:30:45 AM

## Summary
- **Capture Date**: 2025-07-23T15:30:45.444Z
- **Visual Snapshots**: 8
- **Performance Metrics**: 4
- **API Endpoints**: 6

## Build Information

- **Version**: v1.0.19
- **Build Date**: 2025-07-23
- **Commit**: ad36846
- **Environment**: production


## Feature Availability
### Page Structure
- **header**: ✅ Present
- **mainHeading**: Linknode Energy Monitor
- **metricsSection**: ✅ Present
- **powerWidget**: ✅ Present
- **apiStatusWidget**: ✅ Present
- **grafanaPreview**: ✅ Present
- **buildStatus**: ✅ Present
- **footer**: ✅ Present

### Functionality

#### powerMonitoring
- **currentPower**: ✅ Available
- **powerStats**: ✅ Available
- **metricsDisplay**: ✅ Available

#### apiStatus
- **influxStatus**: ✅ Available
- **eagleStatus**: ✅ Available
- **webStatus**: ✅ Available

#### buildInfo
- **version**: ✅ Available
- **buildDate**: ✅ Available
- **commit**: ✅ Available
- **environment**: ✅ Available

#### grafana
- **iframe**: ✅ Available

## Performance Baselines
### Navigation Timing
- **domContentLoaded**: 0ms
- **loadComplete**: 0ms
- **totalDuration**: 86.29999999701977ms
- **dnsLookup**: 0ms
- **tcpConnection**: 0ms
- **serverResponse**: 72.70000000298023ms
- **domInteractive**: 10.600000001490116ms
- **domComplete**: 2.1999999955296516ms

### Paint Timing
- **firstPaint**: 148ms
- **firstContentfulPaint**: 148ms

### Core Web Vitals
- **LCP**: N/Ams
- **CLS**: N/A
- **FID**: N/Ams

### Resource Loading
- **Total Resources**: 5
- **Total Size**: 0.00MB

## API Endpoints
- **GET https://linknode-eagle-monitor.fly.dev/health**: 200
- **GET https://linknode-eagle-monitor.fly.dev/api/stats**: 200
- **GET https://linknode-eagle-monitor.fly.dev/health**: 200
- **GET https://linknode.com/api/stats**: 200
- **GET https://linknode.com/api/current**: 200
- **GET https://linknode.com/health**: 200

## Visual Baselines
The following visual baselines were captured:
- desktop-1080p
- desktop-900p
- tablet-portrait
- mobile
- component-power-widget
- component-api-status-widget
- component-build-status
- component-metrics-section

## Usage
This baseline can be used for:
1. Regression testing after deployments
2. Visual comparison testing
3. Performance degradation detection
4. API contract validation
5. Feature availability verification
