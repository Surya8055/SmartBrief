const API_URL = "https://script.google.com/macros/s/AKfycbzEP3ZtW0RwSuduE2PXNV18FUiNeo3B-oJyhBqs1TJsNFHbpgMR8dP0EIxMDEUlC8sm3A/exec";
const form = document.getElementById("subscribe-form");
const message = document.getElementById("message");

form.addEventListener("submit", (e) => {
  e.preventDefault();
  message.textContent = "Getting your location...";

  navigator.geolocation.getCurrentPosition(async (pos) => {
    const payload = {
      email: document.getElementById("email").value,
      latitude: pos.coords.latitude,
      longitude: pos.coords.longitude,
      location_name: "User Location"
    };

    await fetch(API_URL, {
      method: "POST",
      body: JSON.stringify(payload),
    });

    message.textContent = "✅ Subscribed successfully!";
    form.reset();
  }, () => {
    message.textContent = "❌ Location permission required.";
  });
});
