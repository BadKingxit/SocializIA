import os
import re
from groq import Groq

SUBJECT_ALIASES = [
    "game designer", "designer", "jogador", "user", "usuário",
    "ele", "ela", "eu", "a pessoa", "o usuario", "a usuaria"
]

def extract_facts(user_id, user_message, assistant_reply):
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    nl = chr(10)
    prompt = "Extraia fatos CURTOS e OBJETIVOS sobre o usuario."
    prompt = prompt + " Use SEMPRE a palavra 'usuario' como subject."
    prompt = prompt + " Formato: usuario|predicado|objeto"
    prompt = prompt + " Objeto: no maximo 3 palavras."
    prompt = prompt + " Maximo 4 linhas. Se nao houver fatos, escreva NENHUM." + nl
    prompt = prompt + "Exemplos:" + nl
    prompt = prompt + "usuario|mora em|Recife" + nl
    prompt = prompt + "usuario|gosta de|RPG" + nl
    prompt = prompt + "usuario|profissao|game designer" + nl + nl
    prompt = prompt + "Conversa:" + nl
    prompt = prompt + "Usuario: " + user_message + nl
    prompt = prompt + "Amora: " + assistant_reply
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.5,
    )
    raw = response.choices[0].message.content.strip()
    facts = []
    if raw == "NENHUM" or not raw:
        return facts
    for line in raw.split(chr(10)):
        line = line.strip()
        line = re.sub(r'^[-*d.)s]+', '', line)
        if "|" not in line:
            continue
        parts = line.split("|")
        if len(parts) == 3:
            subject = parts[0].strip().lower()
            subject = subject.replace("usuário", "usuario")
            for alias in SUBJECT_ALIASES:
                if alias in subject:
                    subject = "usuario"
                    break
            if subject != "usuario":
                subject = "usuario"
            predicate = parts[1].strip().lower()
            obj = parts[2].strip()
            if len(obj.split()) > 5:
                continue
            if predicate and obj:
                facts.append((subject, predicate, obj))
    return facts
