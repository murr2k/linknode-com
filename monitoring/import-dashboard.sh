#!/bin/bash

echo "📊 Importing Power Monitoring Dashboard to Grafana"
echo "================================================"
echo ""
echo "Since auto-provisioning had issues, here's how to manually import the dashboard:"
echo ""
echo "1️⃣ Log into Grafana: http://119.9.118.22:30300"
echo ""
echo "2️⃣ Click the '+' icon (or 'Dashboards') in the left sidebar"
echo ""
echo "3️⃣ Select 'Import' or 'New Dashboard' → 'Import'"
echo ""
echo "4️⃣ In the import box, paste this JSON:"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cat << 'EOF'
{
  "id": null,
  "title": "Power Line Monitoring",
  "tags": ["power", "energy", "eagle"],
  "timezone": "browser",
  "schemaVersion": 38,
  "version": 1,
  "refresh": "5s",
  "time": {
    "from": "now-1h",
    "to": "now"
  },
  "panels": [
    {
      "datasource": "InfluxDB",
      "fieldConfig": {
        "defaults": {
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {"color": "green", "value": null},
              {"color": "yellow", "value": 3},
              {"color": "red", "value": 5}
            ]
          },
          "unit": "kwatt",
          "decimals": 3
        }
      },
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
      "id": 1,
      "options": {
        "orientation": "auto",
        "reduceOptions": {
          "values": false,
          "calcs": ["lastNotNull"]
        },
        "showThresholdLabels": false,
        "showThresholdMarkers": true
      },
      "pluginVersion": "10.2.0",
      "targets": [
        {
          "query": "from(bucket: \"power_metrics\")\n  |> range(start: -5m)\n  |> filter(fn: (r) => r[\"_measurement\"] == \"power_metrics\")\n  |> filter(fn: (r) => r[\"_field\"] == \"demand_kw\")\n  |> last()",
          "refId": "A"
        }
      ],
      "title": "Current Power Demand (kW)",
      "type": "gauge"
    },
    {
      "datasource": "InfluxDB",
      "fieldConfig": {
        "defaults": {
          "mappings": [],
          "unit": "kwatth",
          "decimals": 3
        }
      },
      "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
      "id": 2,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {
          "values": false,
          "calcs": ["lastNotNull"]
        }
      },
      "pluginVersion": "10.2.0",
      "targets": [
        {
          "query": "from(bucket: \"power_metrics\")\n  |> range(start: -24h)\n  |> filter(fn: (r) => r[\"_measurement\"] == \"power_metrics\")\n  |> filter(fn: (r) => r[\"_field\"] == \"net_consumption_kwh\")\n  |> last()",
          "refId": "A"
        }
      ],
      "title": "Total Energy Consumed (kWh)",
      "type": "stat"
    },
    {
      "datasource": "InfluxDB",
      "fieldConfig": {
        "defaults": {
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 2,
            "fillOpacity": 10,
            "showPoints": "auto"
          },
          "mappings": [],
          "unit": "kwatt"
        }
      },
      "gridPos": {"h": 10, "w": 24, "x": 0, "y": 8},
      "id": 3,
      "options": {
        "legend": {
          "calcs": ["mean", "max", "min"],
          "displayMode": "table",
          "placement": "bottom"
        },
        "tooltip": {
          "mode": "single"
        }
      },
      "targets": [
        {
          "query": "from(bucket: \"power_metrics\")\n  |> range(start: -1h)\n  |> filter(fn: (r) => r[\"_measurement\"] == \"power_metrics\")\n  |> filter(fn: (r) => r[\"_field\"] == \"demand_kw\")",
          "refId": "A"
        }
      ],
      "title": "Power Demand Over Time",
      "type": "timeseries"
    }
  ]
}
EOF
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "5️⃣ Click 'Load'"
echo ""
echo "6️⃣ Select 'InfluxDB' as the data source"
echo ""
echo "7️⃣ Click 'Import'"
echo ""
echo "✅ Your dashboard should now appear with real-time power data!"
echo ""
echo "💡 Tip: You can also save this JSON to a file and upload it in Grafana"