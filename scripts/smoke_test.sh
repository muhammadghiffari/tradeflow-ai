#!/usr/bin/env bash
set -euo pipefail

# Simple smoke test for local TradeFlow AI stack
# Checks: Keycloak token endpoint, API docs availability, a protected API call using client credentials

KEYCLOAK_URL="http://localhost:8080/realms/tradeflow/protocol/openid-connect/token"
API_DOCS_URL="http://api.localhost:8888/docs"
API_PROTECTED="http://api.localhost:8888/api/health" # change if different

CLIENT_ID=${CLIENT_ID:-tradeflow-api}
CLIENT_SECRET=${CLIENT_SECRET:-change-me-in-production}

echo "Waiting for Keycloak token endpoint..."
for i in {1..60}; do
  if curl -sSf "$KEYCLOAK_URL" -o /dev/null; then
    echo "Keycloak reachable"
    break
  fi
  sleep 2
done

echo "Requesting client_credentials token..."
TOKEN_RESP=$(curl -s -X POST "$KEYCLOAK_URL" -d "grant_type=client_credentials" -d "client_id=$CLIENT_ID" -d "client_secret=$CLIENT_SECRET")
ACCESS_TOKEN=$(echo "$TOKEN_RESP" | (jq -r .access_token 2>/dev/null || python -c "import sys, json; print(json.load(sys.stdin).get('access_token',''))"))

if [ -z "$ACCESS_TOKEN" ]; then
  echo "Failed to obtain access_token. Response:\n$TOKEN_RESP"
  exit 2
fi

echo "Got access token (length ${#ACCESS_TOKEN})"

echo "Checking API docs at $API_DOCS_URL"
if curl -sSf "$API_DOCS_URL" >/dev/null; then
  echo "API docs reachable"
else
  echo "API docs not reachable"
  exit 3
fi

echo "Calling protected API $API_PROTECTED"
if curl -sSf -H "Authorization: Bearer $ACCESS_TOKEN" "$API_PROTECTED" >/dev/null; then
  echo "Protected API reachable with token"
else
  echo "Protected API failed or returned non-2xx"
  exit 4
fi

echo "Smoke tests passed"
