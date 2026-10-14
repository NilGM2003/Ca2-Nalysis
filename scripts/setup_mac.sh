#!/bin/bash
# One-time setup on a Mac that has no Python (and no code editor).
#
#   1. installs uv if it is missing (uv then downloads the right Python itself),
#   2. builds the project environment from uv.lock,
#   3. checks that the window can start,
#   4. creates "Calcium Analysis.app" on the Desktop.
#
# Needs internet the first time. Safe to run again at any time.
#
# Usage: double-click "Setup Mac.command" in the project folder,
#        or:  bash scripts/setup_mac.sh
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

echo "== Calcium analysis: one-time setup =="
echo "folder: $REPO"
echo

# ---- 1. uv
find_uv() {
    local c
    for c in "$HOME/.local/bin/uv" /opt/homebrew/bin/uv /usr/local/bin/uv \
             "$HOME/.cargo/bin/uv"; do
        if [ -x "$c" ]; then
            export PATH="$(dirname "$c"):$PATH"
            return 0
        fi
    done
    return 1
}

if ! command -v uv >/dev/null 2>&1; then
    find_uv || true
fi
if ! command -v uv >/dev/null 2>&1; then
    echo "[1/4] Installing uv (needs internet)..."
    # (with `set -e` a failed download would exit silently, so test it)
    if ! curl -LsSf https://astral.sh/uv/install.sh | sh; then
        echo "warning: the uv installer did not finish." >&2
    fi
    find_uv || true
fi
if ! command -v uv >/dev/null 2>&1; then
    echo "error: uv could not be installed. Check the internet connection," >&2
    echo "       or install it from https://docs.astral.sh/uv/ and run this again." >&2
    exit 1
fi
echo "[1/4] uv: $(command -v uv)"

# ---- 2. environment (downloads Python and the libraries on the first run)
echo "[2/4] Building the environment (first time: a few minutes)..."
uv sync --frozen

# ---- 3. can the window start?
echo "[3/4] Checking that the window can start..."
if ! uv run --frozen python - <<'EOF'
import sys
sys.path.insert(0, "src")
from calcium.gui.tcltk import point_tcl_tk_at_base_python
point_tcl_tk_at_base_python()
import tkinter
root = tkinter.Tk()
root.destroy()
print("      ok (Tk works)")
EOF
then
    echo "error: the window toolkit (Tk) does not start on this Mac." >&2
    echo "       Send the messages above to whoever maintains this project." >&2
    exit 1
fi

# ---- 4. desktop icon
echo "[4/4] Creating the desktop icon..."
bash "$REPO/scripts/make_mac_app.sh"

echo
echo "Setup finished. Open \"Calcium Analysis\" on the Desktop."
echo "macOS may ask permission to access folders (Desktop, Documents): click Allow."
