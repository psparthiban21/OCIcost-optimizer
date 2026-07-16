#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH=apps/backend-api/src
python_bin="${PYTHON_BIN:-.venv/bin/python}"

if [[ ! -x "${python_bin}" ]]; then
  python_bin="python3"
fi

"${python_bin}" -m unittest discover apps/backend-api/tests
"${python_bin}" scripts/security_scan.py

echo "QA checks passed"

