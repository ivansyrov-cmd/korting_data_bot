# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CATALOG_PATH = DATA_DIR / "catalog.json"
SYNONYMS_PATH = ROOT / "Синонимы_YML.xlsx"
FEED_URL = "https://disk.yandex.ru/d/FBceQbtZGwLxTg"
SITE_BASE = "https://korting.ru"
YML_ENRICH_URL = "https://korting.ru/tools/ymarket/showFullRetail.php?ym_show=1&start=1&REGION_ID=1781"
YML_URL = FEED_URL
