#!/usr/bin/env bash
# ONE-COMMAND full run: fresh server -> load dataset -> judge simulator.
# Usage:  bash sutra/scripts/run_all.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUTRA_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

PORT="${PORT:-8081}"
BOT_URL="http://127.0.0.1:${PORT}"

# load .env safely (handles CRLF, spaces, quotes)
load_dotenv() {
  local f="$1"
  [ -f "$f" ] || return 0
  while IFS='=' read -r k v; do
    k="${k//$'\r'/}"; v="${v//$'\r'/}"
    v="${v%\"}"; v="${v#\"}"; v="${v%\'}"; v="${v#\'}"
    case "$k" in ''|\#*) continue ;; esac
    export "$k=$v"
  done < <(sed 's/\r//g' "$f")
}

echo "== [1/5] Freeing port ${PORT} =="
OLD_PID=$(netstat -ano 2>/dev/null | grep "LISTENING" | grep ":${PORT} " | awk '{print $NF}' | head -1)
if [ -n "${OLD_PID}" ]; then
  taskkill //F //PID "${OLD_PID}" >/dev/null 2>&1 || true
  sleep 1
fi

echo "== [2/5] Starting Sutra on ${BOT_URL} =="
(cd "${SUTRA_DIR}" && python -m uvicorn bot:app --host 127.0.0.1 --port "${PORT}" --log-level warning) &
SERVER_PID=$!
for _ in $(seq 1 20); do curl -s "${BOT_URL}/v1/healthz" >/dev/null 2>&1 && break; sleep 1; done
curl -s "${BOT_URL}/v1/healthz" >/dev/null 2>&1 || { echo "   server failed to start"; kill "${SERVER_PID}"; exit 1; }
echo "   server up"

echo "== [3/5] Fresh state (judge pushes its own contexts) =="
curl -s -X POST "${BOT_URL}/v1/teardown" >/dev/null || true
# NOTE: no pre-load here — judge_simulator pushes the base contexts itself
# during warmup. Pre-loading caused 409 stale_version conflicts (contexts
# already at version 1), which the judge marks as [FAIL].

echo "== [4/5] Running judge simulator =="
load_dotenv "${SUTRA_DIR}/.env"
export BOT_URL
export LLM_API_KEY="${OPENROUTER_API_KEY:-}"
export LLM_PROVIDER="${LLM_PROVIDER:-openrouter}"
export LLM_MODEL="${LLM_OPENROUTER_MODEL:-minimax/minimax-m3:free}"
python "${ROOT}/challenge-pack/judge_simulator.py" "${TEST_SCENARIO:-all}" || true

echo "== [5/5] Cleaning up (PID ${SERVER_PID}) =="
kill "${SERVER_PID}" >/dev/null 2>&1 || true
echo "Done."