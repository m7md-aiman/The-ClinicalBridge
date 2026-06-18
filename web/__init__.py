"""ClinicalBridge web package. Ensures the src/ layout is importable when running uvicorn."""

import sys
from pathlib import Path

_src = Path(__file__).resolve().parent.parent / "src"
if _src.is_dir() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))
