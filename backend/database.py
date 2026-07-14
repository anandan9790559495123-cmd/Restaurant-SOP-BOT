import sqlite3
import os
import json
from datetime import datetime

DB_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DB_DIR, "database.db")

def get_db_connection():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Documents table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT UNIQUE,
        display_name TEXT,
        version INTEGER DEFAULT 1,
        allowed_roles TEXT, -- comma-separated e.g. "manager,kitchen"
        uploaded_at TEXT,
        file_path TEXT,
        is_active INTEGER DEFAULT 1
    )
    """)
    
    # 2. Chat history table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        role TEXT,
        question TEXT,
        answer TEXT,
        citations TEXT, -- JSON array of strings
        timestamp TEXT
    )
    """)
    
    # 3. Feedback table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        rating INTEGER, -- 1 for positive, -1 for negative
        comments TEXT,
        timestamp TEXT,
        FOREIGN KEY (chat_id) REFERENCES chat_history (id) ON DELETE CASCADE
    )
    """)
    
    # 4. Users profile table
    # Check if table exists and has 'password' column
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    table_exists = cursor.fetchone()
    
    has_password = False
    has_email = False
    if table_exists:
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'password' in columns:
            has_password = True
        if 'email' in columns:
            has_email = True
            
    if not table_exists or not has_password:
        cursor.execute("DROP TABLE IF EXISTS users")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            display_name TEXT,
            designation TEXT,
            role TEXT,
            email TEXT
        )
        """)
    elif not has_email:
        # Migration: add email column to existing table
        cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")
    
    # 5. OTP codes table for password reset
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS otp_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        otp_code TEXT NOT NULL,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        used INTEGER DEFAULT 0
    )
    """)
    
    # Initialize default staff role-based names if the table is empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        default_users = [
            ("admin", "admin123", "General Manager", "General Manager", "manager", "anandan9790559495123@gmail.com"),
            ("head_chef", "staff123", "Head Chef", "Head Chef", "kitchen", "prasathanandan9790559495123@gmail.com"),
            ("sous_chef", "staff123", "Sous Chef", "Sous Chef", "kitchen", "prasath.a.27.ece@psvpec.in"),
            ("senior_waiter", "staff123", "Senior Waiter", "Senior Waiter", "server", "mohamednizamudeen143@gmail.com"),
            ("waitress", "staff123", "Waitress", "Waitress", "server", "praveen.n.27.ece@psvpec.in"),
            ("bartender", "staff123", "Bartender", "Bartender", "server", "mohamednizamudeen.s.27.ece@psvpec.in")
        ]
        cursor.executemany("INSERT INTO users (username, password, display_name, designation, role, email) VALUES (?, ?, ?, ?, ?, ?)", default_users)
    else:
        # Migration: backfill emails for existing default staff who have no email
        default_emails = {
            "admin": "anandan9790559495123@gmail.com",
            "head_chef": "prasathanandan9790559495123@gmail.com",
            "sous_chef": "prasath.a.27.ece@psvpec.in",
            "senior_waiter": "mohamednizamudeen143@gmail.com",
            "waitress": "praveen.n.27.ece@psvpec.in",
            "bartender": "mohamednizamudeen.s.27.ece@psvpec.in",
        }
        for uname, uemail in default_emails.items():
            cursor.execute("UPDATE users SET email = ? WHERE username = ? AND (email IS NULL OR email = '')", (uemail, uname))
        
    # 6. Role Requests table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS role_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        current_role TEXT,
        requested_role TEXT,
        requested_username TEXT,
        requested_display_name TEXT,
        status TEXT DEFAULT 'pending',
        timestamp TEXT
    )
    """)
        
    conn.commit()
    conn.close()

# Document Operations
def add_document(filename, display_name, file_path, allowed_roles="manager,kitchen,server"):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if exists to handle versioning
    cursor.execute("SELECT version, allowed_roles FROM documents WHERE filename = ?", (filename,))
    row = cursor.fetchone()
    
    now_str = datetime.now().isoformat()
    if row:
        new_version = row["version"] + 1
        # Keep existing roles if not specified, otherwise update
        cursor.execute("""
            UPDATE documents 
            SET display_name = ?, file_path = ?, version = ?, uploaded_at = ?, is_active = 1
            WHERE filename = ?
        """, (display_name, file_path, new_version, now_str, filename))
        version = new_version
    else:
        cursor.execute("""
            INSERT INTO documents (filename, display_name, version, allowed_roles, uploaded_at, file_path, is_active)
            VALUES (?, ?, 1, ?, ?, ?, 1)
        """, (filename, display_name, allowed_roles, now_str, file_path))
        version = 1
        
    conn.commit()
    conn.close()
    return version

def list_documents():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents ORDER BY uploaded_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_document_roles(filename, allowed_roles):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE documents SET allowed_roles = ? WHERE filename = ?", (allowed_roles, filename))
    conn.commit()
    conn.close()

def toggle_document_status(filename, is_active):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE documents SET is_active = ? WHERE filename = ?", (1 if is_active else 0, filename))
    conn.commit()
    conn.close()

def delete_document(filename):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM documents WHERE filename = ?", (filename,))
    conn.commit()
    conn.close()

def get_active_documents_for_role(role):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE is_active = 1")
    rows = cursor.fetchall()
    conn.close()
    
    # Filter documents in Python to find where role is in allowed_roles
    allowed_docs = []
    for r in rows:
        roles_list = [x.strip().lower() for x in r["allowed_roles"].split(",")]
        # manager has access to everything
        if role.lower() == "manager" or role.lower() in roles_list:
            allowed_docs.append(dict(r))
    return allowed_docs

# Chat History Operations
def save_chat_message(username, role, question, answer, citations):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    citations_json = json.dumps(citations)
    
    cursor.execute("""
        INSERT INTO chat_history (username, role, question, answer, citations, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (username, role, question, answer, citations_json, now_str))
    chat_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return chat_id

def get_chat_history(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chat_history WHERE username = ? ORDER BY id ASC", (username,))
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for r in rows:
        item = dict(r)
        try:
            item["citations"] = json.loads(item["citations"])
        except:
            item["citations"] = []
        history.append(item)
    return history

def clear_chat_history(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_history WHERE username = ?", (username,))
    conn.commit()
    conn.close()

# Feedback Operations
def save_feedback(chat_id, rating, comments):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO feedback (chat_id, rating, comments, timestamp)
        VALUES (?, ?, ?, ?)
    """, (chat_id, rating, comments, now_str))
    conn.commit()
    conn.close()

def get_feedback_logs():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT f.id, f.chat_id, f.rating, f.comments, f.timestamp, 
               h.username, h.role, h.question, h.answer
        FROM feedback f
        JOIN chat_history h ON f.chat_id = h.id
        ORDER BY f.timestamp DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_analytics():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Total ratings counts
    cursor.execute("SELECT COUNT(*) as total_feedback, COALESCE(SUM(case when rating = 1 then 1 else 0 end), 0) as positive_feedback, COALESCE(SUM(case when rating = -1 then 1 else 0 end), 0) as negative_feedback FROM feedback")
    row = cursor.fetchone()
    feedback_stats = dict(row) if row else {"total_feedback": 0, "positive_feedback": 0, "negative_feedback": 0}
    
    # Total chats
    cursor.execute("SELECT COUNT(*) as total_chats FROM chat_history")
    row = cursor.fetchone()
    chat_stats = dict(row) if row else {"total_chats": 0}
    
    # Active documents
    cursor.execute("SELECT COUNT(*) as total_docs FROM documents WHERE is_active = 1")
    row = cursor.fetchone()
    doc_stats = dict(row) if row else {"total_docs": 0}
    
    stats = {}
    stats.update(feedback_stats)
    stats.update(chat_stats)
    stats.update(doc_stats)
    conn.close()
    return stats

def clear_all_documents():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM documents")
    conn.commit()
    conn.close()

def clear_all_feedback_and_history():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM feedback")
    cursor.execute("DELETE FROM chat_history")
    conn.commit()
    conn.close()

def delete_chat_log(chat_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Delete from feedback first (cascading cleanup)
    cursor.execute("DELETE FROM feedback WHERE chat_id = ?", (chat_id,))
    # Delete from chat history
    cursor.execute("DELETE FROM chat_history WHERE id = ?", (chat_id,))
    conn.commit()
    conn.close()


def get_user_profile(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_user_display_name(username, new_display_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET display_name = ? WHERE username = ?", (new_display_name, username))
    conn.commit()
    conn.close()

def get_worker_analytics(username, role):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Feedback counts for this user
    cursor.execute("""
        SELECT COUNT(*) as total_feedback, 
               COALESCE(SUM(case when f.rating = 1 then 1 else 0 end), 0) as positive_feedback, 
               COALESCE(SUM(case when f.rating = -1 then 1 else 0 end), 0) as negative_feedback 
        FROM feedback f
        JOIN chat_history h ON f.chat_id = h.id
        WHERE h.username = ?
    """, (username,))
    feedback_row = cursor.fetchone()
    feedback_stats = dict(feedback_row) if feedback_row else {"total_feedback": 0, "positive_feedback": 0, "negative_feedback": 0}
    
    # 2. Total chats for this user
    cursor.execute("SELECT COUNT(*) as total_chats FROM chat_history WHERE username = ?", (username,))
    chat_row = cursor.fetchone()
    chat_stats = dict(chat_row) if chat_row else {"total_chats": 0}
    
    # 3. Active documents allowed for this role
    cursor.execute("SELECT allowed_roles FROM documents WHERE is_active = 1")
    rows = cursor.fetchall()
    total_docs = 0
    for r in rows:
        roles_list = [x.strip().lower() for x in r["allowed_roles"].split(",")]
        if role.lower() in roles_list:
            total_docs += 1
            
    stats = {}
    stats.update(feedback_stats)
    stats.update(chat_stats)
    stats["total_docs"] = total_docs
    conn.close()
    return stats

def get_worker_feedback_logs(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT h.id as chat_id, f.id as feedback_id, f.rating, f.comments, 
               COALESCE(f.timestamp, h.timestamp) as timestamp, 
               h.username, h.role, h.question, h.answer
        FROM chat_history h
        LEFT JOIN feedback f ON f.chat_id = h.id
        WHERE h.username = ?
        ORDER BY timestamp DESC
    """, (username,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_user_role_and_username(old_username, new_username, new_role, new_designation, new_display_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE users 
        SET username = ?, role = ?, designation = ?, display_name = ?
        WHERE username = ?
    """, (new_username, new_role, new_designation, new_display_name, old_username))
    
    cursor.execute("""
        UPDATE chat_history 
        SET username = ?, role = ? 
        WHERE username = ?
    """, (new_username, new_role, old_username))
    
    conn.commit()
    conn.close()

def add_user(username, password, display_name, role, designation, email=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (username, password, display_name, role, designation, email)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (username, password, display_name, role, designation, email))
    conn.commit()
    conn.close()

# ==========================================
# EMAIL, OTP & PASSWORD MANAGEMENT
# ==========================================

def update_user_email(username, email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET email = ? WHERE username = ?", (email, username))
    conn.commit()
    conn.close()

def get_user_by_email(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def save_otp(email, otp_code, expires_at):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    # Invalidate any existing OTPs for this email
    cursor.execute("UPDATE otp_codes SET used = 1 WHERE email = ? AND used = 0", (email,))
    # Insert new OTP
    cursor.execute("""
        INSERT INTO otp_codes (email, otp_code, created_at, expires_at, used)
        VALUES (?, ?, ?, ?, 0)
    """, (email, otp_code, now_str, expires_at))
    conn.commit()
    conn.close()

def verify_otp(email, otp_code):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    cursor.execute("""
        SELECT * FROM otp_codes 
        WHERE email = ? AND otp_code = ? AND used = 0 AND expires_at > ?
        ORDER BY id DESC LIMIT 1
    """, (email, otp_code, now_str))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def mark_otp_used(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE otp_codes SET used = 1 WHERE email = ? AND used = 0", (email,))
    conn.commit()
    conn.close()

def update_user_password(username, new_password):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password = ? WHERE username = ?", (new_password, username))
    conn.commit()
    conn.close()

def delete_user(username):
    """Permanently delete a staff account and all associated data."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Delete feedback linked to this user's chats
    cursor.execute("""
        DELETE FROM feedback WHERE chat_id IN (
            SELECT id FROM chat_history WHERE username = ?
        )
    """, (username,))
    # Delete chat history
    cursor.execute("DELETE FROM chat_history WHERE username = ?", (username,))
    # Delete role requests
    cursor.execute("DELETE FROM role_requests WHERE username = ?", (username,))
    # Delete the user
    cursor.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()

def create_role_request(username, current_role, requested_role, requested_username, requested_display_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO role_requests (username, current_role, requested_role, requested_username, requested_display_name, status, timestamp)
        VALUES (?, ?, ?, ?, ?, 'pending', ?)
    """, (username, current_role, requested_role, requested_username, requested_display_name, now_str))
    conn.commit()
    conn.close()

def get_pending_role_requests():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM role_requests WHERE status = 'pending' ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_user_role_requests(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM role_requests 
        WHERE username = ? OR requested_username = ? 
        ORDER BY timestamp DESC
    """, (username, username))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_role_request_status(request_id, status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE role_requests SET status = ? WHERE id = ?", (status, request_id))
    conn.commit()
    conn.close()

def get_role_request(request_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM role_requests WHERE id = ?", (request_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# Initialize DB when this script runs or is imported
init_db()
