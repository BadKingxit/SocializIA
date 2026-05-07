#!/usr/bin/env bash
set -e

MODELS_DIR="${PIPER_MODELS_DIR:-/root/piper_models}"
VOICE="${1:-pt_BR-faber-medium}"

mkdir -p "$MODELS_DIR"

BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main"

ONNX_PATH="$MODELS_DIR/${VOICE}.onnx"
JSON_PATH="$MODELS_DIR/${VOICE}.onnx.json"

if [ ! -f "$ONNX_PATH" ]; then
    curl -L "${BASE_URL}/${VOICE}.onnx" -o "$ONNX_PATH"
fi

if [ ! -f "$JSON_PATH" ]; then
    curl -L "${BASE_URL}/${VOICE}.onnx.json" -o "$JSON_PATH"
fi

echo "Modelo pronto em: $MODELS_DIR"
ls -lh "$MODELS_DIR" | grep "$VOICE" || true
