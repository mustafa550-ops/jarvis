# JARVIS Windows — UI Package
# Re-exports everything from the legacy ui.py module and the new submodules.

import importlib.util
import sys
from pathlib import Path

# Load the legacy ui.py as a separate module to avoid namespace collision
_ui_path = Path(__file__).resolve().parent.parent / "ui.py"
_spec = importlib.util.spec_from_file_location("ui_legacy", _ui_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["ui_legacy"] = _mod
_spec.loader.exec_module(_mod)

# Re-export all names from the legacy module
_vars = {k: v for k, v in vars(_mod).items() if not k.startswith("__")}
globals().update(_vars)

from .sound_manager import SoundManager, IS_WINDOWS
