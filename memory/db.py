import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "socializ_memory.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            summary TEXT NOT NULL,
            emotion_label TEXT,
            valence REAL DEFAULT 0.0,
            arousal REAL DEFAULT 0.0,
            importance REAL DEFAULT 0.5,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            predicate TEXT NOT NULL,
            object TEXT NOT NULL,
            confidence REAL DEFAULT 1.0,
            source_session TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS emotional_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            episode_id INTEGER,
            description TEXT NOT NULL,
            emotion_label TEXT,
            valence REAL DEFAULT 0.0,
            arousal REAL DEFAULT 0.0,
            importance REAL DEFAULT 0.8,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (episode_id) REFERENCES episodes(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS procedures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            rule TEXT NOT NULL,
            version INTEGER DEFAULT 1,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS working_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS soul_map (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            section TEXT NOT NULL,
            content TEXT NOT NULL,
            version INTEGER DEFAULT 1,
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS emotional_state (
            user_id TEXT PRIMARY KEY,
            valence REAL DEFAULT 0.0,
            arousal REAL DEFAULT 0.0,
            label TEXT DEFAULT 'neutra',
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()
    print("[DB] Tabelas inicializadas.")
