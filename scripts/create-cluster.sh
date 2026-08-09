#!/usr/bin/env bash
# Creates (or recreates) the local kind cluster used by this POC, with ingress-nginx installed.
# Requires: docker, kubectl, kind.
set -euo pipefail

CLUSTER_NAME="mockserver-poc"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if kind get clusters 2>/dev/null | grep -qx "${CLUSTER_NAME}"; then
  echo "Deleting existing kind cluster '${CLUSTER_NAME}'..."
  kind delete cluster --name "${CLUSTER_NAME}"
fi

echo "Creating kind cluster '${CLUSTER_NAME}' with ingress port mappings..."
kind create cluster --name "${CLUSTER_NAME}" --config "${SCRIPT_DIR}/kind-config.yaml"

echo "Installing ingress-nginx (kind provider manifest)..."
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.10.1/deploy/static/provider/kind/deploy.yaml

echo "Waiting for ingress-nginx controller pod to be created..."
kubectl wait --namespace ingress-nginx \
  --for=create pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=60s

echo "Waiting for ingress-nginx controller to become ready..."
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=180s

echo "Cluster '${CLUSTER_NAME}' is ready."
