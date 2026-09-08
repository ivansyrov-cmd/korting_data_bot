# -*- coding: utf-8 -*-
"""Собрать локальный индекс из YML."""
from __future__ import annotations

import json
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.request import Request, urlopen

from .paths import CATALOG_PATH, DATA_DIR, YML_URL

USER_AGENT = "KortingSpecsBot/1.0"


def _writable_dir() -> Path:
    for folder in (DATA_DIR, Path("/tmp/korting"), Path(tempfile.gettempdir()) / "korting"):
        try:
            folder.mkdir(parents=True, exist_ok=True)
            probe = folder / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return folder
        except OSError:
            continue
    return Path(tempfile.gettempdir())


def download_yml(dest: Path, url: str = YML_URL) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=180) as resp:
        dest.write_bytes(resp.read())
    return dest


def _full_category(cats: dict, cid: str) -> str:
    info = cats.get(cid) or {}
    name = info.get("name") or cid
    parent = info.get("parent")
    if parent and cats.get(parent, {}).get("name"):
        return cats[parent]["name"] + " / " + name
    return name


def parse_yml(path: Path) -> dict:
    tree = ET.parse(path)
    shop = tree.getroot().find("shop")
    feed_date = (tree.getroot().get("date") or "").strip()
    cats = {
        c.get("id"): {"name": (c.text or "").strip(), "parent": c.get("parentId") or ""}
        for c in shop.find("categories")
    }
    products = []
    for o in shop.find("offers"):
        cid = (o.findtext("categoryId") or "").strip()
        params = {}
        for p in o.findall("param"):
            n = (p.get("name") or "").strip()
            if not n:
                continue
            params[n] = (p.text or "").strip()
        model = (o.findtext("model") or "").strip()
        products.append({
            "id": o.get("id") or "",
            "model": model,
            "name": (o.findtext("name") or "").strip(),
            "category_id": cid,
            "category": _full_category(cats, cid),
            "url": (o.findtext("url") or "").split("?")[0],
            "params": params,
        })
    return {"source": YML_URL, "feed_date": feed_date, "products": products}


def save_catalog(data: dict, path: Path = CATALOG_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return path


def refresh_from_file(yml_path: Path, catalog_path: Path = CATALOG_PATH) -> dict:
    data = parse_yml(yml_path)
    save_catalog(data, catalog_path)
    return data


def refresh_from_url(catalog_path: Path | None = None, yml_path: Path | None = None) -> dict:
    folder = _writable_dir()
    catalog_path = catalog_path or (folder / "catalog.json")
    yml_path = yml_path or (folder / "feed.yml")
    download_yml(yml_path)
    data = refresh_from_file(yml_path, catalog_path)
    try:
        yml_path.unlink()
    except OSError:
        pass
    return data


def ensure_catalog(path: Path = CATALOG_PATH) -> Path:
    if path.is_file() and path.stat().st_size > 0:
        return path
    dest = path
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        probe = dest.parent / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        dest = _writable_dir() / "catalog.json"
        if dest.is_file() and dest.stat().st_size > 0:
            return dest
    print(f"catalog missing at {path}, downloading YML to {dest}", flush=True)
    refresh_from_url(dest)
    return dest


def load_catalog(path: Path = CATALOG_PATH) -> dict:
    resolved = ensure_catalog(path)
    return json.loads(resolved.read_text(encoding="utf-8"))
