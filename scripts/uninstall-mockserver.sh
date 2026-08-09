#!/usr/bin/env bash
# Removes MockServer and restores the direct ALB -> Gateway path.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Re-applying base overlay to restore the Ingress backend to the Gateway Service..."
kubectl apply -k "${ROOT_DIR}/k8s/base"

echo "Removing MockServer resources..."
kubectl delete deployment mockserver -n mockserver-poc --ignore-not-found
kubectl delete service mockserver -n mockserver-poc --ignore-not-found
kubectl delete configmap mockserver-init -n mockserver-poc --ignore-not-found

echo "Removing mock management web UI resources..."
kubectl delete deployment mock-ui -n mockserver-poc --ignore-not-found
kubectl delete service mock-ui -n mockserver-poc --ignore-not-found

echo "MockServer uninstalled. ALB stand-in routes directly to the Gateway again."
