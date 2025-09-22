from flask import Flask, request, redirect, url_for, render_template, session, jsonify
import sqlite3
import os
import datetime
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = 'your_very_secret_key'
DATABASE = 'database.db'

app.config['UPLOAD_FOLDER'] = 'static/images/'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  
    return conn
def initialize_database():
    print("Initializing the database...")
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    try:
        # Premium Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS premium_users (
                userID TEXT PRIMARY KEY,
                subscription_type TEXT,
                start_date DATE,
                end_date DATE
            )
        ''')
        print("Premium users table created")

        # Daily Likes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_likes (
                userID TEXT,
                date DATE,
                like_count INTEGER DEFAULT 0,
                PRIMARY KEY (userID, date),
                FOREIGN KEY (userID) REFERENCES users(userID)
            )
        ''')
        print("Daily likes table created")

        # Likes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS likes (
                liker_userID TEXT,
                liked_userID TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (liker_userID, liked_userID),
                FOREIGN KEY (liker_userID) REFERENCES users(userID),
                FOREIGN KEY (liked_userID) REFERENCES users(userID)
            )
        ''')
        print("Likes table created")

        # Messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id TEXT,
                receiver_id TEXT,
                message_content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users(userID),
                FOREIGN KEY (receiver_id) REFERENCES users(userID)
            )
        ''')
        print("Messages table created")

        # Matches table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS matches (
                match_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1_id TEXT NOT NULL,
                user2_id TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user1_id) REFERENCES users(userID),
                FOREIGN KEY (user2_id) REFERENCES users(userID)
            )
        ''')
        print("Matches table created")

        conn.commit()
        print("All tables created successfully")
    except sqlite3.Error as e:
        print(f"An error occurred while creating tables: {e}")
    finally:
        conn.close()
        print("Database connection closed")


@app.route('/fetch_next_profile/<int:index>')
def fetch_next_profile(index):
    current_user_id = session.get('userID')
    print("Fetching profiles for userID:", current_user_id)
    if not current_user_id:
        return jsonify({'message': 'user not logged in'}), 401

    conn = get_db_connection()
    cursor = conn.cursor()
    # Modified query to exclude profiles that have been liked
    cursor.execute('''
        SELECT * FROM users
        WHERE userID != ? AND userID NOT IN (
            SELECT liked_userID FROM likes WHERE liker_userID = ?
        )
    ''', (current_user_id, current_user_id))
    profiles = cursor.fetchall()

    cursor.close()
    conn.close()

    if index < len(profiles):
        next_profile = profiles[index]
        profile_data = {
            'userID': next_profile['userID'],
            'fullname': next_profile['fullname'],
            'age': next_profile['age'],
            'location': next_profile['location'],
            'gender': next_profile['gender'],
            'major': next_profile['major'],
            'political_party': next_profile['political_party'],
            'about_me': next_profile['about_me'],
            'profile_picture': next_profile['profile_picture']  # Assuming it's already in base64
        }
        return jsonify(profile_data)
    else:
        return jsonify({}), 204  # No content to send back


@app.route('/fetch_data')
def fetch_data():
    current_user_id = session.get('userID')
    if not current_user_id:
            return jsonify({'message': 'user not logged in'}), 401
    # Connect to database
    conn = get_db_connection()
    cursor = conn.cursor()

    # fetch profiles
    cursor.execute('SELECT * FROM users WHERE userID != ?', (current_user_id))
    profiles = cursor.fetchall()

    # Convert profiles to list of dictionaries
    profile_data = []
    for profile in profiles:
        profile_data.append({
            'userID': profile['userID'],
            'name': profile['fullname'],
            'age': profile['age'],
            'location': profile['location'],
            'gender': profile['gender'],
            'major': profile['major'],
            'political_party': profile['political_party'],
            'about_me': profile['about_me'],
            'profile_picture': profile['profile_picture']
        })

    # Close cursor and connection
    cursor.close()
    conn.close()

    # Return profiles as JSON
    return jsonify(profile_data)


def create_user(userID, email, password):
    hashed_password = generate_password_hash(password)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('INSERT INTO users (userID, email, password) VALUES (?, ?, ?)',
              (userID, email, hashed_password))
    
    conn.commit()
    conn.close()


@app.route('/')
def index():
    return render_template('index.html')


from flask import jsonify, request, session
import datetime
import sqlite3


@app.route('/like_profile', methods=['POST'])
def like_profile():
    if 'userID' not in session:
        return jsonify({'message': 'User not logged in'}), 401

    liked_userID = request.json.get('liked_userID')
    if not liked_userID:
        return jsonify({'message': 'Liked user ID not provided'}), 400

    liker_userID = session['userID']
    if liker_userID == liked_userID:
        return jsonify({'message': 'Cannot like your own profile'}), 400

    today = datetime.date.today()

    conn = get_db_connection()
    try:
        # Fetch user information to check if they are premium
        user = conn.execute('SELECT * FROM users WHERE userID = ?', (liker_userID,)).fetchone()
        if not user:
            return jsonify({'message': 'User not found'}), 404

        is_premium = user['role'] == 'premium'

        if not is_premium:
            # Check if the user has reached the daily like limit
            daily_likes = conn.execute(
                'SELECT like_count FROM daily_likes WHERE userID = ? AND date = ?',
                (liker_userID, today)
            ).fetchone()

            if daily_likes:
                if daily_likes['like_count'] >= 5:
                    return jsonify({'message': 'Daily like limit reached'}), 429
                # Increment like count
                conn.execute(
                    'UPDATE daily_likes SET like_count = like_count + 1 WHERE userID = ? AND date = ?',
                    (liker_userID, today)
                )
            else:
                # Insert a new record with a like count of 1
                conn.execute(
                    'INSERT INTO daily_likes (userID, date, like_count) VALUES (?, ?, 1)',
                    (liker_userID, today)
                )

        # Record the like if the user is premium or has not exceeded the limit
        conn.execute('''
            INSERT INTO likes (liker_userID, liked_userID) VALUES (?, ?)
            ON CONFLICT(liker_userID, liked_userID) DO NOTHING
        ''', (liker_userID, liked_userID))
        conn.commit()

        # Check for mutual like
        mutual_like = conn.execute('''
            SELECT * FROM likes WHERE liker_userID = ? AND liked_userID = ?
        ''', (liked_userID, liker_userID)).fetchone()

        if mutual_like:
            # Check if a match already exists to avoid duplicates
            existing_match = conn.execute('''
                SELECT * FROM matches WHERE (user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?)
            ''', (liker_userID, liked_userID, liked_userID, liker_userID)).fetchone()

            if not existing_match:
                # Insert match into the matches table
                conn.execute('''
                    INSERT INTO matches (user1_id, user2_id) VALUES (?, ?)
                ''', (liker_userID, liked_userID))
                conn.commit()

        return jsonify({'message': 'Like sent successfully', 'match': bool(mutual_like)}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'message': f'An error occurred: {e}'}), 500
    finally:
        conn.close()


@app.route('/signup', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        userID = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Create user
        create_user(userID, email, password)
        session['userID'] = userID

        return redirect(url_for('create_profile'))

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        userID = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE userID = ?', (userID,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['userID'] = userID
            session['role'] = user['role']

            if user['role'] == 'admin':
                return redirect(url_for('admin_page'))
            else:
                return redirect(url_for('main'))
        else:
            # Handle login failure
            pass

    # Render the login template if it's a GET request or login failed
    return render_template('login.html')





@app.route('/admin_page')
def admin_page():
    return render_template('admin_page.html')


@app.route('/create_profile', methods=['GET', 'POST'])
def create_profile():
    userID = session.get('userID')  # Retrieve userID from session

    if not userID:
        # If no userID in session, redirect to login page
        return redirect(url_for('login'))

    if request.method == 'POST':
        fullname = request.form['fullname']
        age = request.form['age']
        location = request.form['location']
        gender = request.form['gender']
        major = request.form['major']
        political_party = request.form['political_party']
        about_me = request.form['about_me']

        profile_picture = request.files.get('profile_picture')
        if profile_picture and profile_picture.filename != '':
            filename = secure_filename(profile_picture.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            profile_picture.save(file_path)
            # Store only the filename in the database
            profile_picture_filename = filename
        else:
            # Handle the case where no file is uploaded; you may want to set a default or keep it as None
            profile_picture_filename = None




        try:
            conn = get_db_connection()
            # Check if the user already has a profile
            existing_profile = conn.execute('SELECT * FROM users WHERE userID = ?', (userID,)).fetchone()
            if existing_profile:
                # Update existing profile
                conn.execute('''UPDATE users 
                                SET fullname=?, age=?, location=?, gender=?, major=?, political_party=?, about_me=?, profile_picture=? 
                                WHERE userID=?''',
                             (fullname, age, location, gender, major, political_party, about_me, profile_picture_filename, userID))
            else:
                # Insert new profile
                conn.execute('''INSERT INTO users (userID, fullname, age, location, gender, major, political_party, about_me, profile_picture) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                             (userID, fullname, age, location, gender, major, political_party, about_me, profile_picture_filename))
            conn.commit()
        except sqlite3.OperationalError as e:
            print("OperationalError:", e)
            return "Database error occurred!", 500
        finally:
            conn.close()
        
        return redirect(url_for('main'))

    return render_template('create_profile.html')


@app.route('/settings')
def settings():
    return render_template('settings.html')


@app.route('/profile')
def profile():
    userID = session.get('userID')
    
    if not userID:
        return redirect(url_for('login'))

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE userID = ?', (userID,)).fetchone()
    conn.close()
   
    if user:
        is_premium = user['role'] == 'premium'
        return render_template('profile.html', user=user)
    else:
        return render_template('profile.html', error="User not found")



@app.route('/messages')
def messages():
    match_id = request.args.get('match_id')

    messages_data = [
        {'name': 'Mason Bravo', 'profile_picture': 'profile_pic_3.jpg'},
        {'name': 'Luke Smith', 'profile_picture': 'profile_pic_4.jpg'},
        # ... add more messages ...
    ]

    for message in messages_data:
        message['profile_picture'] = url_for('static', filename='images/' + message['profile_picture'])
    return render_template('messages.html', messages_data=messages_data, match_id=match_id)



@app.route('/matches')
def matches():
    if 'userID' not in session:
        return redirect(url_for('login'))

    current_user_id = session['userID']
    conn = get_db_connection()
    try:
        matches = conn.execute('''
            SELECT u.*, m.user1_id, m.user2_id FROM matches m
            JOIN users u ON u.userID = m.user1_id OR u.userID = m.user2_id
            WHERE (m.user1_id = ? OR m.user2_id = ?) AND u.userID != ?
        ''', (current_user_id, current_user_id, current_user_id)).fetchall()

        # Prepare data for rendering
        match_data = [{
            'name': match['fullname'],
            'age': match['age'],
            'location': match['location'],
            'photo': url_for('static', filename='images/' + match['profile_picture']) if match['profile_picture'] else None,
            'userID': match['userID']
        } for match in matches]

        return render_template('matches.html', matches=match_data)
    finally:
        conn.close()


@app.route('/main')
def main():
    if 'userID' not in session:
        print("No userID in session.")
        return redirect(url_for('login'))

    current_user_id = session['userID']
    print(f"Current userID: {current_user_id}")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT * FROM users
            WHERE userID != ? AND userID NOT IN (
                SELECT liked_userID FROM likes WHERE liker_userID = ?
            )
        ''', (current_user_id, current_user_id))

        profiles = cursor.fetchall()
        print(f"Fetched profiles: {profiles}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        conn.close()
        return "Database error occurred!", 500

    finally:
        cursor.close()
        conn.close()

    profile_data = [{
        'userID': profile['userID'],
        'fullname': profile['fullname'],
        'age': profile['age'],
        'location': profile['location'],
        'gender': profile['gender'],
        'major': profile['major'],
        'political_party': profile['political_party'],
        'about_me': profile['about_me'],
        'profile_picture': profile['profile_picture']
    } for profile in profiles]

    print(f"Profile data to render: {profile_data}")
    return render_template('main.html', profiles=profile_data)

@app.route('/preferences', methods=['GET', 'POST'])
def preferences():
    if request.method == 'POST':
        return redirect(url_for('settings'))
    else:
        return render_template('preferences.html')


@app.route('/chat')
def chat():
    # Retrieve user ID
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    return render_template('chat.html', user_id=user_id)


@app.route('/send_message', methods=['POST'])
def send_message():
    if 'userID' not in session:
        return jsonify({'message': 'User not logged in'}), 401
    # Retrieve IDs
    sender_id = request.form['sender_id']
    receiver_id = request.form['receiver_id']
    message_content = request.form['message_content']

    if not receiver_id or not message_content:
        return jsonify({'message': 'Missing receiver ID or message content'}), 400

    # Insert the message into the database
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('INSERT INTO messages (sender_id, receiver_id, message_content) VALUES (?, ?, ?)',
                   (sender_id, receiver_id, message_content))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Message sent successfully'}), 200


@app.route('/get_messages')
def get_messages():
    if 'userID' not in session:
        return jsonify({'message': 'User not logged in'}), 401

    user_id = session['userID']
    chat_with_user_id = request.args.get('chat_with_user_id')
    # Retrieve ID's
    sender_id = request.args.get('sender_id')
    receiver_id = request.args.get('receiver_id')

    # Fetch messages from database
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        'SELECT * FROM messages WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?) ORDER BY timestamp ASC',
        (user_id, chat_with_user_id, chat_with_user_id, user_id))
    messages = cursor.fetchall()
    conn.close()

    messages_list = [{'id': message['id'], 'sender_id': message['sender_id'], 'receiver_id': message['receiver_id'],
                      'message_content': message['message_content'], 'timestamp': message['timestamp']} for message in
                     messages]

    return jsonify(messages_list)


@app.route('/editprofile', methods=['GET', 'POST'])
def editprofile():
    if 'userID' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        fullname = request.form['fullname']
        age = request.form['age']
        location = request.form['location']
        gender = request.form['gender']
        major = request.form['major']
        political_party = request.form['political_party'] 
        about_me = request.form['about_me']  
        
        # Handle profile picture update
        profile_picture = request.files.get('profile_picture')
        if profile_picture and profile_picture.filename != '':
            filename = secure_filename(profile_picture.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            profile_picture.save(file_path)
            profile_picture_filename = filename
        else:
            profile_picture_filename = None
        
        try:
            conn = get_db_connection()
            if profile_picture_filename:
                # Update the user's profile with new picture
                conn.execute('''UPDATE users 
                                SET fullname=?, age=?, location=?, gender=?, major=?, political_party=?, about_me=?, profile_picture=? 
                                WHERE userID=?''',
                             (fullname, age, location, gender, major, political_party, about_me, profile_picture_filename, session['userID']))
            else:
                # Update the user's profile without changing the picture
                conn.execute('''UPDATE users 
                                SET fullname=?, age=?, location=?, gender=?, major=?, political_party=?, about_me=? 
                                WHERE userID=?''',
                             (fullname, age, location, gender, major, political_party, about_me, session['userID']))
            conn.commit()
        except Exception as e:
            # Handle database error
            print("Database error:", e)
            return "An error occurred while updating the profile", 500
        finally:
            conn.close()

        return redirect(url_for('profile'))

    else:
        userID = session.get('userID')
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE userID = ?', (userID,)).fetchone()
        conn.close()
        return render_template('editprofile.html', user=user)
    
def add_premium_subscription(userID, subscription_type):
    conn = get_db_connection()
    cursor = conn.cursor()

    start_date = datetime.date.today()
    if subscription_type == "monthly":
        end_date = start_date + datetime.timedelta(days=30)
    elif subscription_type == "yearly":
        end_date = start_date + datetime.timedelta(days=365)

    cursor.execute(
        '''INSERT INTO premium_users (userID, subscription_type, start_date, end_date) 
           VALUES (?, ?, ?, ?)''',
        (userID, subscription_type, start_date, end_date)
    )
    
    # Update the user's role to 'premium'
    cursor.execute('UPDATE users SET role = ? WHERE userID = ?', ("premium", userID))
    conn.commit()
    conn.close()


@app.route('/upgrade', methods=['GET', 'POST'])
def upgrade():
    if 'userID' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        subscription_type = request.form.get('premium')  # Monthly or yearly
        userID = session['userID']
        add_premium_subscription(userID, subscription_type)
        
        return redirect(url_for('credit_card_info'))  # Or another success page

    return render_template('upgrade.html')

@app.route('/credit_card_info', methods=['GET', 'POST'])
def credit_card_info():
    if request.method == 'POST':
        # Handle form submission (retrieve data, validate, process payment, etc.)
        card_number = request.form.get('card_number')
        expiration_date = request.form.get('expiration_date')
        cvv = request.form.get('cvv')

        
        return redirect(url_for('success'))

    # For GET requests, render the form
    return render_template('credit_card_info.html')

# Route to render the success page after successful form submission
@app.route('/success', methods=['GET'])
def success():
    return render_template('success_page.html')


@app.route('/delete', methods=['GET', 'POST'])
def delete():
    if request.method == 'POST':
        user_id = session.get('userID')
        
        if user_id:
            conn = get_db_connection()
            try:
                premium_user = conn.execute('SELECT * FROM premium_users WHERE userID = ?', (user_id,)).fetchone()
                
                conn.execute('BEGIN TRANSACTION')

                if premium_user:
                    conn.execute('DELETE FROM premium_users WHERE userID = ?', (user_id,))
                
                conn.execute('DELETE FROM users WHERE userID = ?', (user_id,))

                conn.commit()
                
                session.pop('userID', None)
                return redirect(url_for('index')) 
            except sqlite3.Error as e:
                print("An error occurred:", e)
                conn.rollback()
            finally:
                conn.close()

    return render_template('delete.html')


if __name__ == '__main__':
    initialize_database()
    app.run(debug=True)





