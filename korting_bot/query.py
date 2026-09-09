# -*- coding: utf-8 -*-
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from functools import lru_cache

from .catalog import load_catalog
from .paths import CATALOG_PATH
from .synonyms import Canon, SynonymIndex, alnum, load_synonyms, norm

MSG_NO_PARAM = "такой параметр не представлен в базе данных"
MSG_NO_DATA = "нет данных"
MSG_NO_MODEL = "модель не найдена в базе данных"
MSG_TTX_NEED_MODEL = "Укажите модель: ТТХ OKB 792 CFN"
MSG_LINK_NEED_MODEL = "Укажите модель: ссылка OKB 792 CFN"

TTX_HEAD = re.compile(r"^(?:[/!])?(?:ттх|ttx)[\s:_\-]*", re.IGNORECASE)
LINK_HEAD = re.compile(
    r"^(?:[/!])?(?:ссылка|сайт|линк|link|url|site)[\s:_\-]*",
    re.IGNORECASE,
)
LINK_WORDS = {"ссылка", "сайт", "линк", "link", "url", "site"}
SKIP_TTX_FIELDS = {"видео", "привязка к цветам", "преимущества и особенности"}
MAX_TTX_PRODUCTS = 8

LATIN = "QWERTYUIOPASDFGHJKLZXCVBNM"
CYR_ON_LATIN = "ЙЦУКЕНГШЩЗФЫВАПРОЛДЯЧСМИТЬ"
RU_TO_EN = str.maketrans(CYR_ON_LATIN + CYR_ON_LATIN.lower(), LATIN + LATIN.lower())
EN_TO_RU = str.maketrans(LATIN + LATIN.lower(), CYR_ON_LATIN + CYR_ON_LATIN.lower())

EMPTY_VALUES = {"", "-", "—", "–", "−", "n/a", "na", "нет данных"}


def _is_empty(value: str | None) -> bool:
    v = (value or "").strip()
    return v.lower() in EMPTY_VALUES or v in EMPTY_VALUES


def family_key(model: str) -> str:
    m = re.match(r"^([A-Za-z]{1,6})\s+(\d+)", (model or "").strip())
    if m:
        return alnum(m.group(1) + m.group(2))
    return alnum(model)


@dataclass
class ProductIndex:
    products: list[dict]
    by_full: dict[str, list[dict]] = field(default_factory=dict)
    by_family: dict[str, list[dict]] = field(default_factory=dict)
    by_prefix: dict[str, list[dict]] = field(default_factory=dict)
    full_keys: list[str] = field(default_factory=list)
    prefixes: list[str] = field(default_factory=list)


def _model_prefix(model: str) -> str:
    m = re.match(r"^([A-Za-z]{1,6})\b", (model or "").strip())
    return alnum(m.group(1)) if m else ""


def _layout_variants(text: str) -> list[str]:
    out = []
    for variant in (text, text.translate(RU_TO_EN), text.translate(EN_TO_RU)):
        if variant and variant not in out:
            out.append(variant)
    return out


@lru_cache(maxsize=1)
def load_index() -> ProductIndex:
    data = load_catalog(CATALOG_PATH)
    products = data["products"]
    by_full: dict[str, list[dict]] = {}
    by_family: dict[str, list[dict]] = {}
    by_prefix: dict[str, list[dict]] = {}
    for p in products:
        full = alnum(p.get("model") or "")
        if not full:
            continue
        by_full.setdefault(full, []).append(p)
        fam = family_key(p.get("model") or "")
        if fam:
            by_family.setdefault(fam, []).append(p)
        pref = _model_prefix(p.get("model") or "")
        if pref:
            by_prefix.setdefault(pref, []).append(p)
    keys = sorted(by_full.keys(), key=len, reverse=True)
    prefixes = sorted(by_prefix.keys(), key=len, reverse=True)
    return ProductIndex(
        products=products,
        by_full=by_full,
        by_family=by_family,
        by_prefix=by_prefix,
        full_keys=keys,
        prefixes=prefixes,
    )


def _parse_hwd(value: str, which: str) -> str | None:
    parts = [p for p in re.split(r"[xх×X*\/]", (value or "").replace(" ", "")) if p]
    if len(parts) < 3:
        return None
    idx = {"H": 0, "W": 1, "D": 2}[which]
    return parts[idx] if idx < len(parts) else None


def _format_value(raw: str, unit: str, rule: str, field_name: str) -> str:
    raw = raw.strip()
    if rule == "length_mixed_units":
        try:
            num = float(raw.replace(",", "."))
        except ValueError:
            return raw
        name = (field_name or "").lower()
        if "см" in name and num > 10:
            meters = num / 100
            text = str(int(meters)) if meters == int(meters) else str(round(meters, 2)).rstrip("0").rstrip(".")
            return f"{text} м"
        if unit:
            return f"{raw} {unit}".strip()
        return raw
    if unit and not raw.lower().endswith(unit.lower()):
        return f"{raw} {unit}".strip()
    return raw


def _lookup_on_product(product: dict, canon: Canon) -> str:
    params = product.get("params") or {}
    rule = canon.rule or "value"
    axis = ""
    if rule.startswith("parse_hwd:") or rule.startswith("direct_or_parse:"):
        axis = rule.split(":")[-1]

    if rule == "parse_hwd:" + axis and axis:
        for fname in canon.fields:
            if fname in params and not _is_empty(params[fname]):
                parsed = _parse_hwd(params[fname], axis)
                if parsed:
                    return _format_value(parsed, canon.unit, "value", fname)
        return MSG_NO_PARAM

    found_field = False
    for fname in canon.fields:
        if fname not in params:
            continue
        found_field = True
        val = params[fname]
        if _is_empty(val):
            continue
        if val.strip().lower() == "нет" and canon.unit:
            continue
        return _format_value(val, canon.unit, rule, fname)

    if rule.startswith("direct_or_parse:") and axis:
        for dim_name in (
            "Габариты (ВхШхГ) (мм)",
            "Габариты (ВxШхГ) (мм)",
            "Габариты (ВxШxГ) (мм)",
        ):
            if dim_name in params and not _is_empty(params[dim_name]):
                parsed = _parse_hwd(params[dim_name], axis)
                if parsed:
                    return _format_value(parsed, canon.unit or "мм", "value", dim_name)
        return MSG_NO_PARAM if not found_field else MSG_NO_DATA

    if not found_field:
        return MSG_NO_PARAM
    return MSG_NO_DATA


def _find_canon(text: str, syn: SynonymIndex) -> Canon | None:
    blob = norm(text)
    if not blob:
        return None
    keys = sorted(syn.synonym_to_canon.keys(), key=len, reverse=True)
    for key in keys:
        if len(key) <= 2:
            if re.search(rf"(^|\s){re.escape(key)}(\s|$)", blob):
                return syn.synonym_to_canon[key]
        elif key in blob:
            return syn.synonym_to_canon[key]
    return None


def _strip_model_from_query(query: str, model_alnum: str) -> str:
    compact = alnum(query)
    idx = compact.find(model_alnum)
    # Reconstruct leftover by removing matched alnum span from original letters/digits only.
    leftover_chars = []
    q_alnum_idx = 0
    skip_until = idx + len(model_alnum) if idx >= 0 else -1
    for ch in query:
        is_al = ch.isalnum()
        if is_al:
            if idx >= 0 and q_alnum_idx >= idx and q_alnum_idx < skip_until:
                q_alnum_idx += 1
                continue
            leftover_chars.append(ch)
            q_alnum_idx += 1
        else:
            leftover_chars.append(ch)
    return norm("".join(leftover_chars))


def _find_category_family(query: str, syn: SynonymIndex, index: ProductIndex) -> tuple[list[dict], str]:
    blob = norm(query)
    nums = re.findall(r"\d{3,6}", query)
    if not nums:
        return [], ""
    cats = sorted(syn.category_by_syn.keys(), key=len, reverse=True)
    hit = None
    for key in cats:
        if len(key) < 2:
            continue
        if key in blob:
            hit = syn.category_by_syn[key]
            break
    if not hit or not hit.prefixes:
        return [], ""
    number = nums[0]
    found: list[dict] = []
    seen = set()
    for pref in hit.prefixes:
        fam = pref + number
        for p in index.by_family.get(fam, []):
            mid = p.get("id")
            if mid in seen:
                continue
            seen.add(mid)
            found.append(p)
    return found, (hit.prefixes[0] + number if found else "")


def _find_prefix(query: str, index: ProductIndex) -> tuple[list[dict], str]:
    tokens = re.findall(r"[A-Za-zА-Яа-я]{2,6}", query)
    for raw in tokens:
        for variant in _layout_variants(raw):
            pref = alnum(variant)
            if pref in index.by_prefix:
                return index.by_prefix[pref], pref
    compact_variants = [alnum(v) for v in _layout_variants(query)]
    for pref in index.prefixes:
        if len(pref) < 2:
            continue
        for compact in compact_variants:
            if compact == pref or compact.endswith(pref):
                return index.by_prefix[pref], pref
    return [], ""


def _model_fragments(query: str) -> list[str]:
    frags: list[str] = []
    for variant in _layout_variants(query):
        for m in re.finditer(
            r"[A-Za-zА-Яа-я]{2,8}(?:[\s\-]?\d+[A-Za-zА-Яа-я0-9]*)?",
            variant,
        ):
            frag = alnum(m.group(0))
            if 2 <= len(frag) <= 24 and frag not in frags:
                frags.append(frag)
    return frags


def _suggest_from_index(query: str, index: ProductIndex, limit: int = 50) -> tuple[list[dict], str]:
    for frag in sorted(_model_fragments(query), key=len, reverse=True):
        hits: list[dict] = []
        seen: set[str] = set()
        for p in index.products:
            full = alnum(p.get("model") or "")
            if not full.startswith(frag):
                continue
            pid = str(p.get("id") or full)
            if pid in seen:
                continue
            seen.add(pid)
            hits.append(p)
        if hits:
            hits.sort(key=lambda p: p.get("model") or "")
            if limit:
                hits = hits[:limit]
            return hits, frag
    return [], ""


def suggest_models(query: str, limit: int = 50) -> list[dict]:
    hits, _frag = _suggest_from_index(query, load_index(), limit=limit)
    return hits


def suggest_prefixes(limit: int = 50) -> list[tuple[str, int]]:
    index = load_index()
    rows = [(pref, len(index.by_prefix.get(pref) or [])) for pref in index.prefixes]
    rows.sort(key=lambda x: (-x[1], x[0]))
    return rows[:limit]


def find_products(query: str, index: ProductIndex, syn: SynonymIndex) -> tuple[list[dict], str]:
    for variant in _layout_variants(query):
        compact = alnum(variant)
        for key in index.full_keys:
            if key and key in compact:
                return index.by_full[key], key
        fam_keys = sorted(index.by_family.keys(), key=len, reverse=True)
        for key in fam_keys:
            if len(key) >= 5 and key in compact:
                return index.by_family[key], key
        found, key = _find_category_family(variant, syn, index)
        if found:
            return found, key
    found, key = _find_prefix(query, index)
    if found:
        if re.search(r"\d", query):
            partial, pkey = _suggest_from_index(query, index, limit=0)
            if partial and pkey and len(pkey) > len(key):
                return partial, pkey
        return found, key
    return _suggest_from_index(query, index, limit=0)


def _list_models(products: list[dict], hint: str = "") -> str:
    names = sorted({p.get("model") or "" for p in products if p.get("model")})
    head = hint or "Уточните модель:"
    shown = names[:40]
    extra = f"\n… ещё {len(names) - 40}" if len(names) > 40 else ""
    return head + "\n" + "\n".join(shown) + extra


def _product_type_text(product: dict) -> str:
    return norm(f"{product.get('name') or ''} {product.get('category') or ''}")


def _parse_ttx(query: str) -> str | None:
    m = TTX_HEAD.match(query or "")
    if not m:
        return None
    return (query or "")[m.end() :].strip()


def _parse_link(query: str) -> str | None:
    m = LINK_HEAD.match(query or "")
    if not m:
        return None
    return (query or "")[m.end() :].strip()


def _is_link_leftover(leftover: str) -> bool:
    words = leftover.split()
    return bool(words) and all(w in LINK_WORDS for w in words)


def _resolve_products(q: str) -> tuple[list[dict], str]:
    syn = load_synonyms()
    index = load_index()
    products, matched_key = find_products(q, index, syn)
    leftover = _strip_model_from_query(q, matched_key) if matched_key else norm(q)
    for w in syn.stop_words:
        leftover = re.sub(rf"(^|\s){re.escape(w)}(\s|$)", " ", leftover)
    leftover = norm(leftover)
    products, leftover = _filter_type_words(products, leftover)
    return products, leftover


def _ttx_label(name: str) -> tuple[str, str]:
    raw = (name or "").strip()
    m = re.search(r"[\(（]([^\)）]+)[\)）]\s*$", raw)
    unit = (m.group(1).strip() if m else "")
    label = re.sub(r"\s*[\(（][^\)）]{0,40}[\)）]\s*$", "", raw).strip(" ,")
    return label or raw, unit


def _skip_ttx_field(name: str) -> bool:
    n = norm(name)
    if not n or n in SKIP_TTX_FIELDS:
        return True
    if n.startswith("им |") or n.startswith("им|"):
        return True
    if "преимущества" in n:
        return True
    return False


def _ttx_value(raw: str, unit: str) -> str:
    val = (raw or "").strip()
    if not unit:
        return val
    if val.lower() in {"нет", "да"}:
        return val
    if val.lower().endswith(unit.lower()):
        return val
    return f"{val} {unit}".strip()


def _dump_product(product: dict) -> str:
    model = (product.get("model") or "").strip()
    name = (product.get("name") or "").strip()
    lines = [model] if model else []
    if name and name != model:
        lines.append(name)
    params = product.get("params") or {}
    for fname, raw in params.items():
        if _skip_ttx_field(fname) or _is_empty(raw):
            continue
        label, unit = _ttx_label(fname)
        safe_label = html.escape(label, quote=False)
        safe_value = html.escape(_ttx_value(raw, unit), quote=False)
        lines.append(f"<b>{safe_label}</b>: {safe_value}")
    return "\n".join(lines)


def _answer_ttx(model_query: str) -> str:
    q = (model_query or "").strip()
    if not q:
        return MSG_TTX_NEED_MODEL
    products, _leftover = _resolve_products(q)
    if not products:
        return MSG_NO_MODEL
    if len(products) > MAX_TTX_PRODUCTS:
        return _list_models(products, "Уточните модель:")
    blocks = [_dump_product(p) for p in sorted(products, key=lambda x: x.get("model") or "")]
    return "\n\n".join(blocks)


def _link_line(product: dict) -> str:
    model = (product.get("model") or "").strip() or "модель"
    url = (product.get("url") or "").strip()
    if not url:
        return f"{model} — {MSG_NO_DATA}"
    return f"{model} — {url}"


def _format_links(products: list[dict]) -> str:
    lines = [_link_line(p) for p in sorted(products, key=lambda x: x.get("model") or "")]
    if len(lines) == 1:
        return lines[0]
    if len(lines) > 40:
        return "\n".join(lines[:40]) + f"\n… ещё {len(lines) - 40}, уточните номер модели"
    return "\n".join(lines)


def _answer_link(model_query: str) -> str:
    q = (model_query or "").strip()
    if not q:
        return MSG_LINK_NEED_MODEL
    products, _leftover = _resolve_products(q)
    if not products:
        return MSG_NO_MODEL
    return _format_links(products)


def _filter_type_words(products: list[dict], leftover: str) -> tuple[list[dict], str]:
    """Keep SKUs whose name/category contains leftover type words (камера, холодильник)."""
    if not products or not leftover:
        return products, leftover
    kept: list[str] = []
    current = products
    for tok in leftover.split():
        if len(tok) < 4:
            kept.append(tok)
            continue
        subset = [
            p
            for p in current
            if re.search(rf"(^|\s){re.escape(tok)}(\s|$)", f" {_product_type_text(p)} ")
        ]
        if subset:
            current = subset
            continue
        kept.append(tok)
    return current, norm(" ".join(kept))


def needs_property(query: str) -> bool:
    """True if the text names a small set of SKUs and no spec/command."""
    q = (query or "").strip()
    if not q or _parse_ttx(q) is not None or _parse_link(q) is not None:
        return False
    products, leftover = _resolve_products(q)
    if leftover or not products:
        return False
    return 1 <= len(products) <= MAX_TTX_PRODUCTS


def answer_query(query: str) -> str:
    q = (query or "").strip()
    if not q:
        return MSG_NO_MODEL
    ttx_model = _parse_ttx(q)
    if ttx_model is not None:
        return _answer_ttx(ttx_model)
    link_model = _parse_link(q)
    if link_model is not None:
        return _answer_link(link_model)
    syn = load_synonyms()
    index = load_index()
    products, matched_key = find_products(q, index, syn)
    leftover = _strip_model_from_query(q, matched_key) if matched_key else norm(q)
    for w in syn.stop_words:
        leftover = re.sub(rf"(^|\s){re.escape(w)}(\s|$)", " ", leftover)
    leftover = norm(leftover)
    products, leftover = _filter_type_words(products, leftover)
    if not products:
        return MSG_NO_MODEL
    if _is_link_leftover(leftover):
        return _format_links(products)
    canon = _find_canon(leftover, syn)
    if not canon and leftover:
        canon = _find_canon(q, syn)
    if not canon:
        return _list_models(products, "Уточните модель и характеристику:")

    lines = []
    for p in sorted(products, key=lambda x: x.get("model") or ""):
        val = _lookup_on_product(p, canon)
        lines.append(f"{p['model']} — {val}")
    if len(lines) == 1:
        return lines[0]
    if len(lines) > 40:
        return "\n".join(lines[:40]) + f"\n… ещё {len(lines) - 40}, уточните номер модели"
    return "\n".join(lines)
