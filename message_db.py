
import sqlite3
from datetime import datetime, timedelta

_db_connection = None

def init_db():
    """Initialize the database and create tables if they don't exist."""
    global _db_connection
    try:
        _db_connection = sqlite3.connect('messages.db')
        c = _db_connection.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id TEXT PRIMARY KEY, 
                  content TEXT, 
                  author TEXT, 
                  timestamp DATETIME,
                  channel_id TEXT)''')
        _db_connection.commit()
    except Exception as e:
        print(f"Error initializing database: {e}")
        if _db_connection:
            _db_connection.close()
            _db_connection = None

def close_db_connection():
    """Close the database connection if it exists."""
    global _db_connection
    try:
        if _db_connection:
            _db_connection.commit()
            _db_connection.close()
            _db_connection = None
            print("Database connection closed successfully")
    except Exception as e:
        print(f"Error closing database: {e}")

def store_message(message):
    """Store a Discord message in the database."""
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    try:
        c.execute('INSERT OR IGNORE INTO messages VALUES (?,?,?,?,?)',
                  (str(message.id),
                   message.content, 
                   str(message.author), 
                   message.created_at, 
                   str(message.channel.id)))
        conn.commit()
    except sqlite3.IntegrityError:
        print(f"Message {message.id} already exists")
    except Exception as e:
        print(f"Error storing message: {e}")
    finally:
        conn.close()

def get_daily_messages(channel_ids=None):
    """Get messages from the last 24 hours."""
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
    
    try:
        if channel_ids:
            channels_str = ','.join(f"'{ch}'" for ch in channel_ids)
            query = f'''SELECT content, author, timestamp, channel_id
                        FROM messages 
                        WHERE timestamp >= ? AND channel_id IN ({channels_str})'''
            c.execute(query, (twenty_four_hours_ago,))
        else:
            c.execute('''SELECT content, author, timestamp, channel_id
                         FROM messages 
                         WHERE timestamp >= ?''', 
                      (twenty_four_hours_ago,))
        
        results = c.fetchall()
        return results
    finally:
        conn.close()
