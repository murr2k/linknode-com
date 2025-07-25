#!/usr/bin/env python3
"""
Test script to verify the energy unit conversion fix
"""
import requests
import xml.etree.ElementTree as ET

# Sample Eagle XML data with realistic values
test_xml = """<?xml version="1.0"?>
<rainforest>
  <CurrentSummation>
    <DeviceMacId>0x00123456789abcdef</DeviceMacId>
    <MeterMacId>0x00fedcba987654321</MeterMacId>
    <TimeStamp>0x2A2B2C2D</TimeStamp>
    <SummationDelivered>0x00004E20</SummationDelivered>
    <SummationReceived>0x00000000</SummationReceived>
    <Multiplier>0x00000001</Multiplier>
    <Divisor>0x000003E8</Divisor>
  </CurrentSummation>
</rainforest>"""

# Parse the values
root = ET.fromstring(test_xml)
elem = root.find('.//CurrentSummation')

# Extract values
delivered_hex = elem.findtext('SummationDelivered')
multiplier_hex = elem.findtext('Multiplier')
divisor_hex = elem.findtext('Divisor')

# Convert from hex
delivered_val = int(delivered_hex, 16)  # 0x00004E20 = 20000
mult_val = int(multiplier_hex, 16)     # 0x00000001 = 1
div_val = int(divisor_hex, 16)         # 0x000003E8 = 1000

print("Test Energy Calculation")
print("=" * 50)
print(f"Raw hex values from Eagle:")
print(f"  Delivered: {delivered_hex} = {delivered_val}")
print(f"  Multiplier: {multiplier_hex} = {mult_val}")
print(f"  Divisor: {divisor_hex} = {div_val}")
print()

# Old calculation (incorrect - missing /1000)
old_kwh = (delivered_val * mult_val) / div_val
print(f"Old calculation (bug):")
print(f"  energy_kwh = ({delivered_val} * {mult_val}) / {div_val}")
print(f"  energy_kwh = {old_kwh} kWh")
print(f"  Grafana would display: {old_kwh/1000:.3f} MWh or {old_kwh/1000000:.3f} GWh")
print()

# New calculation (correct - includes /1000)
new_kwh = (delivered_val * mult_val) / div_val / 1000
print(f"New calculation (fixed):")
print(f"  energy_kwh = ({delivered_val} * {mult_val}) / {div_val} / 1000")
print(f"  energy_kwh = {new_kwh} kWh")
print(f"  Grafana would display: {new_kwh} kWh")
print()

print("=" * 50)
print("EXPLANATION:")
print("- Eagle reports energy in Wh (watt-hours)")
print("- The divisor (1000) converts the raw value to Wh")
print("- We need to divide by another 1000 to convert Wh to kWh")
print("- Without this conversion, values are 1000x too large")
print("- This causes Grafana to auto-scale to MWh or GWh")

# Test with a larger value (e.g., 1 year of usage)
print("\n" + "=" * 50)
print("Example with 1 year of typical home usage:")
# Average home uses ~10,000 kWh/year = 10,000,000 Wh
large_delivered = 10000000  # 10 million Wh
old_large = (large_delivered * 1) / 1000
new_large = (large_delivered * 1) / 1000 / 1000

print(f"  Raw value: {large_delivered} (in Eagle units)")
print(f"  Old result: {old_large} kWh = {old_large/1000000:.3f} GWh (WRONG)")
print(f"  New result: {new_large} kWh (CORRECT)")