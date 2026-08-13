#!/usr/bin/env bash
# Installs all three MockServer-fronted topologies (product, public, private):
#   product: ALB -> MockServer -> Gateway -> Backend
#   public/private: ALB -> MockServer -> Backend (simplified NodeJS stand-in)
# The product topology's Gateway/Backend manifests/config are never touched by this script.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

kubectl apply -k "${ROOT_DIR}/k8s/overlays/with-mockserver"

echo "Waiting for the public and private topologies' backends to become ready..."
kubectl rollout status deployment/backend-public -n mockserver-poc --timeout=120s
kubectl rollout status deployment/backend-private -n mockserver-poc --timeout=120s

echo "Waiting for all three MockServer instances to become ready..."
kubectl rollout status deployment/mockserver -n mockserver-poc --timeout=120s
kubectl rollout status deployment/mockserver-public -n mockserver-poc --timeout=120s
kubectl rollout status deployment/mockserver-private -n mockserver-poc --timeout=120s

echo "Waiting for the mock management web UI to become ready..."
kubectl rollout status deployment/mock-ui -n mockserver-poc --timeout=120s

echo "MockServer installed for all three topologies. ALB stand-in now routes:"
echo "  /         -> MockServer (product)"
echo "  /public   -> MockServer (public)"
echo "  /private  -> MockServer (private)"
echo "Manage mocks at http://localhost:8080/mock-ui/"
