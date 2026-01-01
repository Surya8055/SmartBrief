import requests
import os
from dotenv import load_dotenv
import google.generativeai as genai
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from database import get_all_subscribers

# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("models/gemini-2.5-flash")

# ---- WEATHER ----

def fetch_weather(lat, lon):
    """Fetch weather for specific coordinates"""
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current_weather=true"
        "&daily=temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,sunrise,sunset,precipitation_sum,uv_index_max,cloudcover_mean"
        "&timezone=auto"
    )
    data = requests.get(url).json()
    current = data.get("current_weather", {})
    daily = data.get("daily", {})

    feels_like = (daily.get("apparent_temperature_max", [current.get("temperature")])[0] +
                  daily.get("apparent_temperature_min", [current.get("temperature")])[0]) / 2

    return {
        "temp": current.get("temperature"),
        "windspeed": current.get("windspeed"),
        "winddir": current.get("winddirection"),
        "max": daily["temperature_2m_max"][0],
        "min": daily["temperature_2m_min"][0],
        "feels_like": round(feels_like, 1),
        "sunrise": daily["sunrise"][0].split("T")[1],
        "sunset": daily["sunset"][0].split("T")[1],
        "cloudcover": daily.get("cloudcover_mean", [0])[0],
        "precipitation": daily.get("precipitation_sum", [0])[0],
        "uv_index": daily.get("uv_index_max", [0])[0]
    }

# ---- NEWS ----

def fetch_news(country="us", max_articles=5):
    """Fetch top news"""
    url = f"https://newsapi.org/v2/top-headlines?country={country}&pageSize={max_articles}&apiKey={os.environ['NEWS_API_KEY']}"
    data = requests.get(url).json()
    articles = data.get("articles", [])
    news_list = []
    for article in articles:
        title = article.get("title")
        desc = article.get("description")
        if title and desc:
            news_list.append(f"{title} - {desc}")
    return news_list

# ---- AI MESSAGE ----

def ai_morning_message(weather, location, news_list):
    """Generate AI morning message"""
    today = datetime.now().strftime("%A, %d %B %Y")
    news_text = "\n".join(news_list) if news_list else "No major news today."
    
    prompt = f"""
You are a friendly AI morning assistant.

Create a **short, cheerful Good Morning message** for {location} for {today}.

1. Start with a **weather snapshot** section as bullet points:
- Min
- Max
- Feels Like
- Sunrise
- Sunset

2. Then give a 2–3 line summary of today's weather including highs, lows, wind, cloud cover, precipitation, sunrise/sunset.

3. Include top news headlines from the list below in bullet points, 1–2 sentences each.

Weather details:
Current: {weather['temp']}°C, Wind: {weather['windspeed']} km/h from {weather['winddir']}°, Cloud cover: {weather['cloudcover']}%, Precipitation: {weather['precipitation']} mm, UV index: {weather['uv_index']}

News to summarize:
{news_text}

Format the message with proper line breaks, bullets, and bolds. Use HTML formatting so it looks readable in an email.
"""
    response = model.generate_content(prompt)
    return response.text

# ---- EMAIL ----

def send_email(to_email, subject, html_content):
    """Send email to a subscriber"""
    try:
        EMAIL = os.environ["SENDER_EMAIL"]
        PASSWORD = os.environ["SENDER_PASSWORD"]

        msg = MIMEMultipart("alternative")
        msg["From"] = EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject

        # Wrap in nice template
        full_html = f"""
        <html>
            <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #f5f5f5; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 15px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.1);">
                    
                    <!-- Header -->
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                        <h1 style="color: white; margin: 0; font-size: 2.5rem;">☀️ FirstLight</h1>
                        <p style="color: #f0f0f0; margin: 5px 0 0 0;">Your AI Morning Briefing</p>
                    </div>
                    
                    <!-- Content -->
                    <div style="padding: 30px; line-height: 1.6; color: #333;">
                        {html_content}
                    </div>
                    
                    <!-- Footer -->
                    <div style="background: #f9f9f9; padding: 20px; text-align: center; border-top: 1px solid #e0e0e0;">
                        <p style="margin: 0; color: #999; font-size: 12px;">
                            Powered by Google Gemini AI<br>
                            <a href="#" style="color: #667eea; text-decoration: none;">Manage Subscription</a>
                        </p>
                    </div>
                    
                </div>
            </body>
        </html>
        """

        msg.attach(MIMEText(full_html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL, PASSWORD)
            server.sendmail(EMAIL, to_email, msg.as_string())
        
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

# ---- MAIN ----

def main():
    """Send digest to all subscribers"""
    print("\n🚀 Starting FirstLight Digest Distribution...\n")
    print("="*60)
    
    # Get all subscribers
    subscribers = get_all_subscribers()
    print(f"📊 Found {len(subscribers)} active subscriber(s)\n")
    
    if not subscribers:
        print("⚠️  No subscribers found!")
        print("💡 Go to http://localhost:5000 and subscribe first\n")
        return
    
    # Send to each subscriber
    success_count = 0
    fail_count = 0
    
    for sub in subscribers:
        id_, email, lat, lon, location_name, subscribed_at = sub
        
        try:
            print(f"📧 Processing: {email}")
            print(f"   📍 Location: {location_name}")
            
            # Fetch weather for their location
            weather = fetch_weather(lat, lon)
            
            # Fetch news (customize by location later)
            news = fetch_news("us")
            
            # Generate personalized message
            message = ai_morning_message(weather, location_name, news)
            
            # Send email
            today = datetime.now().strftime("%A, %B %d, %Y")
            subject = f"☀️ FirstLight Briefing - {today}"
            
            if send_email(email, subject, message):
                print(f"   ✅ Sent successfully!\n")
                success_count += 1
            else:
                fail_count += 1
                
        except Exception as e:
            print(f"   ❌ Error: {e}\n")
            fail_count += 1
    
    print("="*60)
    print(f"📊 Distribution Complete!")
    print(f"   ✅ Success: {success_count}")
    print(f"   ❌ Failed: {fail_count}")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()