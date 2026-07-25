"""Tkinter views for Sixth Form Advanced Search.

Single window with three tabs:
* Search          — query bar + scope checkboxes + results treeview
                    grouped by scope.
* Saved Searches  — list / run / new / edit / delete saved queries.
* History         — recent runs with re-run / clear.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import random
import re
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from typing import Callable
from education_system.platform import branding
from education_system.systems.sixth_form.infrastructure import paths
from education_system.systems.sixth_form.domain.learners.advanced_search import (
    advanced_search as data,
)
from education_system.systems.sixth_form.domain.learners.advanced_search.advanced_search import (
    ALL_SCOPES,
    DEFAULT_LIMIT_PER_SCOPE,
    Hit,
    QUERY_SYNTAX_HELP,
    QueryOptions,
    SavedSearch,
    SCOPE_LABELS,
    SearchResults,
    ValidationError,
)

logger = logging.getLogger(__name__)

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
    return paths.DATA_DIR / _UI_STORE_NAME


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
        paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
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
# advanced-search *overlay* metadata keyed by (scope, entity_id). They
# live in their own JSON document — deliberately NOT written into the
# domain tables, so this convenience layer can never corrupt student
# records. Surfaced in the preview pane so they're visible where set.

_ANN_STORE_NAME = "advanced_search_annotations.json"


def _ann_store_path() -> Path:
    return paths.DATA_DIR / _ANN_STORE_NAME


def _load_ann_store() -> dict:
    try:
        with open(_ann_store_path(), encoding="utf-8") as fh:
            store = json.load(fh)
        if isinstance(store, dict):
            return store
    except (OSError, ValueError):
        pass
    return {}


def _save_ann_store(store: dict) -> None:
    try:
        paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _ann_store_path().with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(store, fh, indent=2)
        tmp.replace(_ann_store_path())
    except OSError:
        logger.warning("could not persist advanced-search annotations",
                       exc_info=True)


def _ann_key(scope: str, entity_id: str) -> str:
    return f"{scope}:{entity_id}"


def _get_annotation(scope: str, entity_id: str) -> dict:
    return _load_ann_store().get(_ann_key(scope, entity_id), {})


# ══ Action-log overlay (feature 25) ════════════════════════════════
#
# A lightweight local record of what the operator *did* with results —
# exports, messages, bulk edits. Distinct from the domain-level
# sensitive-access audit (Tools ▸ Audit log): this one is about operator
# actions on results, for safeguarding review. Kept in its own JSON doc.

_ACTION_LOG_NAME = "advanced_search_action_log.json"


def _action_log_path() -> Path:
    return paths.DATA_DIR / _ACTION_LOG_NAME


def _append_action_log(action: str, detail: str = "", count: int = 0) -> None:
    """Append one entry to the operator action log. Never raises — a lost
    log line must not break the action it was recording."""
    try:
        path = _action_log_path()
        log: list = []
        if path.exists():
            with open(path, encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, list):
                log = loaded
        log.append({
            "ts": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action, "detail": detail, "count": count,
        })
        del log[:-500]                      # keep only the last 500 entries
        paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(log, fh, indent=2)
        tmp.replace(path)
    except (OSError, ValueError):
        logger.warning("could not append advanced-search action log",
                       exc_info=True)


def _read_action_log() -> list[dict]:
    try:
        with open(_action_log_path(), encoding="utf-8") as fh:
            loaded = json.load(fh)
        if isinstance(loaded, list):
            return loaded
    except (OSError, ValueError):
        pass
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
        cleaned, _inc, _exc = data._extract_scope_directives(
            data.expand_macros(q))
        data.parse_query(cleaned, QueryOptions())
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


def open_advanced_search_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Advanced Search — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    search_tab = SearchTab(nb)
    SavedTab(nb, search_tab)
    HistoryTab(nb, search_tab)
    ToolsTab(nb)


# ══ Search tab ═════════════════════════════════════════════════════

class SearchTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Search")
        self._scope_vars: dict[str, tk.BooleanVar] = {}
        self._build()

    def _build(self) -> None:
        # Query row
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Query:").pack(side="left")
        self.query_e = ttk.Entry(bar, width=44)
        self.query_e.pack(side="left", padx=(4, 8), fill="x", expand=True)
        self.query_e.bind("<Return>", lambda _e: self.run())
        self.query_e.bind("<KeyRelease>", self._on_query_key)
        ttk.Label(bar, text="Limit/scope:").pack(side="left")
        self.limit_e = ttk.Entry(bar, width=6)
        self.limit_e.insert(0, str(DEFAULT_LIMIT_PER_SCOPE))
        self.limit_e.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Search",
                    command=self.run).pack(side="left")
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left", padx=(4, 0))
        ttk.Button(bar, text="Syntax…",
                    command=self._show_syntax).pack(side="left", padx=(4, 0))

        # ── Query tools row (features 1–10) ───────────────────────────
        tools = ttk.Frame(self.frame)
        tools.pack(fill="x", padx=8, pady=(0, 4))

        # (1) Query templates — query + scopes + filters, named & reusable
        self._tpl_mb = ttk.Menubutton(tools, text="Templates ▾")
        self._tpl_menu = tk.Menu(self._tpl_mb, tearoff=False,
                                  postcommand=self._rebuild_template_menu)
        self._tpl_mb.configure(menu=self._tpl_menu)
        self._tpl_mb.pack(side="left")

        # (9) Filter presets — filter widgets only, named & reusable
        self._preset_mb = ttk.Menubutton(tools, text="Presets ▾")
        self._preset_menu = tk.Menu(self._preset_mb, tearoff=False,
                                     postcommand=self._rebuild_preset_menu)
        self._preset_mb.configure(menu=self._preset_menu)
        self._preset_mb.pack(side="left", padx=(4, 0))

        # (2) Recent raw queries
        self._hist_mb = ttk.Menubutton(tools, text="History ▾")
        self._hist_menu = tk.Menu(self._hist_mb, tearoff=False,
                                   postcommand=self._rebuild_history_menu)
        self._hist_mb.configure(menu=self._hist_menu)
        self._hist_mb.pack(side="left", padx=(4, 0))

        # (3) Natural-language query
        ttk.Button(tools, text="NL…",
                    command=self._natural_language_query).pack(
            side="left", padx=(4, 0))

        # (4) Regex mode (also drives within-results + lint semantics)
        self.regex_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(tools, text="Regex", variable=self.regex_var,
                          command=self._update_lint).pack(side="left",
                                                          padx=(6, 0))

        # (5) Negate last term
        ttk.Button(tools, text="Negate last",
                    command=self._negate_last_term).pack(side="left",
                                                         padx=(4, 0))

        # (7) Random sample
        ttk.Button(tools, text="Random…",
                    command=self._random_sample).pack(side="left", padx=(4, 0))

        # (8) Search within current results
        ttk.Label(tools, text="Within:").pack(side="left", padx=(8, 0))
        self.within_e = ttk.Entry(tools, width=14)
        self.within_e.pack(side="left", padx=(2, 0))
        self.within_e.bind("<Return>",
                           lambda _e: self._search_within_results())
        ttk.Button(tools, text="Filter",
                    command=self._search_within_results).pack(side="left",
                                                              padx=(2, 0))

        # (10) Voice query
        ttk.Button(tools, text="🎤", width=3,
                    command=self._voice_query).pack(side="left", padx=(6, 0))

        # (6) Query lint indicator (updates as you type)
        self.lint_var = tk.StringVar(value="")
        ttk.Label(tools, textvariable=self.lint_var,
                   foreground="#b26a00", anchor="e").pack(side="right")

        # Scopes row
        scopes_frame = ttk.LabelFrame(self.frame, text="Scopes",
                                         padding=6)
        scopes_frame.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Button(scopes_frame, text="All",
                    command=self._select_all_scopes).grid(
            row=0, column=0, padx=2)
        ttk.Button(scopes_frame, text="None",
                    command=self._select_no_scopes).grid(
            row=0, column=1, padx=2)
        col = 2
        row = 0
        for key in ALL_SCOPES:
            var = tk.BooleanVar(value=True)
            self._scope_vars[key] = var
            ttk.Checkbutton(scopes_frame, text=SCOPE_LABELS[key],
                              variable=var).grid(row=row, column=col,
                                                  sticky="w", padx=4)
            col += 1
            if col >= 8:
                col = 2
                row += 1

        # Filters row (items 23–30)
        filt = ttk.LabelFrame(self.frame, text="Filters", padding=6)
        filt.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Label(filt, text="Year:").grid(row=0, column=0, sticky="e")
        self.year_e = ttk.Entry(filt, width=6)
        self.year_e.grid(row=0, column=1, padx=(2, 8))
        ttk.Label(filt, text="Tutor group:").grid(row=0, column=2,
                                                    sticky="e")
        self.tg_e = ttk.Entry(filt, width=10)
        self.tg_e.grid(row=0, column=3, padx=(2, 8))
        ttk.Label(filt, text="Role:").grid(row=0, column=4, sticky="e")
        self.role_e = ttk.Entry(filt, width=10)
        self.role_e.grid(row=0, column=5, padx=(2, 8))
        ttk.Label(filt, text="Staff:").grid(row=0, column=6, sticky="e")
        self.owner_e = ttk.Entry(filt, width=10)
        self.owner_e.grid(row=0, column=7, padx=(2, 8))
        ttk.Label(filt, text="Actor:").grid(row=0, column=8, sticky="e")
        self.actor_e = ttk.Entry(filt, width=10)
        self.actor_e.grid(row=0, column=9, padx=(2, 8))
        self.sen_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filt, text="SEN only",
                          variable=self.sen_var).grid(row=0, column=10,
                                                       padx=4)
        self.arch_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filt, text="Inc. archived",
                          variable=self.arch_var).grid(row=0, column=11,
                                                        padx=4)
        self.interleave_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filt, text="Interleave by score",
                          variable=self.interleave_var).grid(
            row=0, column=12, padx=4)
        self.cluster_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filt, text="Cluster by student",
                          variable=self.cluster_var).grid(
            row=0, column=13, padx=4)
        self.fold_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(filt, text="Fold accents",
                          variable=self.fold_var).grid(
            row=0, column=14, padx=4)
        # Security + live-search controls (items 31, 35, 42)
        self.redact_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filt, text="Redact sensitive",
                          variable=self.redact_var).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Label(filt, text="Break-glass reason:").grid(
            row=1, column=2, sticky="e")
        self.bg_e = ttk.Entry(filt, width=22)
        self.bg_e.grid(row=1, column=3, columnspan=3, sticky="w", padx=(2, 8))
        self.live_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filt, text="Live (search as you type)",
                          variable=self.live_var).grid(
            row=1, column=6, columnspan=3, sticky="w")
        self._live_after = None

        # Controls strip: grouping (21), column chooser (18), stats (22)
        ctrl = ttk.Frame(self.frame)
        ctrl.pack(fill="x", padx=8, pady=(0, 2))
        ttk.Label(ctrl, text="Group by:").pack(side="left")
        self.group_by = tk.StringVar(value="Scope")
        gb = ttk.Combobox(ctrl, textvariable=self.group_by, width=12,
                           state="readonly",
                           values=["Scope", "Year", "Tutor", "Risk",
                                   "Year+Risk", "Tutor+Risk", "Scope+Risk"])
        gb.pack(side="left", padx=(2, 8))
        gb.bind("<<ComboboxSelected>>", lambda _e: self._rerender())
        self._col_vars: dict[str, tk.BooleanVar] = {}
        colmb = ttk.Menubutton(ctrl, text="Columns ▾")
        colmenu = tk.Menu(colmb, tearoff=False)
        for key, lbl in (("entity_id", "ID"), ("label", "Label"),
                         ("sublabel", "Details"), ("match", "Match")):
            v = tk.BooleanVar(value=True)
            self._col_vars[key] = v
            colmenu.add_checkbutton(label=lbl, variable=v,
                                     command=self._apply_columns)
        colmb.configure(menu=colmenu)
        colmb.pack(side="left")
        self.stats_var = tk.StringVar(value="")
        ttk.Label(ctrl, textvariable=self.stats_var,
                   anchor="e").pack(side="right")

        # ── View-options + pagination row (features 11, 13–16) ────────
        view = ttk.Frame(self.frame)
        view.pack(fill="x", padx=8, pady=(0, 2))
        # (11) Flat vs grouped
        self.flat_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(view, text="Flat list", variable=self.flat_var,
                          command=self._rerender).pack(side="left")
        # (13) Row density
        ttk.Label(view, text="Density:").pack(side="left", padx=(8, 2))
        self.density_var = tk.StringVar(value="Comfortable")
        dens = ttk.Combobox(view, textvariable=self.density_var, width=12,
                            state="readonly",
                            values=["Compact", "Comfortable", "Spacious"])
        dens.pack(side="left")
        dens.bind("<<ComboboxSelected>>", lambda _e: self._apply_density())
        # (14) Conditional row colour
        self.colour_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(view, text="Colour by status/risk",
                          variable=self.colour_var,
                          command=self._rerender).pack(side="left", padx=(8, 0))
        # (16) Expand / collapse all groups
        ttk.Button(view, text="Expand all", width=10,
                    command=self._expand_all).pack(side="left", padx=(8, 0))
        ttk.Button(view, text="Collapse all", width=11,
                    command=self._collapse_all).pack(side="left", padx=(2, 0))
        # (15) Pagination
        ttk.Label(view, text="Page size:").pack(side="left", padx=(12, 2))
        self.page_size_var = tk.StringVar(value="All")
        psz = ttk.Combobox(view, textvariable=self.page_size_var, width=6,
                           state="readonly",
                           values=["25", "50", "100", "250", "All"])
        psz.pack(side="left")
        psz.bind("<<ComboboxSelected>>", lambda _e: self._on_page_size())
        ttk.Button(view, text="◀ Prev", width=7,
                    command=self._prev_page).pack(side="left", padx=(6, 0))
        self.page_var = tk.StringVar(value="")
        ttk.Label(view, textvariable=self.page_var, width=14,
                   anchor="center").pack(side="left")
        ttk.Button(view, text="Next ▶", width=7,
                    command=self._next_page).pack(side="left")
        self._page = 0

        # Main split: results (left) + preview/shortlist (right) (19, 23)
        paned = ttk.Panedwindow(self.frame, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=8, pady=4)
        table_frame = ttk.Frame(paned)
        paned.add(table_frame, weight=3)
        self._cols = ("entity_id", "label", "sublabel", "match")
        self._col_titles = {"entity_id": "ID", "label": "Label",
                            "sublabel": "Details", "match": "Match"}
        # Column ordering (12) + pinned/frozen-to-front columns (17).
        self._col_order = list(self._cols)
        self._pinned_cols: set[str] = set()
        self._display_cols = list(self._cols)
        # Dedicated style so row-density (13) changes don't leak to other
        # treeviews in the app.
        self._tree_style = ttk.Style()
        self._tree_style.configure("AdvSearch.Treeview", rowheight=22)
        self.tree = ttk.Treeview(table_frame, columns=self._cols,
                                    show="tree headings",
                                    style="AdvSearch.Treeview")
        self.tree.heading("#0", text="Group")
        for c in self._cols:
            self.tree.heading(
                c, text=self._col_titles[c],
                command=lambda cc=c: self._sort_by(cc))
        self.tree.column("#0", width=150, anchor="w")
        self.tree.column("entity_id", width=80, anchor="w")
        self.tree.column("label", width=300, anchor="w")
        self.tree.column("sublabel", width=420, anchor="w")
        self.tree.column("match", width=150, anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("scope", background="#eef7ff",
                                  font=("", 10, "bold"))
        # Conditional row-colour tags (feature 14).
        for _tag, _bg in _ROW_TAG_COLOURS.items():
            self.tree.tag_configure(_tag, background=_bg)
        # Heatmap buckets (feature 13) — cool→warm by score.
        for _i, _bg in enumerate(
                ("#e8f0ff", "#e6f7ec", "#fff7d6", "#ffe6cc", "#ffd6d6")):
            self.tree.tag_configure(f"heat{_i}", background=_bg)
        # Diff-since-last-run highlight (feature 4).
        self.tree.tag_configure("row-new", background="#d9f2ff",
                                 font=("", 10, "bold"))

        right = ttk.Panedwindow(paned, orient="vertical")
        paned.add(right, weight=2)
        # Preview pane (item 19)
        prev_frame = ttk.LabelFrame(right, text="Preview", padding=4)
        right.add(prev_frame, weight=3)
        self.preview = tk.Text(prev_frame, wrap="word", width=38,
                                font=("TkFixedFont", 9), state="disabled")
        self.preview.pack(fill="both", expand=True)
        # Shortlist tray (item 23) — persists across searches this session
        sl_frame = ttk.LabelFrame(right, text="Shortlist", padding=4)
        right.add(sl_frame, weight=2)
        self.shortlist_box = tk.Listbox(sl_frame, height=6)
        self.shortlist_box.pack(side="left", fill="both", expand=True)
        self.shortlist_box.bind("<Double-1>",
                                 lambda _e: self._open_shortlisted())
        slb = ttk.Frame(sl_frame)
        slb.pack(side="right", fill="y")
        ttk.Button(slb, text="Open", width=7,
                    command=self._open_shortlisted).pack(pady=1)
        ttk.Button(slb, text="Remove", width=7,
                    command=self._remove_shortlisted).pack(pady=1)
        ttk.Button(slb, text="→Cohort", width=7,
                    command=self._shortlist_to_cohort).pack(pady=1)
        ttk.Button(slb, text="Clear", width=7,
                    command=self._clear_shortlist).pack(pady=1)
        self._shortlist: list[Hit] = []

        # Bulk-actions toolbar (item 20) + recent breadcrumb (item 25)
        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(2, 4))
        ttk.Button(actions, text="Open",
                    command=self._open_selected).pack(side="left")
        ttk.Button(actions, text="Copy IDs",
                    command=self._copy_ids).pack(side="left", padx=(4, 0))
        ttk.Button(actions, text="Copy emails",
                    command=self._copy_emails).pack(side="left", padx=(4, 0))
        ttk.Button(actions, text="Export…",
                    command=self._export_results_dialog).pack(
            side="left", padx=(4, 0))
        ttk.Button(actions, text="Message…",
                    command=self._mailmerge_dialog).pack(side="left",
                                                          padx=(4, 0))
        ttk.Button(actions, text="Contact sheet",
                    command=self._contact_sheet).pack(side="left", padx=(4, 0))
        ttk.Button(actions, text="Pin",
                    command=self._pin_selected).pack(side="left", padx=(4, 0))
        ttk.Button(actions, text="Shortlist +",
                    command=self._add_to_shortlist).pack(side="left",
                                                          padx=(4, 0))
        ttk.Button(actions, text="Save as cohort…",
                    command=self._save_cohort).pack(side="left", padx=(4, 0))
        # Bulk actions on the selection (features 21–25).
        bulk_mb = ttk.Menubutton(actions, text="Bulk ▾")
        bulk_menu = tk.Menu(bulk_mb, tearoff=False)
        bulk_menu.add_command(label="Tag selected…",
                              command=self._bulk_tag)
        bulk_menu.add_command(label="Assign owner…",
                              command=self._bulk_assign_staff)
        bulk_menu.add_command(label="Set status…  (students)",
                              command=self._bulk_status_change)
        bulk_menu.add_command(label="Add note…",
                              command=self._bulk_add_note)
        bulk_menu.add_separator()
        bulk_menu.add_command(label="Merge 2 duplicates…  (students)",
                              command=self._merge_duplicates)
        bulk_mb.configure(menu=bulk_menu)
        bulk_mb.pack(side="left", padx=(4, 0))
        self.recent_var = tk.StringVar()
        self.recent_combo = ttk.Combobox(
            actions, textvariable=self.recent_var, width=26,
            state="readonly")
        self.recent_combo.pack(side="right")
        self.recent_combo.bind("<<ComboboxSelected>>", self._reopen_recent)
        ttk.Label(actions, text="Recently opened:").pack(side="right",
                                                          padx=(0, 4))
        self._recent: list[Hit] = []

        # ── New-feature toolbar (features 1–25 of this request) ───────
        self.phonetic_var = tk.BooleanVar(value=False)   # feature 2
        self.diff_var = tk.BooleanVar(value=False)        # feature 4
        self.heatmap_var = tk.BooleanVar(value=False)     # feature 13
        self.safe_var = tk.BooleanVar(value=False)        # feature 24
        self.dark_var = tk.BooleanVar(value=False)        # feature 21
        self._cmp_slots: dict[str, dict] = {}             # feature 12
        self._ann_undo: list[tuple[str, str]] = []        # feature 17

        more = ttk.Frame(self.frame)
        more.pack(fill="x", padx=8, pady=(0, 2))

        # Query ▾
        q_mb = ttk.Menubutton(more, text="Query ▾")
        q_menu = tk.Menu(q_mb, tearoff=False)
        q_menu.add_command(label="Boolean builder…  (1)",
                           command=self._boolean_builder)
        q_menu.add_command(label="Regex tester…  (7)",
                           command=self._regex_tester)
        q_menu.add_command(label="Estimate hit count  (6)",
                           command=self._estimate_query)
        q_menu.add_checkbutton(label="Phonetic / fuzzy match  (2)",
                               variable=self.phonetic_var,
                               command=self._toggle_phonetic)
        q_menu.add_command(label="Pin current query as chip  (23)",
                           command=self._pin_current_query)
        q_mb.configure(menu=q_menu)
        q_mb.pack(side="left")

        # View ▾
        v_mb = ttk.Menubutton(more, text="View ▾")
        v_menu = tk.Menu(v_mb, tearoff=False)
        self._layout_menu = tk.Menu(v_menu, tearoff=False,
                                    postcommand=self._rebuild_layout_menu)
        v_menu.add_cascade(label="Column layouts  (11)",
                           menu=self._layout_menu)
        v_menu.add_checkbutton(label="Heatmap by score  (13)",
                               variable=self.heatmap_var,
                               command=self._toggle_heatmap)
        v_menu.add_checkbutton(label="Diff since last run  (4)",
                               variable=self.diff_var,
                               command=self._toggle_diff)
        v_menu.add_checkbutton(label="Safe mode (mask sensitive)  (24)",
                               variable=self.safe_var,
                               command=self._toggle_safe)
        v_menu.add_checkbutton(label="High-contrast dark theme  (21)",
                               variable=self.dark_var,
                               command=self._toggle_theme)
        v_menu.add_separator()
        v_menu.add_command(label="Pivot — scope × status  (9)",
                           command=self._pivot_view)
        v_menu.add_command(label="Cross-scope overlap  (5)",
                           command=self._cross_scope_overlap)
        v_mb.configure(menu=v_menu)
        v_mb.pack(side="left", padx=(4, 0))

        # Compare ▾ (feature 12)
        c_mb = ttk.Menubutton(more, text="Compare ▾")
        c_menu = tk.Menu(c_mb, tearoff=False)
        c_menu.add_command(label="Capture current as slot A",
                           command=lambda: self._snapshot_slot("A"))
        c_menu.add_command(label="Capture current as slot B",
                           command=lambda: self._snapshot_slot("B"))
        c_menu.add_command(label="Show A vs B", command=self._compare_slots)
        c_mb.configure(menu=c_menu)
        c_mb.pack(side="left", padx=(4, 0))

        # Triage ▾
        t_mb = ttk.Menubutton(more, text="Triage ▾")
        t_menu = tk.Menu(t_mb, tearoff=False)
        t_menu.add_command(label="Flag with reason…  (14)",
                           command=self._bulk_flag)
        t_menu.add_command(label="Assign to workflow…  (18)",
                           command=self._bulk_assign_workflow)
        t_menu.add_command(label="PDF report for selection  (16)",
                           command=self._export_pdf_reports)
        t_menu.add_separator()
        t_menu.add_command(label="Undo last bulk edit  (17)",
                           command=self._undo_bulk)
        t_menu.add_command(label="Operator action log  (25)",
                           command=self._show_action_log)
        t_mb.configure(menu=t_menu)
        t_mb.pack(side="left", padx=(4, 0))

        # Watchlists ▾ (feature 19)
        w_mb = ttk.Menubutton(more, text="Watchlists ▾")
        self._watch_menu = tk.Menu(w_mb, tearoff=False,
                                   postcommand=self._rebuild_watchlist_menu)
        w_mb.configure(menu=self._watch_menu)
        w_mb.pack(side="left", padx=(4, 0))

        # Palette + help (features 22, 20)
        ttk.Button(more, text="⌘ Palette",
                   command=self._command_palette).pack(side="left", padx=(8, 0))
        ttk.Button(more, text="? Shortcuts",
                   command=self._show_shortcuts).pack(side="left", padx=(4, 0))

        # Pinned-query chips (feature 23)
        self.qchip_frame = ttk.Frame(self.frame)
        self.qchip_frame.pack(fill="x", padx=8)

        # Suggested-filter facet chips (item 47).
        self.facet_frame = ttk.Frame(self.frame)
        self.facet_frame.pack(fill="x", padx=8)

        # Did-you-mean row (item 20 of the previous batch).
        self.sugg_frame = ttk.Frame(self.frame)
        self.sugg_frame.pack(fill="x", padx=8)

        # Status bar
        self.status_var = tk.StringVar(value="Ready.  (/ to focus, "
                                              "Enter to search, "
                                              "double-click to open, "
                                              "type to jump)")
        ttk.Label(self.frame, textvariable=self.status_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

        # Keyboard navigation + type-ahead jump (item 24)
        self.tree.bind("<Double-1>", lambda _e: self._open_selected())
        self.tree.bind("<Return>", lambda _e: self._open_selected())
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Key>", self._type_ahead)
        # Column reorder/pin menu (12, 17), inline edit (18),
        # quick-look hover (19), jump-to-scope (20).
        self.tree.bind("<Button-3>", self._show_column_menu)
        self.tree.bind("<F2>", lambda _e: self._inline_edit())
        self.tree.bind("<Motion>", self._on_tree_motion)
        self.tree.bind("<Leave>", lambda _e: self._hide_quicklook())
        self.tree.bind("<Control-Right>", self._jump_next_scope)
        self.tree.bind("<Control-Left>", self._jump_prev_scope)
        self._ql_after = None
        self._ql_win: tk.Toplevel | None = None
        self._ql_row: str | None = None
        self.frame.bind_all("<slash>", self._focus_query)
        self.frame.bind_all("<Control-l>", self._focus_query)
        self.frame.bind_all("<Escape>", self._focus_query)
        self.query_e.bind("<Down>",
                           lambda _e: (self.tree.focus_set(),
                                        self._focus_first_hit()))
        self._typeahead_buf = ""
        self._sort_state: tuple[str, bool] | None = None
        self._last_results: SearchResults | None = None
        self._group_index: dict[str, tuple] = {}

        # Command palette (22) + shortcut cheatsheet (20) key bindings.
        self._build_command_registry()
        self.frame.bind_all("<Control-k>", self._command_palette)
        self.frame.bind_all("<F1>", self._show_shortcuts)
        # '?' opens the cheatsheet only from the results tree, so it never
        # interferes with typing '?' into the query box (regex quantifiers).
        self.tree.bind("<question>", self._show_shortcuts)
        self._rebuild_qchips()               # restore pinned-query chips (23)

    def _selected_scopes(self) -> list[str]:
        return [k for k, v in self._scope_vars.items() if v.get()]

    def _select_all_scopes(self) -> None:
        for v in self._scope_vars.values():
            v.set(True)

    def _select_no_scopes(self) -> None:
        for v in self._scope_vars.values():
            v.set(False)

    def _clear(self) -> None:
        self.query_e.delete(0, "end")
        for i in self.tree.get_children():
            self.tree.delete(i)
        self._show_suggestion("")
        for w in self.facet_frame.winfo_children():
            w.destroy()
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.configure(state="disabled")
        self.stats_var.set("")
        self.status_var.set("Cleared.  (shortlist kept)")

    # Public API for other tabs to load a query into the search bar
    # and run it.
    def load_query(self, query: str, scopes: list[str] | None) -> None:
        self.query_e.delete(0, "end")
        self.query_e.insert(0, query)
        if scopes is not None:
            for k, v in self._scope_vars.items():
                v.set(k in scopes)
        self.run()

    # ══ Query-tool features (1–10) ════════════════════════════════════

    # ── Shared filter-state helpers (used by templates + presets) ──────

    def _collect_filter_state(self) -> dict:
        return {
            "year": self.year_e.get(),
            "tutor_group": self.tg_e.get(),
            "role": self.role_e.get(),
            "owner": self.owner_e.get(),
            "actor": self.actor_e.get(),
            "sen": self.sen_var.get(),
            "arch": self.arch_var.get(),
            "redact": self.redact_var.get(),
            "fold": self.fold_var.get(),
            "interleave": self.interleave_var.get(),
            "cluster": self.cluster_var.get(),
        }

    def _apply_filter_state(self, fs: dict) -> None:
        def _set(entry: ttk.Entry, val) -> None:
            entry.delete(0, "end")
            entry.insert(0, str(val or ""))
        _set(self.year_e, fs.get("year", ""))
        _set(self.tg_e, fs.get("tutor_group", ""))
        _set(self.role_e, fs.get("role", ""))
        _set(self.owner_e, fs.get("owner", ""))
        _set(self.actor_e, fs.get("actor", ""))
        self.sen_var.set(bool(fs.get("sen")))
        self.arch_var.set(bool(fs.get("arch")))
        self.redact_var.set(bool(fs.get("redact")))
        self.fold_var.set(bool(fs.get("fold", True)))
        self.interleave_var.set(bool(fs.get("interleave")))
        self.cluster_var.set(bool(fs.get("cluster")))

    def _results_from_hits(self, hits: list[Hit],
                           query: str) -> SearchResults:
        """Wrap a flat list of hits back into a SearchResults grouped by
        scope — used by regex/within/random which produce hit subsets."""
        by_scope: dict[str, list[Hit]] = {}
        for h in hits:
            by_scope.setdefault(h.scope, []).append(h)
        return SearchResults(
            query=query,
            scopes=list(by_scope.keys()) or self._selected_scopes(),
            hits_by_scope=by_scope, total=len(hits),
            ranked_hits=list(hits), suggestions=[])

    # ── (1) Query templates ────────────────────────────────────────────

    def _rebuild_template_menu(self) -> None:
        m = self._tpl_menu
        m.delete(0, "end")
        m.add_command(label="Save current as template…",
                      command=self._save_query_template)
        store = _load_ui_store()
        names = sorted(store["templates"])
        if names:
            m.add_command(label="Delete a template…",
                          command=self._delete_template)
            m.add_separator()
            for n in names:
                m.add_command(label=n,
                              command=lambda nn=n: self._apply_template(nn))
        else:
            m.add_separator()
            m.add_command(label="(no templates yet)", state="disabled")

    def _save_query_template(self) -> None:
        name = simpledialog.askstring("Save template", "Template name:",
                                      parent=self.frame)
        if not name or not name.strip():
            return
        name = name.strip()
        store = _load_ui_store()
        store["templates"][name] = {
            "query": self.query_e.get().strip(),
            "scopes": self._selected_scopes(),
            "filters": self._collect_filter_state(),
        }
        _save_ui_store(store)
        self.status_var.set(f"Saved template {name!r}.")

    def _apply_template(self, name: str) -> None:
        tpl = _load_ui_store()["templates"].get(name)
        if not tpl:
            return
        self.query_e.delete(0, "end")
        self.query_e.insert(0, tpl.get("query", ""))
        scopes = tpl.get("scopes") or list(ALL_SCOPES)
        for k, v in self._scope_vars.items():
            v.set(k in scopes)
        self._apply_filter_state(tpl.get("filters", {}))
        self._update_lint()
        self.run()

    def _delete_template(self) -> None:
        store = _load_ui_store()
        name = _choose_from("Delete template", "Template to delete:",
                            sorted(store["templates"]), self.frame)
        if name and name in store["templates"]:
            del store["templates"][name]
            _save_ui_store(store)
            self.status_var.set(f"Deleted template {name!r}.")

    # ── (2) Recent query history ────────────────────────────────────────

    def _rebuild_history_menu(self) -> None:
        m = self._hist_menu
        m.delete(0, "end")
        try:
            entries = data.list_history(limit=40)
        except Exception:  # noqa: BLE001
            entries = []
        seen: set[str] = set()
        queries: list[str] = []
        for e in entries:
            qs = (e.query or "").strip()
            if qs and qs not in seen:
                seen.add(qs)
                queries.append(qs)
        if queries:
            for qs in queries[:20]:
                label = (qs[:60] + "…") if len(qs) > 60 else qs
                m.add_command(label=label,
                              command=lambda s=qs: self._use_history_query(s))
            m.add_separator()
            m.add_command(label="Clear history",
                          command=self._clear_history_confirm)
        else:
            m.add_command(label="(no history yet)", state="disabled")

    def _use_history_query(self, q: str) -> None:
        self.query_e.delete(0, "end")
        self.query_e.insert(0, q)
        self._update_lint()
        self.run()

    def _clear_history_confirm(self) -> None:
        if messagebox.askyesno("Clear history",
                               "Delete all recorded search history?"):
            try:
                data.clear_history()
            except Exception:  # noqa: BLE001
                pass
            self.status_var.set("History cleared.")

    # ── (3) Natural-language query ──────────────────────────────────────

    def _natural_language_query(self) -> None:
        top = tk.Toplevel(self.frame.winfo_toplevel())
        top.title("Natural-language query")
        top.geometry("560x340")
        top.transient(self.frame.winfo_toplevel())
        ttk.Label(top, text="Describe what you're looking for:").pack(
            anchor="w", padx=10, pady=(10, 2))
        txt = tk.Text(top, height=4, wrap="word")
        txt.pack(fill="x", padx=10)
        txt.insert("1.0", "e.g. year 13 physics students with attendance "
                          "concerns")
        prev_var = tk.StringVar(value="")
        ttk.Label(top, text="Generated query:").pack(anchor="w", padx=10,
                                                     pady=(10, 2))
        ttk.Label(top, textvariable=prev_var, foreground="#0a5",
                  wraplength=520, justify="left").pack(anchor="w", padx=10)

        state: dict = {"q": "", "filters": {}}

        def _preview() -> None:
            q, filters = _nl_to_query(txt.get("1.0", "end"))
            state["q"], state["filters"] = q, filters
            bits = [f"query: {q!r}" if q else "query: (none)"]
            if filters:
                bits.append("filters: " + ", ".join(
                    f"{k}={v}" for k, v in filters.items()))
            prev_var.set("\n".join(bits))

        def _apply() -> None:
            _preview()
            self.query_e.delete(0, "end")
            self.query_e.insert(0, state["q"])
            self._apply_nl_filters(state["filters"])
            self._update_lint()
            top.destroy()
            self.run()

        btns = ttk.Frame(top)
        btns.pack(pady=12)
        ttk.Button(btns, text="Preview", command=_preview).pack(side="left",
                                                                padx=4)
        ttk.Button(btns, text="Apply & search", command=_apply).pack(
            side="left", padx=4)
        ttk.Button(btns, text="Cancel", command=top.destroy).pack(side="left",
                                                                  padx=4)
        _preview()
        top.grab_set()

    def _apply_nl_filters(self, filters: dict) -> None:
        if "year_group" in filters:
            self.year_e.delete(0, "end")
            self.year_e.insert(0, str(filters["year_group"]))
        if "tutor_group" in filters:
            self.tg_e.delete(0, "end")
            self.tg_e.insert(0, str(filters["tutor_group"]))
        if "role" in filters:
            self.role_e.delete(0, "end")
            self.role_e.insert(0, str(filters["role"]))
        if filters.get("sen_only"):
            self.sen_var.set(True)

    # ── (4) Regex filtering ─────────────────────────────────────────────

    def _filter_results_regex(self, results: SearchResults,
                              pattern: str) -> SearchResults | None:
        try:
            rx = re.compile(pattern, re.IGNORECASE)
        except re.error as exc:
            messagebox.showerror("Invalid regex", str(exc))
            return None
        kept: list[Hit] = [
            h for h in results.all_hits()
            if rx.search(h.entity_id or "") or rx.search(h.label or "")
            or rx.search(h.sublabel or "")]
        return self._results_from_hits(kept, query=f"/{pattern}/")

    # ── (5) Negate last term ────────────────────────────────────────────

    def _negate_last_term(self) -> None:
        text = self.query_e.get()
        parts = text.split()
        if not parts:
            return
        last = parts[-1]
        parts[-1] = last[1:] if last.startswith("-") else "-" + last
        trailing = " " if text.endswith(" ") else ""
        self.query_e.delete(0, "end")
        self.query_e.insert(0, " ".join(parts) + trailing)
        self._update_lint()

    # ── (6) Query lint ──────────────────────────────────────────────────

    def _update_lint(self) -> None:
        if not hasattr(self, "lint_var"):
            return
        q = self.query_e.get().strip()
        if not q:
            self.lint_var.set("")
            return
        if getattr(self, "regex_var", None) and self.regex_var.get():
            try:
                re.compile(q)
                self.lint_var.set("regex ✓")
            except re.error as exc:
                self.lint_var.set(f"⚠ regex: {exc}")
            return
        warns = _lint_query(q)
        self.lint_var.set("⚠ " + "  ·  ".join(warns) if warns else "✓")

    # ── (7) Random sample ───────────────────────────────────────────────

    def _random_sample(self) -> None:
        n = simpledialog.askinteger(
            "Random sample", "How many records to sample?",
            initialvalue=10, minvalue=1, parent=self.frame)
        if not n:
            return
        if self._last_results is None:
            self.run()
        pool_res = self._last_results
        if pool_res is None:
            return
        pool = pool_res.all_hits()
        if not pool:
            self.status_var.set("No results to sample.")
            return
        sample = random.sample(pool, min(n, len(pool)))
        self._render(self._results_from_hits(
            sample, query=f"random {len(sample)} of {len(pool)}"))
        self.status_var.set(
            f"Showing a random {len(sample)} of {len(pool)} results.")

    # ── (8) Search within current results ───────────────────────────────

    def _search_within_results(self) -> None:
        term = self.within_e.get().strip()
        if self._last_results is None:
            self.status_var.set("Run a search first.")
            return
        if not term:
            self.status_var.set("Enter text to filter within results.")
            return
        if getattr(self, "regex_var", None) and self.regex_var.get():
            try:
                rx = re.compile(term, re.IGNORECASE)
            except re.error as exc:
                messagebox.showerror("Invalid regex", str(exc))
                return
            def match(s: str) -> bool:
                return bool(rx.search(s))
        else:
            needle = term.lower()
            def match(s: str) -> bool:
                return needle in s.lower()
        pool = self._last_results
        kept = [h for h in pool.all_hits()
                if match(h.entity_id or "") or match(h.label or "")
                or match(h.sublabel or "")]
        self._render(self._results_from_hits(
            kept, query=f"{pool.query}  (within: {term})"))
        self.status_var.set(
            f"{len(kept)} of {pool.total} matched {term!r} within results.")

    # ── (9) Filter presets ──────────────────────────────────────────────

    def _rebuild_preset_menu(self) -> None:
        m = self._preset_menu
        m.delete(0, "end")
        m.add_command(label="Save current filters…",
                      command=self._save_filter_preset)
        store = _load_ui_store()
        names = sorted(store["presets"])
        if names:
            m.add_command(label="Delete a preset…",
                          command=self._delete_preset)
            m.add_separator()
            for n in names:
                m.add_command(label=n,
                              command=lambda nn=n: self._apply_filter_preset(nn))
        else:
            m.add_separator()
            m.add_command(label="(no presets yet)", state="disabled")

    def _save_filter_preset(self) -> None:
        name = simpledialog.askstring("Save preset", "Preset name:",
                                      parent=self.frame)
        if not name or not name.strip():
            return
        name = name.strip()
        store = _load_ui_store()
        store["presets"][name] = self._collect_filter_state()
        _save_ui_store(store)
        self.status_var.set(f"Saved filter preset {name!r}.")

    def _apply_filter_preset(self, name: str) -> None:
        fs = _load_ui_store()["presets"].get(name)
        if fs is None:
            return
        self._apply_filter_state(fs)
        self.status_var.set(f"Applied filter preset {name!r}.")

    def _delete_preset(self) -> None:
        store = _load_ui_store()
        name = _choose_from("Delete preset", "Preset to delete:",
                            sorted(store["presets"]), self.frame)
        if name and name in store["presets"]:
            del store["presets"][name]
            _save_ui_store(store)
            self.status_var.set(f"Deleted preset {name!r}.")

    # ── (10) Voice query ────────────────────────────────────────────────

    def _voice_query(self) -> None:
        try:
            import speech_recognition as sr  # optional dependency
        except Exception:  # noqa: BLE001
            messagebox.showinfo(
                "Voice query",
                "Voice input needs the optional 'SpeechRecognition' package "
                "and a working microphone.\n\n"
                "Install with:\n    pip install SpeechRecognition pyaudio\n\n"
                "Then click 🎤 again to dictate your query.")
            return
        recogniser = sr.Recognizer()
        try:
            with sr.Microphone() as source:
                self.status_var.set("Listening… speak your query.")
                self.frame.update()
                audio = recogniser.listen(source, timeout=5,
                                          phrase_time_limit=8)
            heard = recogniser.recognize_google(audio)
        except Exception as exc:  # noqa: BLE001
            messagebox.showwarning("Voice query",
                                   f"Could not capture audio: {exc}")
            self.status_var.set("Voice capture cancelled.")
            return
        self.query_e.delete(0, "end")
        self.query_e.insert(0, heard)
        self._update_lint()
        self.status_var.set(f"Heard: {heard!r} — press Enter to search.")

    def run(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        q = self.query_e.get().strip()
        scopes = self._selected_scopes()
        if not scopes:
            self.status_var.set("No scopes selected — pick at least one.")
            return
        try:
            limit = int(self.limit_e.get().strip()
                         or str(DEFAULT_LIMIT_PER_SCOPE))
        except ValueError:
            messagebox.showerror("Limit",
                                    "Limit must be a positive integer.")
            return
        filters: dict[str, object] = {}
        if self.year_e.get().strip():
            filters["year_group"] = self.year_e.get().strip()
        if self.tg_e.get().strip():
            filters["tutor_group"] = self.tg_e.get().strip()
        if self.role_e.get().strip():
            filters["role"] = self.role_e.get().strip()
        if self.owner_e.get().strip():
            filters["owned_by_staff"] = self.owner_e.get().strip()
        if self.sen_var.get():
            filters["sen_only"] = True
        if self.arch_var.get():
            filters["include_archived"] = True
        if self.redact_var.get():
            filters["redact"] = True
        if self.bg_e.get().strip():
            filters["break_glass"] = self.bg_e.get().strip()
        actor = self.actor_e.get().strip() or None
        options = QueryOptions(fold_diacritics=self.fold_var.get())
        # Regex mode (feature 4): the query box holds a regex, not DSL.
        # Gather candidates with an empty DSL query over the same scopes
        # + filters, then post-filter by the pattern.
        regex_on = bool(getattr(self, "regex_var", None)
                        and self.regex_var.get())
        if regex_on and not q:
            self.status_var.set("Enter a regex pattern (Regex mode is on).")
            return
        try:
            results = data.run_search(
                "" if regex_on else q, scopes=scopes, limit_per_scope=limit,
                filters=filters, actor=actor, options=options,
                interleave=self.interleave_var.get(),
                cluster_by_student=self.cluster_var.get())
        except ValidationError as e:
            messagebox.showerror("Search error", str(e))
            return
        if regex_on:
            filtered = self._filter_results_regex(results, q)
            if filtered is None:
                return
            results = filtered
        # Phonetic / fuzzy post-filter (feature 2).
        if (getattr(self, "phonetic_var", None) and self.phonetic_var.get()
                and q and not regex_on):
            results = self._filter_results_phonetic(results, q)
        # Diff-since-last-run bookkeeping (feature 4): which keys are new
        # versus the previous run of this same query string.
        cur_keys = {f"{h.scope}#{h.entity_id}" for h in results.all_hits()}
        prev = getattr(self, "_prev_keys_by_query", {}).get(results.query,
                                                            set())
        self._new_keys = cur_keys - prev if prev else set()
        if not hasattr(self, "_prev_keys_by_query"):
            self._prev_keys_by_query = {}
        self._prev_keys_by_query[results.query] = cur_keys
        self._render(results)

    def _render(self, results: SearchResults) -> None:
        self._last_results = results
        self._page = 0                       # new result set → first page
        self._rerender()
        self._render_facets(results)
        self._show_suggestion(
            results.suggestions[0]
            if results.total == 0 and results.suggestions else "")

    # ── Live search (item 42) ─────────────────────────────────────

    def _on_query_key(self, event) -> None:
        self._update_lint()
        if not getattr(self, "live_var", None) or not self.live_var.get():
            return
        if event.keysym in ("Return", "Up", "Down", "Left", "Right",
                            "Tab", "Escape"):
            return
        if self._live_after is not None:
            try:
                self.frame.after_cancel(self._live_after)
            except Exception:
                pass
        self._live_after = self.frame.after(400, self.run)

    # ── Suggested-filter facet chips (item 47) ────────────────────

    def _render_facets(self, results: SearchResults) -> None:
        for w in self.facet_frame.winfo_children():
            w.destroy()
        try:
            fcs = data.facets(results, top=4)
        except Exception:
            fcs = []
        if not fcs:
            return
        ttk.Label(self.facet_frame, text="Narrow:").pack(side="left")
        shown = 0
        for f in fcs:
            for val, cnt in f.values:
                if shown >= 12:
                    return
                ttk.Button(
                    self.facet_frame, text=f"{f.field}:{val} ({cnt})",
                    command=lambda fl=f.field, v=val: self._apply_facet(fl, v)
                ).pack(side="left", padx=2)
                shown += 1

    def _apply_facet(self, field: str, value: str) -> None:
        add = f'{field}:"{value}"' if " " in value else f"{field}:{value}"
        cur = self.query_e.get().strip()
        self.query_e.delete(0, "end")
        self.query_e.insert(0, (cur + " " + add).strip())
        self.run()

    # ── Export / message / contact sheet (items 36, 37, 39) ───────

    def _export_results_dialog(self) -> None:
        if self._last_results is None or self._last_results.total == 0:
            self.status_var.set("Run a search first.")
            return
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Excel", "*.xlsx"),
                       ("PDF", "*.pdf"), ("HTML", "*.html"),
                       ("JSON", "*.json"), ("Markdown", "*.md"),
                       ("TSV", "*.tsv")],
            initialfile="advanced_search_results.csv")
        if not path:
            return
        try:
            data.export_results_file(self._last_results, path)
            _append_action_log("export", path, self._last_results.total)
            self.status_var.set(f"Exported to {path}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def _mailmerge_dialog(self) -> None:
        if self._last_results is None:
            self.status_var.set("Run a search first.")
            return
        from tkinter import simpledialog
        subject = simpledialog.askstring("Message students", "Subject:")
        if not subject:
            return
        body = simpledialog.askstring("Message students", "Body:") or ""
        # Feature 15: offer to actually dispatch, not just draft.
        send = messagebox.askyesno(
            "Send now?",
            "Send these messages now?\n\n"
            "Yes = dispatch via the email service.\n"
            "No  = save as drafts only.")
        try:
            res = data.mailmerge_results(
                self._last_results, subject=subject, body=body, send=send)
        except Exception as e:
            messagebox.showerror("Message failed", str(e))
            return
        verb = "Sent" if send else "Drafted"
        _append_action_log("message", f"{verb}: {subject!r}",
                            res.get("recipients", 0))
        messagebox.showinfo(
            "Message",
            f"{verb} {res['created']} message(s) to "
            f"{res['recipients']} student(s) (thread {res['thread_id']}).")

    def _contact_sheet(self) -> None:
        if self._last_results is None or self._last_results.total == 0:
            self.status_var.set("Run a search first.")
            return
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".html", filetypes=[("HTML", "*.html")],
            initialfile="contact_sheet.html")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(data.contact_sheet(self._last_results))
            self.status_var.set(f"Contact sheet → {path}")
        except Exception as e:
            messagebox.showerror("Contact sheet failed", str(e))

    def _rerender(self) -> None:
        """(Re)draw the tree honouring flat/grouped (11), pagination (15),
        conditional colour (14) and column layout (12/17)."""
        for i in self.tree.get_children():
            self.tree.delete(i)
        self._hit_by_item: dict[str, Hit] = {}
        results = self._last_results
        if results is None:
            self.page_var.set("")
            return
        mode = self.group_by.get()
        if "Year" in mode or "Tutor" in mode:
            try:
                self._group_index = data.student_group_index()
            except Exception:
                self._group_index = {}
        colour = bool(self.colour_var.get())
        heatmap = bool(getattr(self, "heatmap_var", None)
                       and self.heatmap_var.get())
        diff_on = bool(getattr(self, "diff_var", None)
                       and self.diff_var.get())
        new_keys = getattr(self, "_new_keys", set()) if diff_on else set()
        self._ann_cache = _load_ann_store() if colour else {}
        # Heatmap (feature 13) needs the score range across the result set.
        self._heat_lo = self._heat_hi = 0.0
        if heatmap and results.total:
            scores = [h.score for h in results.all_hits()]
            self._heat_lo, self._heat_hi = min(scores), max(scores)

        # Flatten in scope order, then paginate the flat list (15) so the
        # page window is stable across flat/grouped modes.
        ordered = [(s, h) for s in results.scopes
                   for h in results.hits_by_scope.get(s, [])]
        total = len(ordered)
        page_size = self._page_size()
        if page_size:
            pages = max(1, (total + page_size - 1) // page_size)
            self._page = max(0, min(self._page, pages - 1))
            start = self._page * page_size
            page_slice = ordered[start:start + page_size]
            self.page_var.set(f"Page {self._page + 1}/{pages}")
        else:
            page_slice = ordered
            self.page_var.set(f"All {total}")

        def _child_tags(scope: str, h: Hit) -> tuple[str, ...]:
            tags: list[str] = []
            # Diff-since-last-run (feature 4) wins the row highlight.
            if diff_on and f"{scope}#{h.entity_id}" in new_keys:
                tags.append("row-new")
            elif heatmap:
                span = (self._heat_hi - self._heat_lo) or 1.0
                bucket = int((h.score - self._heat_lo) / span * 4)
                tags.append(f"heat{max(0, min(4, bucket))}")
            elif colour:
                tag = self._row_colour_tag(scope, h)
                if tag:
                    tags.append(tag)
            return tuple(tags)

        if self.flat_var.get():
            self.tree.configure(show="headings")
            for scope, h in page_slice:
                item_id = self.tree.insert(
                    "", "end",
                    values=(h.entity_id, h.label, h.sublabel, h.matched_field),
                    tags=_child_tags(scope, h))
                self._hit_by_item[item_id] = h
        else:
            self.tree.configure(show="tree headings")
            groups: dict[str, list[tuple[str, Hit]]] = {}
            order: list[str] = []
            for scope, h in page_slice:
                key = self._group_key(scope, h)
                if key not in groups:
                    groups[key] = []
                    order.append(key)
                groups[key].append((scope, h))
            for key in order:
                pairs = groups[key]
                node = self.tree.insert(
                    "", "end", text=f"{key}  ({len(pairs)})",
                    values=("", "", "", ""), open=True, tags=("scope",))
                for scope, h in pairs:
                    item_id = self.tree.insert(
                        node, "end", text="",
                        values=(h.entity_id, h.label, h.sublabel,
                                h.matched_field),
                        tags=_child_tags(scope, h))
                    self._hit_by_item[item_id] = h
        self._apply_columns()
        per = {s: len(results.hits_by_scope.get(s, [])) for s in results.scopes}
        chips = [f"{SCOPE_LABELS.get(s, s)} {n}" for s, n in per.items() if n]
        self.stats_var.set("   ·   ".join(chips[:8])
                           + (f"      Σ {results.total}" if results.total
                              else ""))
        layout = ("flat" if self.flat_var.get()
                  else f"grouped by {mode.lower()}")
        self.status_var.set(
            f"{results.total} hit(s) for "
            f"{(results.query or '(empty)')!r}  ·  {layout}")

    def _page_size(self) -> int | None:
        v = self.page_size_var.get()
        if v == "All":
            return None
        try:
            return max(1, int(v))
        except ValueError:
            return None

    def _row_colour_tag(self, scope: str, h: Hit) -> str:
        """Pick a row-colour tag from the hit's status/risk level, or an
        'at-risk'/'flag'/'safeguarding' annotation tag."""
        ann = self._ann_cache.get(_ann_key(scope, h.entity_id), {})
        flags = {t.lower() for t in ann.get("tags", [])}
        if flags & {"at-risk", "flag", "flagged", "safeguarding"}:
            return "row-flagged"
        doc = (h.extra or {}).get("_doc") or {}
        status = str(doc.get("status") or "").strip().lower()
        level = str(doc.get("level") or "").strip().lower()
        if status == "active":
            return "row-active"
        if status == "inactive":
            return "row-inactive"
        if status == "suspended":
            return "row-suspended"
        if status in ("left", "withdrawn"):
            return "row-left"
        if level in ("high", "critical", "red"):
            return "row-flagged"
        if level in ("medium", "amber"):
            return "row-suspended"
        if level in ("low", "green"):
            return "row-active"
        return ""

    # ── Pagination / density / expand controls (15, 13, 16) ───────────

    def _on_page_size(self) -> None:
        self._page = 0
        self._rerender()

    def _prev_page(self) -> None:
        if self._page > 0:
            self._page -= 1
            self._rerender()

    def _next_page(self) -> None:
        self._page += 1        # _rerender clamps to the last page
        self._rerender()

    def _apply_density(self) -> None:
        h = _DENSITY_ROWHEIGHT.get(self.density_var.get(), 22)
        self._tree_style.configure("AdvSearch.Treeview", rowheight=h)

    def _expand_all(self) -> None:
        for n in self.tree.get_children():
            self.tree.item(n, open=True)

    def _collapse_all(self) -> None:
        for n in self.tree.get_children():
            self.tree.item(n, open=False)

    def _hit_student_id(self, scope: str, h: Hit) -> str:
        if scope == "students":
            return h.entity_id
        if scope in data._STUDENT_KEYED_SCOPES:
            doc = (h.extra or {}).get("_doc") or {}
            return str(doc.get("name") or "").strip()
        return ""

    def _group_key(self, scope: str, h: Hit) -> str:
        mode = self.group_by.get()
        # Composite group-by (feature 8): primary + risk band.
        if "+" in mode:
            primary, _plus, secondary = mode.partition("+")
            outer = self._group_key_single(primary, scope, h)
            inner = self._group_key_single(secondary, scope, h)
            return f"{outer}  ·  {inner}"
        return self._group_key_single(mode, scope, h)

    def _group_key_single(self, mode: str, scope: str, h: Hit) -> str:
        if mode == "Scope":
            return SCOPE_LABELS.get(scope, scope)
        if mode == "Risk":
            doc = (h.extra or {}).get("_doc") or {}
            return f"Risk: {doc.get('level') or '—'}"
        sid = self._hit_student_id(scope, h)
        if not sid:
            return "(non-student)"
        yr, tg = self._group_index.get(sid, (None, None))
        if mode == "Year":
            return f"Year {yr}" if yr is not None else "Year —"
        return f"Tutor {tg}" if tg else "Tutor —"

    # ── Column chooser + sortable columns (item 18) ───────────────

    def _apply_columns(self) -> None:
        # Pinned columns (17) are forced to the front and always shown;
        # remaining visible columns follow the chosen order (12).
        pinned = [c for c in self._col_order if c in self._pinned_cols]
        rest = [c for c in self._col_order
                if c not in self._pinned_cols and self._col_vars[c].get()]
        self._display_cols = (pinned + rest) or list(self._cols)
        self.tree.configure(displaycolumns=self._display_cols)

    def _sort_by(self, col: str) -> None:
        asc = True
        if self._sort_state and self._sort_state[0] == col:
            asc = not self._sort_state[1]
        self._sort_state = (col, asc)
        for node in self.tree.get_children():
            kids = list(self.tree.get_children(node))
            kids.sort(key=lambda k: (self.tree.set(k, col) or "").lower(),
                      reverse=not asc)
            for pos, k in enumerate(kids):
                self.tree.move(k, node, pos)
        for c in self._cols:
            arrow = (" ▲" if asc else " ▼") if c == col else ""
            self.tree.heading(c, text=self._col_titles[c] + arrow)

    # ── Preview pane (item 19) ────────────────────────────────────

    def _on_select(self, _event=None) -> None:
        hits = self._selected_hits()
        if not hits:
            return
        h = hits[0]
        safe = bool(getattr(self, "safe_var", None) and self.safe_var.get())
        doc = (h.extra or {}).get("_doc") or {}
        lines = [f"[{h.scope}]  {h.entity_id}", h.label, ""]
        if h.sublabel:
            lines += [self._mask(h.sublabel) if safe else h.sublabel, ""]
        for k, v in doc.items():
            if k.startswith("_") or v in (None, ""):
                continue
            # Numeric series → inline trend sparkline (feature 10).
            if isinstance(v, (list, tuple)) and any(
                    isinstance(x, (int, float)) for x in v):
                spark = _sparkline(list(v))
                if spark:
                    lines.append(f"{k:>14}: {spark}  "
                                 f"({v[0]}→{v[-1]})")
                    continue
            if safe and self._is_sensitive_field(k):
                lines.append(f"{k:>14}: {self._mask(str(v))}")
            else:
                lines.append(f"{k:>14}: {v}")
        if h.matched_fields:
            lines += ["", "matched: " + ", ".join(h.matched_fields)]
        lines += self._annotation_lines(h.scope, h.entity_id)
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", "\n".join(str(x) for x in lines))
        self.preview.configure(state="disabled")

    def _annotation_lines(self, scope: str, entity_id: str) -> list[str]:
        """Render tag/owner/note/merge annotations (21, 22, 24, 25) for
        the preview pane. Empty list when the record has none."""
        ann = _get_annotation(scope, entity_id)
        if not ann:
            return []
        out = ["", "── annotations ──"]
        if ann.get("tags"):
            out.append("tags: " + ", ".join(ann["tags"]))
        for flag in ann.get("flags", []):                 # feature 14
            out.append(f"⚑ flag [{flag.get('code', '?')}]: "
                       f"{flag.get('reason', '')}")
        if ann.get("owner"):
            out.append(f"owner: {ann['owner']}")
        wf = ann.get("workflow")                          # feature 18
        if wf:
            out.append(f"→ workflow: {wf.get('owner', '?')} "
                       f"(due {wf.get('due', '—')}) [{wf.get('state', 'open')}]")
        if ann.get("merged_into"):
            out.append(f"⚠ merged into: {ann['merged_into']}")
        for note in ann.get("notes", []):
            out.append(f"note ({note.get('ts', '')}): {note.get('text', '')}")
        return out

    # ══ Column reorder / pin (features 12, 17) ════════════════════════

    def _show_column_menu(self, event) -> None:
        region = self.tree.identify_region(event.x, event.y)
        if region not in ("heading", "separator"):
            return
        colid = self.tree.identify_column(event.x)      # '#0' or '#n'
        if not colid or colid == "#0":
            return
        try:
            disp_idx = int(colid[1:]) - 1
        except ValueError:
            return
        display = self._display_cols
        if not (0 <= disp_idx < len(display)):
            return
        col = display[disp_idx]
        menu = tk.Menu(self.tree, tearoff=False)
        menu.add_command(label=f"Column: {self._col_titles.get(col, col)}",
                         state="disabled")
        menu.add_separator()
        menu.add_command(label="Move ◀ left",
                         command=lambda c=col: self._move_column(c, -1))
        menu.add_command(label="Move ▶ right",
                         command=lambda c=col: self._move_column(c, +1))
        if col in self._pinned_cols:
            menu.add_command(label="Unpin",
                             command=lambda c=col: self._toggle_pin(c))
        else:
            menu.add_command(label="Pin to front",
                             command=lambda c=col: self._toggle_pin(c))
        menu.add_command(label="Hide",
                         command=lambda c=col: self._hide_column(c))
        menu.tk_popup(event.x_root, event.y_root)

    def _move_column(self, col: str, delta: int) -> None:
        order = self._col_order
        if col not in order:
            return
        i = order.index(col)
        j = i + delta
        if 0 <= j < len(order):
            order[i], order[j] = order[j], order[i]
            self._apply_columns()

    def _toggle_pin(self, col: str) -> None:
        if col in self._pinned_cols:
            self._pinned_cols.discard(col)
        else:
            self._pinned_cols.add(col)
            self._col_vars[col].set(True)       # pinned ⇒ visible
        self._apply_columns()

    def _hide_column(self, col: str) -> None:
        if col in self._pinned_cols:
            self.status_var.set("Unpin the column before hiding it.")
            return
        visible = [c for c in self._cols if self._col_vars[c].get()]
        if len(visible) <= 1:
            self.status_var.set("At least one column must stay visible.")
            return
        self._col_vars[col].set(False)
        self._apply_columns()

    # ══ Inline edit (feature 18) ══════════════════════════════════════

    @staticmethod
    def _students_api():
        from education_system.systems.sixth_form.domain.learners.\
            students.students import (get_student, update_student, STATUSES)
        return get_student, update_student, STATUSES

    def _student_payload(self, stu, **overrides) -> dict:
        payload = {
            "first_name": stu.first_name, "middle_name": stu.middle_name,
            "last_name": stu.last_name, "title": stu.title,
            "gender": stu.gender, "date_of_birth": stu.date_of_birth,
            "phone": stu.phone,
            "emergency_contact_name": stu.emergency_contact_name,
            "emergency_contact_phone": stu.emergency_contact_phone,
            "emergency_contact_relation": stu.emergency_contact_relation,
            "subject_1": stu.subject_1, "subject_2": stu.subject_2,
            "subject_3": stu.subject_3, "status": stu.status,
        }
        payload.update(overrides)
        return payload

    def _inline_edit(self, _event=None) -> None:
        students = [h for h in self._selected_hits() if h.scope == "students"]
        if not students:
            self.status_var.set("Inline edit (F2): select a student row.")
            return
        get_student, update_student, statuses = self._students_api()
        h = students[0]
        try:
            stu = get_student(h.entity_id)
        except Exception:  # noqa: BLE001
            stu = None
        if stu is None:
            self.status_var.set(f"No student record for {h.entity_id}.")
            return
        top = tk.Toplevel(self.frame.winfo_toplevel())
        top.title(f"Edit {stu.student_id}")
        try:
            top.wm_geometry(
                f"+{self.tree.winfo_pointerx()}+{self.tree.winfo_pointery()}")
        except tk.TclError:
            pass
        entries: dict[str, ttk.Entry] = {}
        row = 0
        for attr, label in (("first_name", "First name"),
                            ("middle_name", "Middle"),
                            ("last_name", "Last name"), ("phone", "Phone")):
            ttk.Label(top, text=label + ":").grid(row=row, column=0,
                                                  sticky="e", padx=4, pady=2)
            e = ttk.Entry(top, width=26)
            e.insert(0, getattr(stu, attr) or "")
            e.grid(row=row, column=1, padx=4, pady=2)
            entries[attr] = e
            row += 1
        ttk.Label(top, text="Status:").grid(row=row, column=0, sticky="e",
                                            padx=4, pady=2)
        status_var = tk.StringVar(value=stu.status)
        ttk.Combobox(top, textvariable=status_var, values=list(statuses),
                     state="readonly", width=24).grid(row=row, column=1,
                                                       padx=4, pady=2)
        row += 1

        def _save() -> None:
            payload = self._student_payload(
                stu,
                first_name=entries["first_name"].get(),
                middle_name=entries["middle_name"].get() or None,
                last_name=entries["last_name"].get(),
                phone=entries["phone"].get() or None,
                status=status_var.get())
            try:
                update_student(stu.student_id, payload)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Update failed", str(exc))
                return
            top.destroy()
            self.run()
            self.status_var.set(f"Updated {stu.student_id}.")

        btns = ttk.Frame(top)
        btns.grid(row=row, column=0, columnspan=2, pady=6)
        ttk.Button(btns, text="Save", command=_save).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel",
                   command=top.destroy).pack(side="left", padx=4)
        top.grab_set()

    # ══ Quick-look hover popover (feature 19) ═════════════════════════

    def _on_tree_motion(self, event) -> None:
        row = self.tree.identify_row(event.y)
        if row == self._ql_row:
            return
        self._ql_row = row
        self._hide_quicklook()
        if row and row in self._hit_by_item:
            self._ql_after = self.tree.after(
                500, lambda: self._show_quicklook(row))

    def _show_quicklook(self, row: str) -> None:
        h = self._hit_by_item.get(row)
        if h is None:
            return
        try:
            x = self.tree.winfo_pointerx() + 16
            y = self.tree.winfo_pointery() + 12
        except tk.TclError:
            return
        self._hide_quicklook()
        win = tk.Toplevel(self.tree)
        win.wm_overrideredirect(True)
        win.wm_geometry(f"+{x}+{y}")
        lines = [h.label]
        if h.sublabel:
            lines.append(h.sublabel)
        ann = _get_annotation(h.scope, h.entity_id)
        if ann.get("tags"):
            lines.append("tags: " + ", ".join(ann["tags"]))
        if ann.get("owner"):
            lines.append("owner: " + str(ann["owner"]))
        tk.Label(win, text="\n".join(lines), justify="left",
                 background="#ffffe0", relief="solid", borderwidth=1,
                 font=("", 9), padx=6, pady=4, wraplength=320).pack()
        self._ql_win = win

    def _hide_quicklook(self) -> None:
        if self._ql_after is not None:
            try:
                self.tree.after_cancel(self._ql_after)
            except Exception:  # noqa: BLE001
                pass
            self._ql_after = None
        if self._ql_win is not None:
            try:
                self._ql_win.destroy()
            except Exception:  # noqa: BLE001
                pass
            self._ql_win = None

    # ══ Jump to scope (feature 20) ════════════════════════════════════

    def _ordered_hit_items(self) -> list[str]:
        out: list[str] = []
        for node in self.tree.get_children():
            if node in self._hit_by_item:
                out.append(node)                 # flat-mode row
            for child in self.tree.get_children(node):
                out.append(child)                # grouped child row
        return out

    def _jump_next_scope(self, _event=None):
        self._jump_scope(+1)
        return "break"

    def _jump_prev_scope(self, _event=None):
        self._jump_scope(-1)
        return "break"

    def _jump_scope(self, direction: int) -> None:
        first_of: dict[str, str] = {}
        scope_order: list[str] = []
        for iid in self._ordered_hit_items():
            h = self._hit_by_item.get(iid)
            if h is None or h.scope in first_of:
                continue
            first_of[h.scope] = iid
            scope_order.append(h.scope)
        if not scope_order:
            return
        sel = self.tree.selection()
        cur = (self._hit_by_item[sel[0]].scope
               if sel and sel[0] in self._hit_by_item else None)
        if cur in scope_order:
            idx = (scope_order.index(cur) + direction) % len(scope_order)
        else:
            idx = 0 if direction > 0 else len(scope_order) - 1
        target = first_of[scope_order[idx]]
        self.tree.see(target)
        self.tree.selection_set(target)
        self.tree.focus(target)
        self.status_var.set(
            f"Jumped to scope: "
            f"{SCOPE_LABELS.get(scope_order[idx], scope_order[idx])}")

    # ══ Bulk actions (features 21–25) ═════════════════════════════════

    def _bulk_tag(self) -> None:
        hits = self._selected_hits()
        if not hits:
            self.status_var.set("Select rows to tag.")
            return
        raw = simpledialog.askstring(
            "Bulk tag",
            "Tags to add (comma-separated; prefix with '-' to remove):",
            parent=self.frame)
        if not raw:
            return
        parts = [t.strip() for t in raw.split(",") if t.strip()]
        add = [t for t in parts if not t.startswith("-")]
        remove = {t[1:] for t in parts if t.startswith("-")}
        keys = {(h.scope, h.entity_id) for h in hits}
        self._snapshot_ann("bulk tag")
        store = _load_ann_store()
        for h in hits:
            ann = store.setdefault(_ann_key(h.scope, h.entity_id), {})
            tags = ann.get("tags", [])
            for t in add:
                if t not in tags:
                    tags.append(t)
            ann["tags"] = [t for t in tags if t not in remove]
        _save_ann_store(store)
        self._rerender()             # repaint colours (14) for new tags
        self._reselect(keys)         # rerender regenerates item ids
        self._on_select()
        self.status_var.set(f"Updated tags on {len(hits)} record(s).")

    def _reselect(self, keys: set) -> None:
        """Re-select the rows for the given (scope, entity_id) keys after a
        rerender has regenerated the tree item ids."""
        want = [iid for iid, h in self._hit_by_item.items()
                if (h.scope, h.entity_id) in keys]
        if want:
            self.tree.selection_set(want)
            self.tree.see(want[0])

    def _bulk_assign_staff(self) -> None:
        hits = self._selected_hits()
        if not hits:
            self.status_var.set("Select rows to assign an owner.")
            return
        owner = simpledialog.askstring(
            "Assign owner",
            "Owning staff (name or id; leave blank to clear):",
            parent=self.frame)
        if owner is None:
            return
        owner = owner.strip()
        self._snapshot_ann("bulk assign owner")
        store = _load_ann_store()
        for h in hits:
            ann = store.setdefault(_ann_key(h.scope, h.entity_id), {})
            if owner:
                ann["owner"] = owner
            else:
                ann.pop("owner", None)
        _save_ann_store(store)
        self._on_select()
        verb = "Assigned" if owner else "Cleared"
        self.status_var.set(f"{verb} owner on {len(hits)} record(s).")

    def _bulk_add_note(self) -> None:
        hits = self._selected_hits()
        if not hits:
            self.status_var.set("Select rows to note.")
            return
        text = simpledialog.askstring("Add note", "Note text:",
                                      parent=self.frame)
        if not text or not text.strip():
            return
        ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        self._snapshot_ann("bulk add note")
        store = _load_ann_store()
        for h in hits:
            ann = store.setdefault(_ann_key(h.scope, h.entity_id), {})
            ann.setdefault("notes", []).append(
                {"ts": ts, "text": text.strip()})
        _save_ann_store(store)
        self._on_select()
        self.status_var.set(f"Added note to {len(hits)} record(s).")

    def _bulk_status_change(self) -> None:
        hits = [h for h in self._selected_hits() if h.scope == "students"]
        if not hits:
            self.status_var.set("Select student rows to change status.")
            return
        get_student, update_student, statuses = self._students_api()
        new = _choose_from("Set status",
                           f"New status for {len(hits)} student(s):",
                           list(statuses), self.frame)
        if not new:
            return
        if not messagebox.askyesno(
                "Confirm bulk status change",
                f"Set status to {new!r} for {len(hits)} student(s)?"):
            return
        ok = errs = 0
        for h in hits:
            try:
                stu = get_student(h.entity_id)
                if stu is None:
                    errs += 1
                    continue
                update_student(h.entity_id,
                               self._student_payload(stu, status=new))
                ok += 1
            except Exception:  # noqa: BLE001
                errs += 1
        self.run()
        self.status_var.set(
            f"Status → {new!r}: {ok} updated"
            + (f", {errs} failed" if errs else "") + ".")

    def _merge_duplicates(self) -> None:
        hits = [h for h in self._selected_hits() if h.scope == "students"]
        if len(hits) != 2:
            self.status_var.set(
                "Select exactly 2 student rows to merge.")
            return
        get_student, _update, _statuses = self._students_api()
        a = get_student(hits[0].entity_id)
        b = get_student(hits[1].entity_id)
        if a is None or b is None:
            self.status_var.set("Could not load both student records.")
            return
        self._merge_dialog(a, b)

    _MERGE_FIELDS: tuple[tuple[str, str], ...] = (
        ("first_name", "First name"), ("middle_name", "Middle"),
        ("last_name", "Last name"), ("phone", "Phone"),
        ("emergency_contact_name", "Emerg. name"),
        ("emergency_contact_phone", "Emerg. phone"),
        ("emergency_contact_relation", "Emerg. rel"),
    )

    def _merge_dialog(self, a, b) -> None:
        _get, update_student, _statuses = self._students_api()
        top = tk.Toplevel(self.frame.winfo_toplevel())
        top.title("Merge duplicate students")
        top.transient(self.frame.winfo_toplevel())
        ttk.Label(top, text="Choose the record to KEEP (the primary). "
                            "Empty fields on it are filled from the other; "
                            "the other is marked as a merged duplicate.",
                  wraplength=460, justify="left").grid(
            row=0, column=0, columnspan=3, padx=8, pady=(8, 6), sticky="w")
        primary_var = tk.StringVar(value=a.student_id)
        ttk.Radiobutton(top, text=f"Keep {a.student_id} — {a.full_name}",
                        variable=primary_var, value=a.student_id).grid(
            row=1, column=1, sticky="w", padx=4)
        ttk.Radiobutton(top, text=f"Keep {b.student_id} — {b.full_name}",
                        variable=primary_var, value=b.student_id).grid(
            row=1, column=2, sticky="w", padx=4)
        ttk.Label(top, text="Field", font=("", 9, "bold")).grid(
            row=2, column=0, sticky="w", padx=6)
        ttk.Label(top, text=a.student_id, font=("", 9, "bold")).grid(
            row=2, column=1, sticky="w", padx=4)
        ttk.Label(top, text=b.student_id, font=("", 9, "bold")).grid(
            row=2, column=2, sticky="w", padx=4)
        r = 3
        for attr, label in self._MERGE_FIELDS:
            ttk.Label(top, text=label).grid(row=r, column=0, sticky="w",
                                            padx=6)
            ttk.Label(top, text=str(getattr(a, attr) or "—")).grid(
                row=r, column=1, sticky="w", padx=4)
            ttk.Label(top, text=str(getattr(b, attr) or "—")).grid(
                row=r, column=2, sticky="w", padx=4)
            r += 1

        def _do_merge() -> None:
            primary, secondary = ((a, b) if primary_var.get() == a.student_id
                                  else (b, a))
            payload = self._student_payload(primary)
            filled: list[str] = []
            for attr, label in self._MERGE_FIELDS:
                if not (getattr(primary, attr) or "") and \
                        (getattr(secondary, attr) or ""):
                    payload[attr] = getattr(secondary, attr)
                    filled.append(label)
            try:
                update_student(primary.student_id, payload)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Merge failed", str(exc))
                return
            store = _load_ann_store()
            ann = store.setdefault(
                _ann_key("students", secondary.student_id), {})
            ann["merged_into"] = _ann_key("students", primary.student_id)
            tags = ann.setdefault("tags", [])
            if "merged-duplicate" not in tags:
                tags.append("merged-duplicate")
            _save_ann_store(store)
            top.destroy()
            self.run()
            self.status_var.set(
                f"Merged {secondary.student_id} → {primary.student_id}; "
                f"filled: {', '.join(filled) or 'nothing'}.")

        btns = ttk.Frame(top)
        btns.grid(row=r, column=0, columnspan=3, pady=10)
        ttk.Button(btns, text="Merge", command=_do_merge).pack(
            side="left", padx=4)
        ttk.Button(btns, text="Cancel", command=top.destroy).pack(
            side="left", padx=4)
        top.grab_set()

    # ── Keyboard type-ahead jump (item 24) ────────────────────────

    def _type_ahead(self, event) -> None:
        ch = event.char
        if not ch or len(ch) != 1 or not ch.isprintable():
            return
        self._typeahead_buf = (self._typeahead_buf + ch).lower()
        after = getattr(self, "_ta_after", None)
        if after is not None:
            try:
                self.frame.after_cancel(after)
            except Exception:
                pass
        self._ta_after = self.frame.after(800, self._reset_typeahead)
        for node in self.tree.get_children():
            for k in self.tree.get_children(node):
                lbl = (self.tree.set(k, "label") or "").lower()
                if lbl.startswith(self._typeahead_buf):
                    self.tree.see(k)
                    self.tree.selection_set(k)
                    self.tree.focus(k)
                    return

    def _reset_typeahead(self) -> None:
        self._typeahead_buf = ""

    def _show_suggestion(self, suggestion: str) -> None:
        for w in self.sugg_frame.winfo_children():
            w.destroy()
        if not suggestion:
            return
        ttk.Label(self.sugg_frame,
                   text="Did you mean:").pack(side="left")

        def _apply() -> None:
            self.query_e.delete(0, "end")
            self.query_e.insert(0, suggestion)
            self.run()

        ttk.Button(self.sugg_frame, text=suggestion,
                    command=_apply).pack(side="left", padx=(4, 0))

    def _show_syntax(self) -> None:
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.title("Advanced Search — query syntax")
        win.geometry("760x520")
        txt = tk.Text(win, wrap="none", font=("TkFixedFont", 10))
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        txt.insert("1.0", QUERY_SYNTAX_HELP)
        txt.configure(state="disabled")
        ttk.Button(win, text="Close",
                    command=win.destroy).pack(pady=(0, 8))

    # ── Bulk-action handlers (item 45) ────────────────────────────

    def _selected_hits(self) -> list[Hit]:
        return [self._hit_by_item[i]
                for i in self.tree.selection()
                if i in getattr(self, "_hit_by_item", {})]

    def _open_selected(self) -> None:
        hits = self._selected_hits()
        if not hits:
            self.status_var.set("Nothing selected.")
            return
        opened = 0
        for h in hits:
            self._push_recent(h)
            if data.open_hit(h) is not None:
                opened += 1
        self.status_var.set(
            f"Opened {opened}/{len(hits)} — "
            f"{'(no editor registered)' if not opened else ''}")

    # ── Recent-result breadcrumb (item 25) ────────────────────────

    def _push_recent(self, h: Hit) -> None:
        key = (h.scope, h.entity_id)
        self._recent = [x for x in self._recent
                        if (x.scope, x.entity_id) != key]
        self._recent.insert(0, h)
        self._recent = self._recent[:10]
        self.recent_combo.configure(
            values=[f"[{x.scope}] {x.label[:34]}" for x in self._recent])

    def _reopen_recent(self, _event=None) -> None:
        i = self.recent_combo.current()
        if 0 <= i < len(self._recent):
            data.open_hit(self._recent[i])

    # ── Copy emails + shortlist + cohort (items 20, 23) ───────────

    def _copy_emails(self) -> None:
        emails: list[str] = []
        for h in self._selected_hits():
            doc = (h.extra or {}).get("_doc") or {}
            e = str(doc.get("email") or "").strip()
            if e and e not in emails:
                emails.append(e)
        if not emails:
            self.status_var.set("No emails in selection.")
            return
        self.frame.clipboard_clear()
        self.frame.clipboard_append("; ".join(emails))
        self.status_var.set(f"Copied {len(emails)} email(s).")

    def _add_to_shortlist(self) -> None:
        existing = {(h.scope, h.entity_id) for h in self._shortlist}
        added = 0
        for h in self._selected_hits():
            if (h.scope, h.entity_id) not in existing:
                self._shortlist.append(h)
                existing.add((h.scope, h.entity_id))
                added += 1
        self._refresh_shortlist()
        self.status_var.set(
            f"Added {added} to shortlist ({len(self._shortlist)} total).")

    def _refresh_shortlist(self) -> None:
        self.shortlist_box.delete(0, "end")
        for h in self._shortlist:
            self.shortlist_box.insert("end", f"[{h.scope}] {h.label[:40]}")

    def _open_shortlisted(self) -> None:
        sel = self.shortlist_box.curselection()
        targets = ([self._shortlist[i] for i in sel] if sel
                   else list(self._shortlist))
        for h in targets:
            self._push_recent(h)
            data.open_hit(h)

    def _remove_shortlisted(self) -> None:
        for i in sorted(self.shortlist_box.curselection(), reverse=True):
            del self._shortlist[i]
        self._refresh_shortlist()

    def _clear_shortlist(self) -> None:
        self._shortlist = []
        self._refresh_shortlist()

    def _shortlist_to_cohort(self) -> None:
        if not self._shortlist:
            messagebox.showinfo("Cohort", "Shortlist is empty.")
            return
        self._cohort_from_hits(self._shortlist, "shortlist")

    def _save_cohort(self) -> None:
        if self._last_results is None or self._last_results.total == 0:
            messagebox.showinfo("Cohort", "Run a search with results first.")
            return
        from tkinter import simpledialog
        name = simpledialog.askstring("Save cohort", "Cohort name:")
        if not name:
            return
        try:
            c = data.create_cohort_from_results(name.strip(),
                                                 self._last_results)
        except Exception as e:
            messagebox.showerror("Cohort failed", str(e))
            return
        messagebox.showinfo(
            "Cohort",
            f"Cohort '{c.name}' saved with {c.member_count} student(s).")

    def _cohort_from_hits(self, hits: list[Hit], default_name: str) -> None:
        from tkinter import simpledialog
        name = simpledialog.askstring("Save cohort", "Cohort name:",
                                       initialvalue=default_name)
        if not name:
            return
        ids: list[str] = []
        for h in hits:
            sid = self._hit_student_id(h.scope, h)
            if sid and sid not in ids:
                ids.append(sid)
        if not ids:
            messagebox.showinfo("Cohort", "No students in selection.")
            return
        try:
            c = data.create_cohort(name.strip(), ids)
        except Exception as e:
            messagebox.showerror("Cohort failed", str(e))
            return
        messagebox.showinfo(
            "Cohort",
            f"Cohort '{c.name}' saved with {c.member_count} student(s).")

    def _copy_ids(self) -> None:
        hits = self._selected_hits()
        if not hits:
            return
        text = "\n".join(h.entity_id for h in hits)
        self.frame.clipboard_clear()
        self.frame.clipboard_append(text)
        self.status_var.set(f"Copied {len(hits)} id(s).")

    def _export_csv(self) -> None:
        if self._last_results is None:
            self.status_var.set("Run a search first.")
            return
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
            initialfile="advanced_search_results.csv")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(data.export_results_csv(self._last_results))
            self.status_var.set(f"Exported to {path}")
        except OSError as e:
            messagebox.showerror("Export failed", str(e))

    def _pin_selected(self) -> None:
        hits = self._selected_hits()
        if not hits:
            return
        actor = "default"   # caller can set window.actor for per-user pins
        n = 0
        for h in hits:
            try:
                data.pin_result(actor, h.scope, h.entity_id,
                                 label=h.label)
                n += 1
            except ValidationError:
                pass
        self.status_var.set(f"Pinned {n} hit(s) for actor={actor!r}")

    # ── Keyboard helpers (item 44) ────────────────────────────────

    def _focus_query(self, _event=None) -> str:
        try:
            self.query_e.focus_set()
            self.query_e.select_range(0, "end")
        except Exception:
            pass
        return "break"

    def _focus_first_hit(self) -> None:
        for parent in self.tree.get_children():
            kids = self.tree.get_children(parent)
            if kids:
                self.tree.selection_set(kids[0])
                self.tree.focus(kids[0])
                return

    # ══════════════════════════════════════════════════════════════════
    # New feature batch (features 1–25 of this request)
    # ══════════════════════════════════════════════════════════════════

    # ── Safe-mode masking helpers (feature 24) ────────────────────────

    _SENSITIVE_HINTS: tuple[str, ...] = (
        "dob", "birth", "email", "phone", "mobile", "address",
        "postcode", "nhs", "medical", "ni_number", "guardian",
    )

    def _is_sensitive_field(self, key: str) -> bool:
        k = key.lower()
        return any(h in k for h in self._SENSITIVE_HINTS)

    @staticmethod
    def _mask(text: str) -> str:
        """Redact all but the first character of each word so a value is
        recognisable-as-present without disclosing it."""
        return re.sub(r"(?<=\w)\w", "•", text or "")

    def _toggle_safe(self) -> None:
        state = "ON" if self.safe_var.get() else "OFF"
        self.status_var.set(f"Safe mode {state} — sensitive preview fields "
                            f"are {'masked' if self.safe_var.get() else 'shown'}.")
        self._on_select()

    # ── Feature 1: boolean query builder ──────────────────────────────

    def _boolean_builder(self) -> None:
        top = tk.Toplevel(self.frame.winfo_toplevel())
        top.title("Boolean query builder")
        top.transient(self.frame.winfo_toplevel())
        ttk.Label(top, text="Build a query from field/value clauses:").pack(
            padx=10, pady=(10, 4), anchor="w")
        rows_frame = ttk.Frame(top)
        rows_frame.pack(padx=10, pady=4, fill="x")
        fields = ["name", "status", "subject", "tutor_group", "year",
                  "email", "note", "(keyword)"]
        rows: list[tuple] = []

        def _add_row() -> None:
            r = ttk.Frame(rows_frame)
            r.pack(fill="x", pady=1)
            join = tk.StringVar(value="AND" if rows else "")
            if rows:
                ttk.Combobox(r, textvariable=join, width=5, state="readonly",
                             values=["AND", "OR"]).pack(side="left")
            else:
                ttk.Label(r, width=5).pack(side="left")
            neg = tk.BooleanVar(value=False)
            ttk.Checkbutton(r, text="NOT", variable=neg).pack(side="left")
            fld = tk.StringVar(value="name")
            ttk.Combobox(r, textvariable=fld, width=12, state="readonly",
                         values=fields).pack(side="left", padx=2)
            val = ttk.Entry(r, width=22)
            val.pack(side="left", padx=2)
            rows.append((join, neg, fld, val))

        _add_row()
        _add_row()
        ttk.Button(top, text="+ clause", command=_add_row).pack(
            padx=10, anchor="w")

        def _compile() -> None:
            parts: list[str] = []
            for i, (join, neg, fld, val) in enumerate(rows):
                v = val.get().strip()
                if not v:
                    continue
                field = fld.get()
                term = (v if " " not in v else f'"{v}"')
                clause = (term if field == "(keyword)"
                          else f"{field}:{term}")
                if neg.get():
                    clause = f"-{clause}"
                if parts and join.get() == "OR":
                    clause = f"OR {clause}"
                parts.append(clause)
            query = " ".join(parts)
            self.query_e.delete(0, "end")
            self.query_e.insert(0, query)
            top.destroy()
            self._update_lint()
            if query:
                self.run()

        btns = ttk.Frame(top)
        btns.pack(pady=8)
        ttk.Button(btns, text="Apply & search",
                   command=_compile).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel",
                   command=top.destroy).pack(side="left", padx=4)
        top.grab_set()

    # ── Feature 2: phonetic / fuzzy filter ────────────────────────────

    def _filter_results_phonetic(self, results: SearchResults,
                                 q: str) -> SearchResults:
        keep = [h for h in results.all_hits()
                if _phonetic_match(q, f"{h.label} {h.sublabel}")]
        out = self._results_from_hits(keep, results.query)
        out.suggestions = results.suggestions
        self.status_var.set(
            f"Phonetic filter: {len(keep)}/{results.total} kept for {q!r}.")
        return out

    def _toggle_phonetic(self) -> None:
        if self.phonetic_var.get() and self.query_e.get().strip():
            self.run()

    # ── Feature 4: diff-since-last-run toggle ─────────────────────────

    def _toggle_diff(self) -> None:
        on = self.diff_var.get()
        self.status_var.set(
            "Diff highlight ON — new rows vs the previous run of this query "
            "are highlighted." if on else "Diff highlight OFF.")
        self._rerender()

    # ── Feature 5: cross-scope overlap ────────────────────────────────

    def _cross_scope_overlap(self) -> None:
        if self._last_results is None or self._last_results.total == 0:
            self.status_var.set("Run a search first.")
            return
        by_student: dict[str, dict[str, Hit]] = {}
        for h in self._last_results.all_hits():
            sid = self._hit_student_id(h.scope, h)
            if sid:
                by_student.setdefault(sid, {})[h.scope] = h
        overlaps = {sid: sc for sid, sc in by_student.items() if len(sc) >= 2}
        if not overlaps:
            messagebox.showinfo(
                "Cross-scope overlap",
                "No student appears in two or more scopes in these results.")
            return
        lines = []
        for sid, sc in sorted(overlaps.items(),
                              key=lambda kv: -len(kv[1])):
            label = next(iter(sc.values())).label
            lines.append(f"{sid}  {label[:32]:<32}  "
                         f"in {len(sc)}: {', '.join(sorted(sc))}")
        self._show_text_popup(
            f"Cross-scope overlap — {len(overlaps)} student(s)",
            "\n".join(lines))

    # ── Feature 6: query cost / row estimate ──────────────────────────

    def _estimate_query(self) -> None:
        q = self.query_e.get().strip()
        scopes = self._selected_scopes()
        if not scopes:
            self.status_var.set("Pick at least one scope to estimate.")
            return
        try:
            preview = data.run_search(q, scopes=scopes, limit_per_scope=5,
                                      record_history=False)
        except ValidationError as e:
            messagebox.showerror("Estimate", str(e))
            return
        lines = [f"Estimated hits for {q or '(empty)'!r}:", ""]
        for s in preview.scopes:
            n = len(preview.hits_by_scope.get(s, []))
            cap = "≥5 (capped)" if n >= 5 else str(n)
            lines.append(f"  {SCOPE_LABELS.get(s, s):<24} {cap}")
        lines.append("")
        lines.append(f"Sampled total (cap 5/scope): {preview.total}")
        messagebox.showinfo("Query estimate", "\n".join(lines))

    # ── Feature 7: regex tester ───────────────────────────────────────

    def _regex_tester(self) -> None:
        top = tk.Toplevel(self.frame.winfo_toplevel())
        top.title("Regex tester")
        top.transient(self.frame.winfo_toplevel())
        ttk.Label(top, text="Pattern:").pack(anchor="w", padx=10, pady=(10, 0))
        pat_e = ttk.Entry(top, width=50)
        pat_e.pack(fill="x", padx=10)
        pat_e.insert(0, self.query_e.get().strip())
        ttk.Label(top, text="Sample text (one candidate per line):").pack(
            anchor="w", padx=10, pady=(8, 0))
        sample = tk.Text(top, width=60, height=8, wrap="none")
        sample.pack(fill="both", expand=True, padx=10)
        # Seed with labels from current results so it's useful immediately.
        if self._last_results:
            sample.insert("1.0", "\n".join(
                h.label for h in self._last_results.all_hits()[:20]))
        out_var = tk.StringVar()
        ttk.Label(top, textvariable=out_var, foreground="#0a6").pack(
            anchor="w", padx=10, pady=4)

        def _test() -> None:
            try:
                rx = re.compile(pat_e.get())
            except re.error as e:
                out_var.set(f"✗ invalid regex: {e}")
                return
            lines = sample.get("1.0", "end").splitlines()
            hits = [ln for ln in lines if ln and rx.search(ln)]
            out_var.set(f"✓ matches {len(hits)}/"
                        f"{len([x for x in lines if x])} line(s)")

        pat_e.bind("<KeyRelease>", lambda _e: _test())
        sample.bind("<KeyRelease>", lambda _e: _test())
        btns = ttk.Frame(top)
        btns.pack(pady=8)
        ttk.Button(btns, text="Use as query",
                   command=lambda: (self.query_e.delete(0, "end"),
                                    self.query_e.insert(0, pat_e.get()),
                                    self.regex_var.set(True),
                                    top.destroy(), self.run())).pack(
            side="left", padx=4)
        ttk.Button(btns, text="Close",
                   command=top.destroy).pack(side="left", padx=4)
        _test()

    # ── Feature 9: pivot / crosstab ───────────────────────────────────

    def _pivot_view(self) -> None:
        if self._last_results is None or self._last_results.total == 0:
            self.status_var.set("Run a search first.")
            return
        statuses: list[str] = []
        matrix: dict[str, dict[str, int]] = {}
        for h in self._last_results.all_hits():
            doc = (h.extra or {}).get("_doc") or {}
            st = str(doc.get("status") or doc.get("level") or "—").strip() or "—"
            if st not in statuses:
                statuses.append(st)
            row = matrix.setdefault(SCOPE_LABELS.get(h.scope, h.scope), {})
            row[st] = row.get(st, 0) + 1
        statuses = statuses[:8]
        header = f"{'scope':<22}" + "".join(f"{s[:10]:>11}" for s in statuses)
        header += f"{'Σ':>8}"
        lines = [header, "─" * len(header)]
        for scope, row in matrix.items():
            cells = "".join(f"{row.get(s, 0):>11}" for s in statuses)
            lines.append(f"{scope:<22}{cells}{sum(row.values()):>8}")
        self._show_text_popup("Pivot — scope × status", "\n".join(lines))

    # ── Feature 11: saved column layouts ──────────────────────────────

    def _rebuild_layout_menu(self) -> None:
        m = self._layout_menu
        m.delete(0, "end")
        m.add_command(label="Save current layout…",
                      command=self._save_layout)
        store = _load_ui_store()
        names = sorted(store.get("layouts", {}))
        if names:
            m.add_separator()
            for name in names:
                sub = tk.Menu(m, tearoff=False)
                sub.add_command(label="Apply",
                                command=lambda n=name: self._apply_layout(n))
                sub.add_command(label="Delete",
                                command=lambda n=name: self._delete_layout(n))
                m.add_cascade(label=name, menu=sub)

    def _save_layout(self) -> None:
        name = simpledialog.askstring("Save layout", "Layout name:",
                                      parent=self.frame)
        if not name or not name.strip():
            return
        store = _load_ui_store()
        store.setdefault("layouts", {})[name.strip()] = {
            "order": list(self._col_order),
            "pinned": sorted(self._pinned_cols),
            "hidden": [c for c in self._cols if not self._col_vars[c].get()],
        }
        _save_ui_store(store)
        self.status_var.set(f"Saved layout {name.strip()!r}.")

    def _apply_layout(self, name: str) -> None:
        layout = _load_ui_store().get("layouts", {}).get(name)
        if not layout:
            return
        self._col_order = [c for c in layout.get("order", self._cols)
                           if c in self._cols]
        for c in self._cols:
            if c not in self._col_order:
                self._col_order.append(c)
        self._pinned_cols = {c for c in layout.get("pinned", [])
                             if c in self._cols}
        hidden = set(layout.get("hidden", []))
        for c in self._cols:
            self._col_vars[c].set(c not in hidden)
        self._apply_columns()
        self.status_var.set(f"Applied layout {name!r}.")

    def _delete_layout(self, name: str) -> None:
        store = _load_ui_store()
        if store.get("layouts", {}).pop(name, None) is not None:
            _save_ui_store(store)
            self.status_var.set(f"Deleted layout {name!r}.")

    # ── Feature 12: compare result sets A / B ─────────────────────────

    def _snapshot_slot(self, slot: str) -> None:
        if self._last_results is None:
            self.status_var.set("Run a search first.")
            return
        self._cmp_slots[slot] = {
            "query": self._last_results.query,
            "keys": {f"{h.scope}#{h.entity_id}": h.label
                     for h in self._last_results.all_hits()},
        }
        self.status_var.set(
            f"Captured slot {slot} ({len(self._cmp_slots[slot]['keys'])} hits) "
            f"for {self._last_results.query!r}.")

    def _compare_slots(self) -> None:
        if "A" not in self._cmp_slots or "B" not in self._cmp_slots:
            messagebox.showinfo(
                "Compare",
                "Capture slot A and slot B first (from the Compare menu).")
            return
        a, b = self._cmp_slots["A"], self._cmp_slots["B"]
        ka, kb = set(a["keys"]), set(b["keys"])
        only_a = sorted(ka - kb)
        only_b = sorted(kb - ka)
        both = ka & kb
        lines = [f"A: {a['query']!r}  ({len(ka)} hits)",
                 f"B: {b['query']!r}  ({len(kb)} hits)",
                 f"In both: {len(both)}", "",
                 f"── Only in A ({len(only_a)}) ──"]
        lines += [f"  {a['keys'][k]}  [{k}]" for k in only_a[:60]]
        lines += ["", f"── Only in B ({len(only_b)}) ──"]
        lines += [f"  {b['keys'][k]}  [{k}]" for k in only_b[:60]]
        self._show_text_popup("Compare A vs B", "\n".join(lines))

    # ── Feature 13: heatmap toggle ────────────────────────────────────

    def _toggle_heatmap(self) -> None:
        if self.heatmap_var.get():
            self.colour_var.set(False)
        self._rerender()

    # ── Feature 14: flag with reason code ─────────────────────────────

    _FLAG_CODES: tuple[str, ...] = (
        "safeguarding", "attendance", "behaviour", "academic",
        "pastoral", "sen", "medical", "other",
    )

    def _bulk_flag(self) -> None:
        hits = self._selected_hits()
        if not hits:
            self.status_var.set("Select rows to flag.")
            return
        code = _choose_from("Flag records", "Reason code:",
                            list(self._FLAG_CODES), self.frame)
        if not code:
            return
        reason = simpledialog.askstring(
            "Flag records", "Reason detail (optional):",
            parent=self.frame) or ""
        ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        keys = {(h.scope, h.entity_id) for h in hits}
        self._snapshot_ann("bulk flag")
        store = _load_ann_store()
        for h in hits:
            ann = store.setdefault(_ann_key(h.scope, h.entity_id), {})
            ann.setdefault("flags", []).append(
                {"code": code, "reason": reason.strip(), "ts": ts})
            tags = ann.setdefault("tags", [])
            if "flag" not in tags:
                tags.append("flag")
        _save_ann_store(store)
        _append_action_log("flag", f"{code}: {reason.strip()}", len(hits))
        self._rerender()
        self._reselect(keys)
        self._on_select()
        self.status_var.set(f"Flagged {len(hits)} record(s) as {code!r}.")

    # ── Feature 16: bulk PDF one-pagers ───────────────────────────────

    def _export_pdf_reports(self) -> None:
        hits = self._selected_hits() or (
            self._last_results.all_hits() if self._last_results else [])
        if not hits:
            self.status_var.set("Select rows (or run a search) first.")
            return
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf"), ("HTML", "*.html")],
            initialfile="student_reports.pdf")
        if not path:
            return
        subset = self._results_from_hits(hits, self._last_results.query
                                         if self._last_results else "")
        try:
            data.export_results_file(subset, path)
            _append_action_log("pdf report", path, len(hits))
            self.status_var.set(f"Report for {len(hits)} record(s) → {path}")
        except Exception as e:                       # noqa: BLE001
            messagebox.showerror("Report failed", str(e))

    # ── Feature 17: undo last bulk annotation ─────────────────────────

    def _snapshot_ann(self, label: str) -> None:
        snap = json.dumps(_load_ann_store())
        self._ann_undo.append((label, snap))
        del self._ann_undo[:-20]                     # keep last 20

    def _undo_bulk(self) -> None:
        if not self._ann_undo:
            self.status_var.set("Nothing to undo.")
            return
        label, snap = self._ann_undo.pop()
        try:
            _save_ann_store(json.loads(snap))
        except ValueError:
            self.status_var.set("Undo failed (corrupt snapshot).")
            return
        self._rerender()
        self._on_select()
        self.status_var.set(f"Undid: {label}.")

    # ── Feature 18: assign selection to a workflow / case queue ───────

    def _bulk_assign_workflow(self) -> None:
        hits = self._selected_hits()
        if not hits:
            self.status_var.set("Select rows to assign to a workflow.")
            return
        owner = simpledialog.askstring(
            "Assign to workflow", "Owning staff (name or id):",
            parent=self.frame)
        if not owner or not owner.strip():
            return
        due = simpledialog.askstring(
            "Assign to workflow", "Due date (YYYY-MM-DD, optional):",
            parent=self.frame) or ""
        ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        keys = {(h.scope, h.entity_id) for h in hits}
        self._snapshot_ann("assign workflow")
        store = _load_ann_store()
        for h in hits:
            ann = store.setdefault(_ann_key(h.scope, h.entity_id), {})
            ann["workflow"] = {"owner": owner.strip(), "due": due.strip(),
                               "state": "open", "ts": ts}
        _save_ann_store(store)
        _append_action_log("assign workflow", owner.strip(), len(hits))
        self._reselect(keys)
        self._on_select()
        self.status_var.set(
            f"Assigned {len(hits)} record(s) to {owner.strip()!r}.")

    # ── Feature 19: watchlists ────────────────────────────────────────

    def _rebuild_watchlist_menu(self) -> None:
        m = self._watch_menu
        m.delete(0, "end")
        m.add_command(label="Add selection to watchlist…",
                      command=self._add_to_watchlist)
        store = _load_ui_store()
        names = sorted(store.get("watchlists", {}))
        if names:
            m.add_separator()
            for name in names:
                sub = tk.Menu(m, tearoff=False)
                count = len(store["watchlists"][name])
                sub.add_command(
                    label=f"Load as results ({count})",
                    command=lambda n=name: self._open_watchlist(n))
                sub.add_command(label="Delete",
                                command=lambda n=name: self._delete_watchlist(n))
                m.add_cascade(label=name, menu=sub)

    def _add_to_watchlist(self) -> None:
        hits = self._selected_hits()
        if not hits:
            self.status_var.set("Select rows to add to a watchlist.")
            return
        name = simpledialog.askstring("Watchlist", "Watchlist name:",
                                      parent=self.frame)
        if not name or not name.strip():
            return
        store = _load_ui_store()
        wl = store.setdefault("watchlists", {}).setdefault(name.strip(), [])
        have = {(m["scope"], m["entity_id"]) for m in wl}
        added = 0
        for h in hits:
            if (h.scope, h.entity_id) not in have:
                wl.append({"scope": h.scope, "entity_id": h.entity_id,
                           "label": h.label})
                added += 1
        _save_ui_store(store)
        self.status_var.set(
            f"Added {added} to watchlist {name.strip()!r} ({len(wl)} total).")

    def _open_watchlist(self, name: str) -> None:
        members = _load_ui_store().get("watchlists", {}).get(name, [])
        if not members:
            self.status_var.set(f"Watchlist {name!r} is empty.")
            return
        hits = [Hit(scope=m["scope"], entity_id=m["entity_id"],
                    label=m.get("label", m["entity_id"]))
                for m in members]
        self._render(self._results_from_hits(hits, f"watchlist:{name}"))
        self.status_var.set(f"Loaded watchlist {name!r} ({len(hits)} member(s)).")

    def _delete_watchlist(self, name: str) -> None:
        store = _load_ui_store()
        if store.get("watchlists", {}).pop(name, None) is not None:
            _save_ui_store(store)
            self.status_var.set(f"Deleted watchlist {name!r}.")

    # ── Feature 20: keyboard shortcut cheatsheet ──────────────────────

    def _show_shortcuts(self, _event=None) -> str:
        lines = [f"{keys:<22} {desc}" for keys, desc in _SHORTCUT_HELP]
        self._show_text_popup("Keyboard shortcuts", "\n".join(lines))
        return "break"

    # ── Feature 21: dark / high-contrast theme ────────────────────────

    def _toggle_theme(self) -> None:
        self._apply_theme(self.dark_var.get())

    def _apply_theme(self, dark: bool) -> None:
        if dark:
            bg, fg, sel = "#1e1e1e", "#e6e6e6", "#375a7f"
            self._tree_style.configure(
                "AdvSearch.Treeview", background=bg, fieldbackground=bg,
                foreground=fg)
            self._tree_style.map("AdvSearch.Treeview",
                                 background=[("selected", sel)])
            self.tree.tag_configure("scope", background="#2d3a4a",
                                    foreground="#cfe4ff")
            for tag in _ROW_TAG_COLOURS:
                self.tree.tag_configure(tag, background="#332b1a")
            try:
                self.preview.configure(bg=bg, fg=fg, insertbackground=fg)
            except tk.TclError:
                pass
            self.status_var.set("High-contrast dark theme ON.")
        else:
            self._tree_style.configure(
                "AdvSearch.Treeview", background="white",
                fieldbackground="white", foreground="black")
            self.tree.tag_configure("scope", background="#eef7ff",
                                    foreground="black")
            for tag, colour in _ROW_TAG_COLOURS.items():
                self.tree.tag_configure(tag, background=colour)
            try:
                self.preview.configure(bg="white", fg="black",
                                       insertbackground="black")
            except tk.TclError:
                pass
            self.status_var.set("Light theme.")
        self._rerender()

    # ── Feature 22: command palette ───────────────────────────────────

    def _build_command_registry(self) -> None:
        self._commands: dict[str, Callable[[], object]] = {
            "Search: run": self.run,
            "Search: clear": self._clear,
            "Query: boolean builder": self._boolean_builder,
            "Query: regex tester": self._regex_tester,
            "Query: estimate hits": self._estimate_query,
            "Query: natural language": self._natural_language_query,
            "Query: pin current as chip": self._pin_current_query,
            "View: pivot (scope × status)": self._pivot_view,
            "View: cross-scope overlap": self._cross_scope_overlap,
            "View: save column layout": self._save_layout,
            "View: expand all": self._expand_all,
            "View: collapse all": self._collapse_all,
            "Compare: capture slot A": lambda: self._snapshot_slot("A"),
            "Compare: capture slot B": lambda: self._snapshot_slot("B"),
            "Compare: show A vs B": self._compare_slots,
            "Selection: open": self._open_selected,
            "Selection: copy IDs": self._copy_ids,
            "Selection: copy emails": self._copy_emails,
            "Selection: export…": self._export_results_dialog,
            "Selection: PDF report": self._export_pdf_reports,
            "Selection: message students": self._mailmerge_dialog,
            "Selection: flag with reason": self._bulk_flag,
            "Selection: assign to workflow": self._bulk_assign_workflow,
            "Selection: add to watchlist": self._add_to_watchlist,
            "Bulk: tag": self._bulk_tag,
            "Bulk: add note": self._bulk_add_note,
            "Bulk: undo last": self._undo_bulk,
            "Cohort: save from results": self._save_cohort,
            "Help: keyboard shortcuts": self._show_shortcuts,
            "Log: show action log": self._show_action_log,
        }

    def _command_palette(self, _event=None) -> str:
        if not hasattr(self, "_commands"):
            self._build_command_registry()
        top = tk.Toplevel(self.frame.winfo_toplevel())
        top.title("Command palette")
        top.transient(self.frame.winfo_toplevel())
        top.geometry("460x360")
        entry = ttk.Entry(top)
        entry.pack(fill="x", padx=8, pady=8)
        lb = tk.Listbox(top)
        lb.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        names = sorted(self._commands)

        def _refresh(_e=None) -> None:
            term = entry.get().strip().lower()
            lb.delete(0, "end")
            for n in names:
                if all(w in n.lower() for w in term.split()):
                    lb.insert("end", n)
            if lb.size():
                lb.selection_set(0)

        def _run_sel(_e=None) -> None:
            sel = lb.curselection()
            if not sel:
                return
            name = lb.get(sel[0])
            top.destroy()
            try:
                self._commands[name]()
            except Exception as exc:                 # noqa: BLE001
                self.status_var.set(f"{name}: {exc}")

        entry.bind("<KeyRelease>", _refresh)
        entry.bind("<Return>", _run_sel)
        entry.bind("<Down>", lambda _e: (lb.focus_set(),
                                         lb.selection_set(0)))
        lb.bind("<Return>", _run_sel)
        lb.bind("<Double-1>", _run_sel)
        top.bind("<Escape>", lambda _e: top.destroy())
        _refresh()
        entry.focus_set()
        top.grab_set()
        return "break"

    # ── Feature 23: pinned-query chips ────────────────────────────────

    def _pin_current_query(self) -> None:
        q = self.query_e.get().strip()
        if not q:
            self.status_var.set("Type a query to pin it.")
            return
        store = _load_ui_store()
        chips = store.setdefault("pinned_queries", [])
        if q not in chips:
            chips.insert(0, q)
            del chips[8:]                            # cap at 8 chips
            _save_ui_store(store)
        self._rebuild_qchips()
        self.status_var.set(f"Pinned query {q!r}.")

    def _rebuild_qchips(self) -> None:
        for w in self.qchip_frame.winfo_children():
            w.destroy()
        chips = _load_ui_store().get("pinned_queries", [])
        if not chips:
            return
        ttk.Label(self.qchip_frame, text="Pinned:").pack(side="left")
        for q in chips:
            cf = ttk.Frame(self.qchip_frame)
            cf.pack(side="left", padx=2)
            ttk.Button(cf, text=q[:24], width=min(24, len(q) + 2),
                       command=lambda qq=q: self._use_pinned_query(qq)).pack(
                side="left")
            ttk.Button(cf, text="✕", width=2,
                       command=lambda qq=q: self._unpin_query(qq)).pack(
                side="left")

    def _use_pinned_query(self, q: str) -> None:
        self.query_e.delete(0, "end")
        self.query_e.insert(0, q)
        self.run()

    def _unpin_query(self, q: str) -> None:
        store = _load_ui_store()
        chips = store.get("pinned_queries", [])
        if q in chips:
            chips.remove(q)
            _save_ui_store(store)
            self._rebuild_qchips()

    # ── Feature 25: operator action log viewer ────────────────────────

    def _show_action_log(self) -> None:
        rows = _read_action_log()
        if not rows:
            self._show_text_popup("Action log", "(no actions recorded yet)")
            return
        lines = [f"{r.get('ts', ''):<20} {r.get('action', ''):<14} "
                 f"×{r.get('count', 0):<4} {r.get('detail', '')}"
                 for r in reversed(rows[-200:])]
        self._show_text_popup("Operator action log", "\n".join(lines))

    # ── Shared popup helper for the features above ────────────────────

    def _show_text_popup(self, title: str, text: str) -> None:
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.title(title)
        win.geometry("760x480")
        frame = ttk.Frame(win)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        t = tk.Text(frame, wrap="none", font=("TkFixedFont", 9))
        vs = ttk.Scrollbar(frame, orient="vertical", command=t.yview)
        t.configure(yscrollcommand=vs.set)
        t.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        t.insert("1.0", text or "(nothing)")
        t.configure(state="disabled")
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 8))


# ══ Saved searches tab ═════════════════════════════════════════════

class SavedTab:
    def __init__(self, nb: ttk.Notebook, search_tab: SearchTab) -> None:
        self.search_tab = search_tab
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Saved")
        self._build()
        self.refresh()

    def _build(self) -> None:
        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        cols = ("id", "name", "query", "scopes", "notes")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        widths = {"id": 60, "name": 180, "query": 180,
                  "scopes": 320, "notes": 300}
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._run_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="Run",
                    command=self._run_selected).pack(side="left")
        ttk.Button(actions, text="New",
                    command=self._new).pack(side="left", padx=4)
        ttk.Button(actions, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows = data.list_saved_searches()
        for s in rows:
            scopes = ", ".join(s.scopes) if s.scopes else "(all)"
            self.tree.insert("", "end", iid=str(s.saved_id), values=(
                s.saved_id, s.name, s.query or "(empty)",
                scopes, s.notes or "",
            ))
        self.count_var.set(f"{len(rows)} saved.")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _run_selected(self) -> None:
        sid = self._selected_id()
        if sid is None:
            messagebox.showinfo("Run", "Select a saved search first.")
            return
        s = data.get_saved_search(sid)
        if s is None:
            return
        # Switch to the Search tab and run the saved query.
        nb = self.frame.master
        if isinstance(nb, ttk.Notebook):
            nb.select(0)
        self.search_tab.load_query(s.query, s.scopes or None)

    def _new(self) -> None:
        SavedDialog(self.frame.winfo_toplevel(),
                     existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        sid = self._selected_id()
        if sid is None:
            messagebox.showinfo("Edit", "Select a saved search first.")
            return
        existing = data.get_saved_search(sid)
        if existing is None:
            return
        SavedDialog(self.frame.winfo_toplevel(),
                     existing=existing, on_save=self.refresh)

    def _delete_selected(self) -> None:
        sid = self._selected_id()
        if sid is None:
            messagebox.showinfo("Delete", "Select a saved search first.")
            return
        if not messagebox.askyesno("Delete",
                                     f"Delete saved search #{sid}?"):
            return
        try:
            data.delete_saved_search(sid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


# ══ History tab ════════════════════════════════════════════════════

class HistoryTab:
    def __init__(self, nb: ttk.Notebook, search_tab: SearchTab) -> None:
        self.search_tab = search_tab
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="History")
        self._build()
        self.refresh()

    def _build(self) -> None:
        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        cols = ("id", "ts", "hits", "query", "scopes", "actor")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        headings = {"id": "ID", "ts": "When", "hits": "Hits",
                    "query": "Query", "scopes": "Scopes",
                    "actor": "Actor"}
        widths = {"id": 60, "ts": 160, "hits": 60,
                  "query": 220, "scopes": 320, "actor": 120}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "center" if c == "hits" else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._rerun_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="Re-run",
                    command=self._rerun_selected).pack(side="left")
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")
        ttk.Button(actions, text="Clear all",
                    command=self._clear).pack(side="right", padx=4)

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows = data.list_history(limit=50)
        for h in rows:
            scopes = ", ".join(h.scopes) if h.scopes else "(all)"
            self.tree.insert("", "end", iid=str(h.history_id), values=(
                h.history_id, h.ts, h.result_count,
                h.query or "(empty)", scopes, h.actor or "—",
            ))
        self.count_var.set(f"{len(rows)} entry/entries.")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _rerun_selected(self) -> None:
        hid = self._selected_id()
        if hid is None:
            messagebox.showinfo("Re-run",
                                  "Select a history entry first.")
            return
        rows = data.list_history(limit=50)
        match = next((h for h in rows if h.history_id == hid), None)
        if match is None:
            return
        nb = self.frame.master
        if isinstance(nb, ttk.Notebook):
            nb.select(0)
        self.search_tab.load_query(match.query, match.scopes or None)

    def _clear(self) -> None:
        if not messagebox.askyesno("Clear",
                                     "Clear all search history?"):
            return
        n = data.clear_history()
        messagebox.showinfo("Clear", f"Cleared {n} entry/entries.")
        self.refresh()


# ══ Dialogs ════════════════════════════════════════════════════════

class SavedDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: SavedSearch | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Saved Search" if existing
                          else "New Saved Search")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._scope_vars: dict[str, tk.BooleanVar] = {}
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)

        ttk.Label(form, text="Name:").grid(row=0, column=0,
                                              sticky="e", pady=4)
        self.name_e = ttk.Entry(form, width=40)
        if self.existing:
            self.name_e.insert(0, self.existing.name)
        self.name_e.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Query:").grid(row=1, column=0,
                                               sticky="e", pady=4)
        self.query_e = ttk.Entry(form, width=40)
        if self.existing:
            self.query_e.insert(0, self.existing.query)
        self.query_e.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Scopes:").grid(row=2, column=0,
                                                sticky="ne", pady=4)
        scopes_frame = ttk.Frame(form)
        scopes_frame.grid(row=2, column=1, sticky="w", padx=6)
        current = set(self.existing.scopes) if self.existing else set(ALL_SCOPES)
        col = 0
        row = 0
        for key in ALL_SCOPES:
            var = tk.BooleanVar(value=key in current)
            self._scope_vars[key] = var
            ttk.Checkbutton(scopes_frame, text=SCOPE_LABELS[key],
                              variable=var).grid(row=row, column=col,
                                                  sticky="w", padx=2)
            col += 1
            if col >= 3:
                col = 0
                row += 1

        ttk.Label(form, text="Notes:").grid(row=3, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=40, height=4)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=3, column=1, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=4, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        scopes = [k for k, v in self._scope_vars.items() if v.get()]
        payload = {
            "name":   self.name_e.get().strip(),
            "query":  self.query_e.get().strip(),
            "scopes": scopes or list(ALL_SCOPES),
            "notes":  self.notes_t.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                data.update_saved_search(self.existing.saved_id, payload)
            else:
                data.create_saved_search(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


# ══ Tools tab (telemetry, FTS, pinning, subscriptions, export) ════════

class ToolsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Tools")
        self._build()

    def _build(self) -> None:
        # Section: Index / cache
        sec1 = ttk.LabelFrame(self.frame, text="Index & cache",
                               padding=8)
        sec1.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Button(sec1, text="Rebuild FTS5 index",
                    command=self._rebuild_index).pack(side="left")
        ttk.Button(sec1, text="Clear search cache",
                    command=self._clear_cache).pack(side="left",
                                                     padx=(6, 0))
        self.fts_var = tk.StringVar(value=self._fts_status())
        ttk.Label(sec1, textvariable=self.fts_var).pack(side="left",
                                                          padx=(12, 0))

        # Section: Subscriptions
        sec2 = ttk.LabelFrame(self.frame, text="Subscriptions",
                               padding=8)
        sec2.pack(fill="x", padx=10, pady=4)
        ttk.Button(sec2, text="Poll now",
                    command=self._poll).pack(side="left")
        ttk.Label(sec2, text="  Inbox for actor:").pack(side="left")
        self.inbox_actor = ttk.Entry(sec2, width=14)
        self.inbox_actor.pack(side="left", padx=(2, 4))
        ttk.Button(sec2, text="Show inbox",
                    command=self._show_inbox).pack(side="left")
        ttk.Label(sec2, text="  Snooze id:").pack(side="left")
        self.snooze_id = ttk.Entry(sec2, width=6)
        self.snooze_id.pack(side="left", padx=(2, 4))
        ttk.Button(sec2, text="Snooze 24h",
                    command=self._snooze).pack(side="left")

        # Section: Alerts & dashboards (items 27, 29)
        sec_a = ttk.LabelFrame(self.frame, text="Alerts & dashboards",
                                padding=8)
        sec_a.pack(fill="x", padx=10, pady=4)
        ttk.Label(sec_a, text="Digest actor:").pack(side="left")
        self.digest_actor = ttk.Entry(sec_a, width=12)
        self.digest_actor.pack(side="left", padx=(2, 4))
        ttk.Button(sec_a, text="Build digest",
                    command=self._digest).pack(side="left")
        ttk.Label(sec_a, text="   Dashboard:").pack(side="left")
        self.dash_name = ttk.Entry(sec_a, width=14)
        self.dash_name.pack(side="left", padx=(2, 4))
        ttk.Button(sec_a, text="Run",
                    command=self._run_dashboard).pack(side="left")
        ttk.Button(sec_a, text="List",
                    command=self._list_dashboards).pack(side="left",
                                                        padx=(4, 0))

        # Section: Scheduled searches (feature 3)
        sec_s = ttk.LabelFrame(self.frame, text="Scheduled searches",
                                padding=8)
        sec_s.pack(fill="x", padx=10, pady=4)
        ttk.Label(sec_s, text="Saved id:").pack(side="left")
        self.sched_saved_id = ttk.Entry(sec_s, width=6)
        self.sched_saved_id.pack(side="left", padx=(2, 4))
        ttk.Label(sec_s, text="Cron:").pack(side="left")
        self.sched_cron = ttk.Combobox(
            sec_s, width=8, state="readonly",
            values=["daily", "hourly", "weekly"])
        self.sched_cron.set("daily")
        self.sched_cron.pack(side="left", padx=(2, 4))
        ttk.Label(sec_s, text="Notify:").pack(side="left")
        self.sched_notify = ttk.Entry(sec_s, width=12)
        self.sched_notify.pack(side="left", padx=(2, 4))
        ttk.Button(sec_s, text="Schedule",
                   command=self._schedule_saved).pack(side="left")
        ttk.Button(sec_s, text="List",
                   command=self._list_schedules).pack(side="left", padx=(4, 0))
        ttk.Label(sec_s, text="  Sched id:").pack(side="left")
        self.sched_id = ttk.Entry(sec_s, width=6)
        self.sched_id.pack(side="left", padx=(2, 4))
        ttk.Button(sec_s, text="Run now",
                   command=self._run_schedule).pack(side="left")
        ttk.Button(sec_s, text="Delete",
                   command=self._delete_schedule).pack(side="left", padx=(4, 0))

        # Section: Data quality & admin (items 33, 41, 43, 44, 45, 46)
        sec_b = ttk.LabelFrame(self.frame, text="Data quality & admin",
                                padding=8)
        sec_b.pack(fill="x", padx=10, pady=4)
        ttk.Button(sec_b, text="Index status",
                    command=self._index_status).pack(side="left")
        ttk.Button(sec_b, text="Refresh stale",
                    command=self._refresh_stale).pack(side="left", padx=(4, 0))
        ttk.Button(sec_b, text="Cache stats",
                    command=self._cache_stats).pack(side="left", padx=(4, 0))
        ttk.Button(sec_b, text="Duplicate students",
                    command=self._duplicates).pack(side="left", padx=(4, 0))
        ttk.Button(sec_b, text="Data gaps",
                    command=self._data_gaps).pack(side="left", padx=(4, 0))
        ttk.Button(sec_b, text="Audit log",
                    command=self._audit).pack(side="left", padx=(4, 0))
        ttk.Button(sec_b, text="Search volume",
                    command=self._volume).pack(side="left", padx=(4, 0))
        ttk.Button(sec_b, text="Operator action log",
                    command=self._action_log).pack(side="left", padx=(4, 0))

        # Section: Saved searches export/import
        sec3 = ttk.LabelFrame(self.frame, text="Saved searches",
                               padding=8)
        sec3.pack(fill="x", padx=10, pady=4)
        ttk.Button(sec3, text="Export to JSON…",
                    command=self._export).pack(side="left")
        ttk.Button(sec3, text="Import from JSON…",
                    command=self._import).pack(side="left", padx=(6, 0))

        # Section: Telemetry
        sec4 = ttk.LabelFrame(self.frame, text="Telemetry",
                               padding=8)
        sec4.pack(fill="both", expand=True, padx=10, pady=4)
        ttk.Button(sec4, text="Refresh",
                    command=self._refresh_telemetry).pack(side="top",
                                                            anchor="w")
        self.telem_txt = tk.Text(sec4, height=18, wrap="word")
        self.telem_txt.pack(fill="both", expand=True, pady=(6, 0))
        self._refresh_telemetry()

        # Section: Pinned
        sec5 = ttk.LabelFrame(self.frame, text="Pinned results",
                               padding=8)
        sec5.pack(fill="x", padx=10, pady=(4, 10))
        ttk.Label(sec5, text="Actor:").pack(side="left")
        self.pin_actor = ttk.Entry(sec5, width=14)
        self.pin_actor.pack(side="left", padx=(2, 4))
        ttk.Button(sec5, text="List",
                    command=self._list_pins).pack(side="left")

    # ── handlers ──────────────────────────────────────────────────

    def _fts_status(self) -> str:
        return ("FTS5: available"
                if data._fts_available() else "FTS5: NOT available")

    def _rebuild_index(self) -> None:
        if not data._fts_available():
            messagebox.showinfo("FTS5",
                                "SQLite FTS5 is not available.")
            return
        counts = data.refresh_index()
        total = sum(counts.values())
        messagebox.showinfo(
            "Index rebuilt",
            f"Indexed {total} row(s) across {len(counts)} scope(s).")

    def _clear_cache(self) -> None:
        data.clear_cache()
        messagebox.showinfo("Cache", "Search cache cleared.")

    def _poll(self) -> None:
        fired = data.poll_subscriptions()
        messagebox.showinfo(
            "Subscriptions",
            f"{len(fired)} subscription(s) fired.")

    def _show_inbox(self) -> None:
        actor = self.inbox_actor.get().strip()
        if not actor:
            messagebox.showinfo("Inbox", "Enter an actor id first.")
            return
        rows = data.list_subscription_notifications(actor)
        if not rows:
            messagebox.showinfo("Inbox", "(empty)")
            return
        lines = []
        for r in rows[:50]:
            mark = "•" if not r.get("read_at") else " "
            lines.append(
                f"{mark} #{r['notif_id']} +{r['delta']}/{r['total']}  "
                f"{r.get('sample_scope') or ''}: "
                f"{r.get('sample_label') or ''}")
        messagebox.showinfo(f"Inbox for {actor}",
                            "\n".join(lines))

    def _export(self) -> None:
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            initialfile="saved_searches.json",
            filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(data.export_saved_searches())
            messagebox.showinfo("Export", f"Wrote {path}")
        except OSError as e:
            messagebox.showerror("Export failed", str(e))

    def _import(self) -> None:
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not path:
            return
        overwrite = messagebox.askyesno(
            "Import",
            "Overwrite existing saved searches with same name?")
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
            counts = data.import_saved_searches(text,
                                                  overwrite=overwrite)
            messagebox.showinfo("Import", str(counts))
        except (OSError, ValidationError) as e:
            messagebox.showerror("Import failed", str(e))

    def _refresh_telemetry(self) -> None:
        ts = data.telemetry_summary()
        lines = [
            f"Total searches: {ts.total_searches}",
            f"Zero-result:    {ts.zero_result}",
            "",
            "Top queries:",
        ]
        for q, n in ts.top_queries:
            lines.append(f"  {n:>3}×  {q!r}")
        lines.append("")
        lines.append("Slowest scopes (avg ms):")
        for s, ms in ts.slowest_scopes_ms.items():
            lines.append(f"  {s:<22} {ms:>8.1f}")
        if ts.zero_result_queries:
            lines.append("")
            lines.append("Recent zero-result queries:")
            for q in ts.zero_result_queries:
                lines.append(f"  • {q!r}")
        self.telem_txt.configure(state="normal")
        self.telem_txt.delete("1.0", "end")
        self.telem_txt.insert("1.0", "\n".join(lines))
        self.telem_txt.configure(state="disabled")

    def _list_pins(self) -> None:
        actor = self.pin_actor.get().strip() or None
        pins = data.list_pinned(actor)
        if not pins:
            messagebox.showinfo("Pinned", "(none)")
            return
        text = "\n".join(
            f"#{p.pin_id}  {p.actor}  {p.scope}/{p.entity_id}  "
            f"{p.label}" for p in pins[:50])
        messagebox.showinfo("Pinned results", text)

    # ── Alerts / dashboards / admin handlers (items 26–50) ────────

    def _show_text(self, title: str, text: str) -> None:
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.title(title)
        win.geometry("720x460")
        t = tk.Text(win, wrap="none", font=("TkFixedFont", 9))
        t.pack(fill="both", expand=True, padx=8, pady=8)
        t.insert("1.0", text or "(nothing)")
        t.configure(state="disabled")
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 8))

    def _snooze(self) -> None:
        raw = self.snooze_id.get().strip()
        if not raw.isdigit():
            messagebox.showinfo("Snooze", "Enter a notification id.")
            return
        ok = data.snooze_notification(int(raw), hours=24)
        messagebox.showinfo("Snooze",
                            "Snoozed 24h." if ok else "Not found.")

    def _digest(self) -> None:
        dg = data.build_digest(self.digest_actor.get().strip() or None)
        lines = [f"Digest — {dg.total_new} new across "
                 f"{len(dg.lines)} scheduled search(es)", ""]
        for line in dg.lines:
            lines.append(
                f"{line.new_since_last:>4} new · total {line.total:<5} "
                f"{line.saved_name}  (last {line.last_run_at or '—'})")
        self._show_text("Subscription digest", "\n".join(lines))

    def _run_dashboard(self) -> None:
        name = self.dash_name.get().strip()
        if not name:
            messagebox.showinfo("Dashboard", "Enter a dashboard name/id.")
            return
        try:
            panels = data.run_dashboard(name)
        except Exception as e:
            messagebox.showerror("Dashboard", str(e))
            return
        lines = [f"{name}:", ""]
        for p in panels:
            cnt = "err" if p.total < 0 else str(p.total)
            lines.append(f"{cnt:>6}  {p.name}   ({p.query or '(empty)'})")
        self._show_text(f"Dashboard — {name}", "\n".join(lines))

    def _list_dashboards(self) -> None:
        rows = data.list_dashboards()
        lines = [f"#{d.dashboard_id}  {d.name}  "
                 f"({len(d.saved_ids)} panel(s))" for d in rows]
        self._show_text("Dashboards", "\n".join(lines) or "(none)")

    def _index_status(self) -> None:
        rows = data.index_status()
        lines = [f"{s.scope:<22} indexed {s.indexed_rows:>5} / current "
                 f"{s.current_rows:>5}  [{'STALE' if s.stale else 'ok'}]  "
                 f"{s.last_refresh or '—'}" for s in rows]
        self._show_text("FTS index status", "\n".join(lines))

    def _refresh_stale(self) -> None:
        counts = data.refresh_index(only_stale=True)
        messagebox.showinfo(
            "Refresh stale",
            f"Refreshed {sum(counts.values())} row(s) across "
            f"{len(counts)} scope(s).")
        self.fts_var.set(self._fts_status())

    def _cache_stats(self) -> None:
        st = data.cache_stats()
        messagebox.showinfo(
            "Cache stats",
            f"Entries: {st['entries']}/{st['max_entries']}\n"
            f"Hits: {st['hits']}   Misses: {st['misses']}\n"
            f"Hit-rate: {st['hit_rate']:.0%}   TTL: {st['ttl_seconds']}s")

    def _duplicates(self) -> None:
        groups = data.find_duplicate_students()
        lines = [f"[{g.reason}] {g.key}: {', '.join(g.student_ids)}"
                 for g in groups[:80]]
        self._show_text("Possible duplicate students",
                        "\n".join(lines) or "No likely duplicates.")

    def _data_gaps(self) -> None:
        gaps = data.find_data_gaps("students")
        lines = [f"{g.entity_id}  {g.label[:36]:<36}  "
                 f"missing: {', '.join(g.missing)}" for g in gaps[:120]]
        self._show_text("Student data gaps",
                        "\n".join(lines) or "No data gaps.")

    def _audit(self) -> None:
        rows = data.list_search_audit(limit=80)
        lines = []
        for e in rows:
            bg = "  [BREAK-GLASS]" if e.break_glass else ""
            lines.append(f"{e.ts}  {e.actor or '—'}/{e.role or '—'}  "
                         f"{e.query!r}  "
                         f"sens={','.join(e.sensitive_scopes)}{bg}")
            if e.reason:
                lines.append(f"      reason: {e.reason}")
        self._show_text("Sensitive-access audit",
                        "\n".join(lines) or "(no entries)")

    def _volume(self) -> None:
        rows = data.search_volume_by_day()
        lines = [f"{d}  {'#' * min(n, 50)} {n}" for d, n in rows]
        self._show_text("Searches per day",
                        "\n".join(lines) or "(no history)")

    # ── Scheduled searches (feature 3) ────────────────────────────

    def _schedule_saved(self) -> None:
        raw = self.sched_saved_id.get().strip()
        if not raw.isdigit():
            messagebox.showinfo("Schedule", "Enter a saved-search id.")
            return
        try:
            sc = data.schedule_saved_search(
                int(raw), cron=self.sched_cron.get() or "daily",
                notify_actor=self.sched_notify.get().strip() or None)
        except ValidationError as e:
            messagebox.showerror("Schedule", str(e))
            return
        messagebox.showinfo(
            "Schedule",
            f"Scheduled #{sc.schedule_id}: saved #{sc.saved_id} "
            f"every {sc.cron}"
            + (f", notifying {sc.notify_actor}" if sc.notify_actor else ""))

    def _list_schedules(self) -> None:
        rows = data.list_scheduled_searches()
        lines = [f"#{s.schedule_id}  saved #{s.saved_id}  {s.cron:<8} "
                 f"{'on' if s.enabled else 'off':<3}  "
                 f"last {s.last_run_at or '—'}  "
                 f"(+{s.new_since_last}/{s.last_count})" for s in rows]
        self._show_text("Scheduled searches",
                        "\n".join(lines) or "(none scheduled)")

    def _run_schedule(self) -> None:
        raw = self.sched_id.get().strip()
        if not raw.isdigit():
            messagebox.showinfo("Run schedule", "Enter a schedule id.")
            return
        try:
            res = data.run_scheduled_search(int(raw))
        except ValidationError as e:
            messagebox.showerror("Run schedule", str(e))
            return
        messagebox.showinfo(
            "Run schedule",
            f"Ran schedule #{raw}: {res.total} hit(s).")

    def _delete_schedule(self) -> None:
        raw = self.sched_id.get().strip()
        if not raw.isdigit():
            messagebox.showinfo("Delete schedule", "Enter a schedule id.")
            return
        ok = data.delete_scheduled_search(int(raw))
        messagebox.showinfo("Delete schedule",
                            "Deleted." if ok else "Not found.")

    # ── Operator action log viewer (feature 25) ───────────────────

    def _action_log(self) -> None:
        rows = _read_action_log()
        lines = [f"{r.get('ts', ''):<20} {r.get('action', ''):<14} "
                 f"×{r.get('count', 0):<4} {r.get('detail', '')}"
                 for r in reversed(rows[-200:])]
        self._show_text("Operator action log",
                        "\n".join(lines) or "(no actions recorded yet)")
