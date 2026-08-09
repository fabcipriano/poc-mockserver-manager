#!/usr/bin/env bash
# Deletes a single MockServer expectation by id, restoring pass-through for its route.
# Get the id from the output of scripts/add-mock.sh (or scripts/list-mocks.sh).
#
# IMPORTANT: deleting by method/path instead of id is unsafe here - the seeded
# catch-all forwarding expectation matches any method and path (`/.*`), so a
# clear-by-request-matcher call also matches and removes it, breaking pass-through
# for every other route until MockServer is restarted (which reloads the initializer).
#
# Usage: scripts/delete-mock.sh <EXPECTATION_ID>
# Example: scripts/delete-mock.sh 54a40674-1ce2-4ce0-8915-11d1ed1f677d
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <EXPECTATION_ID>" >&2
  echo "Get the id from scripts/add-mock.sh output or scripts/list-mocks.sh" >&2
  exit 1
fi

EXPECTATION_ID="$1"
MOCKSERVER_URL="${MOCKSERVER_URL:-http://localhost:1080}"

curl -sS -X PUT "${MOCKSERVER_URL}/mockserver/clear" \
  -H "Content-Type: application/json" \
  -d "{\"id\": \"${EXPECTATION_ID}\"}"

echo
echo "Mock expectation ${EXPECTATION_ID} removed. Its route now passes through to the Gateway again."
