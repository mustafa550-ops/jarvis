#!/usr/bin/env python3
"""
scripts/install_rnnoise.py
JARVIS için RNNoise prebuilt binary'lerini indirip audio/lib/ altına yerleştirir.
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
LIB_DIR = PROJECT_ROOT / "audio" / "lib"

SYSTEM = platform.system()
ARCH = platform.machine().lower()

# werman/noise-suppression-for-voice releases — RNNoise DLL/SO içerir
# NOT: Gerçek URL için https://github.com/werman/noise-suppression-for-voice/releases
# adresini kontrol edin ve en güncel rnnoise.zip linkini kullanın.
RELEASE_URL = (
    "https://github.com/werman/noise-suppression-for-voice/releases/download/"
    "v1.03/rnnoise.zip"
)


def download_file(url: str, dest: Path) -> None:
    print(f"[İndiriliyor] {url} -> {dest}")
    urllib.request.urlretrieve(url, str(dest))


def install_windows() -> None:
    """Windows: rnnoise.dll indir."""
    LIB_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = LIB_DIR / "rnnoise.zip"
    try:
        download_file(RELEASE_URL, zip_path)
        extracted = False
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                if member.lower().endswith("rnnoise.dll"):
                    zf.extract(member, LIB_DIR)
                    extracted_path = LIB_DIR / member
                    final = LIB_DIR / "rnnoise.dll"
                    if extracted_path != final:
                        shutil.move(str(extracted_path), str(final))
                    print(f"[OK] {final}")
                    extracted = True
                    break
        zip_path.unlink(missing_ok=True)
        if not extracted:
            print("[UYARI] Zip içinde rnnoise.dll bulunamadı.")
    except Exception as exc:
        print(f"[HATA] İndirilemedi: {exc}")
        _print_manual_instructions()

    # Eğer hala yoksa manuel talimat göster
    if not (LIB_DIR / "rnnoise.dll").exists():
        _print_manual_instructions()


def install_linux() -> None:
    """Linux: Kaynaktan derle veya apt ile kur."""
    LIB_DIR.mkdir(parents=True, exist_ok=True)
    print("[Linux] RNNoise kurulum seçenekleri:")

    # Önce apt dene
    import subprocess

    try:
        ret = subprocess.run(
            ["apt-get", "install", "-y", "librnnoise-dev"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if ret.returncode == 0:
            print("[OK] librnnoise-dev kuruldu.")
            # Kütüphaneyi proje lib klasörüne kopyala
            so_candidates = [
                Path("/usr/lib/x86_64-linux-gnu/librnnoise.so"),
                Path("/usr/lib/aarch64-linux-gnu/librnnoise.so"),
                Path("/usr/lib/librnnoise.so"),
            ]
            for src in so_candidates:
                if src.exists():
                    dest = LIB_DIR / src.name
                    shutil.copy2(str(src), str(dest))
                    print(f"[OK] Kopyalandı: {src} -> {dest}")
                    return
            # Sistem kütüphanesi olarak erişilebilir, kopyalamaya gerek yok
            print("[OK] Sistem kütüphanesi hazır.")
            return
    except FileNotFoundError:
        pass
    except Exception as exc:
        print(f"  apt denemesi başarısız: {exc}")

    # apt yoksa / başarısızsa manuel talimat
    _print_build_instructions()


def install_macos() -> None:
    """macOS: Homebrew veya kaynaktan derle."""
    LIB_DIR.mkdir(parents=True, exist_ok=True)
    import subprocess

    try:
        ret = subprocess.run(
            ["brew", "install", "rnnoise"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if ret.returncode == 0:
            print("[OK] brew install rnnoise başarılı.")
            # Homebrew kurulum yerini bul
            try:
                prefix = subprocess.run(
                    ["brew", "--prefix", "rnnoise"],
                    capture_output=True, text=True, timeout=10,
                ).stdout.strip()
                lib_path = Path(prefix) / "lib" / "librnnoise.dylib"
                if lib_path.exists():
                    dest = LIB_DIR / lib_path.name
                    shutil.copy2(str(lib_path), str(dest))
                    print(f"[OK] Kopyalandı: {lib_path} -> {dest}")
                    return
            except Exception:
                pass
            print("[OK] Sistem kütüphanesi hazır.")
            return
    except FileNotFoundError:
        pass
    except Exception as exc:
        print(f"  brew denemesi başarısız: {exc}")

    _print_build_instructions()


def _print_manual_instructions() -> None:
    print()
    print("[MANUEL] Lütfen https://github.com/werman/noise-suppression-for-voice/releases")
    print("         adresinden rnnoise.dll indirip audio/lib/ altına koyun.")
    print()


def _print_build_instructions() -> None:
    print()
    print("[KAYNAKTAN DERLEME]")
    print("  git clone https://github.com/xiph/rnnoise.git")
    print("  cd rnnoise && ./autogen.sh && ./configure && make && sudo make install")
    print(f"  sudo cp /usr/local/lib/librnnoise.so* {LIB_DIR}/")
    print()


def main() -> None:
    print(f"[JARVIS] RNNoise kurulum scripti — {SYSTEM} {ARCH}")
    print()

    if SYSTEM == "Windows":
        install_windows()
    elif SYSTEM == "Linux":
        install_linux()
    elif SYSTEM == "Darwin":
        install_macos()
    else:
        print(f"[UYARI] Desteklenmeyen sistem: {SYSTEM}")
        sys.exit(1)

    print()
    print(f"[Kontrol] {LIB_DIR} içeriği:")
    if LIB_DIR.exists():
        for f in sorted(LIB_DIR.iterdir()):
            print(f"  - {f.name}")
    else:
        print("  (dizin yok)")

    # Sonda kontrol et
    if SYSTEM == "Windows":
        check = LIB_DIR / "rnnoise.dll"
    elif SYSTEM == "Darwin":
        check = LIB_DIR / "librnnoise.dylib"
    else:
        check = LIB_DIR / "librnnoise.so"

    if check.exists() or SYSTEM != "Windows":
        print(f"\n[KONTROL] RNNoise hazır.")
    else:
        print(f"\n[KONTROL] RNNoise kurulumu tamamlanamadı. {_print_manual_instructions()}")


if __name__ == "__main__":
    main()
