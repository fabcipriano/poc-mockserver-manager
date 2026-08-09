#!/usr/bin/env bash
# Lists all active MockServer expectations (excluding the seeded catch-all forward).
set -euo pipefail

MOCKSERVER_URL="${MOCKSERVER_URL:-http://localhost:1080}"

curl -sS -X PUT "${MOCKSERVER_URL}/mockserver/retrieve?type=ACTIVE_EXPECTATIONS" \
  -H "Content-Type: application/json" \
  -d '{"path": ".*"}' | jq '.'
