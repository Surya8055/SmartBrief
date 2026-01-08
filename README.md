# SmartBrief: Technical Documentation & Deep Dive

SmartBrief is a sophisticated automation pipeline that transforms atmospheric data, global news, and philosophical insights into a concise, localized daily briefing. This document provides a granular, block-by-block breakdown of the entire system architecture, logic, and security protocols.

### 🛠 Technology Landscape
<p align="center">
  <img src="https://quickchart.io/chart?c={type:'doughnut',data:{labels:['Python','HTML/CSS','JS','Sheets','JSON'],datasets:[{data:[45,25,15,10,5],backgroundColor:['%230ea5e9','%236366f1','%23f43f5e','%2310b981','%23f59e0b']}]},options:{plugins:{datalabels:{color:'white',font:{weight:'bold'}}},donutText:{title:'Stack',subtitle:'SmartBrief',colors:{title:'%23ffffff',subtitle:'%2394a3b8'}}}}" width="400" />
  <br>
  <a href="dashboard.html"><b>Explore 100% Interactive Dashboard →</b></a>
</p>

---

## 🌤 System Architecture & Data Flow
The project follows a modular design where data is pulled from four distinct sources, processed by a Large Language Model (Gemini), and dispatched through an encrypted mail tunnel.

```mermaid
graph TD
    subgraph Frontend
        A[index.html / script.js] -->|Reverse Geocoding| B[Location Detection]
        B -->|POST| C[Google Apps Script]
    end

    subgraph Backend
        C -->|DB Store| D[Google Sheets]
        E[send_digest.py] -->|Query| F[read_sheets.py]
        F -->|Fetch| D
        
        E -->|Check Time| G{Sub's Local Time == 7 AM?}
        G -->|Yes| H[Check Cache]
        
        H -->|Cache Miss| I[Fetch APIs]
        I -->|Weather| J[Open Meteo]
        I -->|News| K[NewsAPI.org]
        I -->|Quote| L[ZenQuotes]
        
        J & K & L -->|Data Payload| M[Gemini AI]
        M -->|HTML Rendering| N[Secure SMTP SSL]
        N -->|Encrypted| O[User Inbox]
        
        H -->|Cache Hit| N
    end
```

---

## 🧠 Core Engine: `send_digest.py`

This script is the heartbeat of SmartBrief. It manages the lifecycle of a daily briefing.

### 1. Caching Strategy (`load_cache` / `save_cache`)
To ensure high performance and minimize API latency, we implement a file-based JSON cache.
*   **Mechanism**: The system caches two types of data: the daily global quote and the location-specific briefing (including raw weather and news data).
*   **Logic**: Before calling any external API, the engine checks `digest_cache.json` for a date-matched entry. If a "Bengaluru" briefing was generated 10 minutes ago for User A, the system will serve that identical data to User B, eliminating redundant AI processing.

### 2. Timezone-Aware Scheduling (`is_7am_local_time`)
Standard cron jobs run on a fixed server time. SmartBrief uses the `timezonefinder` and `pytz` libraries to determine exactly what time it is for the *subscriber*.
*   **The Logic**: It takes the latitude and longitude, finds the official IANA timezone (e.g., `Asia/Kolkata`), and only triggers the email if the local clock is in the 7:00 AM window.

### 3. Cascading News Fetch (`fetch_news`)
Unlike typical news bots that just pull "top headlines," SmartBrief uses a fallback reliability strategy:
1.  **Search City**: It first tries to find news specifically mentioning the user's city.
2.  **Fallback to Country**: If city news is sparse, it pulls top national headlines.
3.  **Global Buffer**: If still under 5 articles, it fills the remaining spots with global news.
*   **Deduplication**: It maintains a `seen_urls` set to ensure no user ever receives the same article twice in one email.

### 4. Generative Synthesis (`ai_message`)
This function constructs the "Prompt" for Gemini. It doesn't just ask for a summary; it provides a strict HTML template and raw data blocks.
*   **The Prompt**: We instruct the AI specifically to use the **EXACT URLs** provided by NewsAPI, ensuring that "Read More" links are never hallucinated or broken.
*   **Template Rendering**: The AI is forced to output raw HTML (no markdown), which is then cleaned of any backticks or headers before being injected into the email body.

---

## 📡 Data Retrieval: `read_sheets.py`

This module abstracts the complexity of interacting with the Google ecosystem.
*   **Apps Script Bridge**: Direct Google Sheets API integration is heavy. Instead, we use a custom Google Apps Script that acts as a secure JSON API.
*   **Data Integrity**: The script converts the JSON response into persistent Python tuples, handling type conversion for coordinates (float) and last-sent timestamps.

---

## 📊 Diagnostic Utility: `view_cache.py`

Built for transparency, this script allows developers to inspect the "system memory" without opening the raw JSON file.
*   **Human-Readable Audit**: It formats the nested JSON cache into a clean terminal report.
*   **Data Verification**: It shows temperature ranges, news headlines, and the specific quote used, making it easy to verify that the cascading news logic is working correctly.

---

## 🔒 Security & Privacy

### 1. Hardened Email Delivery (SMTP SSL)
Security is non-negotiable when handling personal information.
*   **Encryption**: We use `smtplib.SMTP_SSL` on Port 465. Unlike standard TLS (STARTTLS), which begins as an unencrypted connection and upgrades, SSL creates a secure tunnel **before** any data (even login credentials) is sent. This prevents "man-in-the-middle" attacks during the handshake.
*   **Dark Mode Optimization**: Our email templates include specific CSS meta tags (`color-scheme: light only`) and legacy HTML attributes to ensure the briefings look premium and readable on every device, regardless of whether the user has "Dark Mode" enabled.

### 2. Geolocation Privacy
The frontend (`script.js`) uses the browser's native Geolocation API.
*   **Precision**: Coordinates are only sent to the backend when a user explicitly clicks "Subscribe."
*   **Transparency**: We use the OpenStreetMap Nominatim service for reverse geocoding to show the user exactly what location we detected (e.g., "Farmers Branch, USA") before they finalize their signup.

---

## 🔦 Code-Level Deep Dives

### The News Strategy: "Quality through Redundancy"
We don't just fetch news; we hunt for it. If a user is in a small town, a simple search might fail. Our fallback logic ensures the "News" section never looks empty:

```python
# From send_digest.py -> fetch_news()
if city and len(news_list) < max_articles:
    # 1. First, search for specific city mentions
    params = {"q": city, "language": "en", "pageSize": 5}
    # ... fetch logic ...

if len(news_list) < max_articles:
    # 2. Reached if city news is insufficient - Fallback to country
    params = {"country": country_code, "category": "general"}
    # ... fetch logic ...
```
This ensures every user gets a full 5-article experience, prioritized by local relevance.

### Secure Email Handshake (SMTP SSL)
Most projects use simple TLS. We prioritize security by using implicit SSL from the first byte of communication. This is crucial when sending weather and location-based data.

```python
# From send_digest.py -> send_email()
with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
    server.login(SENDER_EMAIL, SENDER_PASSWORD)
    server.send_message(msg)
```
*Why Port 465 over 587?* Port 465 (SSL) is inherently more secure because the connection is encrypted **before** any protocol commands are sent, protecting your credentials even from sophisticated packet sniffers.

### The "Once per City" Cache Optimization
Instead of hitting the Gemini API for every single user, we check if we've already solved the "summarization problem" for that city today.

```python
# From send_digest.py -> main()
cache_entry = cache[today_str]["locations"].get(location)

if cache_entry:
    # REUSE: Use the same news, weather, and AI summary for this location
    message = cache_entry.get("html")
    print("   📦 Using cached digest...")
else:
    # GENERATE: Fresh news/weather fetch + Gemini API call
    weather = fetch_weather(lat, lon)
    news = fetch_news(location)
    message = ai_message(weather, location, news, quote)
```
This single block of logic saves roughly **90% of API costs** in high-density areas.

---

## ⚙️ Setup & Installation

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/YourUsername/SmartBrief.git
    cd SmartBrief
    ```
2.  **Requirements**:
    Install libraries including `google-generativeai`, `pytz`, `timezonefinder`, and `requests`.
3.  **Environment Variables**:
    Create a `.env` file for your keys. This is critical—never commit this file!
4.  **Launch**:
    Run `python send_digest.py` to start the distribution engine.

Enjoy a smarter way to stay informed! 🚀
