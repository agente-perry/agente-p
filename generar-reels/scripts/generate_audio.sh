#!/usr/bin/env bash
set -euo pipefail

INSIGHT_JSON="${1:?Usage: scripts/generate_audio.sh <insight_json_path>}"
AUDIO_OUT="assets/voiceover.mp3"
TIMESTAMPS_OUT="assets/voiceover_timestamps.json"
VOICE_ID="${ELEVENLABS_VOICE_ID:-pNInz6obpgDQGcFmaJgB}"
MODEL_ID="${ELEVENLABS_MODEL:-eleven_multilingual_v2}"
TMP_RESPONSE="$(mktemp)"

cleanup() { rm -f "$TMP_RESPONSE"; }
trap cleanup EXIT

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "ERROR: $1 not found" >&2; exit 1; }
}

require_cmd curl
require_cmd jq
require_cmd python3
require_cmd ffprobe

[[ -f "$INSIGHT_JSON" ]] || { echo "ERROR: insight not found: $INSIGHT_JSON" >&2; exit 1; }
[[ -n "${ELEVENLABS_API_KEY:-}" ]] || { echo "ERROR: ELEVENLABS_API_KEY required" >&2; exit 1; }

VOICEOVER_TEXT="$(jq -r '.script.voiceover_text_full // .voiceover_text_full // empty' "$INSIGHT_JSON")"
[[ -n "$VOICEOVER_TEXT" ]] || { echo "ERROR: script.voiceover_text_full missing" >&2; exit 1; }

WORD_COUNT=$(echo "$VOICEOVER_TEXT" | wc -w | tr -d ' ')
if [[ "$WORD_COUNT" -gt 50 ]]; then
  echo "ERROR: voiceover tiene $WORD_COUNT palabras (max 50 — REGLA 1). Acortar el guion." >&2
  exit 1
fi

REQUEST_BODY="$(jq -n --arg text "$VOICEOVER_TEXT" --arg model "$MODEL_ID" '{
  text: $text,
  model_id: $model,
  voice_settings: {
    stability: 0.5,
    similarity_boost: 0.75,
    style: 0.4,
    use_speaker_boost: true
  }
}')"

mkdir -p "$(dirname "$AUDIO_OUT")"

HTTP_STATUS="$(curl -sS -w "%{http_code}" -o "$TMP_RESPONSE" \
  -X POST "https://api.elevenlabs.io/v1/text-to-speech/${VOICE_ID}/with-timestamps" \
  -H "xi-api-key: ${ELEVENLABS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "$REQUEST_BODY")"

if [[ "$HTTP_STATUS" != "200" ]]; then
  echo "ERROR: ElevenLabs returned HTTP $HTTP_STATUS" >&2
  cat "$TMP_RESPONSE" >&2
  exit 1
fi

jq -r '.audio_base64' "$TMP_RESPONSE" | base64 -d > "$AUDIO_OUT"
[[ -s "$AUDIO_OUT" ]] || { echo "ERROR: audio file is empty" >&2; exit 1; }

DURATION="$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$AUDIO_OUT")"
[[ "$DURATION" =~ ^[0-9]+(\.[0-9]+)?$ ]] || { echo "ERROR: invalid MP3 duration: $DURATION" >&2; exit 1; }

awk -v d="$DURATION" 'BEGIN { exit !(d > 20.5) }' \
  && { echo "ERROR: audio dura ${DURATION}s (max 20.5s — REGLA 1). Acortar el guion." >&2; exit 1; } || true

echo "INFO: Audio → $AUDIO_OUT (${DURATION}s)" >&2
echo "AUDIO_DURATION_SECONDS=$DURATION"
