#!/usr/bin/env bash
# Adds (or replaces) a MockServer expectation for a route.
# Assumes `kubectl port-forward svc/mockserver 1080:80 -n mockserver-poc` is running
# (or MOCKSERVER_URL is set to wherever MockServer's control-plane API is reachable).
# Requires: jq.
#
# Prints the new expectation's id - save it, scripts/delete-mock.sh needs it to
# remove *only* this expectation (MockServer's clear-by-request-matcher can also
# sweep up the seeded catch-all forward, since its path regex matches everything).
#
# Usage: scripts/add-mock.sh <METHOD> <PATH> <STATUS> <BODY_JSON_FILE>
# Example: scripts/add-mock.sh GET /booking/1 200 mocks/booking-get.example.json
set -euo pipefail

if [ "$#" -ne 4 ]; then
  echo "Usage: $0 <METHOD> <PATH> <STATUS> <BODY_JSON_FILE>" >&2
  exit 1
fi

METHOD="$1"
ROUTE_PATH="$2"
STATUS="$3"
BODY_FILE="$4"
MOCKSERVER_URL="${MOCKSERVER_URL:-http://localhost:1080}"
DEFAULT_PRIORITY=10

BODY_JSON="$(cat "${BODY_FILE}")"

EXPECTATION=$(cat <<EOF
{
  "httpRequest": {
    "method": "${METHOD}",
    "path": "${ROUTE_PATH}"
  },
  "httpResponse": {
    "statusCode": ${STATUS},
    "headers": {
      "Content-Type": ["application/json"]
    },
    "body": ${BODY_JSON}
  },
  "priority": ${DEFAULT_PRIORITY}
}
EOF
)

RESPONSE=$(curl -sS -X PUT "${MOCKSERVER_URL}/mockserver/expectation" \
  -H "Content-Type: application/json" \
  -d "${EXPECTATION}")

echo "${RESPONSE}" | jq '.'

EXPECTATION_ID=$(echo "${RESPONSE}" | jq -r '.[0].id')

echo
echo "Mock added: ${METHOD} ${ROUTE_PATH} -> ${STATUS} (priority ${DEFAULT_PRIORITY})"
echo "Expectation id: ${EXPECTATION_ID}"
echo "To remove it: scripts/delete-mock.sh ${EXPECTATION_ID}"
