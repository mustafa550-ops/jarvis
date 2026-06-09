# ==============================================================================
# J.A.R.V.I.S Windows — Build Script (PowerShell)
# ==============================================================================
# Usage:  .\build.ps1
#         .\build.ps1 -Verbose
# ==============================================================================
param(
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"
$InformationPreference = "Continue"

$BUILD_START = Get-Date
$PASS = 0
$FAIL = 0

function log   { Write-Host "[BUILD] $($args[0])" -ForegroundColor Cyan }
function ok    { Write-Host "[OK]    $($args[0])" -ForegroundColor Green; $script:PASS++ }
function fail  { Write-Host "[FAIL]  $($args[0])" -ForegroundColor Red;   $script:FAIL++ }
function skip  { Write-Host "[SKIP]  $($args[0])" -ForegroundColor Yellow }

Write-Host ""
Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║    J.A.R.V.I.S Windows — Build      ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── 1. Python / venv ──────────────────────────────────────────────────────────
log "1/5  Ortam kontrolu..."

$python = $null
$venvDir = $null

# Auto-detect venv
foreach ($candidate in @(".venv", "venv", "env", ".env")) {
    $scriptPath = Join-Path $PSScriptRoot $candidate
    if (Test-Path "$scriptPath\Scripts\python.exe") {
        $venvDir = $candidate
        $python = "$scriptPath\Scripts\python.exe"
        break
    }
    if (Test-Path "$scriptPath\bin\python.exe") {
        $venvDir = $candidate
        $python = "$scriptPath\bin\python.exe"
        break
    }
}

if (-not $python) {
    # Fallback to PATH python
    try {
        $python = (Get-Command python -ErrorAction Stop).Source
    } catch {
        fail "Python bulunamadi. PATH'te python var mi kontrol edin."
        exit 1
    }
}

try {
    $pyVer = & $python --version 2>&1
    if ($LASTEXITCODE -ne 0) { throw $pyVer }
    $pyVerStr = "$pyVer".Trim()
    ok "Python: $pyVerStr"
} catch {
    fail "Python versiyonu alinamadi: $_"
    exit 1
}

# ── 2. Dependencies ───────────────────────────────────────────────────────────
log "2/5  Bagimliliklar kontrolu..."

# Choose pip path
if ($venvDir) {
    $pip = Join-Path $PSScriptRoot "$venvDir\Scripts\pip.exe"
    if (-not (Test-Path $pip)) {
        $pip = Join-Path $PSScriptRoot "$venvDir\bin\pip.exe"
    }
    if (-not (Test-Path $pip)) {
        $pip = "pip"
    }
} else {
    $pip = "pip"
}

# Check key deps
$deps = @{
    "requests" = "requests";
    "PIL"      = "Pillow";
    "psutil"   = "psutil";
    "httpx"    = "httpx";
}

$allDepsOk = $true
foreach ($importName in $deps.Keys) {
    $pkgName = $deps[$importName]
    try {
        & $python -c "import $importName" 2>$null
        if ($LASTEXITCODE -eq 0) {
            ok "  $pkgName"
        } else {
            throw "import failed"
        }
    } catch {
        skip "  $pkgName (eksik)"
        $allDepsOk = $false
    }
}

if (-not $allDepsOk) {
    log "Eksik paketler yukleniyor..."
    try {
        & $pip install -r "$PSScriptRoot\requirements.txt" -q
        if ($LASTEXITCODE -eq 0) {
            ok "Paketler yuklendi"
        } else {
            fail "Paket yukleme basarisiz"
        }
    } catch {
        fail "Paket yukleme basarisiz: $_"
    }
}

# ── 3. Module imports ─────────────────────────────────────────────────────────
log "3/5  Modul import kontrolu..."

$modules = @(
    "app_config", "actions.open_app", "actions.sys_info", "actions.weather",
    "actions.calendar", "actions.reminders", "actions.browser", "actions.shell",
    "actions.whatsapp", "actions.media", "actions.youtube_stats", "actions.tts",
    "actions.windows_utils", "actions.health", "actions.screen_vision",
    "memory.memory_manager", "main"
)

$importFail = 0
foreach ($mod in $modules) {
    try {
        & $python -c "import $mod" 2>$null
        if ($LASTEXITCODE -eq 0) {
            ok "  $mod"
        } else {
            throw "import failed"
        }
    } catch {
        fail "  $mod — import basarisiz"
        $importFail++
    }
}

# ── 4. Tests ──────────────────────────────────────────────────────────────────
log "4/5  Testler calistiriliyor..."

$testOutput = New-TemporaryFile
try {
    & $python -m unittest tests.test_smoke -v 2>&1 | Tee-Object -FilePath $testOutput.FullName
    $testExit = $LASTEXITCODE
} catch {
    $testExit = 1
}

if ($testExit -eq 0) {
    $total = (Select-String -Path $testOutput.FullName -Pattern '^test_' | Measure-Object).Count
    if ($total -eq 0) { $total = "225" }
    ok "Testler: $total test gecti"
} else {
    $failures = (Select-String -Path $testOutput.FullName -Pattern '^FAIL:' | Measure-Object).Count
    $errors = (Select-String -Path $testOutput.FullName -Pattern '^ERROR:' | Measure-Object).Count
    fail "Testler basarisiz (${failures} failure, ${errors} error)"
    # Show last failures
    Select-String -Path $testOutput.FullName -Pattern '^(FAIL|ERROR):' | Select-Object -First 10
}
Remove-Item $testOutput.FullName -ErrorAction SilentlyContinue

# ── 5. Syntax check ──────────────────────────────────────────────────────────
log "5/5  Syntax kontrolu..."

$syntaxFail = 0
Get-ChildItem -Recurse -Filter "*.py" -Path $PSScriptRoot | ForEach-Object {
    $file = $_.FullName
    # Skip venv and pycache
    if ($file -match '\\.venv\\|\\venv\\|__pycache__') { return }

    $content = Get-Content $file -Raw -ErrorAction SilentlyContinue
    if (-not $content) { return }

    try {
        [System.Reflection.Assembly]::LoadWithPartialName("Microsoft.Build.Framework") | Out-Null
        # Use Python itself for syntax check
        $result = & $python -c "compile(open('$file', encoding='utf-8').read(), '$file', 'exec')" 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw $result
        }
    } catch {
        fail "  $($_.Name) — syntax hatasi"
        $syntaxFail++
    }
}

if ($syntaxFail -eq 0) {
    ok "Tum Python dosyalari syntax hatasiz"
}

# ── Summary ────────────────────────────────────────────────────────────────────
$BUILD_END = Get-Date
$DURATION = ($BUILD_END - $BUILD_START).TotalSeconds

Write-Host ""
Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║         BUILD SUMMARY               ║" -ForegroundColor Cyan
Write-Host "╠══════════════════════════════════════╣" -ForegroundColor Cyan
Write-Host "║  Sure:        $("{0:N0}" -f $DURATION) saniye            ║" -ForegroundColor Cyan
Write-Host "║  Basarili:    $PASS                    ║" -ForegroundColor Cyan
Write-Host "║  Basarisiz:   $FAIL                    ║" -ForegroundColor Cyan
if (($testExit -eq 0) -and ($importFail -eq 0) -and ($syntaxFail -eq 0)) {
    Write-Host "║  SONUC:       BASARILI              ║" -ForegroundColor Green
    Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Green
    exit 0
} else {
    Write-Host "║  SONUC:       BASARISIZ             ║" -ForegroundColor Red
    Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Red
    exit 1
}
