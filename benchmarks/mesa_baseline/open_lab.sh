#!/usr/bin/env bash
# Open the Mesa 2.3 baseline notebook in Jupyter Lab.
#
# The notebook lives next to this script and is gitignored (research code, not
# library code). Nothing here runs any simulation; it just serves the
# playbook so you can read it and run cells yourself.
#
# Usage:
#   benchmarks/mesa_baseline/open_lab.sh            # opens in this directory
#   benchmarks/mesa_baseline/open_lab.sh --port 9000
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
VENV="$REPO_ROOT/.venv-mesa2"

if [ ! -x "$VENV/bin/jupyter" ]; then
    echo "missing environment: $VENV" >&2
    echo "run: python -m venv .venv-mesa2 && .venv-mesa2/bin/pip install \\" >&2
    echo "  'mesa==2.3.2' numpy pandas matplotlib seaborn jupyterlab ipykernel" >&2
    exit 1
fi

NOTEBOOK="$HERE/Notebook_ABM_TIS_Mis_A_Jour.ipynb"
if [ ! -f "$NOTEBOOK" ]; then
    echo "notebook not found: $NOTEBOOK" >&2
    echo "it is gitignored on purpose; put it in $HERE" >&2
    exit 1
fi

cd "$HERE"
exec "$VENV/bin/jupyter" lab "$NOTEBOOK" "$@"
