# -*- coding: utf-8 -*-
from __future__ import annotations

from install_deps import ensure_deps

ensure_deps()

from bot import main

if __name__ == "__main__":
    raise SystemExit(main())
