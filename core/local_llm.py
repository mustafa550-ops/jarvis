"""
Local LLM Motoru — Ollama yönetimi, model indirme, switch.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

import urllib.request

import traceback

__all__ = ["LocalLLM", "create_local_llm"]

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_model_config() -> dict[str, Any]:
    """Load model config from YAML with defaults."""
    defaults: dict[str, Any] = {
        "llm": {
            "ollama": {
                "endpoint": "http://localhost:11434",
                "default_model": "qwen2.5:1.5b",
                "fallback_model": "qwen2.5:7b",
                "embedding_model": "nomic-embed-text",
                "parameters": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "max_tokens": 2048,
                },
            }
        }
    }
    try:
        import yaml
        config_path = BASE_DIR / "config" / "models.yaml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    llm_config = loaded.get("llm", {})
                    if llm_config:
                        defaults["llm"].update(llm_config)
    except ImportError:
        print("[LocalLLM] YAML destegi yok (pip install pyyaml), varsayilan config")
    except Exception:
        traceback.print_exc()
    return defaults


class LocalLLM:
    """
    Yerel LLM motoru.

    Ollama üzerinden model yönetimi:
    - Model listeleme/indirme/silme
    - Embedding alma
    - Model switch
    - Sağlık kontrolü
    """

    def __init__(self):
        self.config = _load_model_config()
        ollama_cfg = self.config.get("llm", {}).get("ollama", {})
        self.endpoint = ollama_cfg.get("endpoint", "http://localhost:11434")
        self._model = ollama_cfg.get("default_model", "qwen2.5:1.5b")
        self._fallback = ollama_cfg.get("fallback_model", "qwen2.5:7b")
        self._embedding_model = ollama_cfg.get("embedding_model", "nomic-embed-text")
        self._parameters: dict[str, Any] = ollama_cfg.get("parameters", {})

    # ── Health ────────────────────────────────────────────────────────────────

    def is_ollama_running(self) -> bool:
        """Check if Ollama server is reachable."""
        try:
            req = urllib.request.Request(f"{self.endpoint}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def wait_for_ollama(self, timeout: float = 30.0) -> bool:
        """Wait until Ollama becomes available."""
        start = time.time()
        while time.time() - start < timeout:
            if self.is_ollama_running():
                return True
            time.sleep(1.0)
        return False

    # ── Model management ──────────────────────────────────────────────────────

    def list_models(self) -> list[dict[str, Any]]:
        """List available models from Ollama."""
        try:
            req = urllib.request.Request(f"{self.endpoint}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("models", [])
        except Exception:
            traceback.print_exc()
            return []

    def pull_model(self, model_name: str) -> bool:
        """Download a model from Ollama library."""
        try:
            print(f"[LocalLLM] Model indiriliyor: {model_name}")
            payload = json.dumps({"name": model_name}).encode("utf-8")
            req = urllib.request.Request(
                f"{self.endpoint}/api/pull",
                data=payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=600) as resp:
                # Stream response
                for line in resp:
                    try:
                        data = json.loads(line.decode("utf-8").strip())
                        status = data.get("status", "")
                        if status:
                            print(f"  {status}")
                    except json.JSONDecodeError:
                        pass
            print(f"[LocalLLM] Model indirildi: {model_name}")
            return True
        except Exception as exc:
            print(f"[LocalLLM] Model indirme hatasi: {exc}")
            traceback.print_exc()
            return False

    def delete_model(self, model_name: str) -> bool:
        """Delete a model from Ollama."""
        try:
            payload = json.dumps({"name": model_name}).encode("utf-8")
            req = urllib.request.Request(
                f"{self.endpoint}/api/delete",
                data=payload,
                method="DELETE",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status == 200
        except Exception:
            traceback.print_exc()
            return False

    # ── Model selection ──────────────────────────────────────────────────────

    def switch_model(self, model_name: str) -> bool:
        """Switch active model."""
        available = {m.get("name", "") for m in self.list_models()}
        if model_name in available:
            self._model = model_name
            print(f"[LocalLLM] Model degistirildi: {model_name}")
            return True
        print(f"[LocalLLM] Model bulunamadi: {model_name}")
        return False

    @property
    def current_model(self) -> str:
        return self._model

    @current_model.setter
    def current_model(self, name: str):
        self._model = name

    # ── Embedding ────────────────────────────────────────────────────────────

    def get_embedding(self, text: str) -> Optional[list[float]]:
        """Get embedding vector for text."""
        try:
            payload = json.dumps({
                "model": self._embedding_model,
                "prompt": text,
            }).encode("utf-8")
            req = urllib.request.Request(
                f"{self.endpoint}/api/embeddings",
                data=payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("embedding")
        except Exception:
            traceback.print_exc()
            return None

    # ── Parameters ──────────────────────────────────────────────────────────

    def get_parameters(self) -> dict[str, Any]:
        """Get current LLM parameters."""
        return dict(self._parameters)

    def set_parameter(self, key: str, value: Any):
        self._parameters[key] = value

    # ── Info ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        return {
            "ollama_running": self.is_ollama_running(),
            "current_model": self._model,
            "fallback_model": self._fallback,
            "embedding_model": self._embedding_model,
            "endpoint": self.endpoint,
            "parameters": self._parameters,
        }


# ── Factory ──────────────────────────────────────────────────────────────────


def create_local_llm() -> LocalLLM:
    """Create a LocalLLM with sensible defaults."""
    return LocalLLM()
