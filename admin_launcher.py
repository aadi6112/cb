#!/usr/bin/env python3
"""
Fixed Admin Dashboard Launcher - Auto-detects running server
"""

import requests
import webbrowser
import time
import json
import sys
from datetime import datetime

class AdminDashboardLauncher:
    def __init__(self):
        self.api_key = None
        self.base_url = None
        self.possible_ports = [5000, 8080, 3000, 8000, 5001, 8001]
        
    def detect_server(self):
        """Auto-detect which port the server is running on"""
        print("🔍 Detecting server location...")
        
        for port in self.possible_ports:
            url = f"http://localhost:{port}"
            try:
                print(f"   Trying {url}...")
                response = requests.get(f"{url}/health", timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    if "HR Chatbot" in data.get('message', ''):
                        print(f"✅ Found HR Chatbot server at {url}")
                        self.base_url = url
                        return True
            except:
                continue
        
        print("❌ Could not find HR Chatbot server on any common port")
        return False
    
    def manual_server_input(self):
        """Let user manually specify server URL"""
        print("\n🔧 Manual Server Configuration")
        print("Common formats:")
        print("  - http://localhost:5000")
        print("  - http://127.0.0.1:8080")
        print("  - http://localhost:3000")
        
        while True:
            url = input("\nEnter server URL (or 'quit' to exit): ").strip()
            
            if url.lower() == 'quit':
                return False
                
            if not url.startswith('http'):
                url = f"http://{url}"
                
            try:
                response = requests.get(f"{url}/health", timeout=5)
                if response.status_code == 200:
                    self.base_url = url
                    print(f"✅ Server found at {url}")
                    return True
                else:
                    print(f"❌ Server responded but not HR Chatbot")
            except:
                print(f"❌ Cannot connect to {url}")
        
        return False
    
    def get_api_key(self):
        """Get API key from user or storage"""
        print("\n🔑 API Key Setup")
        print("=" * 30)
        
        # Try to get from previous sessions
        try:
            with open('.admin_key', 'r') as f:
                saved_key = f.read().strip()
                use_saved = input(f"Use saved API key ({saved_key[:8]}...)? (y/n): ").lower()
                if use_saved == 'y':
                    return saved_key
        except FileNotFoundError:
            pass
        
        # Get new API key
        print("\n💡 If you don't have an API key, run:")
        print("   python setup_organization.py \"Your Company\" \"yourcompany.com\"")
        
        api_key = input("\nEnter your organization API key: ").strip()
        
        if api_key:
            # Save for next time
            with open('.admin_key', 'w') as f:
                f.write(api_key)
            return api_key
        else:
            print("❌ API key is required!")
            return None
    
    def test_admin_endpoints(self):
        """Test if admin endpoints are working"""
        print(f"\n🔍 Testing admin endpoints at {self.base_url}...")
        
        endpoints = [
            ("/api/v1/admin/users", "Users"),
            ("/api/v1/admin/sessions", "Sessions"),
            ("/api/v1/admin/stats", "Stats"),
        ]
        
        headers = {'X-API-Key': self.api_key}
        working = 0
        
        for endpoint, name in endpoints:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", headers=headers, timeout=5)
                if response.status_code == 200:
                    print(f"   ✅ {name}")
                    working += 1
                elif response.status_code == 401:
                    print(f"   ❌ {name} - Invalid API key")
                else:
                    print(f"   ⚠️ {name} - Status {response.status_code}")
            except Exception as e:
                print(f"   ❌ {name} - Error: {e}")
        
        return working > 0
    
    def get_server_info(self):
        """Get and display server information"""
        print(f"\n📊 Server Information")
        print("-" * 30)
        
        try:
            # Health check
            health = requests.get(f"{self.base_url}/health").json()
            print(f"🏥 Status: {health.get('status', 'unknown')}")
            print(f"📅 Version: {health.get('version', 'unknown')}")
            print(f"🔧 Components:")
            components = health.get('components', {})
            for comp, status in components.items():
                emoji = "✅" if status == "ready" or status == "initialized" else "❌"
                print(f"   {emoji} {comp}: {status}")
            
            # Stats if available
            try:
                headers = {'X-API-Key': self.api_key}
                stats_response = requests.get(f"{self.base_url}/api/v1/admin/stats", headers=headers)
                if stats_response.status_code == 200:
                    stats = stats_response.json().get('stats', {})
                    print(f"\n📈 Quick Stats:")
                    print(f"   👥 Users: {stats.get('total_users', 0)}")
                    print(f"   🔄 Active Sessions: {stats.get('active_sessions', 0)}")
                    print(f"   💬 Messages Today: {stats.get('messages_today', 0)}")
            except:
                pass
                
        except Exception as e:
            print(f"⚠️ Could not fetch server info: {e}")
    
    def open_dashboard(self):
        """Open the admin dashboard"""
        admin_url = f"{self.base_url}/admin"
        
        print(f"\n🌐 Opening admin dashboard...")
        print(f"📍 URL: {admin_url}")
        
        try:
            if webbrowser.open(admin_url):
                print(f"✅ Dashboard opened in browser")
            else:
                print(f"⚠️ Please manually open: {admin_url}")
            
            print(f"\n💡 Dashboard Tips:")
            print(f"   • Use API key: {self.api_key[:8]}...")
            print(f"   • Refreshes every 30 seconds")
            print(f"   • Bookmark: {admin_url}")
            
            return True
        except Exception as e:
            print(f"❌ Error opening dashboard: {e}")
            print(f"   Please manually open: {admin_url}")
            return False
    
    def run(self):
        """Main launcher function"""
        print(f"🚀 HR Chatbot Admin Dashboard Launcher")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
        
        # Step 1: Find the server
        if not self.detect_server():
            print(f"\n🔧 Auto-detection failed. Manual setup required.")
            if not self.manual_server_input():
                print(f"❌ Cannot proceed without server connection")
                input("\nPress Enter to exit...")
                return False
        
        # Step 2: Get API key
        self.api_key = self.get_api_key()
        if not self.api_key:
            print(f"❌ Cannot proceed without API key")
            input("\nPress Enter to exit...")
            return False
        
        # Step 3: Test admin endpoints
        if not self.test_admin_endpoints():
            print(f"\n⚠️ Some admin endpoints may not work")
            continue_anyway = input("Continue anyway? (y/n): ").lower()
            if continue_anyway != 'y':
                return False
        
        # Step 4: Show server info
        self.get_server_info()
        
        # Step 5: Open dashboard
        if self.open_dashboard():
            print(f"\n🎉 Success! Admin dashboard is now open.")
            print(f"🔄 Keeping this window open for 30 seconds...")
            
            for i in range(30, 0, -5):
                print(f"   ⏱️ Closing in {i} seconds...")
                time.sleep(5)
            
            return True
        else:
            input("\nPress Enter to exit...")
            return False

def main():
    try:
        launcher = AdminDashboardLauncher()
        launcher.run()
    except KeyboardInterrupt:
        print(f"\n\n👋 Cancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()