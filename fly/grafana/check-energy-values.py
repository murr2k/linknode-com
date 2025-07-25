#!/usr/bin/env python3
"""
Script to check the actual energy values being stored in InfluxDB
and diagnose why they're displaying as GWh
"""

# Example calculation to understand the issue:
# If Eagle reports energy in Wh with a large multiplier and small divisor,
# the calculation could result in very large kWh values

# Typical Eagle values might be:
# delivered = 0x00123456 (hex) = 1193046 (decimal)
# multiplier = 1
# divisor = 1000

# Current calculation:
# energy_kwh = (delivered * multiplier) / divisor / 1000
# energy_kwh = (1193046 * 1) / 1000 / 1000 = 1.193 kWh (reasonable)

# But if divisor is 1 instead of 1000:
# energy_kwh = (1193046 * 1) / 1 / 1000 = 1193.046 kWh = 1.193 MWh

# Or if the delivered value is already very large (e.g., cumulative over years):
# delivered = 0x12345678 = 305419896
# energy_kwh = (305419896 * 1) / 1000 / 1000 = 305.42 kWh

# If displayed in Grafana and the value is actually in MWh or GWh range,
# Grafana will auto-scale the display

print("Energy Unit Calculation Check")
print("=" * 50)

# Test various scenarios
test_cases = [
    {"name": "Normal residential daily", "delivered": 50000, "mult": 1, "div": 1000},
    {"name": "High usage", "delivered": 500000, "mult": 1, "div": 1000},
    {"name": "Wrong divisor (1)", "delivered": 50000, "mult": 1, "div": 1},
    {"name": "Large cumulative", "delivered": 50000000, "mult": 1, "div": 1000},
    {"name": "Very large hex value", "delivered": 0x12345678, "mult": 1, "div": 1000},
]

for test in test_cases:
    # Current calculation in the code
    energy_kwh = (test["delivered"] * test["mult"]) / test["div"] / 1000
    
    print(f"\n{test['name']}:")
    print(f"  Delivered: {test['delivered']} (0x{test['delivered']:X})")
    print(f"  Multiplier: {test['mult']}")
    print(f"  Divisor: {test['div']}")
    print(f"  Result: {energy_kwh:.6f} kWh")
    
    # Show how Grafana would display it
    if energy_kwh >= 1000000:
        print(f"  Display: {energy_kwh/1000000:.3f} GWh")
    elif energy_kwh >= 1000:
        print(f"  Display: {energy_kwh/1000:.3f} MWh")
    else:
        print(f"  Display: {energy_kwh:.3f} kWh")

print("\n" + "=" * 50)
print("DIAGNOSIS:")
print("If Grafana is showing GWh, the stored kWh values must be >= 1,000,000")
print("This suggests either:")
print("1. The Eagle divisor is incorrect (should be 1000 for Wh->kWh)")
print("2. The delivered value is cumulative over a very long period")
print("3. The Eagle is already reporting in kWh (so we're double-converting)")
print("\nSOLUTION: Check the actual Eagle device configuration and raw values")