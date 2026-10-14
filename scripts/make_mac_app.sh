#!/bin/bash
# Build "Calcium Analysis.app": a double-clickable launcher for app.py (macOS).
#
# Usage (from anywhere):
#     bash scripts/make_mac_app.sh              # puts the app on the Desktop
#     bash scripts/make_mac_app.sh ~/Applications
#
# The app is a thin launcher: it runs `uv run python app.py` in THIS repo, so
# it always uses your current code. If you move or re-clone the repo, run this
# script again. Run it once per computer/user.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${1:-$HOME/Desktop}"
APP="$DEST/Calcium Analysis.app"

# Find uv. Apps started from Finder do not see your shell PATH, so the full
# path is written into the launcher. (Set UV=/path/to/uv to override.)
UV="${UV:-$(command -v uv || true)}"
if [ -z "$UV" ]; then
    for c in "$HOME/.local/bin/uv" /opt/homebrew/bin/uv /usr/local/bin/uv \
             "$HOME/.cargo/bin/uv"; do
        if [ -x "$c" ]; then UV="$c"; break; fi
    done
fi
if [ -z "$UV" ]; then
    echo "error: could not find 'uv'. Install it first: https://docs.astral.sh/uv/" >&2
    exit 1
fi
if [ ! -f "$REPO/app.py" ]; then
    echo "error: $REPO/app.py not found" >&2
    exit 1
fi

echo "repo : $REPO"
echo "uv   : $UV"
echo "app  : $APP"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# ---- the launcher (REPO and UV are baked in; the rest runs at launch time)
{
    echo '#!/bin/bash'
    printf 'REPO=%q\n' "$REPO"
    printf 'UV=%q\n' "$UV"
    cat <<'EOF'
LOG="$HOME/Library/Logs/CalciumAnalysis.log"
mkdir -p "$(dirname "$LOG")"

# Start from a clean environment, as a normal Finder launch would.
unset VIRTUAL_ENV PYTHONPATH SSL_CERT_FILE SSL_CERT_DIR
export PATH="$(dirname "$UV"):/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

cd "$REPO" || exit 1
{
    echo
    echo "=== $(date) : launching ==="
} >> "$LOG"

if ! "$UV" run --frozen --project "$REPO" python app.py >> "$LOG" 2>&1; then
    osascript -e 'display dialog "Calcium Analysis stopped with an error.\n\nDetails: ~/Library/Logs/CalciumAnalysis.log" buttons {"OK"} default button "OK" with icon caution' >/dev/null 2>&1 || true
fi
EOF
} > "$APP/Contents/MacOS/launcher"
chmod +x "$APP/Contents/MacOS/launcher"

# ---- Info.plist
cat > "$APP/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>               <string>Calcium Analysis</string>
    <key>CFBundleDisplayName</key>        <string>Calcium Analysis</string>
    <key>CFBundleIdentifier</key>         <string>local.calcium-analysis.launcher</string>
    <key>CFBundleExecutable</key>         <string>launcher</string>
    <key>CFBundleIconFile</key>           <string>AppIcon</string>
    <key>CFBundlePackageType</key>        <string>APPL</string>
    <key>CFBundleVersion</key>            <string>1.0</string>
    <key>CFBundleShortVersionString</key> <string>1.0</string>
    <key>NSHighResolutionCapable</key>    <true/>
</dict>
</plist>
EOF

# ---- icon (optional: the app still works without it)
if command -v iconutil >/dev/null 2>&1; then
    TMP="$(mktemp -d)"
    if "$UV" run --frozen --project "$REPO" python "$REPO/scripts/make_icon.py" \
            "$TMP/AppIcon.iconset" \
       && iconutil -c icns "$TMP/AppIcon.iconset" \
            -o "$APP/Contents/Resources/AppIcon.icns"; then
        echo "icon : ok"
    else
        echo "icon : skipped (could not build it; the app still works)"
    fi
    rm -rf "$TMP"
else
    echo "icon : skipped (iconutil not available)"
fi

touch "$APP"        # make Finder refresh the icon
echo
echo "Done. Double-click \"Calcium Analysis\" on your Desktop."
echo "If it does not open, look at ~/Library/Logs/CalciumAnalysis.log"
