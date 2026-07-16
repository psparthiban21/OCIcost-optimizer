#!/usr/bin/env bash
set -euo pipefail

CLUSTER="${CLUSTER:-oci-cost-optimizer}"
IMAGE="${IMAGE:-localhost/oci-cost-optimizer/backend-api:local}"
NAMESPACE="${NAMESPACE:-oci-cost-optimizer}"

if ! command -v podman >/dev/null 2>&1; then
  echo "podman is required" >&2
  exit 1
fi

if ! command -v k3d >/dev/null 2>&1; then
  echo "k3d is required" >&2
  exit 1
fi

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required" >&2
  exit 1
fi

if ! k3d cluster list "${CLUSTER}" >/dev/null 2>&1; then
  k3d cluster create "${CLUSTER}" \
    --agents 1 \
    --k3s-arg "--disable=traefik@server:0" \
    --k3s-node-label "optimizer.local=true@agent:0"
fi

"$(dirname "$0")/podman-build.sh"

TMP_IMAGE="/tmp/oci-cost-optimizer-backend-local.tar"
podman save "${IMAGE}" -o "${TMP_IMAGE}"
k3d image import "${TMP_IMAGE}" -c "${CLUSTER}"

kubectl config use-context "k3d-${CLUSTER}" >/dev/null
kubectl apply -k k8s/k3d
kubectl -n "${NAMESPACE}" rollout status deployment/analytics-engine --timeout=120s
kubectl -n "${NAMESPACE}" rollout status deployment/agent-service --timeout=120s
kubectl -n "${NAMESPACE}" rollout status deployment/backend-api --timeout=120s

cat <<MSG
k3d stack is ready.

Run:
  kubectl -n ${NAMESPACE} port-forward svc/backend-api 8080:80

Then open:
  http://127.0.0.1:8080

Ollama should be running on your Mac at:
  http://127.0.0.1:11434
MSG

