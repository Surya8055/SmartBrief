import os
import requests
from dotenv import load_dotenv

load_dotenv()

def get_subscribers_from_sheets():
    """Read ACTIVE subscribers from Google Sheets via Apps Script"""
    try:
        apps_script_url = "https://script.google.com/macros/s/AKfycbzVOQldUHHDhvtA0wk_6ZPF85I-e6OxfwObHPbjVhyNQzTIaulYT0BLwmcMEpErh-ueGQ/exec"
        
        print(f"📡 Fetching from Apps Script...")
        
        response = requests.get(apps_script_url, timeout=15, allow_redirects=True)
        
        print(f"📊 Status: {response.status_code}")
        
        if response.status_code != 200:
            return []
        
        data = response.json()
        
        if not data.get('success'):
            print(f"❌ Apps Script error: {data.get('error')}")
            return []
        
        subscribers_data = data.get('subscribers', [])
        
        print(f"✅ Found {len(subscribers_data)} ACTIVE subscriber(s)\n")
        
        if not subscribers_data:
            print("⚠️ No active subscribers!")
            return []
        
        # Convert to tuple format
        subscribers = []
        for sub in subscribers_data:
            # Only include if is_active is True (Apps Script already filters)
            subscribers.append((
                sub['row'],
                sub['email'],
                float(sub['latitude']),
                float(sub['longitude']),
                sub['location'],
                sub['subscribed_at'],
                sub['last_sent']
            ))
            print(f"  ✓ {sub['email']} from {sub['location']}")
        
        return subscribers
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return []


if __name__ == "__main__":
    print("\n🧪 Testing Google Sheets (Active Subscribers Only)\n")
    print("="*60)
    subs = get_subscribers_from_sheets()
    print("="*60)
    print(f"\n✅ Total active: {len(subs)} subscriber(s)\n")