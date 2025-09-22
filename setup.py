import sqlite3
from werkzeug.security import generate_password_hash
from getpass import getpass

def init_db():
    conn = sqlite3.connect('database.db')
    print(f"Database path: {conn}")
    conn.execute('PRAGMA foreign_keys = ON')
    c = conn.cursor()

    try:
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                userID TEXT PRIMARY KEY,
                fullname TEXT,
                age INTEGER,
                location TEXT,
                gender TEXT,
                major TEXT,
                political_party TEXT,
                about_me TEXT,
                profile_picture BLOB,
                email TEXT UNIQUE,
                password TEXT,
                role TEXT DEFAULT 'user'
            )
        ''')
        print("Users table created")

        c.execute('''
            CREATE TABLE IF NOT EXISTS likes (
                liker_userID TEXT,
                liked_userID TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (liker_userID, liked_userID),
                FOREIGN KEY (liker_userID) REFERENCES users (userID),
                FOREIGN KEY (liked_userID) REFERENCES users (userID)
            )
        ''')
        print("Likes table created")

        c.execute('''
            CREATE TABLE IF NOT EXISTS daily_likes (
                userID TEXT,
                date DATE,
                like_count INTEGER DEFAULT 0,
                PRIMARY KEY (userID, date),
                FOREIGN KEY (userID) REFERENCES users (userID)
            )
        ''')
        print("Daily Likes table created")

        c.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id TEXT,
                receiver_id TEXT,
                message_content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users (userID),
                FOREIGN KEY (receiver_id) REFERENCES users (userID)
            )
        ''')
        print("Messages table created")

        c.execute('''
            CREATE TABLE IF NOT EXISTS matches (
                match_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1_id TEXT NOT NULL,
                user2_id TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user1_id) REFERENCES users (userID),
                FOREIGN KEY (user2_id) REFERENCES users (userID)
            )
        ''')
        print("Matches table created")

        c.execute('''
            CREATE TABLE IF NOT EXISTS premium_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                userID TEXT,
                subscription_type TEXT, 
                start_date TEXT, 
                end_date TEXT,
                FOREIGN KEY (userID) REFERENCES users (userID)
            )
        ''')
        print("Premium Users table created")

        conn.commit()
    except sqlite3.Error as e:
        print("An error occurred:", e)
    finally:
        conn.close()

def init_admin():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    email = input("Enter admin email: ")
    username = input("Enter admin username: ")
    password = getpass("Enter admin password: ")
    hashed_password = generate_password_hash(password)

    try:
        cursor.execute('''
            INSERT INTO users (userID, email, password, role) VALUES (?, ?, ?, ?)
        ''', (username, email, hashed_password, 'admin'))

        conn.commit()
        print("Admin created successfully.")
    except sqlite3.IntegrityError:
        print("Admin already exists.")
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    init_db()
    init_admin()
    print("Database initialization complete.")


