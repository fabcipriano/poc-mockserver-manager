#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
TOTAL_REQUESTS="${TOTAL_REQUESTS:-100000}"
CONCURRENCY="${CONCURRENCY:-50}"
STATUS_FILE="/tmp/load-test-recent-requests.status"

rm -f "${STATUS_FILE}"

echo "Sending ${TOTAL_REQUESTS} requests to ${BASE_URL} (concurrency: ${CONCURRENCY})..."

seq 1 "${TOTAL_REQUESTS}" | xargs -P "${CONCURRENCY}" -I{} bash -c '
  id="$1"
  padded_id=$(printf "%06d" "$id")
  curl -s -o /dev/null -w "%{http_code}\n" "'"${BASE_URL}"'/booking/${padded_id}"
' _ {}

>> "${STATUS_FILE}"

echo "Done. Status code counts:"
sort "${STATUS_FILE}" | uniq -c | sort -rn
rm -f "${STATUS_FILE}"