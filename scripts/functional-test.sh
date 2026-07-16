#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"

curl -fsS "${BASE_URL}/api/v1/health" >/dev/null
curl -fsS "${BASE_URL}/api/v1/ready" >/dev/null
curl -fsS "${BASE_URL}/api/v1/dashboard?region=all&service=all" >/dev/null
curl -fsS -X POST "${BASE_URL}/api/v1/copilot" \
  -H "content-type: application/json" \
  -d '{"question":"Where can I save the most?","filters":{"region":"all","service":"all"}}' >/dev/null

echo "Functional checks passed against ${BASE_URL}"

