#!/usr/bin/env bash
# Sends 20000 GET requests, alternating between /booking/1 and /booking/12, to
# generate traffic for exercising the mock-ui "Recent Requests" page.
# Defaults to the ALB stand-in Ingress (same entrypoint real traffic uses); set
# BASE_URL to target something else (e.g. MockServer directly).
#
# Usage: scripts/load-test-recent-requests.sh
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
TOTAL_REQUESTS="${TOTAL_REQUESTS:-20000}"
CONCURRENCY="${CONCURRENCY:-50}"

echo "Sending ${TOTAL_REQUESTS} requests to ${BASE_URL} (concurrency: ${CONCURRENCY})..."

seq 1 "${TOTAL_REQUESTS}" | xargs -P "${CONCURRENCY}" -I{} bash -c '
  if (( {} % 2 == 0 )); then
    path="/booking/1"
  else
    path="/booking/12"
  fi
  curl -s -o /dev/null -w "%{http_code}\n" "'"${BASE_URL}"'${path}"
' > /tmp/load-test-recent-requests.status

echo "Done. Status code counts:"
sort /tmp/load-test-recent-requests.status | uniq -c | sort -rn
rm -f /tmp/load-test-recent-requests.status
