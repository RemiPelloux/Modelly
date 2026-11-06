#!/bin/bash
# The paper's artifact checks from a fresh clone of HEAD with the working tree's paper/ and
# benchmark results laid over it (the 1.5.0 data are not committed yet), in a fresh venv
# whose dependencies are resolved from PyPI now.
set -u
SRC=$(cd "$(dirname "$0")/../.." && pwd)
DIR=$(mktemp -d -p "$SRC/build" fresh150.XXXX)
git clone -q "$SRC" "$DIR/repo" && cd "$DIR/repo" || exit 1
git -C "$SRC" ls-files -m -o --exclude-standard -- paper benchmarks | while read -r f; do
  mkdir -p "$(dirname "$f")"; cp -p "$SRC/$f" "$f"; done
git -C "$SRC" diff --name-only --diff-filter=D HEAD -- paper benchmarks | xargs -r rm -rf
echo "commit $(git rev-parse --short HEAD), overlay $(git status --short | wc -l) paths"
uv venv -q --python 3.14 .venv && uv pip install -q -p .venv/bin/python -e '.[dev]' 'mesa==3.5.1' || exit 1
.venv/bin/python -c "import sys, modelly, numpy, scipy, mesa; from importlib.metadata import version as v; print(sys.version.split()[0], v('modelly-abm'), numpy.__version__, scipy.__version__, mesa.__version__)"
time .venv/bin/python paper/scripts/verify_artifacts.py 2>&1 | grep -c "^same"; ls paper/tables/*.tex | wc -l; .venv/bin/python paper/scripts/verify_artifacts.py 2>&1 | grep -v "^same\|^ran"
echo "verify exit ${PIPESTATUS[0]}"
time .venv/bin/python paper/scripts/check_listings.py 2>&1 | tail -15
echo "listings exit ${PIPESTATUS[0]}"
echo "dir $DIR"
