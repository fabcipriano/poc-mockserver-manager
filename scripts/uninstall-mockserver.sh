#!/usr/bin/env bash
# Removes all three MockServer instances (product, public, private) and restores the direct
# ALB -> Gateway path for the product topology. The public/private topologies' backends are
# removed entirely, since they only exist to be fronted by MockServer.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Re-applying base overlay to restore the Ingress backend to the Gateway Service..."
kubectl apply -k "${ROOT_DIR}/k8s/base"

echo "Removing MockServer resources (product, public, private)..."
kubectl delete deployment mockserver mockserver-public mockserver-private -n mockserver-poc --ignore-not-found
kubectl delete service mockserver mockserver-public mockserver-private -n mockserver-poc --ignore-not-found
kubectl delete configmap mockserver-init mockserver-public-init mockserver-private-init -n mockserver-poc --ignore-not-found

echo "Removing public and private topologies' backend resources..."
kubectl delete deployment backend-public backend-private -n mockserver-poc --ignore-not-found
kubectl delete service backend-public backend-private -n mockserver-poc --ignore-not-found

echo "Removing mock management web UI resources..."
kubectl delete deployment mock-ui -n mockserver-poc --ignore-not-found
kubectl delete service mock-ui -n mockserver-poc --ignore-not-found

echo "MockServer uninstalled for all three topologies. ALB stand-in routes directly to the Gateway again."
