# Regression Test Blackout System

## Overview

This system prevents false positive regression test failures by "blacking out" dynamic content regions that change on every page load.

## Why Blackouts?

Visual regression tests fail when pixels change. Dynamic content like:
- Real-time charts (Grafana dashboards)
- Power consumption values
- Timestamps
- Animations

...will always cause test failures even when nothing is actually broken.

## How It Works

1. **Before Screenshot**: Dynamic regions are covered with a black overlay containing a descriptive label
2. **During Comparison**: Only static content is compared, dynamic regions are ignored
3. **For Debugging**: Tests can be run without blackouts to see actual content

## Visual Example

```
Normal View:                    Blackout Applied:
┌─────────────────┐            ┌─────────────────┐
│ Power: 607 W    │            │ [Power Reading] │
│                 │            │                 │
│ ┌─────────────┐ │            │ ┌─────────────┐ │
│ │   Grafana   │ │     →      │ │   Grafana   │ │
│ │    Chart    │ │            │ │    Chart    │ │
│ └─────────────┘ │            │ └─────────────┘ │
│                 │            │                 │
│ Updated: 2:45pm │            │  [Timestamp]    │
└─────────────────┘            └─────────────────┘
```

## Usage

### Running Tests with Blackouts (Default)

```bash
npm test regression/power-monitoring-regression.spec.ts
```

### Running Tests without Blackouts (Debug Mode)

```bash
npm test regression/power-monitoring-regression.spec.ts -- --grep "debug mode"
```

### Viewing Blackout Reports

After running tests, check:
- `test-results/regression/linknode-blackout-report.json` - Details of what was blacked out
- `test-results/regression/linknode-blackout-annotated.png` - Visual showing blackout regions
- `test-results/regression/dynamic-elements-report.json` - All detected dynamic elements

## Standard Blackout Regions

### Grafana Charts
- **Selector**: `.grafana-preview iframe, iframe[src*="grafana"]`
- **Reason**: Time-series data changes constantly
- **Label**: "Grafana Chart"

### Power Readings
- **Selector**: `[data-testid="power-value"], .power-reading, .watt-value`
- **Reason**: Real-time values fluctuate
- **Label**: "Power Reading"

### Timestamps
- **Selector**: `[data-testid="timestamp"], .timestamp, .last-updated, time`
- **Reason**: Change on every page load
- **Label**: "Timestamp"

## Adding New Blackouts

```typescript
// In your test:
await blackoutManager.applyBlackouts([
  {
    selector: '.my-dynamic-element',
    label: 'Stock Price',
    reason: 'Market data changes constantly',
    type: 'dynamic-data'
  }
]);
```

## Best Practices

1. **Always Label**: Every blackout should have a clear, visible label
2. **Document Reason**: Explain WHY the region is blacked out
3. **Be Specific**: Use precise selectors to avoid hiding static content
4. **Test Both Ways**: Run with and without blackouts during development
5. **Review Reports**: Check blackout reports to ensure correct regions are hidden

## Troubleshooting

### "Why is my test still failing?"

1. Check if new dynamic content was added
2. Run the "document all dynamic elements" test
3. Add new regions to blackout configuration

### "I can't see what's being tested"

1. Run the debug mode test without blackouts
2. Check the annotated screenshot with red borders
3. Review the blackout report JSON

### "The blackouts aren't working"

1. Verify selectors match current DOM structure
2. Check browser console for errors
3. Ensure blackout CSS is being injected

## Important Note

**Blackouts are NOT errors!** If you see black regions with labels in screenshots, the system is working correctly. This prevents the "Grafana Ouroboros" incident where we spent hours debugging an intentional test feature.

## Future Improvements

- [ ] Automatic detection of dynamic content
- [ ] Configurable blackout opacity (semi-transparent for debugging)
- [ ] Blackout versioning to track changes over time
- [ ] Integration with CI/CD to flag new dynamic regions