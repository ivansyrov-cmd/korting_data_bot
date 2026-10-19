# -*- coding: utf-8 -*-
"""Install deps if needed, then start the Telegram bot."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def ensure_deps() -> None:
    req = ROOT / "requirements.txt"
    if not req.is_file():
        return
    cmd = [sys.executable, "-m", "pip", "install", "-r", str(req)]
    print("installing python deps", flush=True)
    try:
        subprocess.check_call(cmd)
    except Exception as exc:
        print(f"pip install failed: {exc}", flush=True)


if __name__ == "__main__":
    ensure_deps()
    from bot import main

    raise SystemExit(main())
