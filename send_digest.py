import os
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import pytz
from timezonefinder import TimezoneFinder
from dotenv import load_dotenv

from database import get_all_subscribers

# Load environment variables
load_dotenv()

# ----------------------------
# Gemini / Google Generative AI
# ----------------------------
import google.generativeai as genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

# ----------------------------
# Email config
# ----------------------------
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")

# ----------------------------
# Timezone finder
# ----------------------------
tf = TimezoneFinder()

# ----------------------------
# Check if we should send email now (5–7 PM CST)
# ----------------------------
def should_send_now(lat, lon):
    tz_name = tf.timezone_at(lat=lat, lng=lon)
    if not tz_name:
        return False
    local_tz = pytz.timezone(tz_name)
    local_time = datetime.now(pytz.utc).astimezone(local_tz)
    # Send between 5 PM and 6:59 PM local
    return 17 <= local_time.hour < 19

# ----------------------------
# Weather fetch
# ----------------------------
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

# ----------------------------
# News fetch
# ----------------------------
def fetch_news(country="us", max_articles=5):
    NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
    url = (
        f"https://newsapi.org/v2/top-headlines"
        f"?country={country}&pageSize={max_articles}"
        f"&apiKey={NEWS_API_KEY}"
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

# ----------------------------
# AI email content
# ----------------------------
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

    response = client.generate_text(
        model="text-bison-001",  # latest text model
        prompt=prompt,
        temperature=0.5
    )
    return response.result

# ----------------------------
# Send email
# ----------------------------
def send_email(to_email, subject, html_content):
    msg = MIMEMultipart("alternative")
    msg["From"] = SENDER_EMAIL
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
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())

# ----------------------------
# MAIN
# ----------------------------
def main():
    print("\n🚀 FirstLight Distribution Started\n")
    subscribers = get_all_subscribers()
    print(f"📊 Subscribers found: {len(subscribers)}\n")

    for sub in subscribers:
        id_, email, lat, lon, location_name, subscribed_at = sub
        if not should_send_now(lat, lon):
            print(f"⏭️  Skipping {email} (not 5–7 PM local)")
            continue
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
