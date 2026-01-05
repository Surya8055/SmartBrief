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
from read_sheets import get_subscribers_from_sheets

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
# TIME CHECK: Is it 7-8 AM local?
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
        
        # Only send once per day
        if last_sent_date == today_str:
            return False
        
        # Check if 7-8 AM (hour == 7)
        return local_time.hour == 7
        
    except Exception as e:
        print(f"      ⚠️ Time check error: {e}")
        return False


# ----------------------------
# FETCH WEATHER WITH RETRY
# ----------------------------
def fetch_weather(lat, lon, max_retries=3):
    """Fetch weather with retry logic - returns None if all retries fail"""
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
                print(f"         ⏳ Retry attempt {attempt}/{max_retries-1}...")
            
            response = requests.get(url, timeout=15)
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
            if attempt < max_retries - 1:
                print(f"         ⚠️ Attempt {attempt+1} failed: {str(e)[:50]}...")
                time.sleep(2)
                continue
            else:
                print(f"         ❌ All {max_retries} attempts failed")
                return None
    
    return None


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
            if a.get("title") and a.get("description"):
                news_list.append(f"{a['title']} - {a['description']}")
        return news_list or ["No major news today."]
    except Exception as e:
        print(f"         ⚠️ News API failed: {e}")
        return ["No news available at this time."]


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
        print("         🤖 Generating AI content...")
        response = model.generate_content(prompt)
        print("         ✓ AI content ready")
        return response.text
    except Exception as e:
        print(f"         ⚠️ AI generation failed: {e}")
        news_html = ''.join([f'<li>{n[:150]}...</li>' for n in news_list[:5]])
        return f"""
        <h2>Good Morning! ☀️</h2>
        <p>Here's your briefing for <b>{location}</b> on {today}.</p>
        
        <h3>🌤️ Weather</h3>
        <ul>
            <li><b>Min:</b> {weather['min']}°C</li>
            <li><b>Max:</b> {weather['max']}°C</li>
            <li><b>Feels Like:</b> {weather['feels_like']}°C</li>
            <li><b>Sunrise:</b> {weather['sunrise']}</li>
            <li><b>Sunset:</b> {weather['sunset']}</li>
        </ul>
        
        <h3>📰 Top News</h3>
        <ul>{news_html}</ul>
        """


# ----------------------------
# SEND EMAIL WITH UNSUBSCRIBE LINK
# ----------------------------
def send_email(to_email, subject, html_content):
    """Send email to subscriber with personalized unsubscribe link"""
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = SENDER_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject

        # Personalized unsubscribe link with email pre-filled
        from urllib.parse import quote
        unsubscribe_url = f"https://surya8055.github.io/SmartBrief/unsubscribe.html?email={quote(to_email)}"

        full_html = f"""
        <html>
        <body style="font-family: 'Segoe UI', Arial, sans-serif; background:#f8fafc; padding:20px;">
          <div style="max-width:600px;margin:auto;background:white;border-radius:16px;overflow:hidden;box-shadow:0 4px 6px rgba(0,0,0,0.05);border:1px solid #e2e8f0;">
            
            <!-- Header -->
            <div style="background:linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);color:white;padding:30px;text-align:center;">
              <h1 style="margin:0;font-size:2.2rem;font-weight:600;">☀️ SmartBrief</h1>
              <p style="margin:8px 0 0;opacity:0.95;font-size:1rem;">Your AI Morning Briefing</p>
            </div>
            
            <!-- Content -->
            <div style="padding:35px;color:#1e293b;line-height:1.7;">
              {html_content}
            </div>
            
            <!-- Footer with Unsubscribe -->
            <div style="background:#f8fafc;padding:25px;text-align:center;border-top:1px solid #e2e8f0;">
              <p style="margin:0;color:#64748b;font-size:13px;font-weight:500;">
                Powered by Google Gemini AI
              </p>
              
              <div style="margin-top:18px;padding-top:18px;border-top:1px solid #e2e8f0;">
                <p style="margin:0;color:#94a3b8;font-size:12px;line-height:1.6;">
                  Not interested anymore? 
                  <a href="{unsubscribe_url}" 
                     style="color:#3b82f6;text-decoration:none;font-weight:600;">
                    Click here to unsubscribe
                  </a>
                </p>
              </div>
              
              <p style="margin:12px 0 0;color:#cbd5e1;font-size:11px;">
                You're receiving this because you subscribed to SmartBrief at {to_email}
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
        print(f"         ❌ Email send failed: {e}")
        return False


# ----------------------------
# MAIN
# ----------------------------
def main():
    print("\n" + "="*70)
    print(f"🚀 SmartBrief Time-Based Distribution")
    
    if TEST_MODE:
        print(f"🧪 TEST MODE ENABLED - Sending to all active subscribers NOW")
    
    print(f"⏰ UTC Time: {datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print("="*70 + "\n")
    
    # Read from Google Sheets
    print("📊 Reading active subscribers from Google Sheets...")
    subscribers = get_subscribers_from_sheets()
    
    if not subscribers:
        print("⚠️  No active subscribers found!")
        print("💡 Make sure subscribers have is_active = TRUE in Google Sheets\n")
        return

    print(f"✅ Found {len(subscribers)} ACTIVE subscriber(s)\n")

    sent_count = 0
    skipped_count = 0
    failed_count = 0

    for idx, sub in enumerate(subscribers, 1):
        row_id, email, lat, lon, location, subscribed_at, last_sent = sub
        
        print(f"\n{'='*60}")
        # print(f"📧 [{idx}/{len(subscribers)}] {email}")
        print(f"   📍 {location}")
        print(f"{'='*60}")

        # Skip time check if in test mode
        if not TEST_MODE and not is_7am_local_time(lat, lon, last_sent):
            print(f"   ⏭️  Skipping - not 7 AM local or already sent today\n")
            skipped_count += 1
            continue
        
        if TEST_MODE:
            print(f"   🧪 TEST MODE - Sending immediately (bypassing time check)")

        try:
            # Fetch weather - REQUIRED (with retries)
            print("   🌤️  Step 1/4: Fetching weather...")
            weather = fetch_weather(lat, lon, max_retries=3)
            
            if not weather:
                print("      ❌ Weather fetch failed after retries - skipping subscriber")
                failed_count += 1
                time.sleep(2)
                continue
            
            print("      ✓ Weather data received")
            time.sleep(1)
            
            # Fetch news
            print("   📰 Step 2/4: Fetching news...")
            news = fetch_news("us")
            print(f"      ✓ {len(news)} articles fetched")
            time.sleep(1)
            
            # Generate AI message
            print("   🤖 Step 3/4: Generating AI digest...")
            message = ai_message(weather, location, news)
            print("      ✓ Digest generated")
            time.sleep(2)
            
            # Send email
            print("   📤 Step 4/4: Sending email...")
            today = datetime.now().strftime("%A, %B %d, %Y")
            subject = f"☀️ SmartBrief Morning - {today}"
            
            if send_email(email, subject, message):
                print("      ✓ Email sent successfully!")
                sent_count += 1
                # print(f"   ✅ SUCCESS for {email}")
            else:
                failed_count += 1
                # print(f"   ❌ Email delivery failed")
            
            # Wait before next subscriber
            if idx < len(subscribers):
                print(f"   ⏳ Waiting 3 seconds...")
                time.sleep(3)
            
        except Exception as e:
            failed_count += 1
            print(f"   ❌ FAILED: {e}")
            time.sleep(2)
            continue

    print("\n" + "="*70)
    print(f"📊 Distribution Summary:")
    print(f"   ✅ Sent: {sent_count}")
    print(f"   ⏭️  Skipped: {skipped_count}")
    print(f"   ❌ Failed: {failed_count}")
    print(f"   📧 Total: {len(subscribers)}")
    
    if TEST_MODE:
        print(f"\n🧪 TEST MODE was enabled - emails sent immediately")
    
    print("="*70 + "\n")


if __name__ == "__main__":
    main()