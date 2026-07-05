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
    cursor.execute("DROP TABLE IF EXISTS users") # Drop existing users to force re-initialization with new role-based usernames
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        display_name TEXT,
        designation TEXT,
        role TEXT
    )
    """)
    
    # Initialize default staff role-based names if the table is empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        default_users = [
            ("admin", "General Manager", "General Manager", "manager"),
            ("head_chef", "Head Chef", "Head Chef", "kitchen"),
            ("sous_chef", "Sous Chef", "Sous Chef", "kitchen"),
            ("senior_waiter", "Senior Waiter", "Senior Waiter", "server"),
            ("waitress", "Waitress", "Waitress", "server"),
            ("bartender", "Bartender", "Bartender", "server")
        ]
        cursor.executemany("INSERT INTO users (username, display_name, designation, role) VALUES (?, ?, ?, ?)", default_users)
        
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

# Initialize DB when this script runs or is imported
init_db()
