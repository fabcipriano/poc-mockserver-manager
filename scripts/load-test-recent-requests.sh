#!/usr/bin/env bash
# Sends 100000 GET requests, hitting /booking/1 .. /booking/100000 sequentially,
# with up to 50 concurrent requests, to generate traffic for exercising the
# mock-ui "Recent Requests" page.
#
# Usage: scripts/load-test-recent-requests.sh
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
TOTAL_REQUESTS="${TOTAL_REQUESTS:-100000}"
CONCURRENCY="${CONCURRENCY:-50}"   # fixed at 50 by default
STATUS_FILE="/tmp/load-test-recent-requests.status"

rm -f "${STATUS_FILE}"

echo "Sending ${TOTAL_REQUESTS} requests to ${BASE_URL} (concurrency: ${CONCURRENCY})..."

# 1..TOTAL_REQUESTS → /booking/1.. /booking/TOTAL_REQUESTS
seq 1 "${TOTAL_REQUESTS}" | xargs -P "${CONCURRENCY}" -I{} bash -c '
  id="$1"
  curl -s -o /dev/null -w "%{http_code}\n" "'"${BASE_URL}"'/booking/${id}"
' _ {} >> "${STATUS_FILE}"

echo "Done. Status code counts:"
sort "${STATUS_FILE}" | uniq -c | sort -rn
rm -f "${STATUS_FILE}"