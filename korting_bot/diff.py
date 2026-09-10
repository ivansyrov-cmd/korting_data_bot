# -*- coding: utf-8 -*-
"""Сверка двух выгрузок каталога: было → стало."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

from .catalog import SKIP_PARAM_NAMES, SKIP_PARAM_PREFIXES
from .paths import BUNDLED_CHANGELOG, CHANGELOG_JSON, CHANGELOG_TXT, CHANGELOG_XLSX, DATA_DIR
from .synonyms import alnum, norm

MSG_NO_CHANGELOG = (
    "сверки изменений пока нет. Она появится после обновления таблицы на Диске."
)
MSG_MODEL_UNCHANGED = "в последней сверке у этой модели характеристики не менялись"
# Классификаторы у TYPE_DEVICE и служебные поля — не ТТХ.
SKIP_CHANGELOG_FIELDS = {
    "наименование",
    "категория",
    "тип",
    "тип продукта",
    "тип прибора",
    "тип панели",
    "тип вытяжки",
    "дополнительный цвет",
    "основные характеристики",
    "дополнительные характеристики",
}


@dataclass
class FieldChange:
    name: str
    old: str
    new: str


@dataclass
class ModelChange:
    model: str
    name: str = ""
    category: str = ""
    url: str = ""
    fields: list[FieldChange] = field(default_factory=list)


@dataclass
class Changelog:
    old_date: str = ""
    new_date: str = ""
    generated: str = ""
    added: list[ModelChange] = field(default_factory=list)
    removed: list[ModelChange] = field(default_factory=list)
    changed: list[ModelChange] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.changed)

    def counts(self) -> tuple[int, int, int]:
        return len(self.changed), len(self.added), len(self.removed)


def _index(products: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in products or []:
        model = (p.get("model") or "").strip()
        if not model:
            continue
        out[model] = p
    return out


def _is_changelog_field(name: str) -> bool:
    from .query import _skip_ttx_field

    if _skip_ttx_field(name):
        return False
    n = norm(name)
    if n in SKIP_CHANGELOG_FIELDS or n in SKIP_PARAM_NAMES:
        return False
    return not any(n.startswith(p) for p in SKIP_PARAM_PREFIXES)


def _params(product: dict) -> dict[str, str]:
    from .query import _is_empty

    clean = {}
    for key, val in dict(product.get("params") or {}).items():
        if not _is_changelog_field(key):
            continue
        text = (val or "").strip()
        if _is_empty(text):
            continue
        clean[key] = text
    return clean


def _label(name: str) -> str:
    from .query import _ttx_label

    label, _unit = _ttx_label(name)
    return label or name


def _canon_val(text: str) -> str:
    t = norm(text)
    t = t.replace("×", "x").replace("х", "x")
    t = re.sub(r"\s*x\s*", "x", t)
    t = re.sub(r"\s+", " ", t)
    return t


def _same(a: str, b: str) -> bool:
    if _canon_val(a) == _canon_val(b):
        return True
    left = {p.strip() for p in _canon_val(a).split("|") if p.strip()}
    right = {p.strip() for p in _canon_val(b).split("|") if p.strip()}
    return bool(left) and left == right


def diff_catalogs(old: dict | None, new: dict | None) -> Changelog:
    old = old or {}
    new = new or {}
    report = Changelog(
        old_date=str(old.get("feed_date") or ""),
        new_date=str(new.get("feed_date") or ""),
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    old_map = _index(old.get("products") or [])
    new_map = _index(new.get("products") or [])
    for model in sorted(set(new_map) - set(old_map)):
        p = new_map[model]
        report.added.append(
            ModelChange(
                model=model,
                name=p.get("name") or "",
                category=p.get("category") or "",
                url=p.get("url") or "",
            )
        )
    for model in sorted(set(old_map) - set(new_map)):
        p = old_map[model]
        report.removed.append(
            ModelChange(
                model=model,
                name=p.get("name") or "",
                category=p.get("category") or "",
                url=p.get("url") or "",
            )
        )
    for model in sorted(set(old_map) & set(new_map)):
        before = _params(old_map[model])
        after = _params(new_map[model])
        fields: list[FieldChange] = []
        for key in sorted(set(before) | set(after), key=lambda x: x.lower()):
            ov = before.get(key, "")
            nv = after.get(key, "")
            if _same(ov, nv):
                continue
            fields.append(FieldChange(name=key, old=ov, new=nv))
        if fields:
            p = new_map[model]
            report.changed.append(
                ModelChange(
                    model=model,
                    name=p.get("name") or "",
                    category=p.get("category") or "",
                    url=p.get("url") or old_map[model].get("url") or "",
                    fields=fields,
                )
            )
    return report


def _field_line(item: FieldChange) -> str:
    label = _label(item.name)
    if item.old and item.new:
        return f"{label}: было {item.old}, стало {item.new}"
    if item.new and not item.old:
        return f"{label}: появилось {item.new}"
    return f"{label}: было {item.old}, сейчас нет данных"


def format_changelog(report: Changelog, model_query: str = "") -> str:
    if not report.has_changes and not model_query:
        return "в последней сверке характеристики не менялись"
    needle = alnum(model_query)
    changed = report.changed
    added = report.added
    removed = report.removed
    if needle:
        changed = [m for m in changed if needle in alnum(m.model)]
        added = [m for m in added if needle in alnum(m.model)]
        removed = [m for m in removed if needle in alnum(m.model)]
        if not changed and not added and not removed:
            return MSG_MODEL_UNCHANGED
    ch, ad, rm = len(changed), len(added), len(removed)
    lines = ["Изменения ТТХ"]
    if report.old_date or report.new_date:
        lines.append(f"Было: {report.old_date or '—'} → стало: {report.new_date or '—'}")
    if not needle:
        lines.append(
            f"Моделей с изменёнными ТТХ: {ch}, новых: {ad}, нет в выгрузке: {rm}"
        )
    lines.append("")
    for m in changed:
        lines.append(m.model)
        if m.url:
            lines.append(m.url)
        for item in m.fields:
            lines.append("• " + _field_line(item))
        lines.append("")
    if added:
        lines.append("Новые модели в выгрузке:")
        for m in added:
            extra = f" — {m.category}" if m.category else ""
            lines.append(f"• {m.model}{extra}")
        lines.append("")
    if removed:
        lines.append("Больше нет в выгрузке:")
        for m in removed:
            lines.append(f"• {m.model}")
    return "\n".join(lines).strip()


def _to_json(report: Changelog) -> dict:
    def pack_model(m: ModelChange) -> dict:
        return {
            "model": m.model,
            "name": m.name,
            "category": m.category,
            "url": m.url,
            "fields": [{"name": f.name, "old": f.old, "new": f.new} for f in m.fields],
        }

    return {
        "old_date": report.old_date,
        "new_date": report.new_date,
        "generated": report.generated,
        "changed": [pack_model(m) for m in report.changed],
        "added": [pack_model(m) for m in report.added],
        "removed": [pack_model(m) for m in report.removed],
    }


def _from_json(data: dict) -> Changelog:
    def unpack(rows: list, with_fields: bool = True) -> list[ModelChange]:
        out = []
        for row in rows or []:
            fields = []
            if with_fields:
                for f in row.get("fields") or []:
                    fields.append(
                        FieldChange(name=f.get("name") or "", old=f.get("old") or "", new=f.get("new") or "")
                    )
            out.append(
                ModelChange(
                    model=row.get("model") or "",
                    name=row.get("name") or "",
                    category=row.get("category") or "",
                    url=row.get("url") or "",
                    fields=fields,
                )
            )
        return out

    return Changelog(
        old_date=str(data.get("old_date") or ""),
        new_date=str(data.get("new_date") or ""),
        generated=str(data.get("generated") or ""),
        added=unpack(data.get("added") or [], with_fields=False),
        removed=unpack(data.get("removed") or [], with_fields=False),
        changed=unpack(data.get("changed") or []),
    )


def save_xlsx(report: Changelog, path: Path = CHANGELOG_XLSX) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Изменения"
    ws.append(["Модель", "Ссылка", "Категория", "Тип", "Параметр", "Было", "Стало"])
    for m in report.changed:
        for item in m.fields:
            kind = "изменено"
            if item.old and not item.new:
                kind = "параметр удалён"
            elif item.new and not item.old:
                kind = "появился параметр"
            ws.append([m.model, m.url, m.category, kind, _label(item.name), item.old, item.new])
    for m in report.added:
        ws.append([m.model, m.url, m.category, "новая модель", "", "", ""])
    for m in report.removed:
        ws.append([m.model, m.url, m.category, "нет в выгрузке", "", "", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def save_changelog(report: Changelog) -> dict[str, Path]:
    from .changelog_page import render_changelog_page

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(_to_json(report), ensure_ascii=False, indent=2)
    CHANGELOG_JSON.write_text(payload, encoding="utf-8")
    CHANGELOG_TXT.write_text(format_changelog(report), encoding="utf-8")
    try:
        BUNDLED_CHANGELOG.write_text(payload, encoding="utf-8")
    except OSError as exc:
        print(f"bundled changelog skip: {exc}", flush=True)
    xlsx = ensure_changelog_xlsx(report)
    page = render_changelog_page(_to_json(report))
    return {"json": CHANGELOG_JSON, "txt": CHANGELOG_TXT, "xlsx": xlsx, "page": page, "bundled": BUNDLED_CHANGELOG}


def _changelog_paths(explicit: Path | None = None) -> list[Path]:
    from .catalog import _writable_dir

    paths = []
    for p in (
        explicit,
        CHANGELOG_JSON,
        BUNDLED_CHANGELOG,
        Path("/tmp/korting") / "changelog.json",
        _writable_dir() / "changelog.json",
    ):
        if p is not None and p not in paths:
            paths.append(p)
    return paths


def load_changelog(path: Path | None = None) -> Changelog | None:
    for candidate in _changelog_paths(path):
        if not candidate.is_file() or candidate.stat().st_size == 0:
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        report = _from_json(data)
        print(
            f"changelog loaded {candidate} changed={len(report.changed)} "
            f"added={len(report.added)} removed={len(report.removed)}",
            flush=True,
        )
        return report
    print("changelog not found", flush=True)
    return None


def ensure_changelog_xlsx(report: Changelog | None = None) -> Path | None:
    from .catalog import _writable_dir

    report = report or load_changelog()
    if report is None:
        return None
    for dest in (CHANGELOG_XLSX, _writable_dir() / "changelog.xlsx"):
        try:
            return save_xlsx(report, dest)
        except OSError:
            continue
    return None


def answer_changes(query: str = "") -> str:
    report = load_changelog()
    if report is None:
        return MSG_NO_CHANGELOG
    return format_changelog(report, model_query=query)
