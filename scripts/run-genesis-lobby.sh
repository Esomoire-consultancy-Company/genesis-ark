#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# GENESIS-LOBBY-SPRINT0-CI: private mock only; no real Warden or Lobby.
: "${POSTMAN_API_KEY:?Missing POSTMAN_API_KEY secret}"
: "${POSTMAN_COLLECTION_ID:?Missing POSTMAN_COLLECTION_ID variable}"
: "${POSTMAN_SPRINT0_FOLDER_UID:?Missing POSTMAN_SPRINT0_FOLDER_UID variable}"
: "${POSTMAN_MOCK_URL:?Missing POSTMAN_MOCK_URL variable}"
: "${POSTMAN_MOCK_SESSION_ID:=ci-genesis-lobby-${GITHUB_RUN_ID:-local}-${RANDOM}}"

command -v postman >/dev/null || { echo 'Postman CLI not installed' >&2; exit 13; }
command -v python3 >/dev/null || { echo 'python3 not installed' >&2; exit 14; }

# Validate HTTPS private Postman mock endpoint and prevent accidental writes to real service endpoints.
python3 - <<'PY'
import os, re, sys
from urllib.parse import urlsplit
url = os.environ["POSTMAN_MOCK_URL"]
u = urlsplit(url)
valid = (
    u.scheme == "https" and
    bool(re.fullmatch(r"[a-z0-9-]+\.mock\.[a-z0-9-]+\.postman\.dev", u.hostname or "")) and
    not u.username and not u.password and u.port is None and
    u.path in ("", "/") and not u.query and not u.fragment
)
if not valid:
    sys.exit("Refusing non-Postman private mock destination")
PY

mkdir -p results
TMP_ENV=$(mktemp "$PWD/results/.genesis-ci.XXXXXXXX.json")
trap 'rm -f "$TMP_ENV"' EXIT
export TMP_ENV
python3 - <<'PY'
import json,os,pathlib
url=os.environ['POSTMAN_MOCK_URL'].rstrip('/')
values={
  'baseUrl':url,
  'mockBaseUrl':url,
  'warden_baseUrl':url,
  'lobby_baseUrl':url,
  'mock_session_id':os.environ['POSTMAN_MOCK_SESSION_ID'],
  # Aliases are set ONLY for the isolated cloud mock. This is not Warden authority.
  'mock_api_key':os.environ['POSTMAN_API_KEY'],
  'auth_token':os.environ['POSTMAN_API_KEY'],
  'tenant_id':'demo-tenant',
  'lobby_id':'demo-lobby',
  'warden_intent':'synthetic-ci-qualification',
  'execution_target':'synthetic-mock-only'
}
obj={
  'name':'Ephemeral CI - mock-only',
  '_postman_variable_scope':'environment',
  'values':[{'key':k,'value':v,'type':'default','enabled':True} for k,v in values.items()]
}
p=pathlib.Path(os.environ['TMP_ENV'])
p.write_text(json.dumps(obj),encoding='utf-8')
p.chmod(0o600)
PY

# -i selects the actual Postman folder UID containing R1 -> R7.
# No raw request/response payloads exported to CI artifacts.
postman collection run "$POSTMAN_COLLECTION_ID" \
  --environment "$TMP_ENV" \
  -i "$POSTMAN_SPRINT0_FOLDER_UID" \
  --report-events=false \
  --no-insecure-file-read \
  --reporters cli,junit \
  --reporter-junit-export results/genesis-lobby-junit.xml

echo 'Synthetic Sprint-0 regression finished. Inspect the JUnit report before acceptance.'
