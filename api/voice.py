from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import os
import re
import base64
import html
import unicodedata

import httpx

from security import protect


router = APIRouter(prefix="/bridge/voice", tags=["voice"])


# =========================
# MODELS
# =========================

class VoiceAskRequest(BaseModel):
    userid: str
    sessionid: str
    message: str
    auto_tts: bool = True
    voice_id: str = "pt_br_female"
    style: str = "auto"
    effects: List[str] = Field(default_factory=list)
    use_emotion_voice: bool = True

    # TRUE = retorna mp3 bruto
    raw_audio_response: bool = False

    # fallback opcional
    return_audio_base64: bool = True


class VoiceChatRequest(BaseModel):
    userid: str
    sessionid: str
    message: str


class BridgeTTSRequest(BaseModel):
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

    # TRUE = retorna mp3 bruto
    raw_audio_response: bool = True

    # fallback opcional
    return_audio_base64: bool = False


# =========================
# CONFIG
# =========================

BACKEND_URL = os.environ.get(
    "BACKEND_URL",
    "https://web-production-fc5d4.up.railway.app"
).rstrip("/")


EMOJI_MAP = {
    "😊": "hehe",
    "☺️": "hmm",
    "😄": "hahaha",
    "😁": "rsrs",
    "😌": "hmm",
    "😉": "psiu",
    "😏": "hmm",
    "😍": "ah",
    "🥰": "ah",
    "😘": "beijo",
    "❤️": "",
    "❤": "",
    "💖": "",
    "💕": "",
    "🔥": "uau",
    "😢": "hmm",
    "😭": "...",
    "😡": "olha",
    "😳": "ahn",
    "😈": "hmm",
}


VOICE_ALIASES = {
    "default": "pt_br_female",
    "auto": "pt_br_female",

    "pt_br_female": "pt_br_female",
    "female": "pt_br_female",
    "feminina": "pt_br_female",
    "amora": "pt_br_female",

    "pt_br_male": "pt_br_male",
    "male": "pt_br_male",
    "masculina": "pt_br_male",

    # compatibilidade
    "pt_BR-faber-medium": "pt_br_male",
    "pt_br-faber-medium": "pt_br_male",
}


STYLE_PRESETS = {
    "auto": {
        "rate_pct": -5,
        "pitch_hz": 4,
        "volume_pct": 0
    },

    "default": {
        "rate_pct": -5,
        "pitch_hz": 4,
        "volume_pct": 0
    },

    "soft": {
        "rate_pct": -8,
        "pitch_hz": 3,
        "volume_pct": -1
    },

    "warm": {
        "rate_pct": -7,
        "pitch_hz": 2,
        "volume_pct": 1
    },

    "bright": {
        "rate_pct": -2,
        "pitch_hz": 6,
        "volume_pct": 1
    },

    "calm": {
        "rate_pct": -10,
        "pitch_hz": 1,
        "volume_pct": -2
    }
}


EFFECT_DELTAS = {
    "soft": {
        "rate_pct": -2,
        "pitch_hz": 1,
        "volume_pct": -1
    },

    "warm": {
        "rate_pct": -2,
        "pitch_hz": -1,
        "volume_pct": 1
    },

    "bright": {
        "rate_pct": 1,
        "pitch_hz": 2,
        "volume_pct": 1
    },

    "calm": {
        "rate_pct": -3,
        "pitch_hz": -1,
        "volume_pct": -1
    },

    "cute": {
        "rate_pct": 1,
        "pitch_hz": 3,
        "volume_pct": 0
    },

    "sensual": {
        "rate_pct": -4,
        "pitch_hz": -1,
        "volume_pct": -1
    },

    "firm": {
        "rate_pct": 2,
        "pitch_hz": -2,
        "volume_pct": 2
    }
}


EMOTION_PRESETS = {
    "neutra": {
        "rate_pct": 0,
        "pitch_hz": 0,
        "volume_pct": 0,
        "effects": []
    },

    "neutral": {
        "rate_pct": 0,
        "pitch_hz": 0,
        "volume_pct": 0,
        "effects": []
    },

    "feliz": {
        "rate_pct": 2,
        "pitch_hz": 2,
        "volume_pct": 1,
        "effects": ["bright"]
    },

    "alegre": {
        "rate_pct": 2,
        "pitch_hz": 2,
        "volume_pct": 1,
        "effects": ["bright"]
    },

    "animada": {
        "rate_pct": 3,
        "pitch_hz": 3,
        "volume_pct": 2,
        "effects": ["bright"]
    },

    "carinhosa": {
        "rate_pct": -3,
        "pitch_hz": 1,
        "volume_pct": -1,
        "effects": ["soft", "warm"]
    },

    "amorosa": {
        "rate_pct": -3,
        "pitch_hz": 1,
        "volume_pct": -1,
        "effects": ["soft", "warm"]
    },

    "triste": {
        "rate_pct": -4,
        "pitch_hz": -1,
        "volume_pct": -3,
        "effects": ["soft"]
    },

    "melancolica": {
        "rate_pct": -4,
        "pitch_hz": -1,
        "volume_pct": -3,
        "effects": ["soft"]
    },

    "irritada": {
        "rate_pct": 2,
        "pitch_hz": -2,
        "volume_pct": 2,
        "effects": ["firm"]
    },

    "brava": {
        "rate_pct": 2,
        "pitch_hz": -2,
        "volume_pct": 2,
        "effects": ["firm"]
    },

    "ansiosa": {
        "rate_pct": 2,
        "pitch_hz": 1,
        "volume_pct": 0,
        "effects": []
    },

    "assustada": {
        "rate_pct": 3,
        "pitch_hz": 2,
        "volume_pct": 0,
        "effects": []
    }
}


# =========================
# HELPERS
# =========================

def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _strip_accents(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    return "".join(
        ch for ch in raw
        if not unicodedata.combining(ch)
    )


def _normalize_emotion_label(label: Optional[str]) -> str:
    return _strip_accents(
        (label or "").strip().lower()
    )


def _voice_alias(voice: Optional[str]) -> str:
    raw = (voice or "").strip()

    if not raw:
        return "pt_br_female"

    return VOICE_ALIASES.get(raw, raw)


def _format_percent(n: int) -> str:
    return f"{'+' if n >= 0 else ''}{n}%"


def _format_hz(n: int) -> str:
    return f"{'+' if n >= 0 else ''}{n}Hz"


def _clamp(n: float, min_v: int, max_v: int) -> int:
    return int(
        max(min_v, min(max_v, round(n)))
    )


def _replace_emojis(text: str) -> str:
    out = text or ""

    for emoji, repl in EMOJI_MAP.items():
        out = out.replace(emoji, repl)

    return out


def _remove_markdown(text: str) -> str:
    t = text or ""

    # bold
    t = re.sub(r"\*\*(.*?)\*\*", r"\1", t)

    # italic
    t = re.sub(r"\*(.*?)\*", r"\1", t)

    # inline code
    t = re.sub(r"`([^`]*)`", r"\1", t)

    # titles
    t = re.sub(r"#+\s*", "", t)

    # markdown links
    t = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", t)

    return t


def _soften_text_for_tts(text: str) -> str:
    t = html.unescape(text or "")

    t = _replace_emojis(t)
    t = _remove_markdown(t)

    # CAPS
    t = re.sub(
        r"\b[A-Z]{2,}\b",
        lambda m: m.group(0).lower(),
        t
    )

    # aspas
    t = re.sub(r'["“”]', "", t)
    t = re.sub(r"[‘’']", "", t)

    # traços
    t = re.sub(r"\s*-\s*", ", ", t)

    # parenteses
    t = re.sub(r"[\(\)\{\}\[\]]", "", t)

    # risadas
    t = re.sub(
        r"\bkkk+\b",
        " hehe ",
        t,
        flags=re.IGNORECASE
    )

    t = re.sub(
        r"\brs+\b",
        " hehe ",
        t,
        flags=re.IGNORECASE
    )

    # espaços antes de pontuação
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)

    # espaço após pontuação
    t = re.sub(
        r"([.!?])([A-Za-zÀ-ÿ0-9])",
        r"\1 \2",
        t
    )

    t = _normalize_spaces(t)

    if len(t) > 420:
        t = (
            t[:420]
            .rsplit(" ", 1)[0]
            .strip()
            + "..."
        )

    return t


def _emotion_to_voice(
    style: str,
    effects: List[str],
    emotion_label: Optional[str],
    emotional_state: Optional[Dict[str, Any]]
) -> Dict[str, Any]:

    base = STYLE_PRESETS.get(
        style,
        STYLE_PRESETS["default"]
    ).copy()

    label = _normalize_emotion_label(
        emotion_label
    )

    if not label and isinstance(emotional_state, dict):
        label = _normalize_emotion_label(
            emotional_state.get("label")
        )

    emo = EMOTION_PRESETS.get(
        label,
        EMOTION_PRESETS["neutra"]
    )

    valence = 0.0
    arousal = 0.0

    if isinstance(emotional_state, dict):

        try:
            valence = float(
                emotional_state.get("valence", 0.0) or 0.0
            )
        except Exception:
            valence = 0.0

        try:
            arousal = float(
                emotional_state.get("arousal", 0.0) or 0.0
            )
        except Exception:
            arousal = 0.0

    rate_pct = (
        int(base["rate_pct"])
        + int(emo["rate_pct"])
    )

    pitch_hz = (
        int(base["pitch_hz"])
        + int(emo["pitch_hz"])
    )

    volume_pct = (
        int(base["volume_pct"])
        + int(emo["volume_pct"])
    )

    dynamic_rate = _clamp(arousal * 3.0, -2, 2)
    dynamic_pitch = _clamp(valence * 2.0, -2, 2)
    dynamic_volume = _clamp(arousal * 2.0, -2, 2)

    rate_pct += dynamic_rate
    pitch_hz += dynamic_pitch
    volume_pct += dynamic_volume

    all_effects = []

    for item in (
        emo.get("effects", [])
        + (effects or [])
    ):
        name = (item or "").strip().lower()

        if name and name not in all_effects:
            all_effects.append(name)

    for effect in all_effects:
        delta = EFFECT_DELTAS.get(effect)

        if not delta:
            continue

        rate_pct += int(delta.get("rate_pct", 0))
        pitch_hz += int(delta.get("pitch_hz", 0))
        volume_pct += int(delta.get("volume_pct", 0))

    rate_pct = _clamp(rate_pct, -15, 8)
    pitch_hz = _clamp(pitch_hz, -8, 10)
    volume_pct = _clamp(volume_pct, -8, 6)

    return {
        "rate": _format_percent(rate_pct),
        "pitch": _format_hz(pitch_hz),
        "volume": _format_percent(volume_pct),
        "emotion_label": label or "neutra",
        "applied_effects": all_effects
    }


async def _call_chat(
    userid: str,
    sessionid: str,
    message: str,
    auth_header: Optional[str]
) -> Dict[str, Any]:

    headers = {
        "Content-Type": "application/json"
    }

    if auth_header:
        headers["Authorization"] = auth_header

    async with httpx.AsyncClient(
        timeout=60.0
    ) as client:

        resp = await client.post(
            f"{BACKEND_URL}/chat",
            headers=headers,
            json={
                "userid": userid,
                "sessionid": sessionid,
                "message": message
            }
        )

        resp.raise_for_status()

        return resp.json()


async def _call_tts(
    payload: Dict[str, Any],
    auth_header: Optional[str]
) -> bytes:

    headers = {
        "Content-Type": "application/json"
    }

    if auth_header:
        headers["Authorization"] = auth_header

    async with httpx.AsyncClient(
        timeout=120.0
    ) as client:

        resp = await client.post(
            f"{BACKEND_URL}/voice/tts",
            headers=headers,
            json=payload
        )

        resp.raise_for_status()

        return resp.content


# =========================
# ROUTES
# =========================

@router.get("/voices")
async def list_voices(_=Depends(protect)):
    return {
        "voices": [
            {
                "id": "pt_br_female",
                "provider_voice": "pt-BR-FranciscaNeural",
                "label": "Amora feminina"
            },
            {
                "id": "pt_br_male",
                "provider_voice": "pt-BR-AntonioNeural",
                "label": "PT-BR masculina"
            }
        ],

        "styles": list(STYLE_PRESETS.keys()),
        "effects": list(EFFECT_DELTAS.keys())
    }


@router.get("/tts/info")
async def tts_info(_=Depends(protect)):
    return {
        "provider": "edge-tts",
        "format": "audio/mpeg",
        "backend_url": BACKEND_URL
    }


@router.post("/chat")
async def voice_chat(
    req: VoiceChatRequest,
    request: Request,
    _=Depends(protect)
):

    auth_header = request.headers.get(
        "Authorization"
    )

    try:
        chat_data = await _call_chat(
            userid=req.userid,
            sessionid=req.sessionid,
            message=req.message,
            auth_header=auth_header
        )

        return chat_data

    except httpx.HTTPStatusError as e:

        return JSONResponse(
            status_code=e.response.status_code,
            content={
                "error": "chat_upstream_error",
                "detail": e.response.text
            }
        )

    except Exception as e:

        return JSONResponse(
            status_code=500,
            content={
                "error": "chat_bridge_error",
                "detail": str(e)
            }
        )


@router.post("/tts")
async def bridge_tts(
    req: BridgeTTSRequest,
    request: Request,
    _=Depends(protect)
):

    auth_header = request.headers.get(
        "Authorization"
    )

    try:
        cleaned_text = _soften_text_for_tts(
            req.text
        )

        voice_id = _voice_alias(req.voice)

        voice_cfg = _emotion_to_voice(
            style=req.style,
            effects=req.effects,
            emotion_label=req.emotion_label,
            emotional_state=req.emotional_state
        )

        payload = {
            "text": cleaned_text,
            "voice": voice_id,
            "user_id": req.user_id,
            "style": req.style,
            "effects": req.effects,

            "rate": req.rate or voice_cfg["rate"],
            "pitch": req.pitch or voice_cfg["pitch"],
            "volume": req.volume or voice_cfg["volume"],

            "emotion_label": (
                req.emotion_label
                or voice_cfg["emotion_label"]
            ),

            "emotional_state": (
                req.emotional_state or {}
            )
        }

        audio_bytes = await _call_tts(
            payload,
            auth_header
        )

        # =========================
        # MP3 BRUTO
        # =========================

        if req.raw_audio_response:

            return Response(
                content=audio_bytes,
                media_type="audio/mpeg",
                headers={
                    "Content-Disposition":
                        'inline; filename="tts.mp3"',

                    "X-Voice": voice_id,

                    "X-Emotion":
                        payload["emotion_label"]
                }
            )

        # =========================
        # BASE64
        # =========================

        response_payload = {
            "ok": True,
            "text_input": req.text,
            "text_tts": cleaned_text,
            "voice": voice_id,

            "rate": payload["rate"],
            "pitch": payload["pitch"],
            "volume": payload["volume"],

            "emotion_label":
                payload["emotion_label"],

            "applied_effects":
                voice_cfg["applied_effects"]
        }

        if req.return_audio_base64:
            response_payload["audio_base64"] = (
                base64.b64encode(audio_bytes)
                .decode("utf-8")
            )

        return JSONResponse(
            content=response_payload
        )

    except httpx.HTTPStatusError as e:

        return JSONResponse(
            status_code=e.response.status_code,
            content={
                "error": "tts_upstream_error",
                "detail": e.response.text
            }
        )

    except Exception as e:

        return JSONResponse(
            status_code=500,
            content={
                "error": "tts_bridge_error",
                "detail": str(e)
            }
        )


@router.post("/ask")
async def voice_ask(
    req: VoiceAskRequest,
    request: Request,
    _=Depends(protect)
):

    auth_header = request.headers.get(
        "Authorization"
    )

    try:
        chat_data = await _call_chat(
            userid=req.userid,
            sessionid=req.sessionid,
            message=req.message,
            auth_header=auth_header
        )

        reply = chat_data.get("reply", "") or ""

        emotional_state = (
            chat_data.get("emotional_state")
            or {
                "valence": 0.0,
                "arousal": 0.0,
                "label": "neutra"
            }
        )

        cleaned_reply = _soften_text_for_tts(
            reply
        )

        voice_cfg = _emotion_to_voice(
            style=req.style,
            effects=req.effects,

            emotion_label=(
                emotional_state.get("label")
                if req.use_emotion_voice
                else "neutra"
            ),

            emotional_state=(
                emotional_state
                if req.use_emotion_voice
                else {
                    "valence": 0.0,
                    "arousal": 0.0,
                    "label": "neutra"
                }
            )
        )

        tts_payload = {
            "text": cleaned_reply,

            "voice": _voice_alias(
                req.voice_id
            ),

            "user_id": req.userid,
            "style": req.style,
            "effects": req.effects,

            "rate": voice_cfg["rate"],
            "pitch": voice_cfg["pitch"],
            "volume": voice_cfg["volume"],

            "emotion_label":
                voice_cfg["emotion_label"],

            "emotional_state":
                emotional_state
        }

        audio_bytes = await _call_tts(
            tts_payload,
            auth_header
        )

        # =========================
        # MP3 BRUTO
        # =========================

        if req.raw_audio_response:

            return Response(
                content=audio_bytes,
                media_type="audio/mpeg",
                headers={
                    "Content-Disposition":
                        'inline; filename="reply.mp3"'
                }
            )

        # =========================
        # JSON
        # =========================

        response_payload = {
            "reply": reply,
            "emotional_state": emotional_state,
            "actions": chat_data.get(
                "actions",
                []
            ),

            "tts": {
                "provider": "edge-tts",

                "voice":
                    tts_payload["voice"],

                "text_tts":
                    cleaned_reply,

                "rate":
                    tts_payload["rate"],

                "pitch":
                    tts_payload["pitch"],

                "volume":
                    tts_payload["volume"],

                "emotion_label":
                    tts_payload["emotion_label"],

                "applied_effects":
                    voice_cfg["applied_effects"]
            }
        }

        if req.return_audio_base64:

            response_payload["tts"][
                "audio_base64"
            ] = (
                base64.b64encode(audio_bytes)
                .decode("utf-8")
            )

        return JSONResponse(
            content=response_payload
        )

    except httpx.HTTPStatusError as e:

        return JSONResponse(
            status_code=e.response.status_code,
            content={
                "error":
                    "voice_ask_upstream_error",

                "detail":
                    e.response.text
            }
        )

    except Exception as e:

        return JSONResponse(
            status_code=500,
            content={
                "error": "voice_ask_error",
                "detail": str(e)
            }
        )