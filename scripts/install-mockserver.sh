#!/usr/bin/env bash
# Installs MockServer in front of the Gateway: ALB -> MockServer -> Gateway -> Backend.
# The Gateway's own manifests/config are never touched by this script.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

kubectl apply -k "${ROOT_DIR}/k8s/overlays/with-mockserver"

echo "Waiting for mockserver to become ready..."
kubectl rollout status deployment/mockserver -n mockserver-poc --timeout=120s

echo "Waiting for the mock management web UI to become ready..."
kubectl rollout status deployment/mock-ui -n mockserver-poc --timeout=120s

echo "MockServer installed. ALB stand-in now routes through MockServer first."
echo "Manage mocks at http://localhost:8080/mock-ui/"
