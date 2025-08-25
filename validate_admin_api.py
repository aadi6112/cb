#!/usr/bin/env python3
"""
Validates and tests all admin API endpoints
"""

import requests
import json
import sys
from datetime import datetime

def validate_admin_endpoints():
    """Comprehensive admin API validation"""
    
    print("🔍 HR Chatbot Admin API Validator")
    print("=" * 50)
    
    base_url = "http://localhost:5000"
    api_key = input("Enter your API key: ").strip()
    
    if not api_key:
        print("❌ API key required")
        return False
    
    headers = {'X-API-Key': api_key}
    
    # Test cases
    test_cases = [
        {
            'name': 'Health Check',
            'method': 'GET',
            'url': f'{base_url}/health',
            'headers': {},
            'expected_status': 200
        },
        {
            'name': 'Admin Users List',
            'method': 'GET',
            'url': f'{base_url}/api/v1/admin/users',
            'headers': headers,
            'expected_status': 200
        },
        {
            'name': 'Admin Sessions List',
            'method': 'GET',
            'url': f'{base_url}/api/v1/admin/sessions',
            'headers': headers,
            'expected_status': 200
        },
        {
            'name': 'Admin Stats',
            'method': 'GET',
            'url': f'{base_url}/api/v1/admin/stats',
            'headers': headers,
            'expected_status': 200
        },
        {
            'name': 'Recent Messages',
            'method': 'GET',
            'url': f'{base_url}/api/v1/admin/messages/recent',
            'headers': headers,
            'expected_status': 200
        },
        {
            'name': 'Admin Dashboard Page',
            'method': 'GET',
            'url': f'{base_url}/admin',
            'headers': {},
            'expected_status': 200
        }
    ]
    
    results = []
    
    for test in test_cases:
        print(f"\n🧪 Testing: {test['name']}")
        
        try:
            if test['method'] == 'GET':
                response = requests.get(test['url'], headers=test['headers'], timeout=5)
            
            status_ok = response.status_code == test['expected_status']
            
            if status_ok:
                print(f"   ✅ Status: {response.status_code}")
                
                # Try to parse JSON if it's an API endpoint
                if '/api/' in test['url']:
                    try:
                        data = response.json()
                        print(f"   📄 Response: {len(str(data))} characters")
                        
                        # Show data summary
                        if 'users' in data:
                            print(f"   👥 Users found: {len(data['users'])}")
                        elif 'sessions' in data:
                            print(f"   🔄 Sessions found: {len(data['sessions'])}")
                        elif 'messages' in data:
                            print(f"   💬 Messages found: {len(data['messages'])}")
                        elif 'stats' in data:
                            stats = data['stats']
                            print(f"   📊 Stats: {stats.get('total_users', 0)} users, {stats.get('active_sessions', 0)} sessions")
                            
                    except json.JSONDecodeError:
                        print(f"   ⚠️ Non-JSON response")
                else:
                    print(f"   📄 HTML page loaded successfully")
                
                results.append(('✅', test['name'], 'PASS'))
            else:
                print(f"   ❌ Status: {response.status_code} (expected {test['expected_status']})")
                print(f"   📄 Response: {response.text[:100]}...")
                results.append(('❌', test['name'], f'FAIL ({response.status_code})'))
                
        except requests.exceptions.ConnectionError:
            print(f"   ❌ Connection failed - is the server running?")
            results.append(('❌', test['name'], 'CONNECTION_ERROR'))
        except Exception as e:
            print(f"   ❌ Error: {e}")
            results.append(('❌', test['name'], f'ERROR: {e}'))
    
    # Summary
    print(f"\n📋 Test Results Summary")
    print("=" * 50)
    
    passed = 0
    for status, name, result in results:
        print(f"{status} {name}: {result}")
        if status == '✅':
            passed += 1
    
    print(f"\n📊 Results: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print(f"🎉 All tests passed! Admin dashboard should work perfectly.")
        return True
    else:
        print(f"⚠️ Some tests failed. Check your app.py configuration.")
        return False

if __name__ == "__main__":
    validate_admin_endpoints()