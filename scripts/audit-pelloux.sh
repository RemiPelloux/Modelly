#!/usr/bin/env bash
# Pelloux size audit — CI + local (bash scripts/ci-local.sh audit).
# Ratchet: files in pelloux-baseline.json may shrink but never grow.
set -euo pipefail
exec python3 "$(cd "$(dirname "$0")" && pwd)/pelloux_audit.py" audit
