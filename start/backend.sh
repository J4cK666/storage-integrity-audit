#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/audit-backEnd"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
BACKEND_RELOAD="${BACKEND_RELOAD:-0}"

if [[ ! -d "${BACKEND_DIR}" ]]; then
    echo "Backend directory not found: ${BACKEND_DIR}" >&2
    exit 1
fi

if [[ -x "${BACKEND_DIR}/.venvlinux/bin/python" ]]; then
    PYTHON_BIN="${BACKEND_DIR}/.venvlinux/bin/python"
elif [[ -x "${BACKEND_DIR}/.venv/bin/python" ]]; then
    PYTHON_BIN="${BACKEND_DIR}/.venv/bin/python"
else
    PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1 && [[ ! -x "${PYTHON_BIN}" ]]; then
    echo "Python executable not found: ${PYTHON_BIN}" >&2
    echo "Set PYTHON_BIN=/path/to/python or create audit-backEnd/.venvlinux." >&2
    exit 1
fi

cd "${BACKEND_DIR}"
export PYTHONPATH="${BACKEND_DIR}:${PYTHONPATH:-}"

if ! "${PYTHON_BIN}" -c "import uvicorn" >/dev/null 2>&1; then
    echo "uvicorn is not installed for ${PYTHON_BIN}." >&2
    echo "Install backend dependencies first, for example:" >&2
    echo "  cd ${BACKEND_DIR} && ${PYTHON_BIN} -m pip install -r requirements.txt" >&2
    exit 1
fi

ARGS=(app.main:app --host "${BACKEND_HOST}" --port "${BACKEND_PORT}")
if [[ "${BACKEND_RELOAD}" == "1" || "${BACKEND_RELOAD}" == "true" ]]; then
    ARGS+=(--reload)
fi

echo "Starting backend: http://${BACKEND_HOST}:${BACKEND_PORT}"
exec "${PYTHON_BIN}" -m uvicorn "${ARGS[@]}" "$@"
