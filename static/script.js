const form = document.getElementById('subscribeForm');
const emailInput = document.getElementById('emailInput');
const subscribeBtn = document.getElementById('subscribeBtn');
const messageDiv = document.getElementById('message');
const locationInfo = document.getElementById('locationInfo');

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const email = emailInput.value.trim();
    
    if (!email) {
        showMessage('Please enter your email address', 'error');
        return;
    }
    
    // Request location permission
    subscribeBtn.disabled = true;
    subscribeBtn.textContent = 'Getting Location...';
    
    if (!navigator.geolocation) {
        showMessage('Geolocation is not supported by your browser', 'error');
        subscribeBtn.disabled = false;
        subscribeBtn.textContent = 'Subscribe';
        return;
    }
    
    navigator.geolocation.getCurrentPosition(
        // Success callback
        async (position) => {
            const latitude = position.coords.latitude;
            const longitude = position.coords.longitude;
            
            // Get location name
            const locationName = await getLocationName(latitude, longitude);
            
            // Show location info
            locationInfo.textContent = `📍 Location detected: ${locationName}`;
            locationInfo.classList.add('show');
            
            // Send to backend
            subscribeBtn.textContent = 'Subscribing...';
            
            try {
                const response = await fetch('/api/subscribe', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        email: email,
                        latitude: latitude,
                        longitude: longitude,
                        location_name: locationName
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showMessage('🎉 ' + data.message + ' Check your email every morning!', 'success');
                    emailInput.value = '';
                } else {
                    showMessage('❌ ' + data.message, 'error');
                }
                
            } catch (error) {
                showMessage('❌ Failed to subscribe. Please try again.', 'error');
                console.error('Error:', error);
            }
            
            subscribeBtn.disabled = false;
            subscribeBtn.textContent = 'Subscribe';
        },
        // Error callback
        (error) => {
            let errorMessage = 'Unable to get your location. ';
            
            switch(error.code) {
                case error.PERMISSION_DENIED:
                    errorMessage += 'Please allow location access.';
                    break;
                case error.POSITION_UNAVAILABLE:
                    errorMessage += 'Location information is unavailable.';
                    break;
                case error.TIMEOUT:
                    errorMessage += 'Location request timed out.';
                    break;
                default:
                    errorMessage += 'An unknown error occurred.';
            }
            
            showMessage(errorMessage, 'error');
            subscribeBtn.disabled = false;
            subscribeBtn.textContent = 'Subscribe';
        }
    );
});

async function getLocationName(lat, lon) {
    try {
        const response = await fetch(
            `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json`
        );
        const data = await response.json();
        
        const city = data.address.city || data.address.town || data.address.village || 'Unknown';
        const country = data.address.country || 'Unknown';
        
        return `${city}, ${country}`;
    } catch (error) {
        console.error('Error getting location name:', error);
        return `${lat.toFixed(2)}, ${lon.toFixed(2)}`;
    }
}

function showMessage(text, type) {
    messageDiv.textContent = text;
    messageDiv.className = `message ${type}`;
    messageDiv.style.display = 'block';
    
    setTimeout(() => {
        messageDiv.style.display = 'none';
    }, 5000);
}

// Unsubscribe link
document.getElementById('unsubscribeLink').addEventListener('click', (e) => {
    e.preventDefault();
    const email = prompt('Enter your email to unsubscribe:');
    
    if (email) {
        fetch('/api/unsubscribe', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email: email })
        })
        .then(res => res.json())
        .then(data => {
            alert(data.message);
        })
        .catch(error => {
            alert('Failed to unsubscribe. Please try again.');
        });
    }
});