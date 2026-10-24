#!/usr/bin/env bash
# Open the Mesa 2.3 baseline notebook in Jupyter Lab.
#
# Starts (or reuses) a Jupyter Lab server in the background so it survives the
# terminal being closed, then prints a ready-to-click URL.
#
# Usage:
#   benchmarks/mesa_baseline/open_lab.sh
#   benchmarks/mesa_baseline/open_lab.sh --port 8899
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
VENV="$REPO_ROOT/.venv-mesa2"
PORT="${PORT:-8899}"
IP="127.0.0.1"
STATE_DIR="$HERE/.jupyter"
PID_FILE="$STATE_DIR/server.pid"
TOKEN_FILE="$STATE_DIR/token.txt"
LOG_FILE="$STATE_DIR/server.log"

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

# Allow --port override while still honouring PORT env.
while [ $# -gt 0 ]; do
    case "$1" in
        --port) PORT="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

mkdir -p "$STATE_DIR"

# Reuse a live server if one is already up on this port. The token may not
# exist yet on the first-ever launch, so fall back to an unauthenticated probe
# (a 403 from Jupyter still means *something* is listening on the port).
if curl -sf "http://$IP:$PORT/api/status?token=$(cat "$TOKEN_FILE" 2>/dev/null || true)" >/dev/null 2>&1; then
    TOKEN="$(cat "$TOKEN_FILE" 2>/dev/null || true)"
    echo "server already running:"
    echo "  http://$IP:$PORT/lab?token=$TOKEN"
    exit 0
fi

# Stale PID file? Clean up.
if [ -f "$PID_FILE" ]; then
    OLD_PID="$(cat "$PID_FILE")"
    kill "$OLD_PID" 2>/dev/null || true
    rm -f "$PID_FILE"
fi

# Generate a stable token so the printed URL keeps working across restarts of
# the *same* server.
TOKEN="$(cat "$TOKEN_FILE" 2>/dev/null || openssl rand -hex 16 || echo "modelly")"
echo "$TOKEN" > "$TOKEN_FILE"

cd "$HERE"
nohup "$VENV/bin/jupyter" lab \
    --no-browser \
    --ip="$IP" \
    --port="$PORT" \
    --ServerApp.token="$TOKEN" \
    --ServerApp.root_dir="$HERE" \
    --ServerApp.allow_origin='*' \
    --ServerApp.disable_check_xsrf=True \
    > "$LOG_FILE" 2>&1 &

echo $! > "$PID_FILE"

# Wait for it to come up.
for _ in $(seq 1 30); do
    if curl -sf "http://$IP:$PORT/api/status?token=$TOKEN" >/dev/null 2>&1; then
        echo "Jupyter Lab started (pid $(cat "$PID_FILE")):"
        echo
        echo "  http://$IP:$PORT/lab/tree/Notebook_ABM_TIS_Mis_A_Jour.ipynb?token=$TOKEN"
        echo
        echo "Copy that URL into your browser. To stop the server:"
        echo "  kill $(cat "$PID_FILE")"
        exit 0
    fi
    sleep 1
done

echo "server did not come up; last log lines:" >&2
tail -n 20 "$LOG_FILE" >&2
exit 1
