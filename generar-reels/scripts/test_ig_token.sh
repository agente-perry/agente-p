#!/usr/bin/env bash
set -euo pipefail

: "${IG_ACCESS_TOKEN:?IG_ACCESS_TOKEN required}"
: "${IG_USER_ID:?IG_USER_ID required}"

API="https://graph.facebook.com/v22.0"

echo "=== 1. Token identity ==="
me=$(curl -sS "${API}/me?fields=id,name&access_token=${IG_ACCESS_TOKEN}")
echo "$me" | jq .
echo "$me" | jq -e '.id' > /dev/null || { echo "FAIL: token inválido o expirado" >&2; exit 1; }

echo ""
echo "=== 2. Token debug (expiry + scopes) ==="
curl -sS "${API}/debug_token?input_token=${IG_ACCESS_TOKEN}&access_token=${IG_ACCESS_TOKEN}" | jq '.data | {is_valid, expires_at, scopes, error}'

echo ""
echo "=== 3. Descubrir IG Business Account ID ==="
pages=$(curl -sS "${API}/me/accounts?access_token=${IG_ACCESS_TOKEN}")
echo "Pages:" && echo "$pages" | jq '.data[] | {id, name}'

ig_id=""
while IFS= read -r page_id; do
  result=$(curl -sS "${API}/${page_id}?fields=instagram_business_account&access_token=${IG_ACCESS_TOKEN}")
  candidate=$(echo "$result" | jq -r '.instagram_business_account.id // empty')
  if [[ -n "$candidate" ]]; then
    ig_id="$candidate"
    echo "Encontrado IG Business Account ID: $ig_id (page $page_id)"
    break
  fi
done < <(echo "$pages" | jq -r '.data[].id' | tr -d '\r')

if [[ -z "$ig_id" ]]; then
  echo "WARN: No se encontró IG Business Account vinculado a ninguna Page" >&2
else
  echo ""
  echo "=== 3b. Verificar IG account ==="
  curl -sS "${API}/${ig_id}?fields=id,username,name&access_token=${IG_ACCESS_TOKEN}" | jq .
  if [[ "$ig_id" != "$IG_USER_ID" ]]; then
    echo ""
    echo "AVISO: IG_USER_ID en .env ($IG_USER_ID) != correcto ($ig_id)"
    echo "Actualiza .env: IG_USER_ID=$ig_id"
  fi
fi

echo ""
echo "=== 4. Reels publish permission ==="
perms=$(curl -sS "${API}/${IG_USER_ID}/content_publishing_limit?fields=config,quota_usage&access_token=${IG_ACCESS_TOKEN}")
echo "$perms" | jq .

echo ""
echo "=== RESULTADO ==="
expires=$(curl -sS "${API}/debug_token?input_token=${IG_ACCESS_TOKEN}&access_token=${IG_ACCESS_TOKEN}" | jq -r '.data.expires_at // 0')
if [[ "$expires" -eq 0 ]]; then
  echo "Token: sin expiración (long-lived OK)"
else
  exp_date=$(date -d "@${expires}" '+%Y-%m-%d' 2>/dev/null || date -r "${expires}" '+%Y-%m-%d' 2>/dev/null || echo "fecha no parseable")
  echo "Token expira: ${exp_date}"
fi
echo "Token OK para IG_USER_ID=${IG_USER_ID}"
