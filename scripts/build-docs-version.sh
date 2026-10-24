#!/usr/bin/env bash
# Build the HTML docs of one version, as the published site serves it.
#
#   bash scripts/build-docs-version.sh dev <out>      # this checkout, as /dev/
#   bash scripts/build-docs-version.sh v1.1.0 <out>   # tag v1.1.0, as /1.1/
#
# A tag is built in place when HEAD is that tag (the docs workflow), otherwise from a
# temporary git worktree, importing modelly from it. A tag whose docs/conf.py predates
# the version switcher is built through scripts/docs-overlay/conf.py.
# MODELLY_NB_EXECUTION=off skips running the tutorials. PYTHON picks the interpreter
# (default: .venv/bin/python, else python3); it needs the docs extras installed.
# SPHINXOPTS adds sphinx-build options, e.g. SPHINXOPTS="-W --keep-going".
set -euo pipefail

if [[ $# -ne 2 ]]; then
  sed -n '2,12p' "$0" >&2
  exit 2
fi
REF="$1"
OUT="$(mkdir -p "$2" && cd "$2" && pwd)"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-$([[ -x "$ROOT/.venv/bin/python" ]] && echo "$ROOT/.venv/bin/python" || echo python3)}"
WORK="$(mktemp -d)"
TREE="$ROOT"
cleanup() {
  if [[ "$TREE" != "$ROOT" ]]; then git -C "$ROOT" worktree remove --force "$TREE"; fi
  rm -rf "$WORK"
}
trap cleanup EXIT

if [[ "$REF" == dev ]]; then
  export MODELLY_DOCS_VERSION=dev
elif [[ "$REF" =~ ^v([0-9]+)\.([0-9]+)\.[0-9]+$ ]]; then
  export MODELLY_DOCS_VERSION="${BASH_REMATCH[1]}.${BASH_REMATCH[2]}"
  export MODELLY_DOCS_RELEASE="${REF#v}"
  if [[ "$(git -C "$ROOT" rev-parse HEAD)" != "$(git -C "$ROOT" rev-parse "$REF^{commit}")" ]]; then
    TREE="$WORK/tree"
    git -C "$ROOT" worktree add --detach --quiet "$TREE" "$REF"
  fi
else
  echo "version must be dev or a vX.Y.Z tag, got: $REF" >&2
  exit 2
fi

CONF_ARGS=()
if ! grep -q apply_versioning "$TREE/docs/conf.py"; then
  export MODELLY_TAG_CONF="$TREE/docs/conf.py"
  CONF_ARGS=(-c "$ROOT/scripts/docs-overlay")
fi
echo "building $REF as /$MODELLY_DOCS_VERSION/ into $OUT"
PYTHONPATH="$TREE${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON" -m sphinx -b html -q ${SPHINXOPTS:-} \
  -d "$WORK/doctrees" -D nb_execution_cache_path="$WORK/jupyter_cache" ${CONF_ARGS[@]+"${CONF_ARGS[@]}"} "$TREE/docs" "$OUT"
