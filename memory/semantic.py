from .db import get_conn
from typing import List, Dict, Any

def upsert_fact(user_id, subject, predicate, obj, confidence=1.0, source_session=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT id FROM facts
        WHERE user_id = ? AND subject = ? AND predicate = ? AND active = 1
    """, (user_id, subject, predicate))
    existing = c.fetchone()
    if existing:
        c.execute("""
            UPDATE facts SET object = ?, confidence = ?,
            source_session = ?, updated_at = datetime('now')
            WHERE id = ?
        """, (obj, confidence, source_session, existing["id"]))
    else:
        c.execute("""
            INSERT INTO facts (user_id, subject, predicate, object,
                               confidence, source_session)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, subject, predicate, obj, confidence, source_session))
    conn.commit()
    conn.close()

def get_facts(user_id, subject=None):
    conn = get_conn()
    c = conn.cursor()
    if subject:
        c.execute("""
            SELECT * FROM facts WHERE user_id = ? AND subject = ? AND active = 1
            ORDER BY confidence DESC
        """, (user_id, subject))
    else:
        c.execute("""
            SELECT * FROM facts WHERE user_id = ? AND active = 1
            ORDER BY confidence DESC
        """, (user_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows
