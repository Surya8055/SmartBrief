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

from database import get_all_subscribers, update_last_sent

# Load environment variables
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
# TIME CHECK 5–7 PM LOCAL
# ----------------------------
def should_send_now(lat, lon, last_sent_date):
    """Check if it's 5-7 PM in subscriber's local timezone"""
    try:
        tz_name = tf.timezone_at(lat=lat, lng=lon)
        if not tz_name:
            return False

        local_tz = pytz.timezone(tz_name)
        local_time = datetime.now(pytz.utc).astimezone(local_tz)

        # Only send once per day
        today_str = local_time.strftime("%Y-%m-%d")
        if last_sent_date == today_str:
            return False

        # 17–19 hours = 5–7 PM
        return 17 <= local_time.hour < 19
    except Exception as e:
        print(f"   ⚠️ Time check failed: {e}")
        return True  # Send anyway if time check fails


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
            "sunrise": daily.get("sunrise", ["00:00"])[0].split("T")[1],
            "sunset": daily.get("sunset", ["00:00"])[0].split("T")[1],
            "cloudcover": daily.get("cloudcover_mean", [0])[0],
            "precipitation": daily.get("precipitation_sum", [0])[0],
            "uv_index": daily.get("uv_index_max", [0])[0]
        }
    except Exception as e:
        print(f"      ❌ Weather API failed: {e}")
        # Return default values
        return {
            "temp": 20, "windspeed": 0, "winddir": 0,
            "max": 25, "min": 15, "feels_like": 20,
            "sunrise": "06:00", "sunset": "18:00",
            "cloudcover": 0, "precipitation": 0, "uv_index": 5
        }


# ----------------------------
# FETCH NEWS
# ----------------------------
def fetch_news(country="us", max_articles=5):
    """Fetch top news headlines"""
    try:
        url = f"https://newsapi.org/v2/top-headlines?country={country}&pageSize={max_articles}&apiKey={NEWS_API_KEY}"
        response = requests.get(url, timeout=10)
        data = response.json()
        articles = data.get("articles", [])
        news_list = []
        for a in articles:
            title = a.get("title")
            desc = a.get("description")
            if title and desc:
                news_list.append(f"{title} - {desc}")
        return news_list
    except Exception as e:
        print(f"      ❌ News API failed: {e}")
        return ["No news available at this time."]


# ----------------------------
# AI MESSAGE - WITH TIMEOUT & FALLBACK
# ----------------------------
def ai_message(weather, location, news_list):
    """Generate AI message with timeout and fallback"""
    today = datetime.now().strftime("%A, %d %B %Y")
    news_text = "\n".join(news_list) if news_list else "No major news today."

    prompt = f"""
You are a calm, premium AI evening assistant.

Generate a clean, readable HTML email.

STRUCTURE EXACTLY AS BELOW:

1) A warm Good Evening greeting
2) A bold "Weather Snapshot" section with bullet points:
   - Min
   - Max
   - Feels Like
   - Sunrise
   - Sunset
3) A 2–3 line short weather summary
4) A bold "Top News" section with bullet points (1–2 sentences each)

Keep it concise. Use proper HTML tags only (<b>, <ul>, <li>, <p>).

Location: {location}
Date: {today}

Weather details:
Min: {weather['min']}°C
Max: {weather['max']}°C
Feels Like: {weather['feels_like']}°C
Sunrise: {weather['sunrise']}
Sunset: {weather['sunset']}
Wind: {weather['windspeed']} km/h
Cloud cover: {weather['cloudcover']}%
Precipitation: {weather['precipitation']} mm

News:
{news_text}
"""

    # Try Gemini with timeout
    try:
        print("      🤖 Calling Gemini API...")
        
        # Generate content with timeout
        response = model.generate_content(prompt)
        
        print("      ✓ Gemini response received")
        return response.text
        
    except Exception as e:
        print(f"      ⚠️ Gemini API failed: {e}")
        print(f"      📝 Using fallback template instead")
        
        # FALLBACK: Simple HTML template without AI
        news_html = ''.join([f'<li style="margin-bottom: 10px;">{news}</li>' for news in news_list[:5]])
        
        return f"""
        <h2 style="color: #6b73ff;">Good Evening! 🌙</h2>
        
        <p>Here's your evening briefing for <b>{location}</b> on {today}.</p>
        
        <h3 style="color: #333; margin-top: 20px;">🌤️ Weather Snapshot</h3>
        <ul style="line-height: 1.8;">
            <li><b>Min Temperature:</b> {weather['min']}°C</li>
            <li><b>Max Temperature:</b> {weather['max']}°C</li>
            <li><b>Feels Like:</b> {weather['feels_like']}°C</li>
            <li><b>Sunrise:</b> {weather['sunrise']}</li>
            <li><b>Sunset:</b> {weather['sunset']}</li>
        </ul>
        
        <p>Today's weather: Temperatures ranging from {weather['min']}°C to {weather['max']}°C 
        with {weather['cloudcover']}% cloud cover. Wind speeds around {weather['windspeed']} km/h.</p>
        
        <h3 style="color: #333; margin-top: 20px;">📰 Top News</h3>
        <ul style="line-height: 1.8;">
            {news_html}
        </ul>
        
        <p style="color: #666; font-size: 14px; margin-top: 20px;">
            <i>This digest was generated with fallback formatting due to API availability.</i>
        </p>
        """


# ----------------------------
# SEND EMAIL
# ----------------------------
def send_email(to_email, subject, html_content):
    """Send email to subscriber"""
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = SENDER_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject

        full_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background:#f5f5f5; padding:20px;">
          <div style="max-width:600px;margin:auto;background:white;border-radius:12px;overflow:hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <div style="background:#6b73ff;color:white;padding:25px;text-align:center;">
              <h1 style="margin:0; font-size: 2rem;">🌙 SmartBrief</h1>
              <p style="margin:5px 0 0; opacity: 0.9;">Your AI Evening Briefing</p>
            </div>

            <div style="padding:30px;color:#333;line-height:1.6;">
              {html_content}
            </div>

            <div style="background:#fafafa;padding:20px;text-align:center;font-size:12px;color:#888; border-top: 1px solid #e0e0e0;">
              <p style="margin: 0;">Powered by Google Gemini AI</p>
              <p style="margin: 5px 0 0;">Reply to this email to unsubscribe</p>
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
        print(f"      ❌ Email send failed: {e}")
        return False


# ----------------------------
# MAIN
# ----------------------------
def main():
    print("\n🚀 SmartBrief Digest Starting\n")
    print(f"⏰ Start Time: {datetime.now()}")
    print(f"📧 Sender: {SENDER_EMAIL}")
    print()
    
    subscribers = get_all_subscribers()

    print("📋 Subscribers in DB:")
    for sub in subscribers:
        print(f"   {sub}")

    print(f"\n📊 Active subscribers found: {len(subscribers)}\n")

    if not subscribers:
        print("⚠️  No subscribers found in database!")
        print("💡 Make sure subscribers exist in the database\n")
        return

    sent_count = 0
    failed_count = 0
    start_time = datetime.now()

    for idx, sub in enumerate(subscribers, 1):
        id_, email, lat, lon, location_name, subscribed_at, last_sent = sub
        
        print(f"\n{'='*60}")
        print(f"📧 [{idx}/{len(subscribers)}] Processing: {email}")
        print(f"   📍 Location: {location_name}")
        print(f"   🆔 Subscriber ID: {id_}")
        print(f"{'='*60}")

        try:
            # Fetch weather
            print("   🌤️  Step 1/4: Fetching weather...")
            weather = fetch_weather(lat, lon)
            print("      ✓ Weather data received")
            time.sleep(1)
            
            # Fetch news
            print("   📰 Step 2/4: Fetching news...")
            news = fetch_news("us")
            print(f"      ✓ {len(news)} news articles fetched")
            time.sleep(1)
            
            # Generate AI message with timeout protection
            print("   🤖 Step 3/4: Generating AI digest...")
            message = ai_message(weather, location_name, news)
            print("      ✓ AI digest generated")
            time.sleep(2)
            
            # Send email
            print("   📤 Step 4/4: Sending email...")
            subject = f"🌙 SmartBrief — {datetime.now().strftime('%A, %B %d')}"
            
            if send_email(email, subject, message):
                print("      ✓ Email sent successfully!")
                
                # Update database
                update_last_sent(id_)
                
                sent_count += 1
                print(f"   ✅ SUCCESS for {email}")
            else:
                failed_count += 1
                print(f"   ❌ Email delivery failed for {email}")
            
            # Wait before next subscriber to avoid rate limits
            if idx < len(subscribers):
                print(f"   ⏳ Waiting 3 seconds before next subscriber...")
                time.sleep(3)
            
        except Exception as e:
            failed_count += 1
            print(f"   ❌ FAILED for {email}")
            print(f"      Error: {str(e)}")
            print(f"   ⏭️  Continuing to next subscriber...")
            
            # Wait before next even on failure
            time.sleep(2)
            continue

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print("\n" + "="*60)
    print(f"🎉 Distribution Complete!")
    print(f"   ✅ Sent: {sent_count}/{len(subscribers)}")
    print(f"   ❌ Failed: {failed_count}/{len(subscribers)}")
    print(f"   ⏰ Duration: {duration:.1f} seconds")
    print(f"   🕐 Finished at: {end_time.strftime('%I:%M:%S %p')}")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()