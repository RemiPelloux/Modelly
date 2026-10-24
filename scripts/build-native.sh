#!/usr/bin/env bash
# Compile the modelly/_native C modules in place for development (the .so files are gitignored).
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
from hatch_build import NATIVE_DIR, SOURCES, compile_extension
root = Path(sys.argv[1])
failed = 0
for source in SOURCES:
    built = compile_extension(root, root / NATIVE_DIR, source)
    print(f"built {built}" if built else f"{source.name} not built; its Python fallback will be used")
    failed += built is None
sys.exit(1 if failed else 0)
PY
