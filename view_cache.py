import json
import os

CACHE_FILE = "digest_cache.json"

def main():
    if not os.path.exists(CACHE_FILE):
        print(f"❌ Cache file not found: {CACHE_FILE}")
        return

    try:
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)
    except json.JSONDecodeError:
        print(f"❌ Cache file is empty or corrupted.")
        return

    print("\n" + "="*70)
    print("--- SmartBrief Cache Viewer ---")
    print("="*70)

    dates = sorted(cache.keys(), reverse=True)
    if not dates:
        print("Empty cache.")
        return

    for date in dates:
        print(f"\n[DATE: {date}]")
        day_data = cache[date]
        
        # Display Quote
        quote = day_data.get("quote")
        if quote:
            print(f"   - Quote: \"{quote.get('q')}\" - {quote.get('a')}")
        else:
            print("   - No quote cached.")

        # Display Locations
        locations = day_data.get("locations", {})
        if locations:
            print(f"   - Locations cached ({len(locations)}):")
            for loc, entry in locations.items():
                if isinstance(entry, dict):
                    # Expanded Format
                    weather = entry.get("weather", {})
                    news = entry.get("news", [])
                    print(f"      * {loc}:")
                    print(f"        🌤️  Weather: {weather.get('max')}°C / {weather.get('min')}°C (Feels: {weather.get('feels_like')}°C)")
                    print(f"        📰 News Headlines ({len(news)}):")
                    for a in news[:5]:
                        print(f"           - {a.get('title')[:80]}...")
                        print(f"             URL: {a.get('url')}")
                else:
                    # Legacy Format
                    html_size = len(entry)
                    print(f"      * {loc} ({html_size} bytes) [Legacy Format]")
        else:
            print("   - No locations cached.")

    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    main()
