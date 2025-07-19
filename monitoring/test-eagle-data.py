#!/usr/bin/env python3
"""
Test script to simulate EAGLE device sending power data
"""

import requests
import json
import time
import random
from datetime import datetime
import argparse

def generate_sample_data():
    """Generate sample power data similar to EAGLE device format"""
    base_demand = random.uniform(2.5, 4.5)  # kW
    base_consumption = 12345.678
    
    return {
        "DeviceMacId": "0xd8d5b9000000xxxx",
        "MeterMacId": "0x00135003007xxxxx",
        "TimeStamp": datetime.utcnow().isoformat() + "Z",
        "Demand": base_demand * 1000,  # Convert to watts
        "CurrentSummation": base_consumption,
        "CurrentSummationDelivered": base_consumption + random.uniform(0, 10),
        "CurrentSummationReceived": random.uniform(0, 1),
        "Multiplier": 1,
        "Divisor": 1000,
        "DigitsRight": 3,
        "DigitsLeft": 6,
        "SuppressLeadingZero": "Y"
    }

def send_test_data(endpoint_url, count=1, interval=5):
    """Send test data to the monitoring endpoint"""
    print(f"🔌 Sending test data to: {endpoint_url}")
    print(f"📊 Number of readings: {count}")
    print(f"⏱️  Interval: {interval} seconds")
    print("-" * 50)
    
    successful = 0
    failed = 0
    
    for i in range(count):
        try:
            # Generate sample data
            data = generate_sample_data()
            
            # Send POST request
            response = requests.post(
                endpoint_url,
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                successful += 1
                result = response.json()
                print(f"✅ Reading {i+1}/{count}: Success")
                print(f"   Demand: {result['metrics']['demand_kw']} kW")
                print(f"   Net Consumption: {result['metrics']['net_consumption_kwh']} kWh")
            else:
                failed += 1
                print(f"❌ Reading {i+1}/{count}: Failed (Status: {response.status_code})")
                print(f"   Response: {response.text}")
            
        except requests.exceptions.RequestException as e:
            failed += 1
            print(f"❌ Reading {i+1}/{count}: Error - {str(e)}")
        
        # Wait before next reading (except for last one)
        if i < count - 1:
            time.sleep(interval)
    
    print("-" * 50)
    print(f"📈 Summary: {successful} successful, {failed} failed")

def test_endpoints(base_url):
    """Test all monitoring endpoints"""
    print(f"🧪 Testing monitoring endpoints at: {base_url}")
    print("-" * 50)
    
    # Test the test endpoint
    try:
        response = requests.get(f"{base_url}/api/power-data/test", timeout=5)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Test endpoint: {result['message']}")
            print(f"   InfluxDB connected: {result['influxdb_connected']}")
        else:
            print(f"❌ Test endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Test endpoint error: {str(e)}")
    
    # Test latest reading endpoint
    try:
        response = requests.get(f"{base_url}/api/power-data/latest", timeout=5)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Latest reading endpoint: Found data")
            if 'data' in result:
                print(f"   Data: {json.dumps(result['data'], indent=2)}")
        elif response.status_code == 404:
            print(f"ℹ️  Latest reading endpoint: No data yet")
        else:
            print(f"❌ Latest reading endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Latest reading endpoint error: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Test EAGLE power monitoring endpoints')
    parser.add_argument('--url', default='http://119.9.118.22:30500',
                       help='Base URL of the monitoring service')
    parser.add_argument('--count', type=int, default=5,
                       help='Number of test readings to send')
    parser.add_argument('--interval', type=int, default=5,
                       help='Interval between readings in seconds')
    parser.add_argument('--test-only', action='store_true',
                       help='Only test endpoints without sending data')
    
    args = parser.parse_args()
    
    if args.test_only:
        test_endpoints(args.url)
    else:
        # Test endpoints first
        test_endpoints(args.url)
        print("\n")
        
        # Send test data
        send_test_data(f"{args.url}/api/power-data", args.count, args.interval)
        print("\n")
        
        # Check latest reading after sending data
        print("📊 Checking latest reading after sending data...")
        time.sleep(2)
        test_endpoints(args.url)

if __name__ == "__main__":
    main()