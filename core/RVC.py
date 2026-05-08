import os
import tempfile
import subprocess
import httpx

RVC_ENABLED = os.environ.get(
    "RVC_ENABLED",
    "true"
).lower() == "true"

RVC_MODEL = os.environ.get(
    "RVC_MODEL",
    "models/amora.pth"
)

RVC_INDEX = os.environ.get(
    "RVC_INDEX",
    "models/amora.index"
)

BACKEND_URL = os.environ.get(
    "BACKEND_URL",
    "https://web-production-6d0ed.up.railway.app"
).rstrip("/")


async def _call_edge_tts(
    payload,
    auth_header
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


async def generate_tts_with_rvc(
    payload,
    auth_header
) -> bytes:

    edge_audio = await _call_edge_tts(
        payload,
        auth_header
    )

    if not RVC_ENABLED:
        return edge_audio

    try:

        with tempfile.TemporaryDirectory() as tmp:

            input_mp3 = os.path.join(
                tmp,
                "input.mp3"
            )

            output_wav = os.path.join(
                tmp,
                "output.wav"
            )

            with open(input_mp3, "wb") as f:
                f.write(edge_audio)

            cmd = [
                "python",
                "infer.py",

                "--input_path",
                input_mp3,

                "--output_path",
                output_wav,

                "--model_path",
                RVC_MODEL,

                "--index_path",
                RVC_INDEX
            ]

            subprocess.run(
                cmd,
                check=True
            )

            with open(output_wav, "rb") as f:
                return f.read()

    except Exception as e:

        print("RVC FALLBACK:", e)

        return edge_audio