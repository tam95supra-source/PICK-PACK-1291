#!/usr/bin/env bash
set -euo pipefail

: "${CLOUDFLARE_API_TOKEN:?MISSING_REQUIRED_SECRET:CLOUDFLARE_API_TOKEN}"
: "${CLOUDFLARE_ACCOUNT_ID:?MISSING_REQUIRED_SECRET:CLOUDFLARE_ACCOUNT_ID}"
: "${GOOGLE_OAUTH_CLIENT_ID:?MISSING_REQUIRED_SECRET:GOOGLE_OAUTH_CLIENT_ID}"
: "${GOOGLE_OAUTH_CLIENT_SECRET:?MISSING_REQUIRED_SECRET:GOOGLE_OAUTH_CLIENT_SECRET}"
: "${GOOGLE_OAUTH_REFRESH_TOKEN:?MISSING_REQUIRED_SECRET:GOOGLE_OAUTH_REFRESH_TOKEN}"
: "${GAS_SCRIPT_ID:?MISSING_REQUIRED_SECRET:GAS_SCRIPT_ID}"
: "${GAS_DEPLOYMENT_ID:?MISSING_REQUIRED_SECRET:GAS_DEPLOYMENT_ID}"
: "${SIGNING_KEY_B64:?MISSING_REQUIRED_SECRET:ANDROID_SIGNING_KEY_B64}"
: "${SIGNING_STORE_PASSWORD:?MISSING_REQUIRED_SECRET:ANDROID_SIGNING_STORE_PASSWORD}"
: "${SIGNING_KEY_PASSWORD:?MISSING_REQUIRED_SECRET:ANDROID_SIGNING_KEY_PASSWORD}"
: "${SIGNING_ALIAS:?MISSING_REQUIRED_SECRET:ANDROID_SIGNING_ALIAS}"

D1_NAME=${D1_NAME:-pick-pack-1291-service-prod}
WORKER_NAME=${WORKER_NAME:-pick-pack-1291-service}
SERVICE_GENERATION=${SERVICE_GENERATION:-m2-prod-20260819-001}
SOURCE_SHEET_ID=${SOURCE_SHEET_ID:-1E7ZWz-4eMcBliQxDYBVoogIoeSYyiaXGwj0I6mbMm78}
STAGING_SHEET_ID=${STAGING_SHEET_ID:-1naPzyMjjsGvzz1EqWIBk2aS4anYmJqNgEYDCmu5U5aI}
ROLLBACK_FOLDER_ID=${ROLLBACK_FOLDER_ID:-1P7KM5b5D_P69OkyKdmLx0HbL3wRpg0yG}

BRIDGE=$(printf '%s' "$CLOUDFLARE_ACCOUNT_ID|$GOOGLE_OAUTH_CLIENT_SECRET|pick-pack-1291-m2-bridge-v1" | sha256sum | awk '{print $1}')
SERVICE_TOKEN=$(printf '%s' "$CLOUDFLARE_ACCOUNT_ID|$GOOGLE_OAUTH_CLIENT_SECRET|pick-pack-1291-m2-service-token-v1" | sha256sum | awk '{print $1}')
ADMIN_TOKEN=$(printf '%s' "$CLOUDFLARE_ACCOUNT_ID|$SIGNING_STORE_PASSWORD|pick-pack-1291-m2-admin-v1" | sha256sum | awk '{print $1}')
echo "::add-mask::$BRIDGE"; echo "::add-mask::$SERVICE_TOKEN"; echo "::add-mask::$ADMIN_TOKEN"

mkdir -p m2-external-evidence
cd service
npm install --no-audit --no-fund
npm run check
npx wrangler whoami | tee /tmp/m2-whoami.txt
npx wrangler d1 list --json >/tmp/m2-d1-list.json
node -e 'const j=require("/tmp/m2-d1-list.json");if(!Array.isArray(j))throw new Error("D1_LIST_NOT_ARRAY")'

RESP=$(curl -fsS https://oauth2.googleapis.com/token -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode "client_id=$GOOGLE_OAUTH_CLIENT_ID" \
  --data-urlencode "client_secret=$GOOGLE_OAUTH_CLIENT_SECRET" \
  --data-urlencode "refresh_token=$GOOGLE_OAUTH_REFRESH_TOKEN" \
  --data-urlencode 'grant_type=refresh_token')
GOOGLE_TOKEN=$(node -e 'const j=JSON.parse(process.argv[1]);process.stdout.write(j.access_token||"")' "$RESP")
test -n "$GOOGLE_TOKEN"; echo "::add-mask::$GOOGLE_TOKEN"

echo "ROLLBACK_FOLDER_VERIFIED_BY_DRIVE_CONNECTOR:$ROLLBACK_FOLDER_ID"
H=$(curl -sS -o /tmp/m2-source-meta.json -w '%{http_code}' -H "Authorization: Bearer $GOOGLE_TOKEN" "https://sheets.googleapis.com/v4/spreadsheets/$SOURCE_SHEET_ID?fields=spreadsheetId,properties.title")
[[ "$H" == 200 ]] || { echo "GOOGLE_SHEETS_SCOPE_OR_ACCESS:$H" >&2; cat /tmp/m2-source-meta.json >&2; exit 1; }
node -e 'const j=require("/tmp/m2-source-meta.json");if(j.spreadsheetId!==process.env.SOURCE_SHEET_ID)throw new Error(JSON.stringify(j))'
SCRIPT=$(printf '%s' "$GAS_SCRIPT_ID" | tr -d '\r\n\t ')
H=$(curl -sS -o /tmp/m2-gas-project.json -w '%{http_code}' -H "Authorization: Bearer $GOOGLE_TOKEN" "https://script.googleapis.com/v1/projects/$SCRIPT/content")
[[ "$H" == 200 ]] || { echo "GOOGLE_APPS_SCRIPT_SCOPE_OR_ACCESS:$H" >&2; cat /tmp/m2-gas-project.json >&2; exit 1; }

LIST=$(cat /tmp/m2-d1-list.json)
ID=$(node -e 'const a=JSON.parse(process.argv[1]);const x=a.find(v=>v.name===process.env.D1_NAME);process.stdout.write(x?.uuid||x?.id||"")' "$LIST")
if [[ -z "$ID" ]]; then
  npx wrangler d1 create "$D1_NAME" --location apac >/tmp/m2-d1-create.log
  LIST=$(npx wrangler d1 list --json)
  ID=$(node -e 'const a=JSON.parse(process.argv[1]);const x=a.find(v=>v.name===process.env.D1_NAME);process.stdout.write(x?.uuid||x?.id||"")' "$LIST")
fi
test -n "$ID"; export PROD_D1_ID="$ID"
python3 - <<'PY'
from pathlib import Path
import os
s=Path('wrangler.jsonc').read_text()
s=s.replace('"name": "pick-pack-1291-service-m1-staging"','"name": "'+os.environ['WORKER_NAME']+'"')
s=s.replace('"SERVICE_GENERATION": "m2-precutover-20260819-001"','"SERVICE_GENERATION": "'+os.environ['SERVICE_GENERATION']+'"')
s=s.replace('"database_name": "pick-pack-1291-m1-staging"','"database_name": "'+os.environ['D1_NAME']+'"')
s=s.replace('__M1_D1_DATABASE_ID__',os.environ['PROD_D1_ID'])
Path('wrangler.external.jsonc').write_text(s)
PY
npx wrangler d1 migrations apply "$D1_NAME" --remote --config wrangler.external.jsonc

export SERVICE_TOKEN_SECRET="$SERVICE_TOKEN" M2_ADMIN_TOKEN="$ADMIN_TOKEN" GAS_BRIDGE_SHARED_SECRET="$BRIDGE"
node - <<'NODE'
const fs=require('fs');fs.writeFileSync('/tmp/m2-secrets.json',JSON.stringify({SERVICE_TOKEN_SECRET:process.env.SERVICE_TOKEN_SECRET,M1_ADMIN_TOKEN:process.env.M2_ADMIN_TOKEN,GAS_BRIDGE_SHARED_SECRET:process.env.GAS_BRIDGE_SHARED_SECRET,GOOGLE_OAUTH_CLIENT_ID:process.env.GOOGLE_OAUTH_CLIENT_ID,GOOGLE_OAUTH_CLIENT_SECRET:process.env.GOOGLE_OAUTH_CLIENT_SECRET,GOOGLE_OAUTH_REFRESH_TOKEN:process.env.GOOGLE_OAUTH_REFRESH_TOKEN,GOOGLE_STAGING_SHEET_ID:process.env.STAGING_SHEET_ID}));
NODE
chmod 600 /tmp/m2-secrets.json
npx wrangler deploy --config wrangler.external.jsonc --secrets-file /tmp/m2-secrets.json 2>&1 | tee /tmp/m2-deploy.log
SERVICE_URL=$(grep -Eo 'https://[A-Za-z0-9._-]+\.workers\.dev' /tmp/m2-deploy.log | tail -1 || true)
test -n "$SERVICE_URL"; export SERVICE_URL

OK=false
for i in $(seq 1 40); do
  if curl -fsS --connect-timeout 5 --max-time 15 "$SERVICE_URL/health" >/tmp/m2-health.json 2>/tmp/m2-health.err; then
    if node -e 'const j=require("/tmp/m2-health.json");process.exit(j.ok&&j.environment==="staging-shadow"&&j.authority?.scope==="STAGING_SHADOW"&&j.authority?.mode==="SERVICE_PRIMARY"&&j.generation===process.env.SERVICE_GENERATION?0:1)'; then OK=true; break; fi
  fi
  sleep 10
done
[[ "$OK" == true ]] || { cat /tmp/m2-health.err || true; cat /tmp/m2-health.json || true; exit 1; }
curl -fsS "$SERVICE_URL/" >/tmp/m2-pwa.html; grep -qi '<html' /tmp/m2-pwa.html
curl -fsS "$SERVICE_URL/manifest.webmanifest" >/tmp/m2-pwa-manifest.json; grep -q 'Pick Pack 1291' /tmp/m2-pwa-manifest.json

# Bootstrap and Google staging replication are intentionally verified by
# Service M2 External Live Verify, which is the sole owner of source_rows during that gate.
cd ..
cp /tmp/m2-health.json m2-external-evidence/service-health.json
cp /tmp/m2-source-meta.json m2-external-evidence/source-meta.json
node - <<'NODE'
const fs=require('fs');fs.writeFileSync('m2-external-evidence/state.json',JSON.stringify({source_commit:process.env.GITHUB_SHA,service_url:process.env.SERVICE_URL,d1_name:process.env.D1_NAME,d1_id:process.env.PROD_D1_ID,generation:process.env.SERVICE_GENERATION,source_sheet_id:process.env.SOURCE_SHEET_ID,staging_sheet_id:process.env.STAGING_SHEET_ID,rollback_folder_id:process.env.ROLLBACK_FOLDER_ID,authority_scope:'STAGING_SHADOW',production_cutover:false,deploy_gate:true,bootstrap_gate:'Service M2 External Live Verify'},null,2));
NODE

echo "PASS M2_EXTERNAL_DEPLOY_PRECUTOVER service_url=$SERVICE_URL d1_id=$PROD_D1_ID"
