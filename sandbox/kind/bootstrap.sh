#!/usr/bin/env bash
# Bootstrap a shared local kind cluster for Raphael sandbox development.
# Idempotent: safe to re-run. Does NOT create a cluster per sandbox run.
set -euo pipefail

CLUSTER_NAME="${RAPHAEL_KIND_CLUSTER:-raphael-sandbox}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v kind >/dev/null 2>&1; then
  echo "kind not found. Install: https://kind.sigs.k8s.io/docs/user/quick-start/#installation" >&2
  exit 1
fi
if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl not found. Install kubectl first." >&2
  exit 1
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found. kind requires Docker (or a compatible runtime)." >&2
  exit 1
fi

if kind get clusters 2>/dev/null | grep -qx "${CLUSTER_NAME}"; then
  echo "kind cluster '${CLUSTER_NAME}' already exists"
else
  echo "creating kind cluster '${CLUSTER_NAME}'"
  kind create cluster --name "${CLUSTER_NAME}" --config "${SCRIPT_DIR}/cluster.yaml"
fi

kubectl cluster-info --context "kind-${CLUSTER_NAME}"
kubectl apply -f "${SCRIPT_DIR}/namespace-baseline.yaml" || true

echo "Export kubeconfig context: kind-${CLUSTER_NAME}"
echo "Then run controller with:"
echo "  RAPHAEL_CLUSTER_BACKEND=kind KUBECONFIG=\$HOME/.kube/config cargo run -p raphael-sandbox-controller"
