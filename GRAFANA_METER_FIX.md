# Grafana Meter Reading Fix Documentation

## Problem Description
The Utility Meter Reading panel in the Grafana dashboard was displaying "87 MWh" instead of the correct value "86733 kWh". This was caused by Grafana's automatic unit scaling feature converting kilowatt-hours to megawatt-hours.

## Solution Implemented
To prevent auto-scaling while maintaining proper unit display:

1. **Unit Configuration**: Set unit to "none" to disable automatic scaling
2. **Hardcoded Units**: Added " kWh" as a suffix in the text options
3. **Panel Title**: Updated to "Utility Meter Reading (kWh)" for clarity

## Technical Details

### Dashboard Configuration
- File: `/fly/grafana/provisioning/dashboards/power-monitoring.json`
- Panel ID: 3
- Query: `from(bucket: "energy") |> range(start: -5m) |> filter(fn: (r) => r._measurement == "energy_monitor") |> filter(fn: (r) => r._field == "energy_delivered_kwh") |> last()`

### Key Configuration Changes
```json
{
  "fieldConfig": {
    "defaults": {
      "unit": "none",  // Prevents auto-scaling
      "decimals": 0    // Shows whole numbers
    }
  },
  "options": {
    "text": {
      "suffix": " kWh"  // Hardcoded unit display
    }
  }
}
```

## Attempted Solutions That Failed
1. Using "kwatth" unit - resulted in "87 MWh" (auto-scaled)
2. Using "short" unit - resulted in "87 K" (thousands abbreviation)
3. Using displayName override - units not visible
4. Using value mappings - still auto-scaled
5. Converting to Wh with "watth" unit - rendering issues

## Lessons Learned
- Grafana's unit system aggressively auto-scales large values
- The "none" unit with hardcoded text suffix is the most reliable approach
- Field overrides can conflict with default unit settings
- Backend rendering plugin issues can complicate debugging

## Related Issues
- Grafana frontend fails to load with "Invalid language tag: en-US@posix" error
- Backend rendering shows "No image renderer available/installed"
- These are separate issues from the meter reading display problem