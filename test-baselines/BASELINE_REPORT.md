# Regression Testing Baseline Report
Generated: 7/23/2025, 10:52:43 AM

## Summary
- **Capture Date**: 2025-07-23T17:52:43.355Z
- **Visual Snapshots**: 8
- **Performance Metrics**: 4
- **API Endpoints**: 7

## Build Information

- **Version**: v1.0.20
- **Build Date**: 2025-07-23
- **Commit**: 24e570a
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
- **totalDuration**: 84.10000000149012ms
- **dnsLookup**: 0ms
- **tcpConnection**: 0ms
- **serverResponse**: 69.20000000298023ms
- **domInteractive**: 11.599999994039536ms
- **domComplete**: 2.3000000044703484ms

### Paint Timing
- **firstPaint**: 156ms
- **firstContentfulPaint**: 156ms

### Core Web Vitals
- **LCP**: N/Ams
- **CLS**: N/A
- **FID**: N/Ams

### Resource Loading
- **Total Resources**: 8
- **Total Size**: 0.00MB

## API Endpoints
- **GET https://linknode-eagle-monitor.fly.dev/health**: 200
- **GET https://linknode-eagle-monitor.fly.dev/api/stats**: 200
- **GET https://linknode-eagle-monitor.fly.dev/health**: 200
- **GET https://linknode-eagle-monitor.fly.dev/api/stats**: 200
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
