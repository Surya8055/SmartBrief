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

# Gemini AI (or fallback)
import google.generativeai as genai
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

tf = TimezoneFinder()


# ----------------------------
# TIME CHECK 7–8 AM LOCAL
# ----------------------------
def should_send_now(lat, lon, last_sent_date):
    """Check if it's 7-8 AM in subscriber's local timezone"""
    try:
        tz_name = tf.timezone_at(lat=lat, lng=lon)
        if not tz_name:
            print("⚠️ Timezone not found, skipping")
            return False

        local_tz = pytz.timezone(tz_name)
        local_time = datetime.now(pytz.utc).astimezone(local_tz)
        today_str = local_time.strftime("%Y-%m-%d")

        # Only send once per day
        if last_sent_date == today_str:
            return False

        # Check if local time is between 7:00 and 7:59
        if local_time.hour == 7:
            return True
        return False

    except Exception as e:
        print(f"⚠️ Time check failed: {e}")
        return False  # Do NOT send if time check fails



# ----------------------------
# FETCH WEATHER
# ----------------------------
def fetch_weather(lat, lon):
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
        print(f"❌ Weather API failed: {e}")
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
    try:
        url = f"https://newsapi.org/v2/top-headlines?country={country}&pageSize={max_articles}&apiKey={NEWS_API_KEY}"
        response = requests.get(url, timeout=10)
        data = response.json()
        articles = data.get("articles", [])
        news_list = [f"{a['title']} - {a['description']}" for a in articles if a.get("title") and a.get("description")]
        return news_list or ["No news available at this time."]
    except Exception as e:
        print(f"❌ News API failed: {e}")
        return ["No news available at this time."]


# ----------------------------
# SEND EMAIL
# ----------------------------
def send_email(to_email, subject, html_content):
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = SENDER_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        
        return True
    except Exception as e:
        print(f"❌ Email send failed: {e}")
        return False


# ----------------------------
# MAIN
# ----------------------------
def main():
    print("🚀 SmartBrief Digest Starting...\n")
    subscribers = get_all_subscribers()
    print(f"📊 Found {len(subscribers)} subscribers")

    if not subscribers:
        print("⚠️ No subscribers found")
        return

    for sub in subscribers:
        id_, email, lat, lon, location_name, _, last_sent = sub

        if not should_send_now(lat, lon, last_sent):
            continue

        weather = fetch_weather(lat, lon)
        news = fetch_news("us")

        html_content = f"<h2>Good Morning {location_name}!</h2>" \
                       f"<p>Temp: {weather['temp']}°C, Max: {weather['max']}°C, Min: {weather['min']}°C</p>" \
                       f"<h3>Top News:</h3><ul>" + "".join([f"<li>{n}</li>" for n in news]) + "</ul>"

        subject = f"🌞 SmartBrief Morning — {datetime.now().strftime('%A, %B %d')}"
        if send_email(email, subject, html_content):
            print(f"✅ Email sent to {email}")
            update_last_sent(id_)
        else:
            print(f"❌ Failed to send to {email}")
        time.sleep(2)

    print("🎉 All done!")


if __name__ == "__main__":
    main()
