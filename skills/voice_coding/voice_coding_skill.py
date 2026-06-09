"""
Voice Coding Skill — sesli komutlarla kod yazma ve düzenleme.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import traceback

__all__ = ["route_voice_coding_request"]

SKILL_NAME = "Sesli Kod Yazma"
SKILL_ID = "voice-coding-v1"
SKILL_VERSION = "1.0.0"

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Trigger patterns (Türkçe + İngilizce)
_TRIGGERS = {
    "create": re.compile(
        r"(?:kod\s+yaz|dosya\s+olustur|dosya\s+oluştur|yeni\s+dosya|create\s+file|write\s+code)",
        re.IGNORECASE,
    ),
    "add_function": re.compile(
        r"(?:fonksiyon\s+ekle|metot\s+ekle|add\s+function|add\s+method)",
        re.IGNORECASE,
    ),
    "add_import": re.compile(
        r"(?:import\s+ekle|kutuphane\s+ekle|kütüphane\s+ekle|add\s+import)",
        re.IGNORECASE,
    ),
    "fix": re.compile(
        r"(?:kod\s+duzelt|kod\s+düzelt|hata\s+duzelt|hata\s+düzelt|fix\s+code|fix\s+error)",
        re.IGNORECASE,
    ),
    "refactor": re.compile(
        r"(?:refactor\s+et|kodu\s+duzenle|kodu\s+düzenle|kodu\s+iyilestir|kodu\s+iyileştir)",
        re.IGNORECASE,
    ),
}


def _extract_file_path(text: str) -> Optional[str]:
    """Extract file path from command text."""
    # Match common patterns: "file: path", "dosya: path", or just a .py path
    patterns = [
        r"(?:file|dosya|path)\s*[::]\s*(\S+)",
        r"(\S+\.\w+)",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1)
    return None


def _extract_function_name(text: str) -> Optional[str]:
    """Extract function name from command."""
    m = re.search(r"(?:fonksiyon|function|metot|method)\s+(?:adı|ismi|adi)?\s*[::]\s*(\w+)", text, re.IGNORECASE)
    if m:
        return m.group(1)
    # Fallback: find "def function_name" pattern
    m = re.search(r"def\s+(\w+)", text)
    if m:
        return m.group(1)
    return None


def _handle_create(text: str) -> str:
    """Create a new code file."""
    file_path = _extract_file_path(text)
    if not file_path:
        return "Dosya yolu belirtilmedi. Ornek: kod yaz path: deneme.py"

    full_path = BASE_DIR / file_path
    if full_path.exists():
        return f"{file_path} zaten mevcut."

    # Extract code content (text after first colon or newline)
    content = re.sub(r"(?:kod\s+yaz|dosya\s+oluştur|yeni\s+dosya|create\s+file|write\s+code)\s+\S+\s*", "", text, flags=re.IGNORECASE).strip()
    if not content:
        content = f'"""\nAuto-generated file: {file_path}\n"""\n'

    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return f"{file_path} olusturuldu ({len(content)} karakter)."
    except Exception as exc:
        traceback.print_exc()
        return f"Dosya olusturulamadi: {exc}"


def _handle_add_function(text: str) -> str:
    """Add a function to an existing file."""
    file_path = _extract_file_path(text)
    if not file_path:
        return "Dosya yolu belirtilmedi."

    full_path = BASE_DIR / file_path
    if not full_path.exists():
        return f"{file_path} bulunamadi."

    func_name = _extract_function_name(text)
    if not func_name:
        return "Fonksiyon adi belirtilmedi."

    # Extract function body
    func_body = re.sub(
        r".*?(?:fonksiyon|function|metot|method).*?" + (func_name or "") + r"\s*",
        "", text, flags=re.IGNORECASE
    ).strip()
    if not func_body:
        func_body = f"    pass"

    new_code = f"\ndef {func_name}():\n{func_body}\n"

    try:
        with open(full_path, "a", encoding="utf-8") as f:
            f.write(new_code)
        return f"{func_name} fonksiyonu {file_path} dosyasina eklendi."
    except Exception as exc:
        traceback.print_exc()
        return f"Fonksiyon eklenemedi: {exc}"


def _handle_add_import(text: str) -> str:
    """Add an import to an existing Python file."""
    file_path = _extract_file_path(text)
    if not file_path:
        return "Dosya yolu belirtilmedi."

    full_path = BASE_DIR / file_path
    if not full_path.exists():
        return f"{file_path} bulunamadi."

    stripped = _TRIGGERS["add_import"].sub("", text).strip()
    import_match = re.search(r"(import\s+\S+|from\s+\S+\s+import\s+\S+)", stripped)
    if not import_match:
        return "Import ifadesi bulunamadi."

    import_stmt = import_match.group(1).rstrip(".,;")
    if not import_stmt.endswith("\n"):
        import_stmt += "\n"

    try:
        content = full_path.read_text(encoding="utf-8")
        if import_stmt.strip() in content:
            return f"{import_stmt.strip()} zaten mevcut."

        # Add after last existing import or at top of file
        lines = content.splitlines(keepends=True)
        last_import_line = -1
        for i, line in enumerate(lines):
            if line.strip().startswith(("import ", "from ")):
                last_import_line = i

        insert_pos = last_import_line + 1 if last_import_line >= 0 else 0
        lines.insert(insert_pos, import_stmt)
        full_path.write_text("".join(lines), encoding="utf-8")
        return f"{import_stmt.strip()} import edildi."
    except Exception as exc:
        traceback.print_exc()
        return f"Import eklenemedi: {exc}"


def _handle_fix(text: str) -> str:
    """Fix code errors by reading the file and suggesting corrections."""
    file_path = _extract_file_path(text)
    if not file_path:
        return "Dosya yolu belirtilmedi. Ornek: kod duzelt path: hatali_dosya.py"

    full_path = BASE_DIR / file_path
    if not full_path.exists():
        return f"{file_path} bulunamadi."

    try:
        content = full_path.read_text(encoding="utf-8")
        # Extract error description from command
        error_desc = re.sub(
            r"(?:kod\s+d|hata\s+d|fix\s+code|fix\s+error|duzelt)\s+\S+\s*",
            "", text, flags=re.IGNORECASE
        ).strip()

        if not error_desc:
            return (
                f"{file_path} okundu ({len(content)} karakter). "
                "Hata aciklamasi belirtilmemis. Dosyayi inceleyip duzeltme icin"
                " 'su hatayi duzelt: ...' seklinde belirtin."
            )
        return (
            f"{file_path} icinde hata araniyor: '{error_desc[:100]}'. "
            f"Dosya {len(content.splitlines())} satir. "
            "Satir bazli duzeltme icin dosyayi acip duzenleme yapmaliyim."
        )
    except Exception as exc:
        traceback.print_exc()
        return f"Dosya okunamadi: {exc}"


def _handle_refactor(text: str) -> str:
    """Refactor code by restructuring functions."""
    file_path = _extract_file_path(text)
    if not file_path:
        return "Refactor edilecek dosya belirtilmedi. Ornek: refactor et path: dosya.py"

    full_path = BASE_DIR / file_path
    if not full_path.exists():
        return f"{file_path} bulunamadi."

    try:
        content = full_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        func_count = sum(1 for l in lines if l.strip().startswith("def "))
        class_count = sum(1 for l in lines if l.strip().startswith("class "))
        total_lines = len(lines)

        return (
            f"{file_path}: {total_lines} satir, {func_count} fonksiyon, {class_count} sinif. "
            "Refactoring icin: 1) Uzun fonksiyonlari bol, "
            "2) Tekrar eden kodu cikar, "
            "3) Tip eklemeleri yap. "
            "Detayli refactoring icin dosyayi acip duzeltme yapmaliyim."
        )
    except Exception as exc:
        traceback.print_exc()
        return f"Dosya okunamadi: {exc}"


def route_voice_coding_request(user_text: str) -> Optional[str]:
    text = user_text.strip()
    if not text:
        return None

    for action, pattern in _TRIGGERS.items():
        if pattern.search(text):
            handlers = {
                "create": _handle_create,
                "add_function": _handle_add_function,
                "add_import": _handle_add_import,
                "fix": _handle_fix,
                "refactor": _handle_refactor,
            }
            handler = handlers.get(action)
            if handler:
                return handler(text)

    return None
