import requests
import os
from dotenv import load_dotenv
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from database import get_all_subscribers

from timezonefinder import TimezoneFinder
import pytz

# ✅ Correct Gemini SDK
from google.genai import Client

# --------------------------------------------------
# ENV
# --------------------------------------------------

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")

client = Client(api_key=GEMINI_API_KEY)

tf = TimezoneFinder()

# --------------------------------------------------
# TIME CHECK (12 PM – 2 PM LOCAL)
# --------------------------------------------------

def should_send_now(lat, lon):
    tz_name = tf.timezone_at(lat=lat, lng=lon)
    if not tz_name:
        return False

    local_tz = pytz.timezone(tz_name)
    local_time = datetime.now(pytz.utc).astimezone(local_tz)

    # ✅ 5 PM – 7 PM local time
    return 17 <= local_time.hour < 19



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
        daily["apparent_temperature_max"][0] +
        daily["apparent_temperature_min"][0]
    ) / 2

    return {
        "max": daily["temperature_2m_max"][0],
        "min": daily["temperature_2m_min"][0],
        "feels_like": round(feels_like, 1),
        "sunrise": daily["sunrise"][0].split("T")[1],
        "sunset": daily["sunset"][0].split("T")[1],
        "windspeed": current.get("windspeed"),
        "cloudcover": daily.get("cloudcover_mean", [0])[0],
        "precipitation": daily.get("precipitation_sum", [0])[0]
    }


# --------------------------------------------------
# NEWS
# --------------------------------------------------

def fetch_news(country="us", max_articles=5):
    url = (
        f"https://newsapi.org/v2/top-headlines"
        f"?country={country}&pageSize={max_articles}"
        f"&apiKey={NEWS_API_KEY}"
    )

    data = requests.get(url).json()
    articles = data.get("articles", [])

    return [
        f"{a['title']} - {a['description']}"
        for a in articles
        if a.get("title") and a.get("description")
    ]


# --------------------------------------------------
# AI CONTENT
# --------------------------------------------------

def ai_morning_message(weather, location, news_list):
    today = datetime.now().strftime("%A, %d %B %Y")
    news_text = "\n".join(news_list) if news_list else "No major news today."

    prompt = f"""
You are a calm, premium AI assistant.

Generate a CLEAN HTML EMAIL.

Use ONLY HTML tags like <p>, <b>, <ul>, <li>.

Location: {location}
Date: {today}

Weather:
Min: {weather['min']}°C
Max: {weather['max']}°C
Feels Like: {weather['feels_like']}°C
Sunrise: {weather['sunrise']}
Sunset: {weather['sunset']}

News:
{news_text}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return response.text


# --------------------------------------------------
# EMAIL
# --------------------------------------------------

def send_email(to_email, subject, html_content):
    msg = MIMEMultipart("alternative")
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject

    html = f"""
    <html>
    <body style="font-family:Arial;background:#f5f5f5;padding:20px;">
      <div style="max-width:600px;margin:auto;background:white;border-radius:10px;">
        <div style="background:#6b73ff;color:white;padding:20px;text-align:center;">
          <h1>☀️ FirstLight</h1>
          <p>Your AI Briefing</p>
        </div>
        <div style="padding:25px;">
          {html_content}
        </div>
      </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():
    print("\n🚀 FirstLight Distribution Started\n")

    subscribers = get_all_subscribers()
    print(f"📊 Subscribers found: {len(subscribers)}\n")

    for sub in subscribers:
        _, email, lat, lon, location, _ = sub

        if not should_send_now(lat, lon):
            print(f"⏭️ Skipping {email}")
            continue

        print(f"📧 Sending to {email}")

        weather = fetch_weather(lat, lon)
        news = fetch_news()

        message = ai_morning_message(weather, location, news)

        subject = f"☀️ FirstLight — {datetime.now().strftime('%A, %B %d')}"
        send_email(email, subject, message)

        print("✅ Sent\n")

    print("✅ Job complete\n")


if __name__ == "__main__":
    main()
