from .db import get_conn
from typing import List, Dict, Any

MAX_WORKING_SIZE = 20

def add_turn(session_id, user_id, role, content):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO working_memory (session_id, user_id, role, content)
        VALUES (?, ?, ?, ?)
    """, (session_id, user_id, role, content))
    conn.commit()
    c.execute("""
        DELETE FROM working_memory
        WHERE session_id = ? AND id NOT IN (
            SELECT id FROM working_memory WHERE session_id = ?
            ORDER BY id DESC LIMIT ?
        )
    """, (session_id, session_id, MAX_WORKING_SIZE))
    conn.commit()
    conn.close()

def get_history(session_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT role, content, created_at FROM working_memory
        WHERE session_id = ? ORDER BY id ASC
    """, (session_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows
