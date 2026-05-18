#!/usr/bin/env bash
set -euo pipefail

MP4_PATH="${1:-}"
WARNINGS=0
TMP_LINT="$(mktemp)"

cleanup() { rm -f "$TMP_LINT"; }
trap cleanup EXIT

warn() { WARNINGS=$((WARNINGS + 1)); echo "WARN: $*" >&2; }
fail() { echo "ERROR: $*" >&2; exit 1; }

duration_of() {
  ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$1"
}

[[ -f "index.html" ]] || fail "index.html does not exist"
grep -qi '<!doctype html' "index.html" || warn "index.html has no DOCTYPE"
grep -qi 'data-composition-id\|data-scene' "index.html" || fail "index.html does not look like a HyperFrames composition"

if grep -qE '\{\{[^}]+\}\}' "index.html"; then
  fail "index.html still contains unfilled Jinja2 placeholders"
fi

if grep -qE '20[0-9]{9}' "index.html"; then
  warn "index.html contains uncensored 11-digit RUC-like values"
fi

grep -q 'id="karaoke-word"' "index.html" \
  || fail "REGLA2: #karaoke-word ausente — karaoke debe ser palabra a palabra, no texto fijo"

if python3 - <<'PYEOF'
import re, sys
html = open("index.html", encoding="utf-8").read()
m = re.search(r'id=["\']karaoke["\'][^>]*>(.*?)</div>', html, re.DOTALL)
if not m:
    sys.exit(0)
inner = m.group(1)
inner_clean = re.sub(r'<span[^>]*id=["\']karaoke-word["\'][^>]*>.*?</span>', '', inner, flags=re.DOTALL)
inner_clean = re.sub(r'\s+', '', inner_clean)
if inner_clean:
    print(f"STATIC_KARAOKE: {inner_clean[:80]}", file=__import__('sys').stderr)
    sys.exit(1)
sys.exit(0)
PYEOF
then :
else
  fail "REGLA2: texto estatico detectado dentro de #karaoke — usar solo #karaoke-word via JS"
fi

grep -q 'id="hook-datum"' "index.html" \
  || fail "REGLA3: #hook-datum ausente — scene-intro debe usar hook brutalista, no titulo corporativo"

grep -q 'id="binary-rain"' "index.html" \
  || fail "REGLA5: <canvas id=binary-rain> ausente — Capa 1 ambiente obligatoria"

grep -q 'class="scanline"' "index.html" \
  || fail "REGLA5: .scanline ausente"

vignette_count=$(grep -c 'corner-vignette' "index.html" || true)
[[ "$vignette_count" -ge 4 ]] \
  || fail "REGLA5: solo $vignette_count .corner-vignette encontradas (se requieren 4)"

grep -q 'id="status-bar"' "index.html" \
  || fail "REGLA6: #status-bar ausente — zona inferior debe tener indicador de caso/confidence"

[[ -f "assets/voiceover.mp3" ]] || fail "assets/voiceover.mp3 does not exist"
audio_duration="$(duration_of "assets/voiceover.mp3")"

awk -v d="$audio_duration" 'BEGIN { exit !(d >= 19.5 && d <= 20.5) }' \
  || fail "REGLA1: duracion audio fuera de rango: ${audio_duration}s (requerido: 19.5–20.5s)"

if [[ -f "assets/voiceover_timestamps.json" ]]; then
  words_count=$(python3 -c "
import json, sys
d = json.load(open('assets/voiceover_timestamps.json'))
words = d.get('words', [])
print(len(words))
" 2>/dev/null || echo 0)
  [[ "$words_count" -gt 0 ]] \
    || warn "REGLA2: voiceover_timestamps.json no contiene campo 'words' — karaoke sin datos"
else
  warn "assets/voiceover_timestamps.json no existe — karaoke sin datos"
fi

if command -v npx >/dev/null 2>&1; then
  if ! npx hyperframes lint . >"$TMP_LINT" 2>&1; then
    cat "$TMP_LINT" >&2
    fail "npx hyperframes lint failed"
  fi
else
  warn "npx not found; skipped hyperframes lint"
fi

if [[ -n "$MP4_PATH" ]]; then
  [[ -f "$MP4_PATH" ]] || fail "MP4 does not exist: $MP4_PATH"
  size_bytes="$(wc -c < "$MP4_PATH" | tr -d ' ')"
  [[ "$size_bytes" -gt 512000 ]] || fail "MP4 must be >500KB, got ${size_bytes} bytes"
  video_duration="$(duration_of "$MP4_PATH")"
  awk -v d="$video_duration" 'BEGIN { exit !(d >= 19.5 && d <= 20.5) }' \
    || fail "REGLA1: duracion video fuera de rango: ${video_duration}s (requerido: 19.5–20.5s)"
fi

echo "VALIDATION_OK warnings=$WARNINGS audio_duration=$audio_duration"
