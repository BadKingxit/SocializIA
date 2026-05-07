from .db import get_conn
from typing import List, Dict, Any

def save_episode(user_id, session_id, summary, emotion_label="neutra",
                 valence=0.0, arousal=0.0, importance=0.5):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO episodes (session_id, user_id, summary, emotion_label,
                              valence, arousal, importance)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (session_id, user_id, summary, emotion_label, valence, arousal, importance))
    episode_id = c.lastrowid
    conn.commit()
    conn.close()
    return episode_id

def get_recent_episodes(user_id, limit=5):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM episodes WHERE user_id = ?
        ORDER BY created_at DESC LIMIT ?
    """, (user_id, limit))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def get_emotional_episodes(user_id, min_importance=0.75, limit=5):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM episodes WHERE user_id = ? AND importance >= ?
        ORDER BY importance DESC LIMIT ?
    """, (user_id, min_importance, limit))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows
