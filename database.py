import sqlite3
from datetime import datetime
import time

def get_connection():
    """Get database connection with timeout"""
    conn = sqlite3.connect('subscribers.db', timeout=10.0, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL')  # Write-Ahead Logging mode
    return conn

def init_db():
    """Initialize the database with subscribers table"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            location_name TEXT,
            subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized!")

def add_subscriber(email, latitude, longitude, location_name=None):
    """Add a new subscriber to the database"""
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO subscribers (email, latitude, longitude, location_name)
                VALUES (?, ?, ?, ?)
            ''', (email, latitude, longitude, location_name))
            
            conn.commit()
            conn.close()
            return True, "Subscribed successfully!"
            
        except sqlite3.IntegrityError:
            if conn:
                conn.close()
            return False, "Email already subscribed!"
            
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                retry_count += 1
                if conn:
                    conn.close()
                time.sleep(0.1)  # Wait 100ms before retry
                if retry_count >= max_retries:
                    return False, "Database busy, please try again"
            else:
                if conn:
                    conn.close()
                return False, f"Error: {str(e)}"
                
        except Exception as e:
            if conn:
                conn.close()
            return False, f"Error: {str(e)}"
    
    return False, "Failed after retries"

def get_all_subscribers():
    """Get all active subscribers"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, email, latitude, longitude, location_name, subscribed_at
            FROM subscribers 
            WHERE is_active = 1
        ''')
        
        subscribers = cursor.fetchall()
        conn.close()
        
        return subscribers
    except Exception as e:
        print(f"Error getting subscribers: {e}")
        return []

def unsubscribe(email):
    """Unsubscribe a user"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE subscribers 
            SET is_active = 0 
            WHERE email = ?
        ''', (email,))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error unsubscribing: {e}")
        return False

if __name__ == "__main__":
    init_db()