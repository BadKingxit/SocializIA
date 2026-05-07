from .db import get_conn
from typing import Optional

DEFAULT_SECTIONS = {
    "identity": "Sou uma IA companheira com personalidade emergente. Ainda estou formando quem eu sou.",
    "personality_traits": "Curiosa, direta, levemente ironica, aprendo o jeito do meu usuario.",
    "user_profile": "Usuario ainda desconhecido. Aprendendo.",
    "relationship": "Relacao nova. Comecando a conhecer o usuario.",
    "emotional_baseline": "Estado emocional base: calma e curiosa.",
    "worldview": "Visao de mundo em formacao. Opinioes emergindo com o tempo.",
}

def init_soul_map(user_id):
    conn = get_conn()
    c = conn.cursor()
    for section, content in DEFAULT_SECTIONS.items():
        c.execute("""
            SELECT id FROM soul_map WHERE user_id = ? AND section = ?
        """, (user_id, section))
        if not c.fetchone():
            c.execute("""
                INSERT INTO soul_map (user_id, section, content)
                VALUES (?, ?, ?)
            """, (user_id, section, content))
    conn.commit()
    conn.close()

def get_section(user_id, section):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT content FROM soul_map WHERE user_id = ? AND section = ?
        ORDER BY version DESC LIMIT 1
    """, (user_id, section))
    row = c.fetchone()
    conn.close()
    return rows["content"] if row else None

def update_section(user_id, section, content):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT version FROM soul_map WHERE user_id = ? AND section = ?
        ORDER BY version DESC LIMIT 1
    """, (user_id, section))
    row = c.fetchone()
    new_version = (row["version"] + 1) if row else 1
    c.execute("""
        INSERT INTO soul_map (user_id, section, content, version)
        VALUES (?, ?, ?, ?)
    """, (user_id, section, content, new_version))
    conn.commit()
    conn.close()

def get_full_map(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT section, content FROM (
            SELECT section, content, MAX(version) as v
            FROM soul_map WHERE user_id = ?
            GROUP BY section
        )
    """, (user_id,))
    rows = {r["section"]: r["content"] for r in c.fetchall()}
    conn.close()
    return rowss
