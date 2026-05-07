#!/usr/bin/env bash
set -e

MODELS_DIR="${PIPER_MODELS_DIR:-/root/piper_models}"
VOICE="pt_BR-faber-medium"
BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium"

mkdir -p "$MODELS_DIR"

if [ ! -f "$MODELS_DIR/${VOICE}.onnx" ]; then
    echo "[startup] Baixando ${VOICE}.onnx..."
    curl -L --retry 3 "${BASE_URL}/${VOICE}.onnx" -o "$MODELS_DIR/${VOICE}.onnx"
fi

if [ ! -f "$MODELS_DIR/${VOICE}.onnx.json" ]; then
    echo "[startup] Baixando ${VOICE}.onnx.json..."
    curl -L --retry 3 "${BASE_URL}/${VOICE}.onnx.json" -o "$MODELS_DIR/${VOICE}.onnx.json"
fi

echo "[startup] Modelo pronto. Subindo uvicorn..."
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8777}"
