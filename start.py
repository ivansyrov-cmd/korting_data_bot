# -*- coding: utf-8 -*-
"""Install deps if needed, then start the Telegram bot."""
from __future__ import annotations

from install_deps import ensure_deps

if __name__ == "__main__":
    ensure_deps()
    from bot import main

    raise SystemExit(main())
