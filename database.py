import sqlite3
import os

DB_PATH = "contentrace.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS registered_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            filename TEXT NOT NULL,
            phash TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS flagged_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registered_id INTEGER,
            content_name TEXT NOT NULL,
            platform TEXT DEFAULT 'Reddit',
            source_url TEXT NOT NULL,
            post_title TEXT,
            match_score INTEGER NOT NULL,
            detection_method TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            flagged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (registered_id) REFERENCES registered_content(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anomalies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_name TEXT NOT NULL,
            total_flags INTEGER NOT NULL,
            first_seen TIMESTAMP,
            last_seen TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()