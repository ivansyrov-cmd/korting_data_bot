# -*- coding: utf-8 -*-
"""Обновить catalog.json из YML. Для запросов не используется."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from korting_bot.catalog import refresh_from_file, refresh_from_url
from korting_bot.paths import CATALOG_PATH, DATA_DIR


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-file", type=Path, help="готовый YML, без скачивания")
    args = parser.parse_args()
    if args.from_file:
        data = refresh_from_file(args.from_file)
    else:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        data = refresh_from_url()
    print(f"моделей: {len(data['products'])}")
    print(f"выгрузка: {data.get('feed_date')}")
    print(f"файл: {CATALOG_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
