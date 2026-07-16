#!/usr/bin/env bash
set -euo pipefail

CLUSTER="${CLUSTER:-oci-cost-optimizer}"
k3d cluster delete "${CLUSTER}"

