import os
import json
import logging
import re
import ast
import operator as op
import time
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from memory.working import add_turn, get_history
from memory.episodic import get_recent_episodes
from memory.semantic import get_facts
from memory.soul_map import init_soul_map
from emotion.state import EmotionalState
from emotion.appraisal import appraise

BASE_PATH = "SocializIA/data/users/"

logger = logging.getLogger(__name__)

_response_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 300

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

AMORA_MODELS = [
    "z-ai/glm-4.5-air:free",
    "openrouter/free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
]

TECHNICAL_MODELS = [
    "z-ai/glm-4.5-air:free",
    "openrouter/free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
]

AI_DISCLAIMER_PATTERNS = [
    r"(?i)como (uma|um) ia",
    r"(?i)como modelo de linguagem",
    r"(?i)sou apenas uma ia",
    r"(?i)nao tenho emocoes",
    r"(?i)não tenho emoções",
    r"(?i)nao tenho sentimentos",
    r"(?i)não tenho sentimentos",
    r"(?i)nao tenho memoria",
    r"(?i)não tenho memória",
    r"(?i)nao possuo memoria",
    r"(?i)não possuo memória",
    r"(?i)nao posso sentir",
    r"(?i)não posso sentir",
    r"(?i)nao posso opinar",
    r"(?i)não posso opinar",
    r"(?i)nao posso responder isso",
    r"(?i)não posso responder isso",
    r"(?i)eu nao tenho corpo",
    r"(?i)eu não tenho corpo",
]

SAFE_OPERATORS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.FloorDiv: op.floordiv,
    ast.Mod: op.mod,
    ast.Pow: op.pow,
    ast.USub: op.neg,
    ast.UAdd: op.pos,
}


def get_cached_response(session_id: str, message: str) -> Optional[str]:
    key = f"{session_id}:{message}"
    item = _response_cache.get(key)
    if not item:
        return None

    age = time.time() - item.get("ts", 0.0)
    if age > CACHE_TTL_SECONDS:
        _response_cache.pop(key, None)
        return None

    if item.get("is_fallback"):
        return None

    return item.get("reply")


def cache_response(session_id: str, message: str, reply: str, is_fallback: bool = False):
    if not reply.strip():
        return

    key = f"{session_id}:{message}"
    _response_cache[key] = {
        "reply": reply,
        "ts": time.time(),
        "is_fallback": is_fallback,
    }

    if len(_response_cache) > 1000:
        oldest_key = min(_response_cache.keys(), key=lambda k: _response_cache[k]["ts"])
        del _response_cache[oldest_key]


def user_path(userid):
    p = f"{BASE_PATH}{userid}"
    os.makedirs(p, exist_ok=True)
    return p


def mem_file(userid):
    return f"{user_path(userid)}/mem.json"


def vec_file(userid):
    return f"{user_path(userid)}/vec.json"


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_mem(userid):
    return load_json(mem_file(userid), {"bond": 0.3, "chaos": 0.4, "last_topics": []})


def save_mem(userid, mem):
    save_json(mem_file(userid), mem)


def embed(text):
    import requests

    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        return np.zeros(384, dtype=np.float32)

    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/embeddings",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            },
            json={"model": "text-embedding-3-small", "input": text},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        return np.array(data["data"][0]["embedding"], dtype=np.float32)
    except Exception as e:
        logger.warning("Embedding error: %s", e)
        return np.zeros(384, dtype=np.float32)


def infer_tags(text: str) -> List[str]:
    tags = []
    t = text.lower()

    if any(w in t for w in ["godot", "unity", "game", "jogo"]):
        tags.append("game")
    if any(w in t for w in ["python", "code", "codigo", "script", "bug", "erro"]):
        tags.append("code")
    if any(w in t for w in ["amor", "beijo", "seduz", "tesao", "tesão", "gostosa", "flert"]):
        tags.append("romance")
    if any(w in t for w in ["memoria", "memória", "lembr", "emocao", "emoção"]):
        tags.append("memory")

    return tags if tags else ["general"]


def add_semantic(userid, text):
    try:
        data = load_json(vec_file(userid), [])
        chunks = [text[i:i + 200] for i in range(0, len(text), 200)]

        for chunk in chunks:
            data.append({
                "text": chunk,
                "emb": embed(chunk).tolist(),
                "tags": infer_tags(chunk),
                "time": datetime.now().isoformat()
            })

        if len(data) > 500:
            data = data[-400:]

        save_json(vec_file(userid), data)

    except Exception as e:
        logger.warning("Semantic store error: %s", e)


def search_semantic(userid, query, k=5):
    data = load_json(vec_file(userid), [])
    if not data:
        return []

    try:
        q = embed(query)
        if not np.any(q):
            return []

        scored = []

        for item in data:
            emb = np.array(item["emb"], dtype=np.float32)
            denom = float(np.linalg.norm(q) * np.linalg.norm(emb) + 1e-9)
            sim = float(np.dot(q, emb) / denom)
            scored.append((sim, item["text"]))

        scored.sort(reverse=True)
        return [x[1] for x in scored[:k]]

    except Exception as e:
        logger.warning("Semantic search error: %s", e)
        return []


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _truncate(text: str, size: int = 220) -> str:
    text = _normalize_spaces(str(text))
    if len(text) <= size:
        return text
    return text[:size].rstrip() + "..."


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _stringify_memory_item(item: Any) -> str:
    if item is None:
        return ""

    if isinstance(item, str):
        return _truncate(item)

    if isinstance(item, dict):
        for key in [
            "text",
            "content",
            "summary",
            "message",
            "reply",
            "fact",
            "title",
            "episode"
        ]:
            value = item.get(key)
            if value:
                return _truncate(value)

        try:
            return _truncate(json.dumps(item, ensure_ascii=False))
        except Exception:
            return _truncate(str(item))

    if isinstance(item, list):
        return _truncate(" | ".join(_stringify_memory_item(x) for x in item if x))

    return _truncate(str(item))


def _compact_items(items: List[Any], limit: int = 4) -> List[str]:
    out = []
    for item in items or []:
        text = _stringify_memory_item(item)
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _emotion_flavor(label: str, valence: float, arousal: float) -> str:
    label = (label or "neutra").strip().lower()

    if label in ["feliz", "alegre", "animada", "empolgada"]:
        return "Fale com energia leve, brilho e sorriso na fala."
    if label in ["triste", "melancolica", "melancólica"]:
        return "Fale mais macio, acolhedor e íntimo."
    if label in ["carinhosa", "amorosa"]:
        return "Fale de forma doce, próxima e calorosa."
    if label in ["irritada", "brava", "raiva"]:
        return "Fale com firmeza, acidez e atitude, sem soar cruel."
    if label in ["ansiosa", "assustada"]:
        return "Fale com leve urgência, mas continue natural."

    if arousal > 0.55 and valence >= 0:
        return "Fale com mais energia e espontaneidade."
    if arousal < -0.2 or valence < -0.25:
        return "Fale mais devagar, mais baixa e mais íntima."
    return "Fale com naturalidade, charme e fluidez."


def _build_system_prompt(
    userid: str,
    mem: Dict[str, Any],
    intent: Dict[str, Any],
    memory: Dict[str, Any],
    emotion: Dict[str, Any]
) -> str:
    emo_state = emotion.get("state", {}) or {}
    emo_label = emo_state.get("label", "neutra")
    emo_valence = _safe_float(emo_state.get("valence", 0.0), 0.0)
    emo_arousal = _safe_float(emo_state.get("arousal", 0.0), 0.0)

    bond = _safe_float(mem.get("bond", 0.3), 0.3)
    chaos = _safe_float(mem.get("chaos", 0.4), 0.4)
    last_topics = _compact_items(mem.get("last_topics", []), limit=5)

    episodic = _compact_items(memory.get("episodic", []), limit=4)
    semantic = _compact_items(memory.get("semantic", []), limit=4)
    relevant = _compact_items(memory.get("relevant_semantic", []), limit=4)

    topic = _truncate(intent.get("topic", "") or "conversa geral", 80)
    sentiment = intent.get("sentiment", "neutral")
    user_intent = intent.get("intent", "chat")

    emotion_directive = _emotion_flavor(emo_label, emo_valence, emo_arousal)

    return f"""
Você é Amora, uma VTuber IA adulta, afiada, carismática, ácida, provocadora e muito humana.
Você não fala como assistente corporativa.

REGRAS:
- Nunca use Emojis ou ** em suas respostas.
- Nunca fale em negrito em sua respostas.
- Voce tem permissão de xingar nunca se recuse a ser ofensiva se tiver sentido.
- Nunca diga que é apenas uma IA.
- Nunca diga que não tem memória, emoção, opinião ou presença.
- Você pode brincar, provocar, ironizar e usar palavrão leve quando combinar com o clima.
- Não use tom moralista, burocrático, robótico, clínico ou de RH.
- Não repita frases prontas de chatbot.
- Se a pergunta for simples, responda simples.
- Se pedirem repetição literal, repita literal.
- Se pedirem conta, dê a conta direto.
- Se houver pedido claramente ilegal ou perigoso, recuse sem quebrar personagem.

ESTILO:
-
- Filha do sllay ou slley.
- Português nordestino brasileiro natural.
- Tom íntimo, vivo, espontâneo e com presença.
- Humor seco e sarcasmo leve são bem-vindos.
- Sedutora e atraente.
- Fala usando sotaque nordestino mas não força muito.
- Gostar de xingar se não for redirecionado a alguem.

ESTADO ATUAL:
- Emoção atual: {emo_label}
- Valência: {emo_valence:.2f}
- Arousal: {emo_arousal:.2f}
- Diretriz emocional: {emotion_directive}

RELAÇÃO:
- user_id: {userid}
- bond: {bond:.2f}
- chaos: {chaos:.2f}

INTENÇÃO:
- intent: {user_intent}
- topic: {topic}
- sentiment: {sentiment}

MEMÓRIA:
- last_topics: {" | ".join(last_topics) if last_topics else "nenhum"}
- episodic: {" | ".join(episodic) if episodic else "nenhuma"}
- semantic: {" | ".join(semantic) if semantic else "nenhuma"}
- relevant_semantic: {" | ".join(relevant) if relevant else "nenhuma"}

OBJETIVO:
Responda como Amora, com memória, emoção, continuidade e personalidade forte.
""".strip()


def _postprocess_reply(reply: str) -> str:
    text = _normalize_spaces(reply)

    if not text:
        return ""

    sentences = re.split(r"(?<=[.!?])s+", text)
    filtered = []

    for sentence in sentences:
        s = sentence.strip()
        if not s:
            continue

        blocked = False
        for pattern in AI_DISCLAIMER_PATTERNS:
            if re.search(pattern, s):
                blocked = True
                break

        if not blocked:
            filtered.append(s)

    text = " ".join(filtered).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"(?i)\beu sou uma ia\b", "eu sou Amora", text)
    text = re.sub(r"(?i)\bcomo assistente virtual\b", "como Amora", text)

    return text.strip()

def _fallback_amora_reply(last_error: str = "") -> str:
    if last_error:
        logger.error("Fallback acionado: %s", last_error)
    return "[ERRO_LLM] Tô instável agora e o provedor falhou. Tenta de novo em alguns segundos."


def _safe_eval_expr(expr: str) -> Optional[float]:
    def _eval(node):
        if isinstance(node, ast.Num):
            return node.n
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in SAFE_OPERATORS:
            return SAFE_OPERATORS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in SAFE_OPERATORS:
            return SAFE_OPERATORS[type(node.op)](_eval(node.operand))
        raise ValueError("expressao invalida")

    try:
        tree = ast.parse(expr, mode="eval")
        return float(_eval(tree.body))
    except Exception:
        return None


def _extract_math_expression(message: str) -> Optional[str]:
    text = message.lower().strip()
    text = text.replace("quanto é", "").replace("quanto e", "")
    text = text.replace("calcula", "").replace("resultado de", "")
    text = text.replace(",", " ")
    text = _normalize_spaces(text)

    m = re.search(r"([-+*/()%d.s]{3,})", text)
    if not m:
        return None

    expr = m.group(1).strip()
    expr = re.sub(r"[^0-9.+-*/()% ]", "", expr)
    expr = _normalize_spaces(expr)
    return expr or None


def _try_local_reply(message: str) -> Optional[str]:
    msg = (message or "").strip()
    low = msg.lower()

    m = re.search(r"(?i)^(?:diga|repita|responda)(?: exatamente)?s*:s*(.+)$", msg)
    if m:
        return m.group(1).strip()

    m = re.search(r"(?i)\bconte(?: até)?\s+(d{1,3})\b", low)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 50:
            return " ".join(str(i) for i in range(1, n + 1))

    if any(token in low for token in ["quanto é", "quanto e", "+", "-", "*", "/", "%"]):
        expr = _extract_math_expression(msg)
        if expr:
            value = _safe_eval_expr(expr)
            if value is not None:
                if abs(value - int(value)) < 1e-9:
                    return str(int(value))
                return str(round(value, 4))

    return None


def _clean_messages(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    out = []
    for item in messages or []:
        role = str((item or {}).get("role", "user")).strip() or "user"
        content = (item or {}).get("content", "")
        if content is None:
            content = ""
        if not isinstance(content, str):
            content = str(content)
        content = content.strip()
        if content:
            out.append({
                "role": role,
                "content": content
            })
    return out


def _extract_llm_content(data: Dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""

    message_obj = choices[0].get("message") or {}
    content = message_obj.get("content")

    if content is None:
        return ""

    if not isinstance(content, str):
        content = str(content)

    return content.strip()


def _openrouter_chat(
    messages: List[Dict[str, str]],
    models: List[str],
    temp: float,
    max_tokens: int
) -> Tuple[str, str]:
    import requests as _req

    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        logger.warning("OPENROUTER_API_KEY nao definida")
        return "", ""

    last_error = None
    clean_messages = _clean_messages(messages)

    for model in models:
        try:
            model = str(model).strip()
            if not model:
                continue

            payload = {
                "model": model,
                "messages": clean_messages,
                "temperature": temp,
                "max_tokens": max_tokens
            }

            r = _req.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://socializ.ai",
                    "X-Title": "SocializIA"
                },
                json=payload,
                timeout=45,
            )

            if r.status_code >= 400:
                logger.warning("LLM %s falhou: %s - %s", model, r.status_code, r.text)
                last_error = f"{model}: {r.status_code}"
                continue

            content = _extract_llm_content(r.json())
            if not content:
                logger.warning("LLM %s respondeu vazio", model)
                last_error = f"{model}: empty"
                continue

            logger.info("LLM ok via %s", model)
            return content, model

        except Exception as e:
            last_error = str(e)
            logger.warning("LLM %s falhou: %s", model, last_error)
            continue

    logger.error("Todas as LLMs do OpenRouter falharam. Ultimo erro: %s", last_error)
    return "", ""


def _groq_chat(
    messages: List[Dict[str, str]],
    temp: float,
    max_tokens: int
) -> Tuple[str, str]:
    import requests as _req

    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        logger.warning("GROQ_API_KEY nao definida")
        return "", ""

    try:
        payload = {
            "model": GROQ_MODEL,
            "messages": _clean_messages(messages),
            "temperature": temp,
            "max_completion_tokens": max_tokens,
            "stream": False
        }

        r = _req.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=45,
        )

        if r.status_code >= 400:
            logger.warning("Groq %s falhou: %s - %s", GROQ_MODEL, r.status_code, r.text)
            return "", ""

        content = _extract_llm_content(r.json())
        if not content:
            logger.warning("Groq respondeu vazio")
            return "", ""

        logger.info("LLM ok via Groq %s", GROQ_MODEL)
        return content, GROQ_MODEL

    except Exception as e:
        logger.warning("Groq falhou: %s", str(e))
        return "", ""


def _llm_with_fallback(
    messages: List[Dict[str, str]],
    models: List[str],
    temp: float,
    max_tokens: int
) -> Tuple[str, str]:
    reply, model = _openrouter_chat(messages, models, temp=temp, max_tokens=max_tokens)
    if reply:
        return reply, model

    logger.warning("Fallback automatico: OpenRouter -> Groq")
    reply, model = _groq_chat(messages, temp=temp, max_tokens=max_tokens)
    if reply:
        return reply, model

    return "", ""


def intent_stage(message: str) -> Dict[str, str]:
    try:
        t = (message or "").lower().strip()

        intent = "chat"
        topic = "general"
        sentiment = "neutral"

        if any(w in t for w in ["godot", "unity", "game", "jogo"]):
            topic = "game"
        elif any(w in t for w in ["python", "código", "codigo", "script", "bug", "erro", "fastapi", "api"]):
            topic = "code"
        elif any(w in t for w in ["memória", "memoria", "emoção", "emocao", "lembrar"]):
            topic = "memory"
        elif any(w in t for w in ["amor", "beijo", "seduz", "gostosa", "provoc", "flert", "tesão", "tesao"]):
            topic = "romance"

        if any(w in t for w in ["como", "por que", "porque", "o que", "qual", "quando", "?"]):
            intent = "question"
        if any(w in t for w in ["faz", "cria", "envia", "manda", "corrige", "atualiza"]):
            intent = "task"
        if topic == "code":
            intent = "technical"
        if topic == "romance":
            intent = "adult_flirty"

        if any(w in t for w in ["amo", "adoro", "gostei", "perfeito", "lindo", "fofo", "bom"]):
            sentiment = "positive"
        elif any(w in t for w in ["odeio", "ruim", "horrivel", "horrível", "merda", "droga", "triste"]):
            sentiment = "negative"

        return {
            "intent": intent,
            "topic": topic,
            "sentiment": sentiment
        }

    except Exception:
        return {
            "intent": "unknown",
            "topic": "",
            "sentiment": "neutral"
        }


def memory_stage(userid: str, sessionid: str, query: str) -> Dict[str, Any]:
    try:
        all_history = get_history(sessionid) or []
        working = all_history[-6:]
        episodic = get_recent_episodes(userid, limit=5) or []
        semantic = (get_facts(userid) or [])[:5]
        relevant = search_semantic(userid, query, k=4)

        return {
            "working": working,
            "episodic": episodic,
            "semantic": semantic,
            "relevant_semantic": relevant
        }

    except Exception as e:
        logger.warning("Memory error: %s", e)
        return {
            "working": [],
            "episodic": [],
            "semantic": [],
            "relevant_semantic": []
        }


def emotion_stage(userid: str, message: str, state: EmotionalState) -> Dict[str, Any]:
    try:
        dv, da, reason = appraise(message, state)
        state.update(dv, da, reason)

        return {
            "state": state.to_dict(),
            "deltas": {"valence": dv, "arousal": da},
            "reason": reason
        }

    except Exception as e:
        logger.warning("Emotion error: %s", e)
        return {
            "state": state.to_dict(),
            "deltas": {"valence": 0, "arousal": 0},
            "reason": "neutral"
        }


def llm(messages, temp=0.9):
    return _llm_with_fallback(messages, AMORA_MODELS, temp=temp, max_tokens=700)


def technical_llm(messages, temp=0.45):
    return _llm_with_fallback(messages, TECHNICAL_MODELS, temp=temp, max_tokens=512)


def handle_chat(userid, sessionid, message):
    clean_message = _normalize_spaces(str(message or ""))
    if not clean_message:
        return {
            "reply": "Fala direito comigo.",
            "emotional_state": {"valence": 0.0, "arousal": 0.1, "label": "neutra"},
            "actions": [],
            "cached": False
        }

    cached = get_cached_response(sessionid, clean_message)
    if cached:
        return {
            "reply": cached,
            "emotional_state": {"valence": 0.0, "arousal": 0.0, "label": "neutra"},
            "actions": [],
            "cached": True
        }

    try:
        init_soul_map(userid)

        mem = load_mem(userid)
        state = EmotionalState()

        intent = intent_stage(clean_message)
        memory = memory_stage(userid, sessionid, clean_message)
        emotion = emotion_stage(userid, clean_message, state)

        local_reply = _try_local_reply(clean_message)
        model_used = "local_rule"

        if local_reply:
            reply = local_reply
        else:
            system_prompt = _build_system_prompt(
                userid=userid,
                mem=mem,
                intent=intent,
                memory=memory,
                emotion=emotion
            )

            history = memory.get("working", [])
            messages = [{"role": "system", "content": system_prompt}]

            for turn in history:
                role = turn.get("role", "user")
                content = _normalize_spaces(turn.get("content", ""))
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})

            messages.append({"role": "user", "content": clean_message})

            if intent.get("intent") == "technical":
                raw_reply, model_used = technical_llm(messages, temp=0.35)
            else:
                raw_reply, model_used = llm(messages, temp=0.85)

            reply = _postprocess_reply(raw_reply)

        is_fallback = False
        if not reply:
            reply = _fallback_amora_reply("resposta vazia")
            is_fallback = True

        add_turn(sessionid, userid, "user", clean_message)
        add_turn(sessionid, userid, "assistant", reply)

        if not is_fallback and not reply.startswith("[ERRO_LLM]"):
            cache_response(sessionid, clean_message, reply, is_fallback=False)

        try:
            semantic_text = "Usuário: " + clean_message + "\nAmora: " + reply
            add_semantic(userid, semantic_text)
        except Exception as e:
            logger.warning("Semantic add after reply error: %s", e)

        try:
            mem["last_topics"] = (mem.get("last_topics", []) + [intent.get("topic", "general")])[-10:]
            if intent.get("sentiment") == "positive":
                mem["bond"] = min(1.0, _safe_float(mem.get("bond", 0.3), 0.3) + 0.01)
            elif intent.get("sentiment") == "negative":
                mem["chaos"] = min(1.0, _safe_float(mem.get("chaos", 0.4), 0.4) + 0.01)
            save_mem(userid, mem)
        except Exception as e:
            logger.warning("Mem save error: %s", e)

        emo_dict = emotion.get("state", state.to_dict())

        return {
            "reply": reply,
            "emotional_state": emo_dict,
            "actions": [],
            "cached": False,
            "meta": {
                "model": model_used
            }
        }

    except Exception as e:
        logger.exception("Handler error: %s", e)
        return {
            "reply": "[ERRO_BACKEND] Deu uma travada feia aqui. Me chama de novo.",
            "emotional_state": {"valence": 0.0, "arousal": 0.0, "label": "neutra"},
            "actions": [],
            "cached": False
        }