# -*- coding: utf-8 -*-
"""Обновить catalog.json из выгрузки на Яндекс.Диске."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from korting_bot.catalog import refresh_from_file, refresh_from_url
from korting_bot.diff import diff_catalogs, save_changelog
from korting_bot.paths import CATALOG_PATH, DATA_DIR


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-file", type=Path, help="готовая выгрузка, без скачивания")
    args = parser.parse_args()
    old = None
    if CATALOG_PATH.is_file() and CATALOG_PATH.stat().st_size > 0:
        old = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if args.from_file:
        data = refresh_from_file(args.from_file)
    else:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        data = refresh_from_url()
    print(f"моделей: {len(data['products'])}")
    print(f"выгрузка: {data.get('feed_date')}")
    print(f"файл: {CATALOG_PATH}")
    if old:
        report = diff_catalogs(old, data)
        ch, ad, rm = report.counts()
        print(f"сверка ТТХ: изменено {ch}, новых {ad}, нет в выгрузке {rm}")
        if report.has_changes:
            paths = save_changelog(report)
            print(f"выгрузка сверки: {paths['xlsx']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
