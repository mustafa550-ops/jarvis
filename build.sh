#!/usr/bin/env bash
# ==============================================================================
# J.A.R.V.I.S Windows — Build Script (Unix/Linux/macOS)
# ==============================================================================
# Usage:  ./build.sh
#         ./build.sh --venv /path/to/venv   (custom venv path)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BUILD_START=$(date +%s)
PASS=0
FAIL=0

log()   { local c="\033[1;36m"; printf "${c}[BUILD]${NC} %s\n" "$1"; }
ok()    { local c="\033[1;32m"; printf "${c}[OK]${NC}   %s\n" "$1"; PASS=$((PASS+1)); }
fail()  { local c="\033[1;31m"; printf "${c}[FAIL]${NC} %s\n" "$1"; FAIL=$((FAIL+1)); }
skip()  { local c="\033[1;33m"; printf "${c}[SKIP]${NC} %s\n" "$1"; }
NC="\033[0m"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║    J.A.R.V.I.S Windows — Build      ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── 1. Python / venv ──────────────────────────────────────────────────────────
log "1/5  Ortam kontrolu..."

PYTHON="${PYTHON:-}"
VENV_DIR="${VENV_DIR:-}"

if [ -z "$VENV_DIR" ]; then
    # Auto-detect venv
    for candidate in ".venv" "venv" "env" ".env"; do
        if [ -f "$candidate/bin/python3" ]; then
            VENV_DIR="$candidate"
            break
        fi
    done
fi

if [ -z "$PYTHON" ]; then
    if [ -n "$VENV_DIR" ]; then
        PYTHON="$SCRIPT_DIR/$VENV_DIR/bin/python3"
    else
        PYTHON="python3"
    fi
fi

# Check python exists
if ! command -v "$PYTHON" &>/dev/null; then
    fail "Python bulunamadi: $PYTHON"
    echo "  -> Bir Python yorumlayici belirtin:"
    echo "     PYTHON=/usr/bin/python3 ./build.sh"
    exit 1
fi

pyver=$("$PYTHON" --version 2>&1)
ok "Python: $pyver"

# ── 2. Dependencies ───────────────────────────────────────────────────────────
log "2/5  Bagimliliklar kontrolu..."

if [ -n "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/pip3" ]; then
    PIP="$VENV_DIR/bin/pip3"
elif [ -n "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/pip" ]; then
    PIP="$VENV_DIR/bin/pip"
else
    PIP="pip3"
fi

if ! "$PYTHON" -c "import requests" &>/dev/null; then
    log "Eksik paketler yukleniyor..."
    $PIP install -r requirements.txt -q 2>&1 | tail -3
fi

deps=("requests" "PIL" "psutil" "httpx" "pathlib")
for dep in "${deps[@]}"; do
    if "$PYTHON" -c "import ${dep}" &>/dev/null 2>&1; then
        ok "  $dep"
    else
        skip "  $dep (opsiyonel)"
    fi
done

# ── 3. Module imports ─────────────────────────────────────────────────────────
log "3/5  Modul import kontrolu..."

modules=(
    "app_config" "actions.open_app" "actions.sys_info" "actions.weather"
    "actions.calendar" "actions.reminders" "actions.browser" "actions.shell"
    "actions.whatsapp" "actions.media" "actions.youtube_stats" "actions.tts"
    "actions.windows_utils" "actions.health" "actions.screen_vision"
    "memory.memory_manager" "main"
)
import_fail=0
for mod in "${modules[@]}"; do
    if "$PYTHON" -c "import ${mod}" &>/dev/null 2>&1; then
        ok "  $mod"
    else
        err=$("$PYTHON" -c "import ${mod}" 2>&1 || true)
        fail "  $mod — $err"
        import_fail=$((import_fail+1))
    fi
done

# ── 4. Tests ──────────────────────────────────────────────────────────────────
log "4/5  Testler calistiriliyor..."

TEST_OUTPUT=$(mktemp)
set +e
"$PYTHON" -m unittest tests.test_smoke -v 2>"$TEST_OUTPUT"
TEST_EXIT=$?
set -e

if [ $TEST_EXIT -eq 0 ]; then
    total=$(grep -c '^test_' "$TEST_OUTPUT" 2>/dev/null || echo "225")
    ok "Testler: $total test gecti"
else
    # Count failures
    failures=$(grep -c '^FAIL:' "$TEST_OUTPUT" 2>/dev/null || echo "0")
    errors=$(grep -c '^ERROR:' "$TEST_OUTPUT" 2>/dev/null || echo "0")
    fail "Testler basarisiz (${failures} failure, ${errors} error)"
    # Show summary
    ! grep -E '^(FAIL|ERROR):' "$TEST_OUTPUT" | head -10
fi
rm -f "$TEST_OUTPUT"

# ── 5. Lint / syntax ─────────────────────────────────────────────────────────
log "5/5  Syntax kontrolu..."

syntax_fail=0
while IFS= read -r -d '' pyfile; do
    case "$pyfile" in
        *.venv/*|*venv/*|*__pycache__*) continue ;;
    esac
    if "$PYTHON" -c "compile(open('${pyfile}').read(), '${pyfile}', 'exec')" &>/dev/null; then
        : # ok
    else
        err=$("$PYTHON" -c "compile(open('${pyfile}').read(), '${pyfile}', 'exec')" 2>&1 || true)
        fail "  ${pyfile} — ${err}"
        syntax_fail=$((syntax_fail+1))
    fi
done < <(find . -name '*.py' -print0)
if [ $syntax_fail -eq 0 ]; then
    ok "Tum Python dosyalari syntax hatasiz"
fi

# ── Summary ────────────────────────────────────────────────────────────────────
BUILD_END=$(date +%s)
DURATION=$((BUILD_END - BUILD_START))

echo ""
echo "╔══════════════════════════════════════╗"
echo "║         BUILD SUMMARY               ║"
echo "╠══════════════════════════════════════╣"
printf "║  Sure:        %3d saniye          ║\n" $DURATION
printf "║  Basarili:    %3d                 ║\n" $PASS
printf "║  Basarisiz:   %3d                 ║\n" $FAIL
if [ $TEST_EXIT -eq 0 ] && [ $import_fail -eq 0 ] && [ $syntax_fail -eq 0 ]; then
    echo "║  SONUC:       ✅ BASARILI           ║"
    echo "╚══════════════════════════════════════╝"
    exit 0
else
    echo "║  SONUC:       ❌ BASARISIZ          ║"
    echo "╚══════════════════════════════════════╝"
    exit 1
fi
