import requests
import os
from dotenv import load_dotenv
import google.generativeai as genai
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import random
import time

from database import get_all_subscribers

# ⏰ Timezone handling
from timezonefinder import TimezoneFinder
import pytz

# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("models/gemini-2.5-flash")

tf = TimezoneFinder()

# --------------------------------------------------
# TIME CHECK (12–1 PM CST)
# --------------------------------------------------
def should_send_now(lat, lon):
    """
    Returns True if current local time (based on lat/lon)
    is between 12:00–12:59 PM CST
    """
    tz_name = tf.timezone_at(lat=lat, lng=lon)
    if not tz_name:
        return False

    local_tz = pytz.timezone(tz_name)
    local_time = datetime.now(pytz.utc).astimezone(local_tz)

    # Convert to CST
    cst_time = local_time.astimezone(pytz.timezone("US/Central"))
    return 12 <= cst_time.hour < 13

# --------------------------------------------------
# WEATHER
# --------------------------------------------------
def fetch_weather(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current_weather=true"
        "&daily=temperature_2m_max,temperature_2m_min,"
        "apparent_temperature_max,apparent_temperature_min,"
        "sunrise,sunset,precipitation_sum,uv_index_max,cloudcover_mean"
        "&timezone=auto"
    )

    data = requests.get(url).json()
    current = data.get("current_weather", {})
    daily = data.get("daily", {})

    feels_like = (
        daily.get("apparent_temperature_max", [current.get("temperature")])[0] +
        daily.get("apparent_temperature_min", [current.get("temperature")])[0]
    ) / 2

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

# --------------------------------------------------
# NEWS
# --------------------------------------------------
def fetch_news(country="us", max_articles=5):
    url = (
        f"https://newsapi.org/v2/top-headlines"
        f"?country={country}&pageSize={max_articles}"
        f"&apiKey={os.environ['NEWS_API_KEY']}"
    )

    data = requests.get(url).json()
    articles = data.get("articles", [])

    news_list = []
    for article in articles:
        title = article.get("title")
        desc = article.get("description")
        if title and desc:
            news_list.append(f"{title} - {desc}")

    return news_list

# --------------------------------------------------
# AI MESSAGE
# --------------------------------------------------
def ai_morning_message(weather, location, news_list):
    today = datetime.now().strftime("%A, %d %B %Y")
    news_text = "\n".join(news_list) if news_list else "No major news today."

    prompt = f"""
You are a calm, premium AI morning assistant.

Generate a clean, readable HTML email.

STRUCTURE EXACTLY AS BELOW:

1) A warm Good Morning greeting
2) A bold "Weather Snapshot" section with bullet points:
   - Min
   - Max
   - Feels Like
   - Sunrise
   - Sunset
3) A 2–3 line short weather summary
4) A bold "Top News" section with bullet points (1–2 sentences each)

Keep spacing clean. Do NOT use markdown symbols like ** or ###.
Use proper HTML tags only (<b>, <ul>, <li>, <p>).

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

    response = model.generate_content(prompt)
    return response.text

# --------------------------------------------------
# EMAIL
# --------------------------------------------------
def send_email(to_email, subject, html_content):
    EMAIL = os.environ["SENDER_EMAIL"]
    PASSWORD = os.environ["SENDER_PASSWORD"]

    msg = MIMEMultipart("alternative")
    msg["From"] = EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject

    full_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background:#f5f5f5; padding:20px;">
      <div style="max-width:600px;margin:auto;background:white;border-radius:12px;overflow:hidden;">
        <div style="background:#6b73ff;color:white;padding:20px;text-align:center;">
          <h1 style="margin:0;">☀️ FirstLight</h1>
          <p style="margin:5px 0 0;">Your AI Morning Briefing</p>
        </div>

        <div style="padding:25px;color:#333;line-height:1.6;">
          {html_content}
        </div>

        <div style="background:#fafafa;padding:15px;text-align:center;font-size:12px;color:#888;">
          Powered by Gemini AI
        </div>
      </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(full_html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL, PASSWORD)
        server.sendmail(EMAIL, to_email, msg.as_string())

# --------------------------------------------------
# MAIN
# --------------------------------------------------
def main():
    print("\n🚀 FirstLight Distribution Started\n")

    subscribers = get_all_subscribers()
    print(f"📊 Subscribers found: {len(subscribers)}\n")

    for sub in subscribers:
        id_, email, lat, lon, location_name, subscribed_at = sub

        if not should_send_now(lat, lon):
            print(f"⏭️ Skipping {email} (outside 12–1 PM CST)")
            continue

        # Random delay between 0–3600 seconds (spread within the 12–1 PM window)
        delay = random.randint(0, 3600)
        print(f"⏳ Delaying email to {email} by {delay} seconds")
        time.sleep(delay)

        print(f"📧 Sending to {email} ({location_name})")
        weather = fetch_weather(lat, lon)
        news = fetch_news("us")
        message = ai_morning_message(weather, location_name, news)
        subject = f"☀️ FirstLight — {datetime.now().strftime('%A, %B %d')}"
        send_email(email, subject, message)
        print("   ✅ Sent\n")

    print("✅ FirstLight run complete\n")

if __name__ == "__main__":
    main()
