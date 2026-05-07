from .db import get_conn

def load_state(user_id):
    conn = get_conn()
    c = conn.cursor()
    sql = "SELECT valence, arousal, label FROM emotional_state WHERE user_id = ?"
    c.execute(sql, (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"valence": row["valence"], "arousal": row["arousal"], "label": row["label"]}
    return None

def save_state(user_id, valence, arousal, label):
    conn = get_conn()
    c = conn.cursor()
    sql = "INSERT INTO emotional_state (user_id, valence, arousal, label, updated_at) "
    sql = sql + "VALUES (?, ?, ?, ?, datetime('now')) "
    sql = sql + "ON CONFLICT(user_id) DO UPDATE SET "
    sql = sql + "valence = excluded.valence, "
    sql = sql + "arousal = excluded.arousal, "
    sql = sql + "label = excluded.label, "
    sql = sql + "updated_at = excluded.updated_at"
    c.execute(sql, (user_id, valence, arousal, label))
    conn.commit()
    conn.close()