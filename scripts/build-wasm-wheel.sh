#!/usr/bin/env bash
# Build the Modelly wheel for WebAssembly (Pyodide), with the modelly/_native C modules
# compiled by Emscripten. modelly export-web --wheel ships it instead of the pure wheel.
#
#   bash scripts/build-wasm-wheel.sh [OUT_DIR]      # default: dist/wasm/
#
# Needs pyodide-build on PATH, run from a Python of the same minor version as Pyodide's
# (3.14 for Pyodide 314), and its cross-build environment with Emscripten:
#
#   pip install pyodide-build
#   pyodide xbuildenv install 314.0.7 && pyodide xbuildenv install-emscripten
#
# The wheel is built from a copy of the files git does not ignore, so compiled modules of
# the host (modelly/_native/*.so) never end up in it. A C module that does not compile
# fails the build (MODELLY_REQUIRE_NATIVE=1).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$(mkdir -p "${1:-$ROOT/dist/wasm}" && cd "${1:-$ROOT/dist/wasm}" && pwd)"
SRC="$(mktemp -d)"
trap 'rm -rf "$SRC"' EXIT

git -C "$ROOT" ls-files -z --cached --others --exclude-standard \
  | (cd "$ROOT" && xargs -0 cp -P --parents -t "$SRC")
cd "$SRC"
MODELLY_REQUIRE_NATIVE=1 pyodide build --outdir "$OUT" "$SRC"
ls "$OUT"/*.whl
