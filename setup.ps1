Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     J.A.R.V.I.S Windows Kurulumu     ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

$ErrorActionPreference = "Stop"

# --- Python kontrol ---
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "[HATA] Python bulunamadi." -ForegroundColor Red
    Write-Host "Python 3.10+ kurup tekrar deneyin: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# --- Python versiyon kontrol ---
try {
    $pyVer = & python --version 2>&1
    Write-Host "[OK] $pyVer bulundu" -ForegroundColor Green
} catch {
    Write-Host "[HATA] Python versiyonu alinamadi: $_" -ForegroundColor Red
    exit 1
}

# --- pip güncelleme ---
Write-Host "[ADIM 1/4] pip güncelleniyor..." -ForegroundColor Cyan
try {
    & python -m pip install --upgrade pip
    Write-Host "[OK] pip güncellendi" -ForegroundColor Green
} catch {
    Write-Host "[UYARI] pip güncellenemedi: $_" -ForegroundColor Yellow
}

# --- Bagimliliklari yukle ---
Write-Host "[ADIM 2/4] Python paketleri yukleniyor..." -ForegroundColor Cyan
$reqFile = Join-Path $PSScriptRoot "requirements.txt"
if (-not (Test-Path $reqFile)) {
    Write-Host "[HATA] requirements.txt bulunamadi: $reqFile" -ForegroundColor Red
    exit 1
}

try {
    & python -m pip install -r $reqFile
    if ($LASTEXITCODE -ne 0) { throw "pip install basarisiz (exit code: $LASTEXITCODE)" }
    Write-Host "[OK] Tum paketler yuklendi" -ForegroundColor Green
} catch {
    Write-Host "[HATA] Paket yukleme basarisiz: $_" -ForegroundColor Red
    Write-Host "Not: Baglantinizi kontrol edin veya elle yuklemeyi deneyin:" -ForegroundColor Yellow
    Write-Host "  pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

# --- Binary kontrolleri ---
Write-Host "[ADIM 2.5/4] Gerekli binary'ler kontrol ediliyor..." -ForegroundColor Cyan

$binaries = @(
    @{Name="edge-tts"; Label="Edge-TTS (Microsoft Neural Ses)"; Optional=$false},
    @{Name="mpg123"; Label="mpg123 (MP3 Oynatici)"; Optional=$true},
    @{Name="ffmpeg"; Label="FFmpeg (Ses/Video Donusturucu)"; Optional=$true}
)

$missingCount = 0
foreach ($bin in $binaries) {
    $found = Get-Command $bin.Name -ErrorAction SilentlyContinue
    if ($found) {
        Write-Host "  [OK] $($bin.Label)" -ForegroundColor Green
    } else {
        if ($bin.Optional) {
            Write-Host "  [UYARI] $($bin.Label) bulunamadi — opsiyonel" -ForegroundColor Yellow
        } else {
            Write-Host "  [HATA] $($bin.Label) bulunamadi!" -ForegroundColor Red
            $missingCount++
        }
    }
}

if ($missingCount -gt 0) {
    Write-Host ""
    Write-Host "[UYARI] $missingCount zorunlu binary eksik. Soyle kurabilirsiniz:" -ForegroundColor Yellow
    Write-Host "  winget install edge-tts" -ForegroundColor Yellow
    Write-Host "  veya: pip install edge-tts" -ForegroundColor Yellow
    Write-Host "  Detay: helpers/bin/README.md" -ForegroundColor Yellow
}

Write-Host ""

# --- Ses surucu bildirimi ---
Write-Host "[ADIM 3/4] Ses suruculeri kontrol ediliyor..." -ForegroundColor Cyan
$pulseOk = $false
try {
    $null = pyaudio --version 2>$null
    $pulseOk = $true
} catch { }

if (-not $pulseOk) {
    Write-Host "[BILGI] PyAudio'nun bagimli oldugu PortAudio surucusu sistemde yoksa," -ForegroundColor Yellow
    Write-Host "       soyle kurabilirsiniz:" -ForegroundColor Yellow
    Write-Host "       winget install PortAudio" -ForegroundColor Yellow
}

# --- Model dosyasi kontrolleri ---
Write-Host "[ADIM 3.5/4] Model dosyalari kontrol ediliyor..." -ForegroundColor Cyan

$models = @(
    @{Path="voice\Fahrettin-TTS\tr_TR-fahrettin-medium.onnx"; Label="Piper TTS (Fahrettin ses modeli)"; Optional=$false},
    @{Path="voice\faster-whisper\model.bin"; Label="Faster-Whisper STT modeli"; Optional=$false},
    @{Path="voice\faster-whisper-large-backup\model.bin"; Label="Faster-Whisper Large yedek modeli"; Optional=$true}
)

$modelMissing = 0
foreach ($m in $models) {
    $modelPath = Join-Path $PSScriptRoot $m.Path
    if (Test-Path $modelPath) {
        Write-Host "  [OK] $($m.Label)" -ForegroundColor Green
    } else {
        if ($m.Optional) {
            Write-Host "  [UYARI] $($m.Label) bulunamadi — opsiyonel" -ForegroundColor Yellow
        } else {
            Write-Host "  [HATA] $($m.Label) bulunamadi!" -ForegroundColor Red
            $modelMissing++
        }
    }
}

if ($modelMissing -gt 0) {
    Write-Host ""
    Write-Host "[UYARI] $modelMissing zorunlu model dosyasi eksik." -ForegroundColor Yellow
    Write-Host "       Model dosyalarini voice/ klasorune indirin:" -ForegroundColor Yellow
    Write-Host "       Piper TTS: https://huggingface.co/hexgrad/Kokoro-82M" -ForegroundColor Yellow
    Write-Host "       Whisper: python -c 'from faster_whisper import WhisperModel; WhisperModel(\"base\")'" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║      KURULUM TAMAMLANDI!             ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "Baslatmak icin:" -ForegroundColor White
Write-Host "  python main.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "Not: Kullanmadan once asagidaki adimlari tamamlayin:" -ForegroundColor Yellow
Write-Host "  1. config/api_keys.json dosyasina Gemini API anahtarini girin" -ForegroundColor Yellow
Write-Host "  2. (istege bagli) Ollama lokalinizde calisiyor mu kontrol edin" -ForegroundColor Yellow
Write-Host ""
Read-Host "Cikmak icin Enter'a basin"
