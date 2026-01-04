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
from read_sheets import get_subscribers_from_sheets

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")

# Initialize Gemini
import google.generativeai as genai
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

tf = TimezoneFinder()


# ----------------------------
# TIME CHECK: Is it 7-8 AM local?
# ----------------------------
def is_7am_local_time(lat, lon, last_sent_date):
    """
    Check if it's currently 7-8 AM in the subscriber's local timezone
    AND they haven't received an email today yet
    """
    try:
        # Get timezone for coordinates
        tz_name = tf.timezone_at(lat=lat, lng=lon)
        if not tz_name:
            print(f"      ⚠️ Could not determine timezone for {lat}, {lon}")
            return False

        # Get current time in their timezone
        local_tz = pytz.timezone(tz_name)
        utc_now = datetime.now(pytz.utc)
        local_time = utc_now.astimezone(local_tz)
        
        # Check if already sent today
        today_str = local_time.strftime("%Y-%m-%d")
        if last_sent_date == today_str:
            return False  # Already sent today
        
        # Check if current hour is 7 AM (7:00-7:59)
        is_time = local_time.hour == 10
        
        if is_time:
            print(f"      ✓ It's {local_time.strftime('%I:%M %p')} local time - TIME TO SEND!")
        
        return is_time
        
    except Exception as e:
        print(f"      ❌ Time check error: {e}")
        return False


# ----------------------------
# FETCH WEATHER
# ----------------------------
def fetch_weather(lat, lon):
    """Fetch weather data for coordinates"""
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
        response = requests.get(url, timeout=10)
        data = response.json()
        current = data.get("current_weather", {})
        daily = data.get("daily", {})

        feels_like = (
            daily.get("apparent_temperature_max", [current.get("temperature")])[0] +
            daily.get("apparent_temperature_min", [current.get("temperature")])[0]
        ) / 2

        return {
            "temp": current.get("temperature", 0),
            "windspeed": current.get("windspeed", 0),
            "winddir": current.get("winddirection", 0),
            "max": daily.get("temperature_2m_max", [0])[0],
            "min": daily.get("temperature_2m_min", [0])[0],
            "feels_like": round(feels_like, 1),
            "sunrise": daily.get("sunrise", ["06:00"])[0].split("T")[1],
            "sunset": daily.get("sunset", ["18:00"])[0].split("T")[1],
            "cloudcover": daily.get("cloudcover_mean", [0])[0],
            "precipitation": daily.get("precipitation_sum", [0])[0],
            "uv_index": daily.get("uv_index_max", [0])[0]
        }
    except Exception as e:
        print(f"      ❌ Weather failed: {e}")
        return None


# ----------------------------
# FETCH NEWS
# ----------------------------
def fetch_news(country="us", max_articles=5):
    """Fetch top news"""
    try:
        url = f"https://newsapi.org/v2/top-headlines?country={country}&pageSize={max_articles}&apiKey={NEWS_API_KEY}"
        response = requests.get(url, timeout=10)
        data = response.json()
        articles = data.get("articles", [])
        news_list = []
        for a in articles:
            if a.get("title") and a.get("description"):
                news_list.append(f"{a['title']} - {a['description']}")
        return news_list or ["No major news today."]
    except Exception as e:
        print(f"      ❌ News failed: {e}")
        return ["No news available."]


# ----------------------------
# AI MESSAGE
# ----------------------------
def ai_message(weather, location, news_list):
    """Generate AI morning message"""
    today = datetime.now().strftime("%A, %d %B %Y")
    news_text = "\n".join(news_list[:5])

    prompt = f"""
Create a friendly Good Morning email for {location} on {today}.

1. Weather Snapshot (HTML bullet points):
   - Min: {weather['min']}°C
   - Max: {weather['max']}°C
   - Feels Like: {weather['feels_like']}°C
   - Sunrise: {weather['sunrise']}
   - Sunset: {weather['sunset']}

2. Brief weather summary (2-3 lines)

3. Top News (HTML bullet points, 1-2 sentences each):
{news_text}

Use HTML tags. Keep it concise and cheerful.
"""

    try:
        print("      🤖 Generating AI content...")
        response = model.generate_content(prompt)
        print("      ✓ AI content ready")
        return response.text
    except Exception as e:
        print(f"      ⚠️ AI failed, using fallback: {e}")
        news_html = ''.join([f'<li>{n[:100]}...</li>' for n in news_list[:5]])
        return f"""
        <h2>Good Morning! ☀️</h2>
        <p>Today is {today} in {location}.</p>
        
        <h3>🌤️ Weather</h3>
        <ul>
            <li><b>Min:</b> {weather['min']}°C</li>
            <li><b>Max:</b> {weather['max']}°C</li>
            <li><b>Sunrise:</b> {weather['sunrise']}</li>
        </ul>
        
        <h3>📰 News</h3>
        <ul>{news_html}</ul>
        """


# ----------------------------
# SEND EMAIL
# ----------------------------
def send_email(to_email, subject, html_content):
    """Send email"""
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = SENDER_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject

        full_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background:#f5f5f5; padding:20px;">
          <div style="max-width:600px;margin:auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 4px 6px rgba(0,0,0,0.1);">
            <div style="background:#6b73ff;color:white;padding:25px;text-align:center;">
              <h1 style="margin:0;font-size:2rem;">☀️ SmartBrief</h1>
              <p style="margin:5px 0 0;opacity:0.9;">Your AI Morning Briefing</p>
            </div>
            <div style="padding:30px;color:#333;line-height:1.6;">
              {html_content}
            </div>
            <div style="background:#fafafa;padding:20px;text-align:center;font-size:12px;color:#888;border-top:1px solid #e0e0e0;">
              <p style="margin:0;">Powered by Google Gemini AI</p>
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
        print(f"      ❌ Email failed: {e}")
        return False


# ----------------------------
# MAIN - Check All Subscribers Every Run
# ----------------------------
def main():
    print("\n" + "="*70)
    print(f"🚀 SmartBrief Time-Based Distribution")
    print(f"⏰ UTC Time: {datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print("="*70 + "\n")
    
    # Read subscribers from Google Sheets
    print("📊 Reading subscribers from Google Sheets...")
    subscribers = get_subscribers_from_sheets()
    
    if not subscribers:
        print("⚠️  No subscribers found in Google Sheets!")
        print("💡 Make sure sheet is publicly readable\n")
        return

    print(f"✅ Found {len(subscribers)} total subscriber(s)\n")

    sent_count = 0
    skipped_count = 0
    failed_count = 0

    # Check EACH subscriber to see if it's their 7 AM
    for idx, sub in enumerate(subscribers, 1):
        row_id, email, lat, lon, location, subscribed_date, last_sent = sub
        
        print(f"[{idx}/{len(subscribers)}] Checking: {email} ({location})")
        
        # Get their current local time
        try:
            tz_name = tf.timezone_at(lat=lat, lng=lon)
            if tz_name:
                local_tz = pytz.timezone(tz_name)
                local_time = datetime.now(pytz.utc).astimezone(local_tz)
                print(f"   🕐 Local time: {local_time.strftime('%I:%M %p %Z')}")
            else:
                print(f"   ⚠️ Could not determine timezone")
                skipped_count += 1
                continue
        except Exception as e:
            print(f"   ❌ Error: {e}")
            skipped_count += 1
            continue
        
        # Check if it's 7-8 AM their time AND they haven't received today's email
        if not is_7am_local_time(lat, lon, last_sent):
            print(f"   ⏭️  Skipping - not 7 AM local or already sent today\n")
            skipped_count += 1
            continue
        
        # IT'S THEIR 7 AM! Send the email
        print(f"   🎯 TIME TO SEND! It's 7 AM in {location}")
        
        try:
            # Fetch weather
            print("   🌤️  Fetching weather...")
            weather = fetch_weather(lat, lon)
            if not weather:
                raise Exception("Weather fetch failed")
            print("      ✓ Weather data received")
            time.sleep(1)
            
            # Fetch news
            print("   📰 Fetching news...")
            news = fetch_news("us")
            print(f"      ✓ {len(news)} articles fetched")
            time.sleep(1)
            
            # Generate AI message
            print("   🤖 Generating AI digest...")
            message = ai_message(weather, location, news)
            print("      ✓ Digest generated")
            time.sleep(2)
            
            # Send email
            print("   📤 Sending email...")
            today = datetime.now().strftime("%A, %B %d, %Y")
            subject = f"☀️ SmartBrief Morning - {today}"
            
            if send_email(email, subject, message):
                print("      ✓ Email sent successfully!")
                sent_count += 1
                
                # TODO: Update Google Sheets with last_sent_date
                # For now, we rely on date checking to prevent duplicates
                
            else:
                failed_count += 1
            
            print(f"   ✅ SUCCESS for {email}\n")
            
            # Wait before next subscriber
            if idx < len(subscribers):
                time.sleep(3)
            
        except Exception as e:
            failed_count += 1
            print(f"   ❌ FAILED: {e}\n")
            time.sleep(2)

    print("\n" + "="*70)
    print(f"📊 Distribution Summary:")
    print(f"   ✅ Sent: {sent_count}")
    print(f"   ⏭️  Skipped: {skipped_count} (not their 7 AM yet)")
    print(f"   ❌ Failed: {failed_count}")
    print(f"   📧 Total checked: {len(subscribers)}")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()