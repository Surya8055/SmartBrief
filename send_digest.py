import os
import requests
from datetime import datetime
from dotenv import load_dotenv
import pytz
from timezonefinder import TimezoneFinder
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import time
import sys
import re
from read_sheets import get_subscribers_from_sheets

# Suppress warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import warnings
warnings.filterwarnings('ignore')

# Load environment variables
load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")

# Check for test mode flag
TEST_MODE = '--test' in sys.argv

# Initialize Gemini
import google.generativeai as genai
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

tf = TimezoneFinder()

# ----------------------------
# TIME CHECK
# ----------------------------
def is_7am_local_time(lat, lon, last_sent_date):
    """Check if it's 7-8 AM in subscriber's local timezone"""
    try:
        tz_name = tf.timezone_at(lat=lat, lng=lon)
        if not tz_name:
            return False
        
        local_tz = pytz.timezone(tz_name)
        local_time = datetime.now(pytz.utc).astimezone(local_tz)
        today_str = local_time.strftime("%Y-%m-%d")
        
        if last_sent_date == today_str:
            return False
        
        return local_time.hour == 18
        
    except Exception as e:
        print(f"      ⚠️ Time check error: {e}")
        return False

# ----------------------------
# FETCH WEATHER
# ----------------------------
def fetch_weather(lat, lon, max_retries=3):
    """Fetch weather with retry logic"""
    for attempt in range(max_retries):
        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lon}"
                "&current_weather=true"
                "&daily=temperature_2m_max,temperature_2m_min,"
                "apparent_temperature_max,apparent_temperature_min,"
                "sunrise,sunset,precipitation_sum,uv_index_max,cloudcover_mean"
                "&timezone=auto"
            )
            
            if attempt > 0:
                print(f"         ⏳ Retry {attempt}/{max_retries-1}...")
            
            response = requests.get(url, timeout=15)
            data = response.json()
            
            current = data.get("current_weather", {})
            daily = data.get("daily", {})
            
            feels_like = (
                daily.get("apparent_temperature_max", [current.get("temperature")])[0] +
                daily.get("apparent_temperature_min", [current.get("temperature")])[0]
            ) / 2
            
            return {
                "max": daily.get("temperature_2m_max", [0])[0],
                "min": daily.get("temperature_2m_min", [0])[0],
                "feels_like": round(feels_like, 1),
                "sunrise": daily.get("sunrise", ["06:00"])[0].split("T")[1],
                "sunset": daily.get("sunset", ["18:00"])[0].split("T")[1],
                "uv_index": daily.get("uv_index_max", [0])[0]
            }
            
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            else:
                print(f"         ❌ Weather failed")
                return None
    
    return None

# ----------------------------
# FETCH WORLDWIDE NEWS
# ----------------------------
def fetch_news(location=None, max_articles=10):
    """Fetch news headlines, localized if possible"""
    try:
        # Default fallback
        params = {
            "language": "en",
            "pageSize": max_articles,
            "apiKey": NEWS_API_KEY
        }
        
        country_map = {
            "united states": "us", "usa": "us", "us": "us",
            "india": "in", "uk": "gb", "united kingdom": "gb",
            "australia": "au", "canada": "ca", "germany": "de",
            "france": "fr", "italy": "it", "japan": "jp",
            "china": "cn", "brazil": "br"
        }
        
        if location:
            # Simple heuristic: extract the last part of "City, Country"
            parts = location.split(',')
            if len(parts) > 1:
                country_name = parts[-1].strip().lower()
                # Check known mappings
                if country_name in country_map:
                    params["country"] = country_map[country_name]
                else:
                    # Fallback to query if no code match
                    params["q"] = country_name
        
        if "country" not in params and "q" not in params:
            params["category"] = "general" # Worldwide top headlines

        response = requests.get("https://newsapi.org/v2/top-headlines", params=params, timeout=10)
        data = response.json()
        
        articles = data.get("articles", [])
        news_list = []
        
        for a in articles:
            if a.get("title") and a.get("description") and a.get("url"):
                news_list.append({
                    "title": a['title'],
                    "description": a['description'],
                    "url": a['url']
                })
        
        return news_list[:5] if news_list else [{"title": "No news", "description": "", "url": ""}]
        
    except Exception as e:
        print(f"         ⚠️ News failed: {e}")
        return [{"title": "No news", "description": "", "url": ""}]

# ----------------------------
# FETCH QUOTE
# ----------------------------
def fetch_quote():
    """Fetch daily quote from ZenQuotes"""
    try:
        response = requests.get("https://zenquotes.io/api/today", timeout=10)
        data = response.json()
        if data and isinstance(data, list) and len(data) > 0:
            return {
                "q": data[0].get("q", "No quote today"),
                "a": data[0].get("a", "Unknown")
            }
        return {"q": "The best way to predict the future is to create it.", "a": "Peter Drucker"}
    except Exception as e:
        print(f"         ⚠️ Quote failed: {e}")
        return {"q": "The best way to predict the future is to create it.", "a": "Peter Drucker"}

# ----------------------------
# CLEAN HTML
# ----------------------------
def clean_html_response(text):
    """Remove markdown from AI response"""
    text = re.sub(r'```html\n?', '', text)
    text = re.sub(r'```\n?', '', text)
    text = text.strip()
    text = re.sub(r'<!DOCTYPE html>.*?<body[^>]*>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'</body>.*?</html>', '', text, flags=re.DOTALL | re.IGNORECASE)
    return text

# ----------------------------
# AI MESSAGE
# ----------------------------
def ai_message(weather, location, news_list, quote):
    """Generate brief"""
    today = datetime.now().strftime("%A, %B %d, %Y")
    
    news_text = ""
    for i, a in enumerate(news_list[:5], 1):
        news_text += f"{i}. {a['title']}\n{a['description'][:120]}\nURL: {a['url']}\n\n"
    
    prompt = f"""Email for {location}, {today}. NO markdown, ONLY HTML:

<h2 style="color:#0F172A;margin:0 0 10px 0;font-size:1.75rem;font-weight:700">Hello! 👋</h2>
<p style="color:#334155;font-size:1rem;margin:0 0 32px 0">{today} • {location}</p>

<div style="margin-bottom:28px;padding:20px;background:#F8FAFC;border-radius:12px;border-left:4px solid #6366F1">
<p style="font-size:1.1rem;font-style:italic;color:#1E293B;margin:0 0 8px 0">"{quote['q']}"</p>
<p style="font-size:0.9rem;color:#64748B;margin:0;font-weight:600">— {quote['a']}</p>
</div>

<div style="background:#ECFDF5;padding:28px;border-radius:16px;margin-bottom:28px;border-left:5px solid #14B8A6">
<h3 style="color:#0D9488;font-size:1.2rem;margin:0 0 16px 0;font-weight:700">🌤️ Weather</h3>
<div style="margin-bottom:14px">
<span style="font-size:1rem;color:#0F172A;margin-right:20px"><strong>High:</strong> {weather['max']}°C</span>
<span style="font-size:1rem;color:#0F172A;margin-right:20px"><strong>Low:</strong> {weather['min']}°C</span>
<span style="font-size:1rem;color:#0F172A;margin-right:20px"><strong>Feels:</strong> {weather['feels_like']}°C</span>
<span style="font-size:1rem;color:#0F172A"><strong>UV:</strong> {weather['uv_index']}</span>
</div>
<p style="font-size:1rem;color:#1E293B;line-height:1.7;margin:0 0 12px 0">[1-2 helpful sentences]</p>
<p style="font-size:0.9rem;color:#334155;margin:0">☀️ {weather['sunrise']} • 🌙 {weather['sunset']}</p>
</div>

<div style="background:#ffffff;padding:28px;border-radius:16px;border-left:5px solid #EF4444;box-shadow:0 4px 12px rgba(0,0,0,0.06)">
<h3 style="color:#DC2626;font-size:1.2rem;margin:0 0 20px 0;font-weight:700">📰 Top 5 News • TLDR</h3>

[5 items:]
<div style="margin-bottom:18px;padding-bottom:18px;border-bottom:1px solid #E2E8F0">
<p style="font-weight:700;margin:0 0 8px 0;font-size:1rem;color:#0F172A;line-height:1.5">[Headline]</p>
<p style="font-size:0.95rem;color:#334155;margin:0 0 10px 0;line-height:1.6">[TLDR]</p>
<a href="[URL]" style="color:#0D9488;font-size:0.9rem;text-decoration:none;font-weight:600">Read more →</a>
</div>

NEWS:
{news_text}

Remove border from #5.
</div>

<p style="text-align:center;color:#334155;font-size:1rem;margin:24px 0 0 0;font-weight:600">Have a great day! 🚀</p>

Natural. All 5 + URLs."""
    
    try:
        print("         🤖 Generating...")
        response = model.generate_content(prompt)
        content = clean_html_response(response.text)
        print("         ✓ Ready")
        return content
        
    except Exception as e:
        print(f"         ⚠️ Failed")
        
        news_html = ''
        for idx, article in enumerate(news_list[:5]):
            border = '' if idx == 4 else 'border-bottom:1px solid #E2E8F0;'
            news_html += f"""
<div style="margin-bottom:18px;padding-bottom:18px;{border}">
<p style="font-weight:700;margin:0 0 8px 0;font-size:1rem;color:#0F172A;line-height:1.5">{article['title'][:120]}</p>
<p style="font-size:0.95rem;color:#334155;margin:0 0 10px 0;line-height:1.6">{article['description'][:180] if article['description'] else 'Full story available.'}</p>
<a href="{article['url']}" style="color:#0D9488;font-size:0.9rem;text-decoration:none;font-weight:600">Read more →</a>
</div>
"""
        
        return f"""
<h2 style="color:#0F172A;margin:0 0 10px 0;font-size:1.75rem;font-weight:700">Hello! 👋</h2>
<p style="color:#334155;font-size:1rem;margin:0 0 32px 0">{today} • {location}</p>

<div style="margin-bottom:28px;padding:20px;background:#F8FAFC;border-radius:12px;border-left:4px solid #6366F1">
<p style="font-size:1.1rem;font-style:italic;color:#1E293B;margin:0 0 8px 0">"{quote['q']}"</p>
<p style="font-size:0.9rem;color:#64748B;margin:0;font-weight:600">— {quote['a']}</p>
</div>

<div style="background:#ECFDF5;padding:28px;border-radius:16px;margin-bottom:28px;border-left:5px solid #14B8A6">
<h3 style="color:#0D9488;font-size:1.2rem;margin:0 0 16px 0;font-weight:700">🌤️ Weather</h3>
<div style="margin-bottom:14px">
<span style="font-size:1rem;color:#0F172A;margin-right:20px"><strong>High:</strong> {weather['max']}°C</span>
<span style="font-size:1rem;color:#0F172A;margin-right:20px"><strong>Low:</strong> {weather['min']}°C</span>
<span style="font-size:1rem;color:#0F172A;margin-right:20px"><strong>Feels:</strong> {weather['feels_like']}°C</span>
<span style="font-size:1rem;color:#0F172A"><strong>UV:</strong> {weather['uv_index']}</span>
</div>
<p style="font-size:1rem;color:#1E293B;line-height:1.7;margin:0 0 12px 0">Temperature from {weather['min']}°C to {weather['max']}°C. Conditions look good.</p>
<p style="font-size:0.9rem;color:#334155;margin:0">☀️ {weather['sunrise']} • 🌙 {weather['sunset']}</p>
</div>

<div style="background:#ffffff;padding:28px;border-radius:16px;border-left:5px solid #EF4444;box-shadow:0 4px 12px rgba(0,0,0,0.06)">
<h3 style="color:#DC2626;font-size:1.2rem;margin:0 0 20px 0;font-weight:700">📰 Top 5 News • TLDR</h3>
{news_html}
</div>

<p style="text-align:center;color:#334155;font-size:1rem;margin:24px 0 0 0;font-weight:600">Have a great day! 🚀</p>
"""

# ----------------------------
# SEND EMAIL - DARK MODE FIX
# ----------------------------
def send_email(to_email, subject, html_content):
    """Send email with high contrast for dark mode"""
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = SENDER_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject
        
        from urllib.parse import quote
        unsubscribe_url = f"https://surya8055.github.io/SmartBrief/unsubscribe.html?email={quote(to_email)}"
        
        # Using much darker colors that show up in dark mode
        full_html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="light only">
  <meta name="supported-color-schemes" content="light">
  <style>
    * {{ color-scheme: light only !important; }}
    body {{ background-color: #F0FDFA !important; }}
  </style>
</head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;background-color:#F0FDFA !important;padding:40px 20px">
  
  <div style="max-width:700px;margin:0 auto;background-color:#ffffff !important;border-radius:24px;overflow:hidden;box-shadow:0 10px 40px rgba(0,0,0,0.1);border:1px solid #14B8A6">
    
    <!-- Header -->
    <div style="background:linear-gradient(135deg,#14B8A6 0%,#1E40AF 100%);padding:40px 36px;text-align:center">
      <div style="margin-bottom:14px">
        <div style="display:inline-block;width:56px;height:56px;background-color:#ffffff !important;border-radius:14px;line-height:56px;text-align:center">
          <span style="font-family:'Segoe UI',Arial,sans-serif;font-weight:900;font-size:1.7rem;color:#14B8A6 !important">SB</span>
        </div>
      </div>
      <h1 style="color:#ffffff !important;font-size:2rem;font-weight:800;margin:0 0 6px 0">SmartBrief</h1>
      <p style="color:#ffffff !important;font-size:1.05rem;margin:0">Start Your Day Smart</p>
    </div>
    
    <!-- Content -->
    <div style="padding:40px 36px;background-color:#ffffff !important;color:#0F172A !important">
      {html_content}
    </div>
    
    <!-- Footer -->
    <div style="background-color:#F8FAFC !important;padding:24px 36px;border-top:1px solid #CBD5E1;text-align:center">
      <p style="color:#334155 !important;font-size:0.9rem;margin:0">
        <a href="{unsubscribe_url}" style="color:#0D9488 !important;text-decoration:none;font-weight:600">Unsubscribe</a> • © 2026 SmartBrief
      </p>
    </div>
    
  </div>
  
</body>
</html>
        """
        
        msg.attach(MIMEText(full_html, "html"))
        
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        
        return True
        
    except Exception as e:
        print(f"         ❌ Send failed: {e}")
        return False

# ----------------------------
# MAIN
# ----------------------------
def main():
    print("\n" + "="*70)
    print(f"🚀 SmartBrief Distribution")
    
    if TEST_MODE:
        print(f"🧪 TEST MODE")
    
    print(f"⏰ {datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print("="*70 + "\n")
    
    print("📊 Reading subscribers...")
    subscribers = get_subscribers_from_sheets()
    
    if not subscribers:
        print("⚠️  No active subscribers\n")
        return
    
    print(f"✅ Found {len(subscribers)} subscriber(s)\n")
    
    sent_count = 0
    skipped_count = 0
    failed_count = 0
    
    for idx, sub in enumerate(subscribers, 1):
        row_id, email, lat, lon, location, subscribed_at, last_sent = sub
        
        print(f"\n{'='*60}")
        print(f"📧 [{idx}/{len(subscribers)}] {location}")
        print(f"{'='*60}")
        
        if not TEST_MODE and not is_7am_local_time(lat, lon, last_sent):
            print(f"   ⏭️  Skipping\n")
            skipped_count += 1
            continue
        
        if TEST_MODE:
            print(f"   🧪 TEST MODE")
        
        try:
            print("   🌤️  Weather...")
            weather = fetch_weather(lat, lon, max_retries=3)
            
            if not weather:
                failed_count += 1
                time.sleep(2)
                continue
            
            print("      ✓ Done")
            time.sleep(1)
            
            print("   📰 News...")
            news = fetch_news(location)
            print(f"      ✓ {len(news)} articles")
            time.sleep(1)

            print("   💬 Quote...")
            quote = fetch_quote()
            print(f"      ✓ {quote['a']}")
            time.sleep(1)
            
            print("   ✨ Generating...")
            message = ai_message(weather, location, news, quote)
            print("      ✓ Done")
            time.sleep(2)
            
            print("   📤 Sending...")
            today_subject = datetime.now().strftime("%A, %B %d, %Y")
            subject = f"Your SmartBrief for {today_subject}"
            
            if send_email(email, subject, message):
                print("      ✓ Sent!")
                sent_count += 1
            else:
                failed_count += 1
            
            if idx < len(subscribers):
                print(f"   ⏳ Wait 3s...")
                time.sleep(3)
            
        except Exception as e:
            failed_count += 1
            print(f"   ❌ FAILED: {e}")
            time.sleep(2)
    
    print("\n" + "="*70)
    print(f"📊 Summary:")
    print(f"   ✅ Sent: {sent_count}")
    print(f"   ⏭️  Skipped: {skipped_count}")
    print(f"   ❌ Failed: {failed_count}")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()