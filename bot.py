# -*- coding: utf-8 -*-
"""Справка по характеристикам: фраза → ответ из локального catalog.json."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from korting_bot.query import answer_query


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if args:
        print(answer_query(" ".join(args)))
        return 0
    print("Введите запрос (пустая строка — выход).")
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            return 0
        print(answer_query(line))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
