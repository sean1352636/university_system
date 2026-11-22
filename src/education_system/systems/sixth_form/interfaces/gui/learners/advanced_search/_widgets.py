"""Shared constants, UI/annotation/action-log stores, phonetic + NL helpers,
sparkline and keyboard-shortcut reference for the Advanced Search views.

Moved verbatim from ``advanced_search_views``.
"""

from __future__ import annotations

import json
import logging
import re
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook
from education_system import paths
from education_system.systems.sixth_form.domain.learners.advanced_search import (
    annotations as search_annotations,
    query as search_query,
)
from education_system.systems.sixth_form.domain.learners.advanced_search.models import (
    ALL_SCOPES,
    QueryOptions,
    ValidationError,
)

logger = logging.getLogger("education_system.systems.sixth_form.interfaces.gui.learners.advanced_search.advanced_search_views")


WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

# Conditional row-colour tags (feature 14) — keyed status/risk → bg.
_ROW_TAG_COLOURS: dict[str, str] = {
    "row-active": "#eaffea",     # Active / low risk
    "row-inactive": "#f0f0f0",   # Inactive
    "row-suspended": "#fff3d6",  # Suspended / medium risk
    "row-left": "#ffe3e3",       # Left / high risk
    "row-flagged": "#ffd6d6",    # safeguarding / at-risk
}

# Row-density (feature 13) label → treeview rowheight in px.
_DENSITY_ROWHEIGHT: dict[str, int] = {
    "Compact": 18, "Comfortable": 22, "Spacious": 30,
}


# ══ Persistent UI state (templates + filter presets) ═══════════════
#
# Query templates (feature 1) and filter presets (feature 9) are stored
# as a small JSON document alongside the sixth-form data dir. Kept out
# of the search DB deliberately — it is per-user UI convenience state,
# not shared domain data.

_UI_STORE_NAME = "advanced_search_ui.json"


def _ui_store_path() -> Path:
    return paths.SIXTH_FORM_DATA_DIR / _UI_STORE_NAME


def _load_ui_store() -> dict:
    """Return the UI store dict, always with ``templates``/``presets``
    keys present. Any read/parse error yields a fresh empty store."""
    try:
        with open(_ui_store_path(), encoding="utf-8") as fh:
            store = json.load(fh)
        if isinstance(store, dict):
            store.setdefault("templates", {})
            store.setdefault("presets", {})
            store.setdefault("layouts", {})          # column layouts (feature 11)
            store.setdefault("watchlists", {})        # watchlists (feature 19)
            store.setdefault("pinned_queries", [])    # query chips (feature 23)
            return store
    except (OSError, ValueError):
        pass
    return {"templates": {}, "presets": {}, "layouts": {},
            "watchlists": {}, "pinned_queries": []}


def _save_ui_store(store: dict) -> None:
    """Persist *store* atomically. Failures are logged, not raised —
    losing a template must never crash the search window."""
    try:
        paths.SIXTH_FORM_DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _ui_store_path().with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(store, fh, indent=2)
        tmp.replace(_ui_store_path())
    except OSError:
        logger.warning("could not persist advanced-search UI store",
                       exc_info=True)


# ══ Advanced-search annotations (features 21, 22, 24, 25) ══════════
#
# Tags, an assigned owner, free-text notes and duplicate-merge links are
# advanced-search *overlay* metadata keyed by (scope, entity_id), held in
# the advanced-search database (domain ``annotations``) — never in the
# domain tables — so they are shared and stamped with who set them.

def _load_ann_store() -> dict:
    try:
        return search_annotations.load_all()
    except Exception:
        logger.warning("could not read advanced-search annotations",
                       exc_info=True)
        return {}


def _save_ann_store(store: dict) -> None:
    try:
        search_annotations.save_all(store)
    except Exception:
        logger.warning("could not persist advanced-search annotations",
                       exc_info=True)


def _ann_key(scope: str, entity_id: str) -> str:
    return search_annotations.key(scope, entity_id)


def _get_annotation(scope: str, entity_id: str) -> dict:
    try:
        return search_annotations.get(scope, entity_id)
    except Exception:
        logger.warning("could not read an annotation", exc_info=True)
        return {}


# ══ Action-log overlay (feature 25) ════════════════════════════════
#
# What the operator *did* with results — exports, messages, bulk edits.
# Distinct from the sensitive-access audit (Tools ▸ Audit log).

def _append_action_log(action: str, detail: str = "", count: int = 0) -> None:
    search_annotations.log_action(action, detail, count)


def _read_action_log() -> list[dict]:
    try:
        return search_annotations.list_actions(500)
    except Exception:
        logger.warning("could not read the action log", exc_info=True)
        return []


# ══ Phonetic / fuzzy matching (feature 2) ══════════════════════════

def _soundex(word: str) -> str:
    """Classic Soundex code (letter + 3 digits) for *word*. Drives the
    fuzzy/phonetic result filter so 'Catherine' matches 'Katharine'."""
    word = re.sub(r"[^a-z]", "", (word or "").lower())
    if not word:
        return ""
    codes = {**dict.fromkeys("bfpv", "1"),
             **dict.fromkeys("cgjkqsxz", "2"),
             **dict.fromkeys("dt", "3"), "l": "4",
             **dict.fromkeys("mn", "5"), "r": "6"}
    first = word[0]
    tail: list[str] = []
    prev = codes.get(first, "")
    for ch in word[1:]:
        code = codes.get(ch, "")
        if code and code != prev:
            tail.append(code)
        if ch not in "hw":
            prev = code
    return (first.upper() + "".join(tail) + "000")[:4]


def _phonetic_match(needle: str, haystack: str) -> bool:
    """True if any token of *haystack* is a phonetic or close-fuzzy match
    for any token of *needle*. Deterministic and side-effect free."""
    import difflib
    terms = [t for t in re.split(r"\s+", (needle or "").strip()) if t]
    words = [w for w in re.split(r"\W+", (haystack or "")) if w]
    if not terms or not words:
        return False
    word_sdx = {w: _soundex(w) for w in words}
    for term in terms:
        tsdx = _soundex(term)
        for w, wsdx in word_sdx.items():
            if tsdx and tsdx == wsdx:
                return True
            ratio = difflib.SequenceMatcher(
                None, term.lower(), w.lower()).ratio()
            # Equal Soundex tails cover homophones whose first letters
            # differ (Catherine/Katharine, Steven/Stephen); a moderate
            # similarity floor keeps out coincidental tail matches.
            if tsdx and wsdx and tsdx[1:] == wsdx[1:] and ratio >= 0.6:
                return True
            if ratio >= 0.82:               # close spelling / typo
                return True
    return False


# ── Sparkline + keyboard-shortcut reference (features 10, 20) ───────

def _sparkline(values: list[float]) -> str:
    """Render *values* as a compact unicode sparkline. Empty string for
    an empty/degenerate series."""
    nums = [float(v) for v in values
            if isinstance(v, (int, float))]
    if not nums:
        return ""
    blocks = "▁▂▃▄▅▆▇█"
    lo, hi = min(nums), max(nums)
    span = (hi - lo) or 1.0
    return "".join(blocks[min(len(blocks) - 1,
                              int((v - lo) / span * (len(blocks) - 1)))]
                   for v in nums)


_SHORTCUT_HELP: tuple[tuple[str, str], ...] = (
    ("/  or  Ctrl-L", "Focus the query box"),
    ("Enter", "Run search (query box) / open record (results)"),
    ("Esc", "Return focus to the query box"),
    ("Down (in query box)", "Jump into the results list"),
    ("Double-click", "Open the selected record"),
    ("F2", "Inline-edit the selected student"),
    ("Ctrl-→ / Ctrl-←", "Jump to next / previous scope group"),
    ("Right-click header", "Reorder / pin / hide a column"),
    ("Ctrl-K", "Open the command palette"),
    ("F1  or  ?", "Show this shortcut reference"),
    ("Type letters", "Type-ahead jump to a matching row"),
)


# ══ Natural-language query translation (feature 3) ═════════════════

_NL_STOP: frozenset[str] = frozenset({
    "student", "students", "show", "me", "all", "find", "list", "the",
    "in", "and", "who", "have", "has", "a", "an", "with", "of", "for",
    "that", "are", "is", "please", "give", "get", "records", "record",
    "pupil", "pupils", "any", "some", "their", "them", "whose", "where",
})

_NL_SUBJECTS: frozenset[str] = frozenset({
    "physics", "chemistry", "biology", "maths", "mathematics",
    "economics", "history", "geography", "english", "psychology",
    "sociology", "art", "business", "computing", "law", "politics",
    "french", "spanish", "german", "statistics", "philosophy",
})

# Free-standing thematic terms that map to a plain keyword search.
_NL_THEMES: tuple[str, ...] = (
    "attendance", "behaviour", "behavior", "safeguarding", "risk",
    "email", "phone",
)

_NL_STATUS: dict[str, str] = {
    "withdrawn": "withdrawn",
    "enrolled": "active",
    "active": "active",
    "lost contact": "lost contact",
}


def _nl_to_query(text: str) -> tuple[str, dict]:
    """Heuristically translate an English phrase into a DSL query string
    plus a filter dict.

    Returns ``(query, filters)`` where *filters* may contain
    ``year_group``, ``tutor_group``, ``role`` and ``sen_only`` — the
    concepts the search UI expresses as filter widgets rather than query
    terms. Deterministic and side-effect free so it can be unit tested.
    """
    raw = (text or "").strip()
    if not raw:
        return "", {}
    low = raw.lower()
    filters: dict = {}
    tokens: list[str] = []

    # Quoted phrases → explicit name search, then blank them out so the
    # words inside aren't re-picked as loose keywords.
    for m in re.finditer(r'"([^"]+)"', raw):
        tokens.append(f'name:"{m.group(1)}"')
    low = re.sub(r'"[^"]*"', " ", low)

    # Tutor group first (its "tutor" word must not leak into role
    # detection, and its group code must not survive as a loose keyword).
    m = re.search(r'tutor\s*group\s*([a-z0-9]+)', low)
    if m:
        filters["tutor_group"] = m.group(1).upper()
        low = low[:m.start()] + " " + low[m.end():]

    m = re.search(r'year\s*(12|13)|y(?:r)?\s*(12|13)|(12|13)\s*(?:th)?\s*year',
                  low)
    if m:
        filters["year_group"] = next(g for g in m.groups() if g)
        low = low[:m.start()] + " " + low[m.end():]

    if re.search(r'\bsen\b|special educational', low):
        filters["sen_only"] = True
        low = re.sub(r'\bsen\b|special educational', " ", low)

    for role in ("teacher", "tutor", "teaching assistant", "staff"):
        if re.search(rf'\b{role}\b', low):
            filters["role"] = role
            break

    for phrase, val in _NL_STATUS.items():
        if phrase in low:
            tokens.append(f'status:"{val}"' if " " in val
                          else f'status:{val}')

    for subj in sorted(_NL_SUBJECTS):
        if re.search(rf'\b{subj}\b', low):
            tokens.append(f'subject:{subj}')

    for term in _NL_THEMES:
        if re.search(rf'\b{term}\b', low):
            tokens.append("behaviour" if term == "behavior" else term)

    # Whatever words the structured tokens already consumed shouldn't be
    # re-added as loose keywords.
    consumed = {"year", "tutor", "group", "sen", "special", "educational"}
    for t in tokens:
        consumed.update(re.findall(r'[a-z0-9]+', t.lower()))
    for w in re.findall(r'[a-z0-9]+', low):
        if w in _NL_STOP or w in consumed or w.isdigit() or len(w) < 3:
            continue
        tokens.append(w)
        consumed.add(w)

    seen: set[str] = set()
    out: list[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            out.append(t)
    query = " ".join(out)
    if not query and not filters:
        query = raw          # nothing recognised — fall back to keywords
    return query, filters


# ══ Query lint (feature 6) ═════════════════════════════════════════

def _lint_query(q: str) -> list[str]:
    """Return a list of human-readable warnings for query string *q*.
    Empty list ⇒ the query looks well-formed."""
    warns: list[str] = []
    if q.count('"') % 2:
        warns.append("unbalanced quote")
    depth = 0
    for ch in q:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                break
    if depth != 0:
        warns.append("unbalanced ()")
    for m in re.finditer(r'-?(?:scope|in):([\w,]+)', q, re.IGNORECASE):
        for name in m.group(1).lower().split(","):
            if name and name not in ALL_SCOPES:
                warns.append(f"unknown scope '{name}'")
    # Structural parse — surfaces the same errors run_search would raise,
    # but without touching the database.
    try:
        cleaned, _inc, _exc = search_query._extract_scope_directives(
            search_query.expand_macros(q))
        search_query.parse_query(cleaned, QueryOptions())
    except ValidationError as exc:
        warns.append(str(exc))
    except Exception:  # noqa: BLE001 — lint must never raise
        pass
    return warns


def _choose_from(title: str, prompt: str, options: list[str],
                 parent: tk.Misc) -> str | None:
    """Modal single-choice picker. Returns the chosen option or None."""
    top = tk.Toplevel(parent.winfo_toplevel())
    top.title(title)
    top.transient(parent.winfo_toplevel())
    ttk.Label(top, text=prompt).pack(padx=10, pady=(10, 4), anchor="w")
    var = tk.StringVar()
    cb = ttk.Combobox(top, textvariable=var, values=list(options),
                      state="readonly", width=42)
    cb.pack(padx=10, pady=4)
    if options:
        cb.current(0)
    result: dict[str, str | None] = {"v": None}

    def _ok() -> None:
        result["v"] = var.get() or None
        top.destroy()

    btns = ttk.Frame(top)
    btns.pack(pady=8)
    ttk.Button(btns, text="OK", command=_ok).pack(side="left", padx=4)
    ttk.Button(btns, text="Cancel",
               command=top.destroy).pack(side="left", padx=4)
    top.grab_set()
    parent.winfo_toplevel().wait_window(top)
    return result["v"]


def _add_page(nb, frame: tk.Misc, text: str, group: str) -> None:
    """Add *frame* to a :class:`SidebarBook` under *group*, or to a Notebook."""
    if isinstance(nb, SidebarBook):
        nb.add(frame, text=text, group=group)
    else:
        nb.add(frame, text=text)
