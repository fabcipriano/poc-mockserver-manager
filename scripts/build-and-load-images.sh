#!/usr/bin/env bash
# Builds the backend, gateway, and mock-ui stand-in images for all three topologies (product,
# public, private) and loads them into the kind cluster.
set -euo pipefail

CLUSTER_NAME="mockserver-poc"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

docker build -t mockserver-poc/backend:local "${ROOT_DIR}/backend"
docker build -t mockserver-poc/gateway:local "${ROOT_DIR}/gateway"
docker build -t mockserver-poc/backend-public:local "${ROOT_DIR}/backend-public"
docker build -t mockserver-poc/backend-private:local "${ROOT_DIR}/backend-private"
docker build -t mockserver-poc/mock-ui:local "${ROOT_DIR}/mock-ui"

kind load docker-image mockserver-poc/backend:local --name "${CLUSTER_NAME}"
kind load docker-image mockserver-poc/gateway:local --name "${CLUSTER_NAME}"
kind load docker-image mockserver-poc/backend-public:local --name "${CLUSTER_NAME}"
kind load docker-image mockserver-poc/backend-private:local --name "${CLUSTER_NAME}"
kind load docker-image mockserver-poc/mock-ui:local --name "${CLUSTER_NAME}"

echo "Images built and loaded into kind cluster '${CLUSTER_NAME}'."
