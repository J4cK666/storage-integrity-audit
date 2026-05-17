#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
FRONTEND_DIR="${PROJECT_ROOT}/audit-frontEnd"

FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5500}"

if [[ ! -d "${FRONTEND_DIR}" ]]; then
    echo "Frontend directory not found: ${FRONTEND_DIR}" >&2
    exit 1
fi

if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="${PYTHON_BIN:-python3}"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="${PYTHON_BIN:-python}"
else
    echo "Python is required to serve the static frontend." >&2
    exit 1
fi

cd "${FRONTEND_DIR}"

echo "Starting frontend: http://${FRONTEND_HOST}:${FRONTEND_PORT}/"
echo "Login page:        http://${FRONTEND_HOST}:${FRONTEND_PORT}/src/views/login/login.html"
exec "${PYTHON_BIN}" -m http.server "${FRONTEND_PORT}" --bind "${FRONTEND_HOST}" "$@"
