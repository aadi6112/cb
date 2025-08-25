#!/usr/bin/env python3
"""
Quick server status checker
"""

import requests
import sys

def quick_check():
    ports_to_check = [5000, 8080, 3000, 8000, 5001, 8001]
    
    print("🔍 Quick Server Check")
    print("=" * 30)
    
    for port in ports_to_check:
        url = f"http://localhost:{port}"
        try:
            response = requests.get(f"{url}/health", timeout=2)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ FOUND: {url}")
                print(f"   📄 {data.get('message', 'Server running')}")
                print(f"   🌐 Admin: {url}/admin")
                print(f"   💬 Chat: {url}")
                return url
        except:
            print(f"❌ {url} - Not responding")
    
    print(f"\n❌ No HR Chatbot server found!")
    print(f"💡 Make sure you run: python app.py")
    return None

if __name__ == "__main__":
    quick_check()