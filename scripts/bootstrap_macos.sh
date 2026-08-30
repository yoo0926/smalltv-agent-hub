#!/bin/sh
# Reproducible, project-local build for a fresh macOS clone.
set -eu

usage() {
  cat <<'EOF'
Usage: scripts/bootstrap_macos.sh [options]

Creates firmware/smalltv-agent-hub/.venv, installs the pinned development
toolchain, regenerates the embedded web UI, and runs the bridge tests. This
command never changes user hooks or launchd services; run setup_macos.sh after
the build for those machine-local changes.

Options:
  --build                 Build the SmallTV Pro firmware (large first download).
  --python PATH           Python 3.9+ interpreter to use.
  -h, --help              Show this help.

Examples:
  ./scripts/bootstrap_macos.sh
  ./scripts/bootstrap_macos.sh --build
  ./scripts/setup_macos.sh
EOF
}

BUILD=0
PYTHON_BIN="${PYTHON_BIN:-}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --build) BUILD=1 ;;
    --python)
      [ "$#" -ge 2 ] || { echo "--python requires a value" >&2; exit 2; }
      PYTHON_BIN=$2
      shift
      ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

if [ "$(uname -s)" != "Darwin" ]; then
  echo "This build bootstrap currently supports macOS only." >&2
  exit 1
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(dirname -- "$SCRIPT_DIR")
FIRMWARE_DIR="$PROJECT_DIR/firmware/smalltv-agent-hub"
VENV_DIR="$FIRMWARE_DIR/.venv"
PIO_CORE_DIR="$FIRMWARE_DIR/.pio-core"

if [ -z "$PYTHON_BIN" ]; then
  if [ -x /opt/homebrew/bin/python3 ]; then
    PYTHON_BIN=/opt/homebrew/bin/python3
  elif [ -x /usr/local/bin/python3 ]; then
    PYTHON_BIN=/usr/local/bin/python3
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=$(command -v python3)
  else
    echo "Python 3.9+ is required. Install it first (for example: brew install python)." >&2
    exit 1
  fi
fi

"$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else "Python 3.9+ is required")'

echo "Project: $PROJECT_DIR"
echo "Python:  $PYTHON_BIN"

if [ ! -x "$VENV_DIR/bin/python" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

VENV_PYTHON="$VENV_DIR/bin/python"
PIO="$VENV_DIR/bin/pio"
"$VENV_PYTHON" -m pip install --disable-pip-version-check --upgrade "pip==26.2.1"
"$VENV_PYTHON" -m pip install --disable-pip-version-check --requirement "$PROJECT_DIR/requirements-dev.txt"

WEBUI_HEADER="$FIRMWARE_DIR/src/webui.h"
WEBUI_HEADER_BEFORE=$(cksum "$WEBUI_HEADER")
"$VENV_PYTHON" "$FIRMWARE_DIR/tools/gzip_webui.py"
WEBUI_HEADER_AFTER=$(cksum "$WEBUI_HEADER")
if [ "$WEBUI_HEADER_BEFORE" != "$WEBUI_HEADER_AFTER" ]; then
  echo "Generated webui.h was out of date." >&2
  echo "Review the regenerated file, then rerun this command." >&2
  exit 1
fi

"$VENV_PYTHON" "$PROJECT_DIR/scripts/check_repository_hygiene.py"
PYTHONPATH="$PROJECT_DIR/src" "$VENV_PYTHON" -m unittest discover -s "$PROJECT_DIR/tests" -v

if [ "$BUILD" -eq 1 ]; then
  PLATFORMIO_CORE_DIR="$PIO_CORE_DIR" PLATFORMIO_SETTING_ENABLE_TELEMETRY=no \
    "$PIO" run --project-dir "$FIRMWARE_DIR" -e smalltv_esp32_8mb
fi

echo "Bootstrap complete."
if [ "$BUILD" -eq 0 ]; then
  echo "Firmware build was skipped; rerun with --build when needed."
fi
echo "Run ./scripts/setup_macos.sh when you are ready to configure this Mac."
