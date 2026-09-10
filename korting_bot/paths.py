# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
CATALOG_PATH = DATA_DIR / "catalog.json"
CHANGELOG_JSON = DATA_DIR / "changelog.json"
CHANGELOG_TXT = DATA_DIR / "changelog.txt"
CHANGELOG_XLSX = DATA_DIR / "changelog.xlsx"
BUNDLED_CHANGELOG = PACKAGE_DIR / "changelog.json"
CHANGELOG_PAGE = ROOT / "docs" / "KORTING_DATA_CHANGES" / "index.html"
CHANGELOG_PAGE_XLSX = CHANGELOG_PAGE.parent / "izmeneniya_ttx.xlsx"
SYNONYMS_PATH = ROOT / "Синонимы_YML.xlsx"
FEED_URL = "https://disk.yandex.ru/d/FBceQbtZGwLxTg"
SITE_BASE = "https://korting.ru"
YML_ENRICH_URL = "https://korting.ru/tools/ymarket/showFullRetail.php?ym_show=1&start=1&REGION_ID=1781"
YML_URL = FEED_URL
