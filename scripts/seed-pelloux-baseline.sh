#!/usr/bin/env bash
# Seed pelloux-baseline.json from the current tree.
# Re-seed ONLY when a split/removal legitimately changes the recorded ceilings.
set -euo pipefail
exec python3 "$(cd "$(dirname "$0")" && pwd)/pelloux_audit.py" seed
