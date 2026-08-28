#!/usr/bin/env bash
# Official local judge against the running bot (docs/7.Tracker.md pre-submission gate).
# Usage: bash sutra/scripts/run_simulator.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# Load .env (API keys) so the simulator reads them from env, never from the file.
set -a; [ -f .env ] && . ./.env || true; set +a
export BOT_URL="${BOT_URL:-http://127.0.0.1:8081}"
export LLM_PROVIDER="${LLM_PROVIDER:-openai}"
exec python "$PWD/../challenge-pack/judge_simulator.py" "${TEST_SCENARIO:-all}"
