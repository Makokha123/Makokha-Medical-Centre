#!/usr/bin/env python
"""Test script to verify monthly financial dashboard endpoint"""

import requests
from datetime import datetime, date

# Base URL
BASE_URL = 'http://localhost:5000'

# Test credentials
TEST_USER = 'admin@clinic.local'
TEST_PASSWORD = 'admin123'

def test_monthly_endpoint():
    """Test the monthly financial dashboard endpoint"""
    
    session = requests.Session()
    
    # First, login
    print("1. Logging in...")
    login_data = {
        'username': TEST_USER,
        'password': TEST_PASSWORD
    }
    
    response = session.post(f'{BASE_URL}/auth/login', data=login_data)
    if response.status_code != 200:
        print(f"   ❌ Login failed: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        return False
    
    print("   ✅ Login successful")
    
    # Test 1: Single month request
    print("\n2. Testing single month endpoint...")
    try:
        response = session.get(
            f'{BASE_URL}/api/financial/dashboard/monthly',
            params={'year': 2026, 'month': 1}
        )
        
        if response.status_code == 200:
            print(f"   ✅ Single month request successful")
            print(f"   Response length: {len(response.text)} chars")
        else:
            print(f"   ❌ Request failed with status {response.status_code}")
            print(f"   Response: {response.text[:500]}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        return False
    
    # Test 2: Date range request
    print("\n3. Testing date range endpoint...")
    try:
        response = session.get(
            f'{BASE_URL}/api/financial/dashboard/monthly',
            params={
                'startDate': '2025-11-01',
                'endDate': '2026-01-31'
            }
        )
        
        if response.status_code == 200:
            print(f"   ✅ Date range request successful")
            print(f"   Response length: {len(response.text)} chars")
        else:
            print(f"   ❌ Request failed with status {response.status_code}")
            print(f"   Response: {response.text[:500]}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        return False
    
    print("\n✅ All tests passed!")
    return True

if __name__ == '__main__':
    test_monthly_endpoint()
