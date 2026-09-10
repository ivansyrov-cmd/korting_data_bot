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
MSG_UNKNOWN_PARAM = (
    "я не понял какой параметр вы хотите узнать, попробуйте написать его название иначе"
)
MSG_REVERSE_NONE = "таких моделей не найдено"

REVERSE_HINT = re.compile(
    r"(в каких|у каких|какие модели|каких моделях|какие из|"
    r"перечислите модели|перечисли модели|модели с\b|в каких моделях)",
    re.IGNORECASE,
)
REVERSE_STOP = {
    "в", "каких", "каком", "какие", "какая", "какой", "какую", "каким",
    "моделях", "модели", "модель", "моделей",
    "есть", "ли", "где", "из", "у", "с", "со", "для",
    "серии", "линейке", "присутствует", "имеется", "имеют", "наличие",
}
INVERTER_ALIAS = {
    "мотор", "мотора", "мотором", "моторы", "моторов",
    "компрессор", "компрессора", "компрессором", "компрессоры",
    "двигатель", "двигателя", "двигателем",
}
FEATURE_NOISE = {
    "технология", "технологией", "технологии", "технологию", "технологий", "технологи",
    "функция", "функцией", "функции", "функцию",
    "опция", "опцией", "система", "системой",
}
WEAK_STEMS = ("подсвет", "освещ", "свет", "ламп", "технолог", "функц")
FEATURE_ALIASES = (
    ("ambilight", "ambiance", "ambience"),
    (
        "heatpump",
        "тепловойнасос",
        "тепловогонасоса",
        "тепловымнасосом",
        "тепловомунасосу",
        "тепловыенасосы",
        "тепловыхнасосов",
    ),
)
MSG_LINK_NEED_MODEL = "Укажите модель: ссылка OKB 792 CFN"

TTX_HEAD = re.compile(r"^(?:[/!])?(?:ттх|ttx)[\s:_\-]*", re.IGNORECASE)
LINK_HEAD = re.compile(
    r"^(?:[/!])?(?:ссылка|сайт|линк|link|url|site)[\s:_\-]*",
    re.IGNORECASE,
)
LINK_WORDS = {"ссылка", "сайт", "линк", "link", "url", "site"}
SKIP_TTX_FIELDS = {
    "видео",
    "привязка к цветам",
    "преимущества и особенности",
    "наличие",
    "цена для фильтра",
    "новинка",
    "популярный",
    "спецпредложение",
}
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
        if re.search(rf"(^|\s){re.escape(key)}(\s|$)", blob):
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


def _find_category(query: str, syn: SynonymIndex):
    blob = norm(query)
    for key in sorted(syn.category_by_syn.keys(), key=len, reverse=True):
        if len(key) < 4:
            continue
        if key in blob:
            return syn.category_by_syn[key]
        stem = key.rstrip("аяьыие")
        if len(stem) >= 6 and stem in blob:
            return syn.category_by_syn[key]
    return None


def _category_products(index: ProductIndex, cat) -> list[dict]:
    title = norm(cat.title)
    found: list[dict] = []
    seen: set[str] = set()

    def _add(p: dict) -> None:
        pid = str(p.get("id") or p.get("model") or "")
        if not pid or pid in seen:
            return
        seen.add(pid)
        found.append(p)

    if title:
        for p in index.products:
            if title in norm(p.get("category") or ""):
                _add(p)
        if found:
            return found
    words = [w for w in title.split() if len(w) >= 4]
    generic = {"машины", "печи", "шкафы", "камеры", "поверхности", "техника"}
    stems: list[str] = []
    for w in words:
        if w in generic:
            continue
        stems.append(w)
        st = w.rstrip("аяьыие")
        if len(st) >= 5 and st not in stems:
            stems.append(st)
    if not stems:
        stems = words[:1]
    for p in index.products:
        blob = _product_type_text(p)
        if stems and not any(s in blob for s in stems):
            continue
        _add(p)
    if found:
        return found
    prefixes = set(cat.prefixes or [])
    if not prefixes:
        return []
    for p in index.products:
        pref = _model_prefix(p.get("model") or "")
        if pref not in prefixes:
            continue
        _add(p)
    return found


def _strip_reverse_noise(query: str, syn: SynonymIndex, cat) -> str:
    blob = norm(query)
    for w in REVERSE_STOP:
        blob = re.sub(rf"(^|\s){re.escape(w)}(\s|$)", " ", blob)
    if cat:
        stems = []
        for s in list(cat.synonyms) + [cat.title]:
            ns = norm(s)
            if len(ns) >= 5:
                stems.append(ns)
            stem = ns.rstrip("аяьыие")
            if len(stem) >= 6:
                stems.append(stem)
        for ns in sorted(set(stems), key=len, reverse=True):
            blob = re.sub(rf"{re.escape(ns)}\w*", " ", blob)
    return norm(blob)


def _compact_text(s: str) -> str:
    return re.sub(r"[^a-zа-я0-9]+", "", norm(s))


def _stem_token(tok: str) -> str:
    t = norm(tok).replace("-", "")
    for suf in (
        "ами", "ями", "ого", "ему", "ыми", "ими",
        "ой", "ей", "ом", "ем", "ах", "ях", "ую", "ая", "ое", "ие", "ые",
        "ий", "ый", "ым", "им", "ов", "ев",
    ):
        if t.endswith(suf) and len(t) - len(suf) >= 4:
            return t[:-len(suf)]
    return t


def _params_blob(product: dict) -> str:
    parts = []
    for k, v in (product.get("params") or {}).items():
        if norm(k) in {"видео", "привязка к цветам"}:
            continue
        parts.append(f"{k} {v or ''}")
    return " ".join(parts)


def _alias_hit(left_compact: str, blob_compact: str) -> bool:
    for group in FEATURE_ALIASES:
        if any(a in left_compact for a in group) and any(a in blob_compact for a in group):
            return True
    return False


def _token_in_blob(tok: str, spaced: str, compact: str) -> bool:
    st = _stem_token(tok)
    if len(st) >= 3 and st in spaced:
        return True
    raw = norm(tok).replace("-", "")
    if len(raw) >= 3 and (raw in spaced or raw in compact):
        return True
    return False


def _is_weak_token(tok: str) -> bool:
    st = _stem_token(tok)
    return st.startswith(WEAK_STEMS)


def _is_noise_token(tok: str) -> bool:
    if tok in FEATURE_NOISE or tok in REVERSE_STOP:
        return True
    st = _stem_token(tok)
    if st in FEATURE_NOISE:
        return True
    return st.startswith(("технолог", "функц", "опци"))


def _token_in_alias_group(tok: str) -> bool:
    tc = _compact_text(tok)
    if len(tc) < 4:
        return False
    for group in FEATURE_ALIASES:
        if any(a == tc or a in tc or tc in a for a in group):
            return True
    return False


def _distinctive_tokens(leftover: str) -> list[str]:
    return [t for t in leftover.split() if len(t) >= 3 and not _is_noise_token(t)]


def _best_feature_value(product: dict, leftover: str, inverter: bool) -> str:
    left_compact = _compact_text(leftover)
    distinctive = _distinctive_tokens(leftover)
    strong = [t for t in distinctive if not _is_weak_token(t)]
    scored: list[tuple[int, int, int, str]] = []
    for k, v in (product.get("params") or {}).items():
        if norm(k) in {"видео", "привязка к цветам"}:
            continue
        val = (v or "").strip()
        if not val:
            continue
        nv = norm(val)
        nc = _compact_text(f"{k} {val}")
        if inverter and "инверт" in nv:
            rank = 0
        elif _alias_hit(left_compact, nc):
            rank = 0
        elif strong and any(_token_in_blob(t, nv, nc) for t in strong):
            rank = 1
        elif any(_token_in_blob(t, nv, nc) for t in distinctive):
            rank = 2
        else:
            continue
        usp = "преимущества" in norm(k) or norm(k).startswith("им")
        scored.append((1 if usp else 0, rank, len(val), val))
    if not scored:
        return "да"
    scored.sort()
    val = scored[0][3]
    if len(val) > 90:
        for part in re.split(r"[,;]", val):
            pc = _compact_text(part)
            if _alias_hit(left_compact, pc) or "инверт" in pc:
                return part.strip()
        return val[:90].rstrip() + "…"
    return val


def _feature_hit_value(product: dict, leftover: str) -> str | None:
    distinctive = _distinctive_tokens(leftover)
    if not distinctive:
        return None
    raw = _params_blob(product)
    if not raw.strip():
        return None
    spaced = norm(raw)
    compact = _compact_text(raw)
    left_compact = _compact_text(leftover)
    has_inv = any(_stem_token(t).startswith("инверт") for t in distinctive)
    rest = [
        t for t in distinctive
        if not _stem_token(t).startswith("инверт") and _stem_token(t) not in INVERTER_ALIAS
    ]
    if has_inv:
        if "инверт" not in compact:
            return None
        if rest and not all(_token_in_blob(t, spaced, compact) for t in rest):
            return None
        return _best_feature_value(product, leftover, True)
    alias_ok = _alias_hit(left_compact, compact)
    failed = []
    for t in distinctive:
        if _token_in_blob(t, spaced, compact):
            continue
        if alias_ok and (_is_weak_token(t) or _token_in_alias_group(t)):
            continue
        failed.append(t)
    if failed:
        return None
    return _best_feature_value(product, leftover, False)


def _is_reverse_query(query: str, syn: SynonymIndex) -> bool:
    blob = norm(query)
    if REVERSE_HINT.search(blob):
        return True
    cat = _find_category(query, syn)
    if not cat:
        return False
    if re.search(r"[A-Za-z]{2,6}\s*\d{3}", query):
        return False
    leftover = _strip_reverse_noise(query, syn, cat)
    return bool(leftover)


def _answer_reverse(query: str) -> str:
    syn = load_synonyms()
    index = load_index()
    cat = _find_category(query, syn)
    pool = _category_products(index, cat) if cat else list(index.products)
    leftover = _strip_reverse_noise(query, syn, cat)
    if leftover:
        rows = []
        for p in pool:
            val = _feature_hit_value(p, leftover)
            if not val:
                continue
            model = (p.get("model") or "").strip()
            if not model:
                continue
            rows.append((model, val))
        if not rows:
            return MSG_REVERSE_NONE
        rows.sort(key=lambda x: x[0])
        uniq = []
        seen = set()
        for model, val in rows:
            if model in seen:
                continue
            seen.add(model)
            uniq.append(f"{model} — {val}")
        head = f"Найдены модели, {len(uniq)} шт.:"
        if cat:
            head = f"Найдены модели ({cat.title}), {len(uniq)} шт.:"
        shown = uniq[:40]
        extra = f"\n… ещё {len(uniq) - 40}" if len(uniq) > 40 else ""
        return head + "\n" + "\n".join(shown) + extra
    if not pool:
        return MSG_REVERSE_NONE
    return _list_models(pool, "Уточните модель:")


def needs_property(query: str) -> bool:
    """True if the text names a small set of SKUs and no spec/command."""
    q = (query or "").strip()
    if not q or _parse_ttx(q) is not None or _parse_link(q) is not None:
        return False
    if _is_reverse_query(q, load_synonyms()):
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
    if _is_reverse_query(q, syn):
        return _answer_reverse(q)
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
    if not canon:
        if leftover:
            return MSG_UNKNOWN_PARAM
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
