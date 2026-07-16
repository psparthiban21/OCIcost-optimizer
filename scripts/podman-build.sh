#!/usr/bin/env bash
set -euo pipefail

IMAGE="${IMAGE:-localhost/oci-cost-optimizer/backend-api:local}"

podman build \
  --pull=never \
  --memory=1g \
  --cpus=1 \
  -f apps/backend-api/Dockerfile \
  -t "${IMAGE}" \
  .

printf 'Built %s\n' "${IMAGE}"

