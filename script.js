const BACKEND_URL = 'https://script.google.com/macros/s/AKfycbzVOQldUHHDhvtA0wk_6ZPF85I-e6OxfwObHPbjVhyNQzTIaulYT0BLwmcMEpErh-ueGQ/exec';

const subscribeForm = document.getElementById('subscribeForm');
const unsubscribeForm = document.getElementById('unsubscribeForm');
const emailInput = document.getElementById('emailInput');
const messageDiv = document.getElementById('message');
const locationInfo = document.getElementById('locationInfo');

/* ---------- SUBSCRIBE ---------- */
if (subscribeForm) {
  subscribeForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = emailInput.value.trim();
    
    if (!email) {
      showMessage('Please enter your email', 'error');
      return;
    }

    if (!navigator.geolocation) {
      showMessage('Geolocation not supported', 'error');
      return;
    }

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = pos.coords.latitude;
        const lon = pos.coords.longitude;
        
        // Get location name
        const locationName = await getLocationName(lat, lon);
        
        if (locationInfo) {
          locationInfo.textContent = `📍 ${locationName}`;
        }

        await fetch(BACKEND_URL, {
          method: 'POST',
          mode: 'no-cors',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            action: 'subscribe',
            email: email,
            latitude: lat,
            longitude: lon,
            location_name: locationName
          })
        });

        showMessage('🎉 Subscribed! You'll receive SmartBrief at 7 AM your local time.', 'success');
        emailInput.value = '';
      },
      (error) => {
        showMessage('Please allow location access to subscribe.', 'error');
      }
    );
  });
}

/* ---------- UNSUBSCRIBE ---------- */
if (unsubscribeForm) {
  unsubscribeForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = emailInput.value.trim();
    
    if (!email) {
      showMessage('Please enter your email', 'error');
      return;
    }

    await fetch(BACKEND_URL, {
      method: 'POST',
      mode: 'no-cors',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: 'unsubscribe',
        email: email
      })
    });

    showMessage('✅ You have been unsubscribed. Sorry to see you go!', 'success');
    emailInput.value = '';
  });
}

/* ---------- HELPER FUNCTIONS ---------- */
async function getLocationName(lat, lon) {
  try {
    const response = await fetch(
      `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json`
    );
    const data = await response.json();
    const city = data.address.city || data.address.town || 'Unknown';
    const country = data.address.country || 'Unknown';
    return `${city}, ${country}`;
  } catch (error) {
    return `${lat.toFixed(2)}, ${lon.toFixed(2)}`;
  }
}

function showMessage(text, type) {
  if (messageDiv) {
    messageDiv.textContent = text;
    messageDiv.className = `message ${type}`;
    messageDiv.style.display = 'block';
    
    setTimeout(() => {
      messageDiv.style.display = 'none';
    }, 5000);
  }
}