#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PID=""
FRONTEND_PID=""

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

cleanup() {
  trap - EXIT INT TERM
  for process_id in "$BACKEND_PID" "$FRONTEND_PID"; do
    if [[ -n "$process_id" ]] && kill -0 "$process_id" 2>/dev/null; then
      kill "$process_id" 2>/dev/null || true
    fi
  done
  for process_id in "$BACKEND_PID" "$FRONTEND_PID"; do
    if [[ -n "$process_id" ]]; then
      wait "$process_id" 2>/dev/null || true
    fi
  done
}

trap cleanup EXIT INT TERM

require_command uv
require_command npm

if [[ ! -d "$PROJECT_ROOT/frontend/node_modules" ]]; then
  echo "Frontend dependencies are missing. Run: cd frontend && npm install" >&2
  exit 1
fi

cd "$PROJECT_ROOT"

CUDA_LIBRARY_PATH="$(uv run --extra full python -c 'import os; import nvidia.cublas.lib; import nvidia.cudnn.lib; print(os.path.dirname(nvidia.cublas.lib.__file__) + ":" + os.path.dirname(nvidia.cudnn.lib.__file__))' 2>/dev/null || true)"
if [[ -n "$CUDA_LIBRARY_PATH" ]]; then
  export LD_LIBRARY_PATH="$CUDA_LIBRARY_PATH${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

uv run --extra full uvicorn fir.serving.app:app --reload --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

(
  cd "$PROJECT_ROOT/frontend"
  exec npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
) &
FRONTEND_PID=$!

echo "Frontend: http://127.0.0.1:5173"
echo "API:      http://127.0.0.1:8000"
echo "Press Ctrl+C to stop both processes."

if wait -n "$BACKEND_PID" "$FRONTEND_PID"; then
  exit 0
else
  exit $?
fi
