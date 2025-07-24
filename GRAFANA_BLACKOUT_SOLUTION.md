# Grafana Dashboard Blackout Solution & Meter Fix

## The Blackout Issue

The black screenshots we've been seeing are NOT from a server-side blackout mechanism. Instead:

1. **Grafana Frontend Loading Issue**: The Grafana dashboard shows "Grafana has failed to load its application files" 
2. **JavaScript Error**: There's a "Invalid language tag: en-US@posix" error preventing initialization
3. **API Works Fine**: The backend API and rendering work correctly

## Why Screenshots Show Black

When Playwright (or any browser) captures the Grafana dashboard, it sees the loading error screen which has a dark background, making it appear as a "blackout".

## Viewing the Dashboard

To view the actual dashboard data:

1. **Use the API**: Query `/api/dashboards/uid/power-monitoring` to see configuration
2. **Use Backend Rendering**: Access `/render/d/power-monitoring/eagle-energy-monitor` for PNG images
3. **Open in Browser**: Use the HTML viewer at `grafana-viewer-no-blackout.html`

## The Meter Reading Fix

The Utility Meter Reading panel was showing "87 MWh" instead of "86733 kWh" because:

1. **Auto-scaling**: Grafana's "kwatth" unit auto-scales large values (86733 kWh → 87 MWh)
2. **Solution**: Modified the query to multiply by 1000 and use "watth" unit
   - Query: `... |> map(fn: (r) => ({r with _value: r._value * 1000.0}))`
   - Unit: "watth" (displays as kWh)
   - This shows: 86733000 Wh = 86733 kWh

## Current Status

- ✅ Panel configuration fixed to show correct value
- ✅ API endpoints working correctly
- ❌ Frontend not loading due to JavaScript initialization issue
- ✅ Backend rendering works (can generate PNG images)

## How to Test

1. Check API: `curl https://linknode-grafana.fly.dev/api/dashboards/uid/power-monitoring | jq`
2. Get rendered image: `https://linknode-grafana.fly.dev/render/d/power-monitoring/eagle-energy-monitor?panelId=3`
3. Use the HTML viewer to bypass the loading issue

## Note

There is NO blackout switch needed - the issue is a Grafana frontend loading problem, not an intentional blackout.