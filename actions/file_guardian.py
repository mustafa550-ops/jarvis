"""
File Guardian — Dosya sistemi izleme, temizlik ve arşivleme.
OpenClaw'dan uyarlanmıştır.
"""

from __future__ import annotations

import os
import shutil
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


import traceback
def find_large_files(path: str = "", min_size_mb: int = 100, limit: int = 20) -> str:
    """
    Büyük dosyaları bulur.
    path: Aranacak klasör (boşsa kullanıcı dizini)
    min_size_mb: Minimum dosya boyutu MB cinsinden
    limit: Maksimum sonuç sayısı
    """
    search_path = Path(path or os.path.expanduser("~"))
    min_bytes = min_size_mb * 1024 * 1024
    limit = max(1, min(100, int(limit)))

    large_files = []

    try:
        for root, _, files in os.walk(search_path):
            for filename in files:
                try:
                    filepath = Path(root) / filename
                    size = filepath.stat().st_size
                    if size >= min_bytes:
                        large_files.append((filepath, size))
                except (OSError, PermissionError):
                    continue
    except Exception as e:
        return f"Tarama hatası: {e}"

    large_files.sort(key=lambda x: x[1], reverse=True)

    if not large_files:
        return f"{min_size_mb}MB'dan büyük dosya bulunamadı."

    lines = [f"── BÜYÜK DOSYALAR (>{min_size_mb}MB, top {limit}) ──"]
    for filepath, size in large_files[:limit]:
        size_str = f"{size / (1024**3):.2f}GB" if size >= 1024**3 else f"{size / (1024**2):.1f}MB"
        lines.append(f"  • {filepath} — {size_str}")

    total_size = sum(size for _, size in large_files)
    total_str = f"{total_size / (1024**3):.2f}GB" if total_size >= 1024**3 else f"{total_size / (1024**2):.1f}MB"
    lines.append(f"\nToplam: {len(large_files)} dosya, {total_str}")

    return "\n".join(lines)


def find_duplicate_files(path: str = "", limit: int = 10) -> str:
    """
    Yinelenen dosyaları bulur (hash tabanlı).
    path: Aranacak klasör
    limit: Maksimum sonuç sayısı
    """
    search_path = Path(path or os.path.expanduser("~"))
    limit = max(1, min(50, int(limit)))

    from collections import defaultdict
    import hashlib

    hashes = defaultdict(list)

    try:
        for root, _, files in os.walk(search_path):
            for filename in files:
                try:
                    filepath = Path(root) / filename
                    # Hızlı hash: ilk 8KB + son 8KB
                    with open(filepath, "rb") as f:
                        head = f.read(8192)
                        f.seek(-8192, 2)
                        tail = f.read(8192)
                    file_hash = hashlib.md5(head + tail).hexdigest()
                    hashes[file_hash].append(filepath)
                except (OSError, PermissionError):
                    continue
    except Exception as e:
        return f"Tarama hatası: {e}"

    duplicates = {h: files for h, files in hashes.items() if len(files) > 1}

    if not duplicates:
        return "Yinelenen dosya bulunamadı."

    lines = [f"── YİNELENEN DOSYALAR ──"]
    count = 0
    for file_hash, files in sorted(duplicates.items(), key=lambda x: len(x[1]), reverse=True):
        if count >= limit:
            break
        lines.append(f"\nHash: {file_hash[:16]}... ({len(files)} kopya)")
        for f in files[:5]:
            size = f.stat().st_size
            size_str = f"{size / (1024**2):.1f}MB" if size >= 1024**2 else f"{size / 1024:.1f}KB"
            lines.append(f"  • {f} ({size_str})")
        if len(files) > 5:
            lines.append(f"  ... ve {len(files) - 5} kopya daha")
        count += 1

    return "\n".join(lines)


def archive_old_files(path: str = "", days: int = 30, archive_path: str = "") -> str:
    """
    Belirli süre erişilmeyen dosyaları arşivler.
    path: Aranacak klasör
    days: Kaç günden eski dosyalar arşivlenecek
    archive_path: Arşiv dosyası yolu (boşsa otomatik)
    """
    search_path = Path(path or os.path.expanduser("~"))
    cutoff = datetime.now() - timedelta(days=int(days))

    if not archive_path:
        archive_name = f"archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        archive_path = str(search_path / archive_name)

    archived = []
    errors = []

    try:
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(search_path):
                for filename in files:
                    try:
                        filepath = Path(root) / filename
                        mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
                        if mtime < cutoff:
                            arcname = str(filepath.relative_to(search_path))
                            zf.write(filepath, arcname)
                            archived.append(str(filepath))
                    except (OSError, PermissionError) as e:
                        errors.append(str(e))
                        continue
    except Exception as e:
        return f"Arşivleme hatası: {e}"

    if not archived:
        return f"{days} günden eski dosya bulunamadı."

    return f"Arşivlendi: {len(archived)} dosya → {archive_path}"


def cleanup_folder(path: str, pattern: str = "*", dry_run: bool = True) -> str:
    """
    Klasördeki dosyaları temizler.
    path: Temizlenecek klasör
    pattern: Dosya deseni (örn. "*.tmp", "*.log")
    dry_run: True ise sadece raporlar, silmez
    """
    target = Path(path)
    if not target.exists():
        return f"Klasör bulunamadı: {path}"

    import fnmatch
    to_delete = []
    total_size = 0

    for item in target.rglob("*"):
        if item.is_file() and fnmatch.fnmatch(item.name, pattern):
            to_delete.append(item)
            total_size += item.stat().st_size

    if not to_delete:
        return f"'{pattern}' desenine uyan dosya bulunamadı."

    lines = [f"── TEMİZLİK RAPORU: {path} ──"]
    lines.append(f"Desen: {pattern}")
    lines.append(f"Bulunan: {len(to_delete)} dosya, {total_size / (1024**2):.1f}MB")

    if dry_run:
        lines.append("\n[DRY RUN — silinmedi]")
        for f in to_delete[:10]:
            lines.append(f"  • {f}")
        if len(to_delete) > 10:
            lines.append(f"  ... ve {len(to_delete) - 10} dosya daha")
        return "\n".join(lines)

    deleted = 0
    freed = 0
    for f in to_delete:
        try:
            size = f.stat().st_size
            f.unlink()
            deleted += 1
            freed += size
        except Exception:
            continue

    return f"Temizlendi: {deleted}/{len(to_delete)} dosya silindi, {freed / (1024**2):.1f}MB boşaltıldı."


def get_folder_summary(path: str = "") -> str:
    """Klasör özet istatistikleri."""
    target = Path(path or os.path.expanduser("~"))
    if not target.exists():
        return f"Klasör bulunamadı: {path}"

    total_size = 0
    file_count = 0
    dir_count = 0
    ext_counts = {}

    try:
        for item in target.rglob("*"):
            if item.is_file():
                file_count += 1
                total_size += item.stat().st_size
                ext = item.suffix.lower() or "(uzantısız)"
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
            elif item.is_dir():
                dir_count += 1
    except Exception as e:
        return f"Tarama hatası: {e}"

    lines = [f"── KLASÖR ÖZETİ: {target} ──"]
    lines.append(f"Dosya: {file_count}")
    lines.append(f"Klasör: {dir_count}")
    size_str = f"{total_size / (1024**3):.2f}GB" if total_size >= 1024**3 else f"{total_size / (1024**2):.1f}MB"
    lines.append(f"Toplam boyut: {size_str}")

    if ext_counts:
        lines.append("\nEn çok dosya türü:")
        for ext, count in sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            lines.append(f"  {ext}: {count}")

    return "\n".join(lines)
