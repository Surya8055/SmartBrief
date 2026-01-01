from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from database import init_db, add_subscriber, unsubscribe, get_all_subscribers
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Initialize database on startup
init_db()

@app.route('/')
def index():
    """Serve the landing page"""
    print("📍 Route '/' accessed - serving index.html")
    try:
        return render_template('index.html')
    except Exception as e:
        print(f"❌ Error rendering index.html: {e}")
        return f"<h1>Error loading page</h1><p>{e}</p><p>Make sure templates/index.html exists!</p>", 500

@app.route('/admin')
def admin():
    """Admin page to view subscribers"""
    print("📍 Route '/admin' accessed - serving admin.html")
    try:
        return render_template('admin.html')
    except Exception as e:
        print(f"❌ Error rendering admin.html: {e}")
        return f"<h1>Error loading admin page</h1><p>{e}</p><p>Make sure templates/admin.html exists!</p>", 500

@app.route('/test')
def test():
    """Test route to verify Flask is working"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Flask Test</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                padding: 40px;
                text-align: center;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                min-height: 100vh;
                margin: 0;
            }
            .container {
                background: white;
                color: #333;
                padding: 40px;
                border-radius: 15px;
                max-width: 600px;
                margin: 0 auto;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }
            h1 { color: #667eea; }
            a {
                color: #667eea;
                text-decoration: none;
                font-weight: bold;
            }
            .success { color: green; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1 class="success">✅ Flask is Working!</h1>
            <p>Your Flask server is running correctly.</p>
            <hr>
            <p><a href="/">Go to Home Page</a></p>
            <p><a href="/admin">Go to Admin Panel</a></p>
            <p><a href="/api/subscribers">View API (JSON)</a></p>
        </div>
    </body>
    </html>
    """

@app.route('/api/subscribe', methods=['POST'])
def subscribe():
    """Handle subscription requests"""
    try:
        data = request.get_json()
        
        # DEBUG: Print what we received
        print("\n🔍 DEBUG - Received subscription data:")
        print(f"   Email: {data.get('email')}")
        print(f"   Latitude: {data.get('latitude')}")
        print(f"   Longitude: {data.get('longitude')}")
        print(f"   Location: {data.get('location_name')}\n")
        
        email = data.get('email')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        location_name = data.get('location_name')
        
        # Validation
        if not email or latitude is None or longitude is None:
            error_msg = f"Missing required fields"
            print(f"❌ Validation failed: {error_msg}")
            return jsonify({
                'success': False,
                'message': 'Email and location are required!'
            }), 400
        
        # Validate email format
        if '@' not in email or '.' not in email.split('@')[1]:
            print(f"❌ Invalid email format: {email}")
            return jsonify({
                'success': False,
                'message': 'Invalid email format!'
            }), 400
        
        # Add to database
        success, message = add_subscriber(email, latitude, longitude, location_name)
        
        if success:
            print(f"✅ New subscriber: {email} from {location_name}")
            return jsonify({
                'success': True,
                'message': message
            }), 201
        else:
            print(f"❌ Failed to add subscriber: {message}")
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except Exception as e:
        print(f"❌ Exception in /api/subscribe: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

@app.route('/api/unsubscribe', methods=['POST'])
def unsubscribe_user():
    """Handle unsubscribe requests"""
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({
                'success': False,
                'message': 'Email is required!'
            }), 400
        
        if unsubscribe(email):
            print(f"✅ Unsubscribed: {email}")
            return jsonify({
                'success': True,
                'message': 'Unsubscribed successfully!'
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to unsubscribe'
            }), 500
        
    except Exception as e:
        print(f"❌ Exception in /api/unsubscribe: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

@app.route('/api/subscribers/count', methods=['GET'])
def get_subscriber_count():
    """Get total subscriber count"""
    try:
        subscribers = get_all_subscribers()
        return jsonify({
            'count': len(subscribers)
        })
    except Exception as e:
        print(f"❌ Error getting subscriber count: {e}")
        return jsonify({
            'count': 0,
            'error': str(e)
        }), 500

@app.route('/api/subscribers', methods=['GET'])
def list_subscribers():
    """List all subscribers (for admin panel)"""
    print("📍 Route '/api/subscribers' accessed")
    try:
        subscribers = get_all_subscribers()
        subscriber_list = []
        
        for sub in subscribers:
            subscriber_list.append({
                'id': sub[0],
                'email': sub[1],
                'latitude': sub[2],
                'longitude': sub[3],
                'location_name': sub[4],
                'subscribed_at': sub[5]
            })
        
        print(f"   ✓ Returning {len(subscriber_list)} subscriber(s)")
        return jsonify({
            'subscribers': subscriber_list,
            'total': len(subscriber_list)
        })
    except Exception as e:
        print(f"❌ Error in /api/subscribers: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'subscribers': [],
            'total': 0,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    print("\n" + "="*70)
    print("🚀 FIRSTLIGHT SERVER STARTING")
    print("="*70)
    
    # Check folder structure
    import os
    
    templates_exist = os.path.exists('templates')
    static_exist = os.path.exists('static')
    
    if templates_exist:
        print("✅ Templates folder found")
        index_exists = os.path.exists('templates/index.html')
        admin_exists = os.path.exists('templates/admin.html')
        print(f"   {'✅' if index_exists else '❌'} index.html {'exists' if index_exists else 'MISSING'}")
        print(f"   {'✅' if admin_exists else '❌'} admin.html {'exists' if admin_exists else 'MISSING'}")
    else:
        print("❌ WARNING: 'templates' folder NOT FOUND!")
        print("   Run: mkdir templates")
    
    if static_exist:
        print("✅ Static folder found")
        css_exists = os.path.exists('static/style.css')
        js_exists = os.path.exists('static/script.js')
        print(f"   {'✅' if css_exists else '❌'} style.css {'exists' if css_exists else 'MISSING'}")
        print(f"   {'✅' if js_exists else '❌'} script.js {'exists' if js_exists else 'MISSING'}")
    else:
        print("❌ WARNING: 'static' folder NOT FOUND!")
        print("   Run: mkdir static")
    
    print()
    print("="*70)
    print("📍 ROUTES:")
    print("="*70)
    print("🏠 Home Page:  http://localhost:5000")
    print("👤 Admin Page: http://localhost:5000/admin")
    print("🧪 Test Page:  http://localhost:5000/test")
    print("📊 API List:   http://localhost:5000/api/subscribers")
    print("="*70)
    print()
    
    if not templates_exist or not static_exist:
        print("⚠️  WARNING: Missing folders detected!")
        print("   The server will start but pages may not load correctly.")
        print()
    
    app.run(debug=True, port=8080, host='127.0.0.1')