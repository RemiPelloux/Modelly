#!/usr/bin/env bash
# Compile modelly/_native/fastrng.c in place for development (the .so is gitignored).
#
#   bash scripts/build-native.sh            # with .venv/bin/python, else python3
#   PYTHON=python3.13 bash scripts/build-native.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-$([[ -x "$ROOT/.venv/bin/python" ]] && echo "$ROOT/.venv/bin/python" || echo python3)}"
"$PYTHON" - "$ROOT" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from hatch_build import compile_extension, SOURCE
root = Path(sys.argv[1])
built = compile_extension(root, root / SOURCE.parent)
print(f"built {built}" if built else "native core not built; FastRandom will use the Python fallback")
sys.exit(0 if built else 1)
PY
