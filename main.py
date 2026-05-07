from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request, Response
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import os
import io
import wave
import numpy as np
from pathlib import Path
import unicodedata
from api.voice import router as voice_router
from core.chat_handler import handle_chat
from security import protect


@asynccontextmanager
async def lifespan(app: FastAPI):
    from memory.db import init_db
    init_db()
    print("[DB] Tabelas inicializadas.")
    yield


app = FastAPI(title="Socializ Core", version="0.0.9", lifespan=lifespan)
app.include_router(voice_router)

# =========================
# MODELS
# =========================

class ChatRequest(BaseModel):
    userid: str
    sessionid: str
    message: str


class TTSRequest(BaseModel):
    text: str
    voice: str = "pt_br_female"
    user_id: str = "default"
    style: str = "auto"
    effects: List[str] = Field(default_factory=list)
    rate: Optional[str] = None
    pitch: Optional[str] = None
    volume: Optional[str] = None
    emotion_label: Optional[str] = None
    emotional_state: Optional[Dict[str, Any]] = None


class EmotionalState(BaseModel):
    valence: float
    arousal: float
    label: str


class ChatResponse(BaseModel):
    reply: str
    emotional_state: EmotionalState
    actions: List[Dict[str, Any]] = Field(default_factory=list)


# =========================
# VOICE CONFIG
# =========================

VOICE_ALIASES = {
    "default": "pt_br_female",
    "auto": "pt_br_female",

    "pt_br_female": "pt_br_female",
    "female": "pt_br_female",
    "feminina": "pt_br_female",
    "mulher": "pt_br_female",

    "pt_br_male": "pt_br_male",
    "male": "pt_br_male",
    "masculina": "pt_br_male",
    "homem": "pt_br_male",

    # compatibilidade com valor antigo
    "pt_BR-faber-medium": "pt_br_male",
    "pt_br-faber-medium": "pt_br_male",
}

VOICE_PROVIDER_MAP = {
    "pt_br_female": "pt-BR-FranciscaNeural",
    "pt_br_male": "pt-BR-AntonioNeural",
}

STYLE_PRESETS = {
    "auto": {
        "voice_id": "pt_br_female",
        "rate_pct": -4,
        "pitch_hz": 8,
        "volume_pct": 0,
        "description": "Ajuste automatico guiado por emocao."
    },
    "default": {
        "voice_id": "pt_br_female",
        "rate_pct": -4,
        "pitch_hz": 8,
        "volume_pct": 0,
        "description": "Preset feminino equilibrado."
    },
    "female_natural": {
        "voice_id": "pt_br_female",
        "rate_pct": -6,
        "pitch_hz": 10,
        "volume_pct": 0,
        "description": "Feminina mais natural e menos apressada."
    },
    "female_soft": {
        "voice_id": "pt_br_female",
        "rate_pct": -10,
        "pitch_hz": 14,
        "volume_pct": -2,
        "description": "Feminina delicada e macia."
    },
    "female_warm": {
        "voice_id": "pt_br_female",
        "rate_pct": -8,
        "pitch_hz": 6,
        "volume_pct": 2,
        "description": "Feminina acolhedora e humana."
    },
    "female_bright": {
        "voice_id": "pt_br_female",
        "rate_pct": -2,
        "pitch_hz": 16,
        "volume_pct": 2,
        "description": "Feminina mais viva e brilhante."
    },
    "male_natural": {
        "voice_id": "pt_br_male",
        "rate_pct": -4,
        "pitch_hz": 0,
        "volume_pct": 0,
        "description": "Masculina natural."
    },
    "male_warm": {
        "voice_id": "pt_br_male",
        "rate_pct": -8,
        "pitch_hz": -6,
        "volume_pct": 2,
        "description": "Masculina quente e menos seca."
    }
}

EFFECT_DELTAS = {
    "soft": {"rate_pct": -3, "pitch_hz": 2, "volume_pct": -1},
    "cute": {"rate_pct": 2, "pitch_hz": 6, "volume_pct": -1},
    "warm": {"rate_pct": -4, "pitch_hz": -2, "volume_pct": 2},
    "bright": {"rate_pct": 1, "pitch_hz": 4, "volume_pct": 2},
    "calm": {"rate_pct": -6, "pitch_hz": -1, "volume_pct": -1},
    "boost": {"rate_pct": 0, "pitch_hz": 0, "volume_pct": 4},
    "robot_soft": {"rate_pct": -8, "pitch_hz": -8, "volume_pct": 0},
    "phone": {"rate_pct": 0, "pitch_hz": 0, "volume_pct": -3}
}

EMOTION_PRESETS = {
    "neutra": {"style": "female_natural", "rate_pct": 0, "pitch_hz": 0, "volume_pct": 0, "effects": []},
    "neutral": {"style": "female_natural", "rate_pct": 0, "pitch_hz": 0, "volume_pct": 0, "effects": []},
    "calma": {"style": "female_soft", "rate_pct": -4, "pitch_hz": 1, "volume_pct": -1, "effects": ["soft", "calm"]},
    "calm": {"style": "female_soft", "rate_pct": -4, "pitch_hz": 1, "volume_pct": -1, "effects": ["soft", "calm"]},
    "feliz": {"style": "female_bright", "rate_pct": 4, "pitch_hz": 10, "volume_pct": 2, "effects": ["bright"]},
    "alegre": {"style": "female_bright", "rate_pct": 4, "pitch_hz": 10, "volume_pct": 2, "effects": ["bright"]},
    "animada": {"style": "female_bright", "rate_pct": 6, "pitch_hz": 12, "volume_pct": 3, "effects": ["bright"]},
    "empolgada": {"style": "female_bright", "rate_pct": 7, "pitch_hz": 14, "volume_pct": 3, "effects": ["bright"]},
    "triste": {"style": "female_warm", "rate_pct": -10, "pitch_hz": -4, "volume_pct": -4, "effects": ["soft"]},
    "melancolica": {"style": "female_warm", "rate_pct": -10, "pitch_hz": -4, "volume_pct": -4, "effects": ["soft"]},
    "carinhosa": {"style": "female_warm", "rate_pct": -6, "pitch_hz": 6, "volume_pct": 1, "effects": ["soft", "warm"]},
    "amorosa": {"style": "female_warm", "rate_pct": -6, "pitch_hz": 6, "volume_pct": 1, "effects": ["soft", "warm"]},
    "irritada": {"style": "female_natural", "rate_pct": 8, "pitch_hz": -3, "volume_pct": 4, "effects": ["boost"]},
    "brava": {"style": "female_natural", "rate_pct": 10, "pitch_hz": -5, "volume_pct": 5, "effects": ["boost"]},
    "raiva": {"style": "female_natural", "rate_pct": 10, "pitch_hz": -6, "volume_pct": 5, "effects": ["boost"]},
    "ansiosa": {"style": "female_natural", "rate_pct": 7, "pitch_hz": 4, "volume_pct": 1, "effects": []},
    "assustada": {"style": "female_bright", "rate_pct": 8, "pitch_hz": 12, "volume_pct": 1, "effects": []},
}


# =========================
# VOICE HELPERS
# =========================

def _normalize_text(text: str) -> str:
    return " ".join((text or "").strip().split())


def _normalize_label(label: Optional[str]) -> str:
    raw = (label or "").strip().lower()
    if not raw:
        return ""
    raw = unicodedata.normalize("NFKD", raw)
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    return raw


def _resolve_voice_alias(voice: Optional[str]) -> str:
    raw = (voice or "").strip()
    if not raw:
        return "pt_br_female"
    return VOICE_ALIASES.get(raw, raw)


def _format_percent(value: int) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value}%"


def _format_hz(value: int) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value}Hz"


def _coerce_percent(value: Optional[str], fallback: int) -> str:
    if value is None:
        return _format_percent(fallback)

    s = str(value).strip()
    if not s:
        return _format_percent(fallback)

    if s.endswith("%"):
        if s.startswith("+") or s.startswith("-"):
            return s
        return f"+{s}"

    try:
        n = int(float(s))
        return _format_percent(n)
    except Exception:
        return _format_percent(fallback)


def _coerce_hz(value: Optional[str], fallback: int) -> str:
    if value is None:
        return _format_hz(fallback)

    s = str(value).strip()
    if not s:
        return _format_hz(fallback)

    if s.lower().endswith("hz"):
        if s.startswith("+") or s.startswith("-"):
            return s
        return f"+{s}"

    try:
        n = int(float(s))
        return _format_hz(n)
    except Exception:
        return _format_hz(fallback)


def _resolve_style(style: Optional[str]) -> Dict[str, Any]:
    key = (style or "auto").strip()
    return STYLE_PRESETS.get(key, STYLE_PRESETS["default"])


def _merge_unique(items_a: List[str], items_b: List[str]) -> List[str]:
    out = []
    for item in (items_a or []) + (items_b or []):
        key = (item or "").strip()
        if key and key not in out:
            out.append(key)
    return out


def _clamp_int(n: float, minimum: int, maximum: int) -> int:
    return int(max(minimum, min(maximum, round(n))))


def _emotion_payload(emotion_label: Optional[str], emotional_state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    label = _normalize_label(emotion_label)

    if not label and isinstance(emotional_state, dict):
        label = _normalize_label(emotional_state.get("label"))

    preset = EMOTION_PRESETS.get(label, EMOTION_PRESETS.get("neutra"))

    valence = 0.0
    arousal = 0.0

    if isinstance(emotional_state, dict):
        try:
            valence = float(emotional_state.get("valence", 0.0) or 0.0)
        except Exception:
            valence = 0.0

        try:
            arousal = float(emotional_state.get("arousal", 0.0) or 0.0)
        except Exception:
            arousal = 0.0

    dynamic_rate = _clamp_int(arousal * 8.0, -8, 8)
    dynamic_pitch = _clamp_int(valence * 6.0, -6, 6)
    dynamic_volume = _clamp_int(arousal * 4.0, -4, 4)

    return {
        "label": label or "neutra",
        "style": preset["style"],
        "rate_pct": int(preset["rate_pct"]) + dynamic_rate,
        "pitch_hz": int(preset["pitch_hz"]) + dynamic_pitch,
        "volume_pct": int(preset["volume_pct"]) + dynamic_volume,
        "effects": preset.get("effects", []),
        "valence": valence,
        "arousal": arousal
    }


def _resolve_voice_payload(
    voice: Optional[str],
    style: Optional[str],
    effects: List[str],
    rate: Optional[str],
    pitch: Optional[str],
    volume: Optional[str],
    emotion_label: Optional[str],
    emotional_state: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    requested_voice = (voice or "").strip()
    resolved_voice = _resolve_voice_alias(requested_voice)

    emotion = _emotion_payload(emotion_label, emotional_state)

    if (style or "auto").strip() == "auto":
        preset = _resolve_style(emotion["style"])
        style_key = emotion["style"]
    else:
        style_key = (style or "default").strip()
        preset = _resolve_style(style_key)

    if requested_voice in ("", "default", "auto"):
        resolved_voice = preset["voice_id"]

    rate_pct = int(preset["rate_pct"]) + int(emotion["rate_pct"])
    pitch_hz = int(preset["pitch_hz"]) + int(emotion["pitch_hz"])
    volume_pct = int(preset["volume_pct"]) + int(emotion["volume_pct"])

    applied_effects = _merge_unique(emotion.get("effects", []), effects or [])

    unknown_effects = []
    for effect in applied_effects:
        delta = EFFECT_DELTAS.get(effect)
        if not delta:
            unknown_effects.append(effect)
            continue

        rate_pct += int(delta.get("rate_pct", 0))
        pitch_hz += int(delta.get("pitch_hz", 0))
        volume_pct += int(delta.get("volume_pct", 0))

    final_rate = _coerce_percent(rate, rate_pct)
    final_pitch = _coerce_hz(pitch, pitch_hz)
    final_volume = _coerce_percent(volume, volume_pct)

    provider_voice = VOICE_PROVIDER_MAP.get(resolved_voice, VOICE_PROVIDER_MAP["pt_br_female"])

    return {
        "requested_voice_id": requested_voice or "auto",
        "resolved_voice_id": resolved_voice,
        "provider_voice": provider_voice,
        "style": style_key if style_key in STYLE_PRESETS else "default",
        "style_description": STYLE_PRESETS.get(style_key, STYLE_PRESETS["default"])["description"],
        "emotion_label": emotion["label"],
        "valence": emotion["valence"],
        "arousal": emotion["arousal"],
        "effects": applied_effects,
        "unknown_effects": unknown_effects,
        "rate": final_rate,
        "pitch": final_pitch,
        "volume": final_volume
    }


# =========================
# ROUTES
# =========================

@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.0.9"}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request, _=Depends(protect)):
    result = handle_chat(req.userid, req.sessionid, req.message)

    emo_raw = (
        result.get("emotional_state")
        or {"valence": 0.0, "arousal": 0.0, "label": "neutra"}
    )
    emo = EmotionalState(**emo_raw)

    return ChatResponse(
        reply=result.get("reply", ""),
        emotional_state=emo,
        actions=result.get("actions", []),
    )


@app.post("/voice/tts")
async def voice_tts(req: TTSRequest, _=Depends(protect)):
    text = _normalize_text(req.text)

    if not text:
        return Response(
            content='{"error": "Texto vazio"}',
            status_code=400,
            media_type="application/json"
        )

    voice_meta = _resolve_voice_payload(
        voice=req.voice,
        style=req.style,
        effects=req.effects,
        rate=req.rate,
        pitch=req.pitch,
        volume=req.volume,
        emotion_label=req.emotion_label,
        emotional_state=req.emotional_state
    )

    try:
        import edge_tts

        communicate = edge_tts.Communicate(
            text=text,
            voice=voice_meta["provider_voice"],
            rate=voice_meta["rate"],
            pitch=voice_meta["pitch"],
            volume=voice_meta["volume"]
        )

        audio_buffer = bytearray()

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.extend(chunk["data"])

        if not audio_buffer or len(audio_buffer) < 100:
            return Response(
                content='{"error": "Audio vazio ou muito pequeno"}',
                status_code=500,
                media_type="application/json"
            )

        return Response(
            content=bytes(audio_buffer),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": 'inline; filename="tts_output.mp3"',
                "X-TTS-Voice": voice_meta["provider_voice"],
                "X-Voice-Id": voice_meta["resolved_voice_id"],
                "X-Voice-Style": voice_meta["style"],
                "X-Voice-Emotion": voice_meta["emotion_label"],
                "X-Voice-Rate": voice_meta["rate"],
                "X-Voice-Pitch": voice_meta["pitch"],
                "X-Voice-Volume": voice_meta["volume"],
                "X-Voice-Effects": ",".join(voice_meta["effects"])
            }
        )

    except ImportError:
        return Response(
            content='{"error": "edge-tts nao instalado no servidor"}',
            status_code=503,
            media_type="application/json"
        )

    except Exception as e:
        return Response(
            content=f'{{"error": "{str(e)}"}}',
            status_code=500,
            media_type="application/json"
        )


@app.get("/voice/tts/info")
async def voice_tts_info(_=Depends(protect)):
    return {
        "provider": "edge-tts",
        "default_voice_id": "pt_br_female",
        "voices_supported": list(VOICE_PROVIDER_MAP.keys()),
        "styles": STYLE_PRESETS,
        "effects_supported": list(EFFECT_DELTAS.keys()),
        "emotion_profiles": list(EMOTION_PRESETS.keys())
    }


@app.get("/memory/state")
async def memory_state(user_id: str, request: Request, _=Depends(protect)):
    from memory.emotional_state_db import load_state
    state = load_state(user_id)
    if not state:
        return {"user_id": user_id, "found": False, "state": None}
    return {"user_id": user_id, "found": True, "state": state}


@app.get("/memory/facts")
async def memory_facts(
    user_id: str,
    subject: str = None,
    request: Request = None,
    _=Depends(protect)
):
    from memory.semantic import get_facts
    facts = get_facts(user_id, subject=subject)
    return {"user_id": user_id, "count": len(facts), "facts": facts}