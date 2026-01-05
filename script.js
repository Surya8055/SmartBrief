const BACKEND_URL =
  'https://script.google.com/macros/s/AKfycbzVOQldUHHDhvtA0wk_6ZPF85I-e6OxfwObHPbjVhyNQzTIaulYT0BLwmcMEpErh-ueGQ/exec';

// ---------------- SUBSCRIBE ----------------
document.getElementById('subscribeForm').addEventListener('submit', async (e) => {
  e.preventDefault();

  const email = document.getElementById('emailInput').value.trim();
  const msg = document.getElementById('message');
  const btn = document.getElementById('subscribeBtn');

  if (!email) return;

  btn.disabled = true;
  btn.textContent = 'Detecting location...';

  navigator.geolocation.getCurrentPosition(
    async (pos) => {
      const lat = pos.coords.latitude;
      const lon = pos.coords.longitude;

      btn.textContent = 'Subscribing...';

      await fetch(BACKEND_URL, {
        method: 'POST',
        mode: 'no-cors',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'subscribe',
          email,
          latitude: lat,
          longitude: lon
        })
      });

      msg.textContent = '🎉 Subscribed! You’ll receive SmartBrief at 7 AM.';
      btn.textContent = 'Subscribe';
      btn.disabled = false;
      document.getElementById('emailInput').value = '';
    },
    () => {
      msg.textContent = '❌ Location access is required.';
      btn.textContent = 'Subscribe';
      btn.disabled = false;
    }
  );
});

// ---------------- UNSUBSCRIBE ----------------
document.getElementById('unsubscribeForm').addEventListener('submit', async (e) => {
  e.preventDefault();

  const email = document.getElementById('unsubscribeEmail').value.trim();
  const msg = document.getElementById('unsubscribeMessage');

  if (!email) return;

  await fetch(BACKEND_URL, {
    method: 'POST',
    mode: 'no-cors',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      action: 'unsubscribe',
      email
    })
  });

  msg.textContent = '✅ You have been unsubscribed.';
  document.getElementById('unsubscribeEmail').value = '';
});
