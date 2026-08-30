#!/bin/sh
# Interactive machine-local setup after the project build completes.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(dirname -- "$SCRIPT_DIR")
VENV_PYTHON="$PROJECT_DIR/firmware/smalltv-agent-hub/.venv/bin/python"

if [ ! -x "$VENV_PYTHON" ]; then
  echo "Build environment not found." >&2
  echo "Run ./scripts/bootstrap_macos.sh --build first." >&2
  exit 1
fi

exec "$VENV_PYTHON" "$SCRIPT_DIR/setup_macos.py" "$@"
