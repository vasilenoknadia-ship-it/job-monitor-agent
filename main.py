"""Корневая точка входа. Используется и локально (`python main.py`), и в
GitHub Actions (см. .github/workflows/daily_run.yml)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from pipeline import run  # noqa: E402

if __name__ == "__main__":
    run()
