import requests

# 🔹 Replace with your deployed Apps Script doGet URL
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzVOQldUHHDhvtA0wk_6ZPF85I-e6OxfwObHPbjVhyNQzTIaulYT0BLwmcMEpErh-ueGQ/exec"

def get_subscribers_from_sheets():
    """
    Fetch subscribers from Apps Script doGet() endpoint.
    Returns a list of tuples:
    (row_id, email, latitude, longitude, location, subscribed_at, last_sent_date)
    """
    try:
        response = requests.get(APPS_SCRIPT_URL, timeout=15)
        response.raise_for_status()

        data = response.json()

        if not data.get("success"):
            print(f"❌ Apps Script returned error: {data.get('message')}")
            return []

        subscribers = []

        for sub in data.get("subscribers", []):
            # Keep exact same tuple format for send_digest.py
            subscribers.append((
                sub[0],            # row_id
                sub[1],            # email (plaintext)
                float(sub[2]),     # latitude
                float(sub[3]),     # longitude
                sub[4],            # location
                sub[5],            # subscribed_at
                sub[6] if sub[6] else None  # last_sent_date
            ))

        return subscribers

    except Exception as e:
        print(f"❌ Failed to fetch subscribers: {e}")
        return []


def update_last_sent_in_sheets(row_number, date_str):
    """
    Optional: Update last_sent_date for subscriber.
    This requires enabling Google Sheets API write access.
    For now, we'll skip this in favor of checking last_sent in Python.
    """
    pass


if __name__ == "__main__":
    print("Testing Apps Script connection...\n")
    subs = get_subscribers_from_sheets()
    print(f"✅ Found {len(subs)} subscribers:\n")
    for s in subs:
        print(f"  Row {s[0]}: {s[1]} - {s[4]} (Last sent: {s[6] or 'Never'})")
