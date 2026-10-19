# -*- coding: utf-8 -*-
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def ensure_deps() -> None:
    try:
        import openpyxl  # noqa: F401
        import telegram  # noqa: F401
        return
    except ImportError:
        pass
    req = Path(__file__).resolve().parent / "requirements.txt"
    print("installing python deps", flush=True)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req)])


ensure_deps()

from bot import main

if __name__ == "__main__":
    raise SystemExit(main())
