#!/usr/bin/env bash
set -euo pipefail

VOICE="${PIPER_VOICE:-pt_BR-faber-medium}"
VOLUME_ROOT="${RAILWAY_VOLUME_MOUNT_PATH:-$HOME/piper_volume}"
MODELS_DIR="${PIPER_MODELS_DIR:-$VOLUME_ROOT/piper_models}"

mkdir -p "$MODELS_DIR"

ONNX="$MODELS_DIR/${VOICE}.onnx"
JSON="$MODELS_DIR/${VOICE}.onnx.json"

BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium"

if [ ! -f "$ONNX" ]; then
    echo "[piper] baixando $ONNX"
    curl -L --retry 5 --retry-delay 2 -o "$ONNX" "$BASE_URL/${VOICE}.onnx"
fi

if [ ! -f "$JSON" ]; then
    echo "[piper] baixando $JSON"
    curl -L --retry 5 --retry-delay 2 -o "$JSON" "$BASE_URL/${VOICE}.onnx.json"
fi

echo "[piper] pronto em $MODELS_DIR"
ls -lh "$MODELS_DIR"
