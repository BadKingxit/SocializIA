from .db import get_conn
from typing import List, Dict, Any

def save_rule(user_id, name, rule):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT id, version FROM procedures
        WHERE user_id = ? AND name = ? AND active = 1
    """, (user_id, name))
    existing = c.fetchone()
    if existing:
        new_version = existing["version"] + 1
        c.execute("UPDATE procedures SET active = 0 WHERE id = ?", (existing["id"],))
        c.execute("""
            INSERT INTO procedures (user_id, name, rule, version)
            VALUES (?, ?, ?, ?)
        """, (user_id, name, rule, new_version))
    else:
        c.execute("""
            INSERT INTO procedures (user_id, name, rule)
            VALUES (?, ?, ?)
        """, (user_id, name, rule))
    conn.commit()
    conn.close()

def get_rules(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT name, rule FROM procedures
        WHERE user_id = ? AND active = 1
    """, (user_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows
