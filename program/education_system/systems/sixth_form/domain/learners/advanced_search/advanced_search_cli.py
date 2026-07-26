"""CLI flows for Sixth Form Advanced Search."""

from __future__ import annotations

import datetime as _dt
import json
import logging
import random
import re
from pathlib import Path
from typing import Any, Callable
from education_system.systems.sixth_form.infrastructure import paths
from education_system.systems.sixth_form.domain.learners.advanced_search import (
    advanced_search as data,
)
from education_system.systems.sixth_form.domain.learners.advanced_search.advanced_search import (
    ALL_SCOPES,
    DEFAULT_LIMIT_PER_SCOPE,
    Hit,
    QUERY_SYNTAX_HELP,
    SavedSearch,
    SCOPE_LABELS,
    SearchResults,
    ValidationError,
)

logger = logging.getLogger(__name__)

# Session state shared across flows: the most recent result set (so
# random/within/facets/pivot/etc. can operate on it), the A/B compare
# slots, and per-query key snapshots for diff-since-last-run.
_LAST_RESULTS: SearchResults | None = None
_CMP_SLOTS: dict[str, dict] = {}
_PREV_KEYS: dict[str, set] = {}
_ANN_UNDO: list[tuple[str, str]] = []      # (label, json snapshot) for undo


class _UserAbort(Exception):
    pass


# ── Overlay stores (shared with the GUI) ───────────────────────────
#
# Tags, flags, owners, notes, workflow assignments and watchlists are
# advanced-search *overlay* metadata — deliberately NOT written into the
# domain tables. They live in the same JSON documents the GUI uses, so a
# flag added from the CLI is visible in the GUI and vice-versa.

_ANN_STORE_NAME = "advanced_search_annotations.json"
_UI_STORE_NAME = "advanced_search_ui.json"
_ACTION_LOG_NAME = "advanced_search_action_log.json"


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
    _save_json(_ann_store_path(), store)


def _ann_key(scope: str, entity_id: str) -> str:
    return f"{scope}:{entity_id}"


def _get_annotation(scope: str, entity_id: str) -> dict:
    return _load_ann_store().get(_ann_key(scope, entity_id), {})


def _ui_store_path() -> Path:
    return paths.DATA_DIR / _UI_STORE_NAME


def _load_ui_store() -> dict:
    try:
        with open(_ui_store_path(), encoding="utf-8") as fh:
            store = json.load(fh)
        if isinstance(store, dict):
            store.setdefault("watchlists", {})
            store.setdefault("pinned_queries", [])
            return store
    except (OSError, ValueError):
        pass
    return {"templates": {}, "presets": {}, "layouts": {},
            "watchlists": {}, "pinned_queries": []}


def _save_ui_store(store: dict) -> None:
    _save_json(_ui_store_path(), store)


def _append_action_log(action: str, detail: str = "", count: int = 0) -> None:
    """Record an operator action (flag/message/export…) to the shared log."""
    try:
        path = paths.DATA_DIR / _ACTION_LOG_NAME
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
        del log[:-500]
        _save_json(path, log)
    except (OSError, ValueError):
        logger.warning("could not append action log", exc_info=True)


def _read_action_log() -> list[dict]:
    try:
        with open(paths.DATA_DIR / _ACTION_LOG_NAME, encoding="utf-8") as fh:
            loaded = json.load(fh)
        if isinstance(loaded, list):
            return loaded
    except (OSError, ValueError):
        pass
    return []


def _save_json(path: Path, obj) -> None:
    """Atomically write *obj* as JSON. Failures are logged, not raised."""
    try:
        paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2)
        tmp.replace(path)
    except OSError:
        logger.warning("could not persist %s", path.name, exc_info=True)


# ── Phonetic / fuzzy matching (mirrors the GUI) ────────────────────

def _soundex(word: str) -> str:
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
            if tsdx and wsdx and tsdx[1:] == wsdx[1:] and ratio >= 0.6:
                return True
            if ratio >= 0.82:
                return True
    return False


def _sparkline(values: list) -> str:
    nums = [float(v) for v in values if isinstance(v, (int, float))]
    if not nums:
        return ""
    blocks = "▁▂▃▄▅▆▇█"
    lo, hi = min(nums), max(nums)
    span = (hi - lo) or 1.0
    return "".join(blocks[min(len(blocks) - 1,
                              int((v - lo) / span * (len(blocks) - 1)))]
                   for v in nums)


# ── Prompt helpers ─────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "",
            allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    if not s:
        if default:
            return default
        if not allow_empty:
            print("    Value is required.")
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _pick_scopes(default: list[str] | None = None) -> list[str]:
    """Ask the user which scopes to include. Empty = all."""
    print("\n  Scopes (Enter for all; comma list e.g. 'students,staff'):")
    for i, s in enumerate(ALL_SCOPES, 1):
        marker = " *" if default and s in default else "  "
        print(f"    {marker}{i:>2}) {SCOPE_LABELS[s]:<22} ({s})")
    while True:
        raw = _input("  Scopes",
                      default=",".join(default) if default else "")
        if not raw:
            return list(ALL_SCOPES)
        tokens = [t.strip() for t in raw.replace(" ", "").split(",")
                   if t.strip()]
        # Allow numeric picks too
        resolved: list[str] = []
        ok = True
        for t in tokens:
            if t.isdigit():
                n = int(t)
                if 1 <= n <= len(ALL_SCOPES):
                    resolved.append(ALL_SCOPES[n - 1])
                else:
                    print(f"    Out of range: {t}")
                    ok = False
                    break
            elif t in ALL_SCOPES:
                resolved.append(t)
            else:
                print(f"    Unknown scope: {t!r}")
                ok = False
                break
        if not ok:
            continue
        return resolved


# ── Print helpers ──────────────────────────────────────────────────

def _print_results(results: SearchResults) -> None:
    if results.total == 0:
        print(f"\n  No hits for query {results.query!r}.")
        if results.suggestions:
            print(f"  Did you mean:  {results.suggestions[0]}")
        return
    print(f"\n  {results.total} hit(s) for query {results.query!r}.")
    for scope in results.scopes:
        hits = results.hits_by_scope.get(scope, [])
        if not hits:
            continue
        label = SCOPE_LABELS.get(scope, scope)
        print(f"\n  ── {label} ({len(hits)}) ──")
        for h in hits:
            print(f"    [{scope}#{h.entity_id}]  {h.label}")
            if h.sublabel:
                print(f"        {h.sublabel}")
            if h.matched_field:
                print(f"        ({h.matched_field})")


def _print_saved(rows: list[SavedSearch]) -> None:
    if not rows:
        print("\n  (no saved searches)")
        return
    print()
    print(f"  {'#':>4}  {'Name':<24}  {'Query':<26}  Scopes")
    print("  " + "-" * 90)
    for s in rows:
        scopes = ",".join(s.scopes) if s.scopes else "(all)"
        q = s.query or "(empty)"
        print(f"  {s.saved_id:>4}  {s.name[:24]:<24}  "
              f"{q[:26]:<26}  {scopes}")
    print(f"\n  {len(rows)} saved.")


# ── Result-set helpers (session state) ─────────────────────────────

def _hit_student_id(h: Hit) -> str:
    if h.scope == "students":
        return h.entity_id
    if h.scope in data._STUDENT_KEYED_SCOPES:
        doc = (h.extra or {}).get("_doc") or {}
        return str(doc.get("name") or "").strip()
    return ""


def _results_from_hits(hits: list[Hit], query: str) -> SearchResults:
    by_scope: dict[str, list[Hit]] = {}
    for h in hits:
        by_scope.setdefault(h.scope, []).append(h)
    return SearchResults(
        query=query, scopes=list(by_scope.keys()),
        hits_by_scope=by_scope, total=len(hits),
        ranked_hits=list(hits), suggestions=[])


def _store_last(results: SearchResults) -> SearchResults:
    """Remember *results* as the current set and record which keys are new
    versus the previous run of the same query (diff-since-last-run)."""
    global _LAST_RESULTS
    _LAST_RESULTS = results
    cur = {f"{h.scope}#{h.entity_id}" for h in results.all_hits()}
    prev = _PREV_KEYS.get(results.query, set())
    results_new = cur - prev if prev else set()
    _PREV_KEYS[results.query] = cur
    _LAST_RESULTS._new_keys = results_new     # type: ignore[attr-defined]
    return results


def _require_last() -> SearchResults | None:
    if _LAST_RESULTS is None or _LAST_RESULTS.total == 0:
        print("\n  No current results — run a search first.")
        _pause()
        return None
    return _LAST_RESULTS


def _pick_hits_from_last() -> list[Hit]:
    """Let the user pick records from the current result set by entity id
    (comma list) or 'all'. Returns the chosen hits."""
    res = _require_last()
    if res is None:
        return []
    _print_results(res)
    raw = _input("Entity ids to act on (comma list, or 'all')",
                 default="all")
    hits = res.all_hits()
    if raw.lower() in ("all", ""):
        return hits
    ids = {t.strip() for t in raw.split(",") if t.strip()}
    sel = [h for h in hits if h.entity_id in ids]
    if not sel:
        print("  No matching records in the current results.")
    return sel


# ── Flows ──────────────────────────────────────────────────────────

def syntax_help() -> None:
    print("\n═══ Query Syntax ═══\n")
    for line in QUERY_SYNTAX_HELP.splitlines():
        print(f"  {line}")
    print("\n  Examples (copy into the query bar):")
    for desc, q in data.query_examples():
        print(f"    {desc:<38} {q}")
    _pause()


def quick_search() -> None:
    print("\n═══ Quick Search (all scopes) ═══")
    try:
        q = _input("Query (empty = list everything)")
        n = int(_input("Per-scope limit", default=str(DEFAULT_LIMIT_PER_SCOPE)))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = _store_last(data.run_search(q, limit_per_scope=n))
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_results(r)
    _pause()


def scoped_search() -> None:
    print("\n═══ Scoped Search ═══")
    try:
        q = _input("Query (empty = list)")
        scopes = _pick_scopes()
        n = int(_input("Per-scope limit", default=str(DEFAULT_LIMIT_PER_SCOPE)))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = _store_last(data.run_search(q, scopes=scopes, limit_per_scope=n))
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_results(r)
    _pause()


def search_one_scope() -> None:
    print("\n═══ Search a Single Scope ═══")
    try:
        scopes = _pick_scopes()
        q = _input("Query")
        n = int(_input("Per-scope limit",
                          default=str(DEFAULT_LIMIT_PER_SCOPE)))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if not scopes:
        scopes = list(ALL_SCOPES)
    try:
        r = _store_last(data.run_search(q, scopes=scopes, limit_per_scope=n))
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_results(r)
    _pause()


# ── Saved searches ────────────────────────────────────────────────

def list_saved() -> None:
    print("\n═══ Saved Searches ═══")
    _print_saved(data.list_saved_searches())
    _pause()


def new_saved() -> None:
    print("\n═══ New Saved Search ═══")
    try:
        name = _input("Name", allow_empty=False)
        q = _input("Query")
        scopes = _pick_scopes()
        notes = _input("Notes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        s = data.create_saved_search({
            "name": name, "query": q, "scopes": scopes, "notes": notes,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created saved search #{s.saved_id} {s.name!r}")
    _pause()


def edit_saved() -> None:
    print("\n═══ Edit Saved Search ═══")
    try:
        sid = int(_input("Saved ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_saved_search(sid)
    if existing is None:
        print(f"  ✗ No saved search #{sid}")
        _pause()
        return
    try:
        name = _input("Name", default=existing.name, allow_empty=False)
        q = _input("Query", default=existing.query)
        scopes = _pick_scopes(default=existing.scopes)
        notes = _input("Notes", default=existing.notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_saved_search(sid, {
            "name": name, "query": q, "scopes": scopes, "notes": notes,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{sid}")
    _pause()


def run_saved() -> None:
    print("\n═══ Run Saved Search ═══")
    saved = data.list_saved_searches()
    if not saved:
        print("\n  (no saved searches yet)")
        _pause()
        return
    _print_saved(saved)
    try:
        sid = int(_input("Saved ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = data.run_saved_search(sid)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_results(r)
    _pause()


def delete_saved() -> None:
    print("\n═══ Delete Saved Search ═══")
    try:
        sid = int(_input("Saved ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_saved_search(sid) is None:
        print(f"  ✗ No saved search #{sid}")
        _pause()
        return
    if _input(f"Delete saved search #{sid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_saved_search(sid):
        print(f"\n  ✓ Deleted #{sid}")
    _pause()


# ── History ───────────────────────────────────────────────────────

def show_history() -> None:
    print("\n═══ Search History ═══")
    rows = data.list_history(limit=50)
    if not rows:
        print("\n  (no history)")
        _pause()
        return
    print()
    print(f"  {'#':>4}  {'When':<19}  {'Hits':>5}  Query  ·  Scopes")
    print("  " + "-" * 90)
    for h in rows:
        scopes = ",".join(h.scopes) if h.scopes else "(all)"
        q = h.query or "(empty)"
        print(f"  {h.history_id:>4}  {h.ts[:19]:<19}  "
              f"{h.result_count:>5}  {q}  ·  {scopes}")
    print(f"\n  {len(rows)} entry/entries.")
    _pause()


def clear_history_flow() -> None:
    print("\n═══ Clear Search History ═══")
    if _input("Clear all history? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    n = data.clear_history()
    print(f"\n  ✓ Cleared {n} entry/entries.")
    _pause()


# ── New flows: filters, pinning, schedules, telemetry, infra ──────

def filtered_search() -> None:
    """Search with structured filters (year, tutor group, role, etc.)."""
    q = _input("Query (empty = list)")
    scopes = _pick_scopes()
    filters: dict[str, Any] = {}
    yr = _input("Year group (e.g. 12, blank=any)")
    if yr:
        filters["year_group"] = yr
    tg = _input("Tutor group name (blank=any)")
    if tg:
        filters["tutor_group"] = tg
    role = _input("Role (e.g. tutor; blank=admin)")
    if role:
        filters["role"] = role
    owner = _input("Owned by staff_id (blank=any)")
    if owner:
        filters["owned_by_staff"] = owner
    sen = _input("SEN only? y/N", default="n").lower().startswith("y")
    if sen:
        filters["sen_only"] = True
    inc_arch = _input("Include archived? y/N",
                       default="n").lower().startswith("y")
    if inc_arch:
        filters["include_archived"] = True
    actor = _input("Actor (for pinning boost; blank=none)")
    try:
        results = _store_last(data.run_search(
            q, scopes=scopes, filters=filters,
            actor=actor or None, interleave=True))
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        return
    _print_results(results)
    _pause()


def pin_flow() -> None:
    actor = _input("Your actor id", allow_empty=False)
    scope = _input(f"Scope (one of {','.join(ALL_SCOPES)})",
                    allow_empty=False)
    eid = _input("Entity id", allow_empty=False)
    label = _input("Label (optional)")
    try:
        p = data.pin_result(actor, scope, eid, label=label)
        print(f"\n  ✓ Pinned #{p.pin_id} ({p.scope}/{p.entity_id})")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    _pause()


def list_pins_flow() -> None:
    actor = _input("Actor (blank = all)")
    pins = data.list_pinned(actor or None)
    if not pins:
        print("\n  No pinned results.")
    else:
        print(f"\n  {len(pins)} pinned:")
        for p in pins:
            print(f"   #{p.pin_id}  {p.actor}  {p.scope}/{p.entity_id}"
                  f"  {p.label}")
    _pause()


def unpin_flow() -> None:
    actor = _input("Actor", allow_empty=False)
    scope = _input("Scope", allow_empty=False)
    eid = _input("Entity id", allow_empty=False)
    ok = data.unpin_result(actor, scope, eid)
    print(f"\n  {'✓ Unpinned' if ok else '✗ Not found'}")
    _pause()


def schedule_saved_flow() -> None:
    sid = _input("Saved-search id", allow_empty=False)
    cron = _input("Cron (e.g. daily/hourly)", default="daily")
    actor = _input("Notify actor", allow_empty=False)
    try:
        s = data.schedule_saved_search(
            int(sid), cron=cron, notify_actor=actor)
        print(f"\n  ✓ Scheduled #{s.schedule_id} cron={s.cron}")
    except (ValueError, ValidationError) as e:
        print(f"\n  ✗ {e}")
    _pause()


def list_schedules_flow() -> None:
    rows = data.list_scheduled_searches()
    if not rows:
        print("\n  No scheduled searches.")
    else:
        for r in rows:
            print(f"   #{r.schedule_id}  saved={r.saved_id}  "
                  f"cron={r.cron}  notify={r.notify_actor}  "
                  f"last_run={r.last_run_at or '—'}  "
                  f"last_count={r.last_count}  "
                  f"enabled={r.enabled}")
    _pause()


def poll_subscriptions_flow() -> None:
    fired = data.poll_subscriptions()
    print(f"\n  Polled. {len(fired)} subscription(s) fired.")
    for s in fired:
        print(f"   • #{s.schedule_id} → {s.notify_actor}")
    _pause()


def inbox_flow() -> None:
    actor = _input("Actor", allow_empty=False)
    unread = _input("Unread only? Y/n",
                     default="y").lower().startswith("y")
    rows = data.list_subscription_notifications(actor, unread_only=unread)
    if not rows:
        print("\n  (empty)")
    else:
        for r in rows:
            mark = "•" if not r.get("read_at") else " "
            print(f"   {mark} #{r['notif_id']}  "
                  f"+{r['delta']}/{r['total']}  "
                  f"{r.get('sample_scope') or ''}: "
                  f"{r.get('sample_label') or ''}")
    _pause()


def export_saved_flow() -> None:
    path = _input("Export file path (blank = print)")
    text = data.export_saved_searches()
    if path:
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            print(f"\n  ✓ Wrote {len(text)} chars to {path}")
        except OSError as e:
            print(f"\n  ✗ {e}")
    else:
        print("\n" + text)
    _pause()


def import_saved_flow() -> None:
    path = _input("Import file path", allow_empty=False)
    overwrite = _input("Overwrite existing? y/N",
                        default="n").lower().startswith("y")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        counts = data.import_saved_searches(text, overwrite=overwrite)
        print(f"\n  ✓ {counts}")
    except (OSError, ValidationError) as e:
        print(f"\n  ✗ {e}")
    _pause()


def telemetry_flow() -> None:
    ts = data.telemetry_summary()
    print(f"\n  Searches: {ts.total_searches}  "
          f"Zero-result: {ts.zero_result}")
    if ts.top_queries:
        print("\n  Top queries:")
        for q, n in ts.top_queries:
            print(f"   {n:>3}× {q!r}")
    if ts.slowest_scopes_ms:
        print("\n  Slowest scopes (avg ms):")
        for s, ms in ts.slowest_scopes_ms.items():
            print(f"   {s:<22} {ms:>8.1f}")
    if ts.zero_result_queries:
        print("\n  Recent zero-result queries:")
        for q in ts.zero_result_queries:
            print(f"   • {q!r}")
    _pause()


def refresh_index_flow() -> None:
    if not data._fts_available():
        print("\n  FTS5 is not available in this SQLite build.")
        _pause()
        return
    scopes = _pick_scopes()
    print("\n  Refreshing index...")
    counts = data.refresh_index(scopes)
    total = sum(counts.values())
    print(f"\n  ✓ Indexed {total} row(s) across "
          f"{len(counts)} scope(s).")
    for s, n in counts.items():
        print(f"   {s:<22} {n}")
    _pause()


def clear_cache_flow() -> None:
    data.clear_cache()
    print("\n  ✓ Search cache cleared.")
    _pause()


def suggest_flow() -> None:
    prefix = _input("Prefix")
    out = data.suggest(prefix, limit=10)
    if not out:
        print("\n  (no suggestions)")
    else:
        for s in out:
            print(f"   • {s}")
    _pause()


# ── Relational tools (items 11–17) ────────────────────────────────

_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def list_cohorts_flow() -> None:
    print("\n═══ Cohorts ═══")
    rows = data.list_cohorts()
    if not rows:
        print("\n  (no cohorts yet)")
    else:
        print()
        for c in rows:
            print(f"   #{c.cohort_id:<4} {c.name:<28} "
                  f"{c.member_count:>4} member(s)   {c.notes or ''}")
    _pause()


def save_cohort_flow() -> None:
    print("\n═══ Save Search Results as Cohort ═══")
    try:
        q = _input("Query")
        scopes = _pick_scopes()
        name = _input("Cohort name", allow_empty=False)
        notes = _input("Notes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        results = data.run_search(q, scopes=scopes, limit_per_scope=1000)
        c = data.create_cohort_from_results(
            name, results, notes=notes or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Cohort #{c.cohort_id} {c.name!r} "
          f"with {c.member_count} student(s).")
    _pause()


def cohort_members_flow() -> None:
    name = _input("Cohort name or id", allow_empty=False)
    members = data.cohort_members(name)
    if not members:
        print("\n  (empty or unknown cohort)")
    else:
        print(f"\n  {len(members)} member(s):")
        for sid in members:
            print(f"   • {sid}")
    _pause()


def delete_cohort_flow() -> None:
    name = _input("Cohort name or id", allow_empty=False)
    if _input(f"Delete cohort {name!r}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    print("\n  ✓ Deleted." if data.delete_cohort(name)
          else "\n  ✗ Not found.")
    _pause()


def family_flow() -> None:
    sid = _input("Student id", allow_empty=False)
    try:
        rels = data.find_relatives(sid)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if not rels:
        print("\n  No likely relatives found.")
    else:
        print(f"\n  {len(rels)} possible relative(s):")
        for r in rels:
            print(f"   • {r.student_id}  {r.full_name}  — {r.basis}")
    _pause()


def group_rollup_flow() -> None:
    gid = _input("Class group id", allow_empty=False)
    try:
        roll = data.group_rollup(int(gid))
    except (ValueError, ValidationError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    att = "—" if roll.avg_attendance is None else f"{roll.avg_attendance}%"
    print(f"\n  {roll.group_name}  (group #{roll.group_id})")
    print(f"   Members:           {roll.member_count}")
    print(f"   Avg attendance:    {att}")
    print(f"   Behaviour points:  {roll.behaviour_points} "
          f"({roll.behaviour_count} entries)")
    print(f"   Open concerns:     {roll.open_concerns}")
    _pause()


def ucas_peers_flow() -> None:
    uni = _input("University (substring)", allow_empty=False)
    course = _input("Course code (optional)")
    try:
        peers = data.ucas_peers(uni, course or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if not peers:
        print("\n  No matching applicants.")
    else:
        print(f"\n  {len(peers)} applicant(s):")
        for p in peers:
            print(f"   • {p.student_id}  {p.university} — "
                  f"{p.course_name} ({p.course_code or '—'})  [{p.status}]")
    _pause()


def ucas_clusters_flow() -> None:
    by_course = _input("Cluster by course too? y/N",
                       default="n").lower().startswith("y")
    cl = data.ucas_choice_clusters(by_course=by_course)
    if not cl:
        print("\n  No shared choices (min 2 applicants).")
    else:
        print()
        for c in cl[:30]:
            label = c.university + (f" / {c.course_code}"
                                    if c.course_code else "")
            print(f"   {len(c.student_ids):>3}×  {label}: "
                  f"{', '.join(c.student_ids)}")
    _pause()


def clashes_flow() -> None:
    cl = data.timetable_clashes()
    if not cl:
        print("\n  No timetable clashes detected.")
    else:
        print(f"\n  {len(cl)} clash(es):")
        for c in cl[:60]:
            d = _DAYS[c.day - 1] if 1 <= c.day <= 7 else f"day{c.day}"
            print(f"   [{c.kind:<7}] {d} P{c.period}  {c.detail}  "
                  f"groups={c.group_ids}")
    _pause()


def similar_flow() -> None:
    sid = _input("Student id", allow_empty=False)
    try:
        sim = data.similar_students(sid)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if not sim:
        print("\n  No similar students found.")
    else:
        print(f"\n  {len(sim)} similar:")
        for s in sim:
            print(f"   {s.score:>5}  {s.student_id}  {s.full_name}  "
                  f"— {'; '.join(s.shared)}")
    _pause()


# ── Alerts, dashboards, security, exports, analytics (26–50) ──────

def schedule_delta_flow() -> None:
    sid = _input("Scheduled-search id", allow_empty=False)
    try:
        d = data.schedule_delta(int(sid))
    except (ValueError, ValidationError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  Total now: {d.total}   +{len(d.added)} added   "
          f"-{len(d.removed)} removed")
    for k in d.added[:20]:
        print(f"   + {k}")
    for k in d.removed[:20]:
        print(f"   - {k}")
    _pause()


def digest_flow() -> None:
    actor = _input("Actor (blank = all)")
    dg = data.build_digest(actor or None)
    print(f"\n  Digest — {dg.total_new} new across "
          f"{len(dg.lines)} scheduled search(es):")
    for line in dg.lines:
        print(f"   {line.new_since_last:>4} new · total {line.total:<5} "
              f"{line.saved_name}  (last {line.last_run_at or '—'})")
    _pause()


def list_dashboards_flow() -> None:
    rows = data.list_dashboards()
    if not rows:
        print("\n  (no dashboards)")
    else:
        for d in rows:
            print(f"   #{d.dashboard_id:<4} {d.name:<26} "
                  f"{len(d.saved_ids)} panel(s)")
    _pause()


def create_dashboard_flow() -> None:
    name = _input("Dashboard name", allow_empty=False)
    ids = _input("Saved-search ids (comma-separated)")
    saved_ids = [int(x) for x in ids.replace(" ", "").split(",") if x.isdigit()]
    try:
        d = data.create_dashboard(name, saved_ids)
        print(f"\n  ✓ Dashboard #{d.dashboard_id} with "
              f"{len(d.saved_ids)} panel(s).")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    _pause()


def run_dashboard_flow() -> None:
    name = _input("Dashboard name or id", allow_empty=False)
    role = _input("Role (blank = admin)")
    try:
        panels = data.run_dashboard(name, role=role or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  {name}:")
    for p in panels:
        cnt = "err" if p.total < 0 else str(p.total)
        print(f"   {cnt:>5}  {p.name}   ({p.query or '(empty)'})")
    _pause()


def audit_flow() -> None:
    sens = _input("Sensitive only? y/N", default="n").lower().startswith("y")
    rows = data.list_search_audit(limit=50, sensitive_only=sens)
    if not rows:
        print("\n  (no audit entries)")
    else:
        for e in rows:
            bg = "  [BREAK-GLASS]" if e.break_glass else ""
            print(f"   {e.ts}  {e.actor or '—'}/{e.role or '—'}  "
                  f"{e.query!r}  sens={','.join(e.sensitive_scopes)}{bg}")
            if e.reason:
                print(f"       reason: {e.reason}")
    _pause()


def duplicates_flow() -> None:
    groups = data.find_duplicate_students()
    if not groups:
        print("\n  No likely duplicate students.")
    else:
        print(f"\n  {len(groups)} possible duplicate group(s):")
        for g in groups[:40]:
            print(f"   [{g.reason}] {g.key}: {', '.join(g.student_ids)}")
    _pause()


def data_gaps_flow() -> None:
    scope = _input("Scope", default="students")
    try:
        gaps = data.find_data_gaps(scope)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if not gaps:
        print("\n  No data gaps found.")
    else:
        print(f"\n  {len(gaps)} record(s) with gaps:")
        for g in gaps[:50]:
            print(f"   {g.entity_id}  {g.label[:40]:<40}  "
                  f"missing: {', '.join(g.missing)}")
    _pause()


def export_search_flow() -> None:
    q = _input("Query")
    scopes = _pick_scopes()
    fmt = _input("Format (csv/tsv/json/html/md/xlsx/pdf)", default="csv")
    path = _input("Output file path", allow_empty=False)
    try:
        r = data.run_search(q, scopes=scopes, limit_per_scope=1000)
        data.export_results_file(r, path, fmt=fmt)
        print(f"\n  ✓ Wrote {r.total} row(s) to {path}")
    except (ValidationError, OSError) as e:
        print(f"\n  ✗ {e}")
    _pause()


def contact_sheet_flow() -> None:
    q = _input("Query")
    scopes = _pick_scopes(default=["students"])
    path = _input("Output HTML path", allow_empty=False)
    try:
        r = data.run_search(q, scopes=scopes, limit_per_scope=1000)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(data.contact_sheet(r))
        print(f"\n  ✓ Contact sheet written to {path}")
    except (ValidationError, OSError) as e:
        print(f"\n  ✗ {e}")
    _pause()


def nl_query_flow() -> None:
    text = _input("Describe what you want", allow_empty=False)
    q = data.nl_to_query(text)
    if not q:
        print("\n  (couldn't translate — try the query syntax help)")
        _pause()
        return
    print(f"\n  Suggested query:  {q}")
    if _input("Run it? Y/n", default="y").lower().startswith("y"):
        _print_results(data.run_search(q, limit_per_scope=DEFAULT_LIMIT_PER_SCOPE))
    _pause()


def index_status_flow() -> None:
    rows = data.index_status()
    print()
    for s in rows:
        flag = "STALE" if s.stale else "ok"
        print(f"   {s.scope:<22} indexed {s.indexed_rows:>5} / "
              f"current {s.current_rows:>5}  [{flag}]  "
              f"{s.last_refresh or '—'}")
    if _input("\n  Refresh stale scopes now? y/N",
              default="n").lower().startswith("y"):
        counts = data.refresh_index(only_stale=True)
        print(f"\n  ✓ Refreshed {sum(counts.values())} row(s) across "
              f"{len(counts)} scope(s).")
    _pause()


def cache_stats_flow() -> None:
    st = data.cache_stats()
    print(f"\n  Cache: {st['entries']}/{st['max_entries']} entries  ·  "
          f"hits {st['hits']}  misses {st['misses']}  "
          f"hit-rate {st['hit_rate']:.0%}  ·  TTL {st['ttl_seconds']}s")
    _pause()


def volume_flow() -> None:
    rows = data.search_volume_by_day()
    if not rows:
        print("\n  (no search history)")
    else:
        print("\n  Searches per day:")
        for d, n in rows:
            print(f"   {d}  {'█' * min(n, 40)} {n}")
    _pause()


# ══════════════════════════════════════════════════════════════════
# CLI equivalents of the advanced-search GUI features
# ══════════════════════════════════════════════════════════════════

# ── Query builders (boolean / phonetic / regex) ────────────────────

def boolean_builder_flow() -> None:
    """Build a query from field/value clauses without knowing the DSL."""
    print("\n═══ Boolean Query Builder ═══")
    print("  Enter clauses; blank field name finishes.")
    fields = ["name", "status", "subject", "tutor_group", "year",
              "email", "note", "keyword"]
    print("  Fields: " + ", ".join(fields))
    parts: list[str] = []
    try:
        while True:
            field = _input("Field (blank = done)")
            if not field:
                break
            if field not in fields:
                print(f"    Unknown field {field!r}.")
                continue
            value = _input("Value", allow_empty=False)
            neg = _input("Negate (exclude)? y/N",
                         default="n").lower().startswith("y")
            join = "AND"
            if parts:
                join = _input("Join with previous (AND/OR)",
                              default="AND").upper()
            term = value if " " not in value else f'"{value}"'
            clause = term if field == "keyword" else f"{field}:{term}"
            if neg:
                clause = f"-{clause}"
            if parts and join == "OR":
                clause = f"OR {clause}"
            parts.append(clause)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    query = " ".join(parts)
    if not query:
        print("\n  Nothing built.")
        _pause()
        return
    print(f"\n  Query:  {query}")
    if _input("Run it? Y/n", default="y").lower().startswith("y"):
        try:
            _print_results(_store_last(
                data.run_search(query, limit_per_scope=DEFAULT_LIMIT_PER_SCOPE)))
        except ValidationError as e:
            print(f"\n  ✗ {e}")
    _pause()


def phonetic_search_flow() -> None:
    """Search, then keep only hits that phonetically/fuzzily match a name
    (so 'Catherine' finds 'Katharine')."""
    print("\n═══ Phonetic / Fuzzy Search ═══")
    try:
        name = _input("Name to match (phonetically)", allow_empty=False)
        scopes = _pick_scopes()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        base = data.run_search("", scopes=scopes, limit_per_scope=1000)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    kept = [h for h in base.all_hits()
            if _phonetic_match(name, f"{h.label} {h.sublabel}")]
    res = _store_last(_results_from_hits(kept, f"phonetic:{name}"))
    print(f"\n  {len(kept)} of {base.total} record(s) match {name!r} "
          f"phonetically.")
    _print_results(res)
    _pause()


def regex_search_flow() -> None:
    """Filter results by a regular expression over id/label/details."""
    print("\n═══ Regex Search ═══")
    try:
        pattern = _input("Regex pattern", allow_empty=False)
        scopes = _pick_scopes()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        print(f"\n  ✗ invalid regex: {e}")
        _pause()
        return
    try:
        base = data.run_search("", scopes=scopes, limit_per_scope=1000)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    kept = [h for h in base.all_hits()
            if rx.search(h.entity_id or "") or rx.search(h.label or "")
            or rx.search(h.sublabel or "")]
    res = _store_last(_results_from_hits(kept, f"regex:{pattern}"))
    print(f"\n  {len(kept)} of {base.total} record(s) match /{pattern}/.")
    _print_results(res)
    _pause()


# ── Operations on the current result set ───────────────────────────

def random_sample_flow() -> None:
    res = _require_last()
    if res is None:
        return
    try:
        n = int(_input("How many to sample", default="10"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    pool = res.all_hits()
    sample = random.sample(pool, min(n, len(pool)))
    out = _store_last(_results_from_hits(
        sample, f"random {len(sample)} of {len(pool)}"))
    _print_results(out)
    _pause()


def within_results_flow() -> None:
    res = _require_last()
    if res is None:
        return
    term = _input("Filter current results by text", allow_empty=False)
    needle = term.lower()
    kept = [h for h in res.all_hits()
            if needle in (h.entity_id or "").lower()
            or needle in (h.label or "").lower()
            or needle in (h.sublabel or "").lower()]
    out = _store_last(_results_from_hits(
        kept, f"{res.query}  (within: {term})"))
    print(f"\n  {len(kept)} of {res.total} matched {term!r} within results.")
    _print_results(out)
    _pause()


def estimate_flow() -> None:
    """Cheap per-scope hit estimate before committing to a full search."""
    print("\n═══ Estimate Hit Count ═══")
    try:
        q = _input("Query (empty = list)")
        scopes = _pick_scopes()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        preview = data.run_search(q, scopes=scopes, limit_per_scope=5,
                                  record_history=False)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  Estimate for {q or '(empty)'!r} (sampled, cap 5/scope):")
    for s in preview.scopes:
        n = len(preview.hits_by_scope.get(s, []))
        cap = "≥5 (capped)" if n >= 5 else str(n)
        print(f"   {SCOPE_LABELS.get(s, s):<24} {cap}")
    print(f"\n  Sampled total: {preview.total}")
    _pause()


def facets_flow() -> None:
    """Show value distributions across the current results (narrow-by)."""
    res = _require_last()
    if res is None:
        return
    fcs = data.facets(res, top=8)
    if not fcs:
        print("\n  No facetable fields in the current results.")
        _pause()
        return
    print("\n  Narrow by:")
    for f in fcs:
        print(f"\n   {f.field}:")
        for val, cnt in f.values:
            print(f"     {cnt:>4}×  {val}")
    _pause()


def pivot_flow() -> None:
    """Crosstab of scope × status/risk across the current results."""
    res = _require_last()
    if res is None:
        return
    statuses: list[str] = []
    matrix: dict[str, dict[str, int]] = {}
    for h in res.all_hits():
        doc = (h.extra or {}).get("_doc") or {}
        st = str(doc.get("status") or doc.get("level") or "—").strip() or "—"
        if st not in statuses:
            statuses.append(st)
        row = matrix.setdefault(SCOPE_LABELS.get(h.scope, h.scope), {})
        row[st] = row.get(st, 0) + 1
    statuses = statuses[:8]
    header = f"  {'scope':<22}" + "".join(f"{s[:10]:>11}" for s in statuses)
    header += f"{'Σ':>8}"
    print("\n" + header)
    print("  " + "-" * (len(header) - 2))
    for scope, row in matrix.items():
        cells = "".join(f"{row.get(s, 0):>11}" for s in statuses)
        print(f"  {scope:<22}{cells}{sum(row.values()):>8}")
    _pause()


def cross_scope_flow() -> None:
    """Students that appear in two or more scopes of the current results."""
    res = _require_last()
    if res is None:
        return
    by_student: dict[str, dict[str, Hit]] = {}
    for h in res.all_hits():
        sid = _hit_student_id(h)
        if sid:
            by_student.setdefault(sid, {})[h.scope] = h
    overlaps = {sid: sc for sid, sc in by_student.items() if len(sc) >= 2}
    if not overlaps:
        print("\n  No student appears in two or more scopes.")
        _pause()
        return
    print(f"\n  {len(overlaps)} student(s) span multiple scopes:")
    for sid, sc in sorted(overlaps.items(), key=lambda kv: -len(kv[1])):
        label = next(iter(sc.values())).label
        print(f"   {sid}  {label[:32]:<32}  in {len(sc)}: "
              f"{', '.join(sorted(sc))}")
    _pause()


def grouped_view_flow() -> None:
    """Re-group the current results by year / tutor / risk (or a pair)."""
    res = _require_last()
    if res is None:
        return
    mode = _input("Group by (scope/year/tutor/risk, or e.g. year+risk)",
                  default="year").lower()
    parts = mode.split("+")
    gidx = {}
    if "year" in mode or "tutor" in mode:
        try:
            gidx = data.student_group_index()
        except Exception:
            gidx = {}

    def _key1(m: str, h: Hit) -> str:
        if m == "scope":
            return SCOPE_LABELS.get(h.scope, h.scope)
        if m == "risk":
            doc = (h.extra or {}).get("_doc") or {}
            return f"Risk: {doc.get('level') or '—'}"
        sid = _hit_student_id(h)
        if not sid:
            return "(non-student)"
        yr, tg = gidx.get(sid, (None, None))
        if m == "year":
            return f"Year {yr}" if yr is not None else "Year —"
        if m == "tutor":
            return f"Tutor {tg}" if tg else "Tutor —"
        return SCOPE_LABELS.get(h.scope, h.scope)

    groups: dict[str, list[Hit]] = {}
    for h in res.all_hits():
        key = "  ·  ".join(_key1(p, h) for p in parts)
        groups.setdefault(key, []).append(h)
    print(f"\n  {res.total} hit(s) grouped by {mode}:")
    for key in sorted(groups):
        hits = groups[key]
        print(f"\n  ── {key}  ({len(hits)}) ──")
        for h in hits:
            print(f"    [{h.scope}#{h.entity_id}]  {h.label}")
    _pause()


def diff_last_flow() -> None:
    """Show which records are new in the current results versus the
    previous run of the same query."""
    res = _require_last()
    if res is None:
        return
    new_keys = getattr(res, "_new_keys", set())
    if not new_keys:
        print("\n  No new records since the previous run of this query "
              "(or this is its first run).")
        _pause()
        return
    print(f"\n  {len(new_keys)} new record(s) since the last run of "
          f"{res.query!r}:")
    for h in res.all_hits():
        if f"{h.scope}#{h.entity_id}" in new_keys:
            print(f"   + [{h.scope}#{h.entity_id}]  {h.label}")
    _pause()


# ── Compare two result sets (A / B) ────────────────────────────────

def compare_capture_flow() -> None:
    res = _require_last()
    if res is None:
        return
    slot = _input("Capture current results into slot (A/B)",
                  default="A").upper()
    if slot not in ("A", "B"):
        print("\n  Slot must be A or B.")
        return
    _CMP_SLOTS[slot] = {
        "query": res.query,
        "keys": {f"{h.scope}#{h.entity_id}": h.label for h in res.all_hits()},
    }
    print(f"\n  ✓ Captured slot {slot} "
          f"({len(_CMP_SLOTS[slot]['keys'])} hits) for {res.query!r}.")
    _pause()


def compare_show_flow() -> None:
    if "A" not in _CMP_SLOTS or "B" not in _CMP_SLOTS:
        print("\n  Capture both slot A and slot B first.")
        _pause()
        return
    a, b = _CMP_SLOTS["A"], _CMP_SLOTS["B"]
    ka, kb = set(a["keys"]), set(b["keys"])
    only_a, only_b, both = sorted(ka - kb), sorted(kb - ka), ka & kb
    print(f"\n  A: {a['query']!r}  ({len(ka)} hits)")
    print(f"  B: {b['query']!r}  ({len(kb)} hits)")
    print(f"  In both: {len(both)}")
    print(f"\n  ── Only in A ({len(only_a)}) ──")
    for k in only_a[:60]:
        print(f"   {a['keys'][k]}  [{k}]")
    print(f"\n  ── Only in B ({len(only_b)}) ──")
    for k in only_b[:60]:
        print(f"   {b['keys'][k]}  [{k}]")
    _pause()


# ── Watchlists ─────────────────────────────────────────────────────

def watchlist_add_flow() -> None:
    hits = _pick_hits_from_last()
    if not hits:
        _pause()
        return
    name = _input("Watchlist name", allow_empty=False)
    store = _load_ui_store()
    wl = store.setdefault("watchlists", {}).setdefault(name, [])
    have = {(m["scope"], m["entity_id"]) for m in wl}
    added = 0
    for h in hits:
        if (h.scope, h.entity_id) not in have:
            wl.append({"scope": h.scope, "entity_id": h.entity_id,
                       "label": h.label})
            added += 1
    _save_ui_store(store)
    print(f"\n  ✓ Added {added} to watchlist {name!r} ({len(wl)} total).")
    _pause()


def watchlist_list_flow() -> None:
    wls = _load_ui_store().get("watchlists", {})
    if not wls:
        print("\n  (no watchlists)")
    else:
        print()
        for name, members in sorted(wls.items()):
            print(f"   {name:<24} {len(members):>4} member(s)")
    _pause()


def watchlist_load_flow() -> None:
    name = _input("Watchlist name", allow_empty=False)
    members = _load_ui_store().get("watchlists", {}).get(name, [])
    if not members:
        print(f"\n  Watchlist {name!r} is empty or unknown.")
        _pause()
        return
    hits = [Hit(scope=m["scope"], entity_id=m["entity_id"],
                label=m.get("label", m["entity_id"]))
            for m in members]
    _print_results(_store_last(_results_from_hits(hits, f"watchlist:{name}")))
    _pause()


def watchlist_delete_flow() -> None:
    name = _input("Watchlist name", allow_empty=False)
    store = _load_ui_store()
    if store.get("watchlists", {}).pop(name, None) is not None:
        _save_ui_store(store)
        print(f"\n  ✓ Deleted watchlist {name!r}.")
    else:
        print(f"\n  ✗ No watchlist {name!r}.")
    _pause()


# ── Message students (mail-merge) ──────────────────────────────────

def message_flow() -> None:
    res = _require_last()
    if res is None:
        return
    try:
        subject = _input("Subject", allow_empty=False)
        body = _input("Body")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    send = _input("Send now (else draft only)? y/N",
                  default="n").lower().startswith("y")
    try:
        r = data.mailmerge_results(res, subject=subject, body=body, send=send)
    except Exception as e:                       # noqa: BLE001
        print(f"\n  ✗ {e}")
        _pause()
        return
    verb = "Sent" if send else "Drafted"
    _append_action_log("message", f"{verb}: {subject}", r.get("recipients", 0))
    print(f"\n  ✓ {verb} {r['created']} message(s) to "
          f"{r['recipients']} student(s) (thread {r['thread_id']}).")
    _pause()


def redacted_search_flow() -> None:
    """Search with sensitive fields redacted (safe mode / break-glass)."""
    print("\n═══ Safe (Redacted) Search ═══")
    try:
        q = _input("Query (empty = list)")
        scopes = _pick_scopes()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    reason = _input("Break-glass reason (blank = redacted view only)")
    filters: dict[str, Any] = {"redact": True}
    if reason:
        filters["break_glass"] = reason
    try:
        r = _store_last(data.run_search(
            q, scopes=scopes, filters=filters, limit_per_scope=1000))
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_results(r)
    _pause()


def action_log_flow() -> None:
    """Show the operator action log (flags/messages/exports…)."""
    rows = _read_action_log()
    if not rows:
        print("\n  (no operator actions recorded yet)")
        _pause()
        return
    print("\n  Operator action log (most recent last):")
    for r in rows[-100:]:
        print(f"   {r.get('ts', ''):<20} {r.get('action', ''):<12} "
              f"×{r.get('count', 0):<4} {r.get('detail', '')}")
    _pause()


# ── Annotations (tags / flags / notes / owner / workflow) ──────────

def _snapshot_ann(label: str) -> None:
    _ANN_UNDO.append((label, json.dumps(_load_ann_store())))
    del _ANN_UNDO[:-20]


_FLAG_CODES = ("safeguarding", "attendance", "behaviour", "academic",
               "pastoral", "sen", "medical", "other")


def flag_flow() -> None:
    hits = _pick_hits_from_last()
    if not hits:
        _pause()
        return
    print("  Reason codes: " + ", ".join(_FLAG_CODES))
    code = _input("Flag reason code", default="other")
    reason = _input("Reason detail (optional)")
    ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    _snapshot_ann("flag")
    store = _load_ann_store()
    for h in hits:
        ann = store.setdefault(_ann_key(h.scope, h.entity_id), {})
        ann.setdefault("flags", []).append(
            {"code": code, "reason": reason, "ts": ts})
        tags = ann.setdefault("tags", [])
        if "flag" not in tags:
            tags.append("flag")
    _save_ann_store(store)
    _append_action_log("flag", f"{code}: {reason}", len(hits))
    print(f"\n  ✓ Flagged {len(hits)} record(s) as {code!r}.")
    _pause()


def tag_flow() -> None:
    hits = _pick_hits_from_last()
    if not hits:
        _pause()
        return
    raw = _input("Tags (comma list; prefix '-' to remove)", allow_empty=False)
    parts = [t.strip() for t in raw.split(",") if t.strip()]
    add = [t for t in parts if not t.startswith("-")]
    remove = {t[1:] for t in parts if t.startswith("-")}
    _snapshot_ann("tag")
    store = _load_ann_store()
    for h in hits:
        ann = store.setdefault(_ann_key(h.scope, h.entity_id), {})
        tags = ann.get("tags", [])
        for t in add:
            if t not in tags:
                tags.append(t)
        ann["tags"] = [t for t in tags if t not in remove]
    _save_ann_store(store)
    print(f"\n  ✓ Updated tags on {len(hits)} record(s).")
    _pause()


def note_flow() -> None:
    hits = _pick_hits_from_last()
    if not hits:
        _pause()
        return
    text = _input("Note text", allow_empty=False)
    ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    _snapshot_ann("note")
    store = _load_ann_store()
    for h in hits:
        ann = store.setdefault(_ann_key(h.scope, h.entity_id), {})
        ann.setdefault("notes", []).append({"ts": ts, "text": text})
    _save_ann_store(store)
    print(f"\n  ✓ Added note to {len(hits)} record(s).")
    _pause()


def assign_owner_flow() -> None:
    hits = _pick_hits_from_last()
    if not hits:
        _pause()
        return
    owner = _input("Owning staff (blank = clear)")
    _snapshot_ann("assign owner")
    store = _load_ann_store()
    for h in hits:
        ann = store.setdefault(_ann_key(h.scope, h.entity_id), {})
        if owner:
            ann["owner"] = owner
        else:
            ann.pop("owner", None)
    _save_ann_store(store)
    print(f"\n  ✓ {'Assigned' if owner else 'Cleared'} owner on "
          f"{len(hits)} record(s).")
    _pause()


def assign_workflow_flow() -> None:
    hits = _pick_hits_from_last()
    if not hits:
        _pause()
        return
    owner = _input("Owning staff", allow_empty=False)
    due = _input("Due date (YYYY-MM-DD, optional)")
    ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    _snapshot_ann("assign workflow")
    store = _load_ann_store()
    for h in hits:
        ann = store.setdefault(_ann_key(h.scope, h.entity_id), {})
        ann["workflow"] = {"owner": owner, "due": due,
                           "state": "open", "ts": ts}
    _save_ann_store(store)
    _append_action_log("assign workflow", owner, len(hits))
    print(f"\n  ✓ Assigned {len(hits)} record(s) to {owner!r}.")
    _pause()


def view_annotations_flow() -> None:
    scope = _input(f"Scope (one of {','.join(ALL_SCOPES)})",
                   allow_empty=False)
    eid = _input("Entity id", allow_empty=False)
    ann = _get_annotation(scope, eid)
    if not ann:
        print("\n  (no annotations on this record)")
        _pause()
        return
    print(f"\n  Annotations for {scope}#{eid}:")
    if ann.get("tags"):
        print("   tags: " + ", ".join(ann["tags"]))
    for flag in ann.get("flags", []):
        print(f"   ⚑ flag [{flag.get('code', '?')}]: {flag.get('reason', '')}"
              f"  ({flag.get('ts', '')})")
    if ann.get("owner"):
        print(f"   owner: {ann['owner']}")
    wf = ann.get("workflow")
    if wf:
        print(f"   → workflow: {wf.get('owner', '?')} "
              f"(due {wf.get('due', '—')}) [{wf.get('state', 'open')}]")
    if ann.get("merged_into"):
        print(f"   ⚠ merged into: {ann['merged_into']}")
    for note in ann.get("notes", []):
        print(f"   note ({note.get('ts', '')}): {note.get('text', '')}")
    _pause()


def undo_annotation_flow() -> None:
    if not _ANN_UNDO:
        print("\n  Nothing to undo.")
        _pause()
        return
    label, snap = _ANN_UNDO.pop()
    try:
        _save_ann_store(json.loads(snap))
    except ValueError:
        print("\n  ✗ Undo failed (corrupt snapshot).")
        _pause()
        return
    print(f"\n  ✓ Undid: {label}.")
    _pause()


# ── Bulk student status change ─────────────────────────────────────

def bulk_status_flow() -> None:
    """Change the status of selected students in the current results."""
    res = _require_last()
    if res is None:
        return
    from education_system.systems.sixth_form.domain.learners.\
        students.students import get_student, update_student, STATUSES
    hits = [h for h in _pick_hits_from_last() if h.scope == "students"]
    if not hits:
        print("\n  No student records selected.")
        _pause()
        return
    print("  Statuses: " + ", ".join(STATUSES))
    new = _input("New status", allow_empty=False)
    if new not in STATUSES:
        print(f"\n  ✗ Unknown status {new!r}.")
        _pause()
        return
    if _input(f"Set status to {new!r} for {len(hits)} student(s)? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    ok = errs = 0
    fields = ("first_name", "middle_name", "last_name", "title", "gender",
              "date_of_birth", "phone", "emergency_contact_name",
              "emergency_contact_phone", "emergency_contact_relation",
              "subject_1", "subject_2", "subject_3", "status")
    for h in hits:
        try:
            stu = get_student(h.entity_id)
            if stu is None:
                errs += 1
                continue
            payload = {f: getattr(stu, f) for f in fields}
            payload["status"] = new
            update_student(h.entity_id, payload)
            ok += 1
        except Exception:                        # noqa: BLE001
            errs += 1
    _append_action_log("bulk status", new, ok)
    print(f"\n  ✓ Status → {new!r}: {ok} updated"
          + (f", {errs} failed" if errs else "") + ".")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Quick search (all scopes)",  quick_search),
    ("Scoped search",              scoped_search),
    ("Single-scope search",        search_one_scope),
    ("Filtered search (advanced)", filtered_search),
    ("Boolean query builder",      boolean_builder_flow),
    ("Phonetic / fuzzy search",    phonetic_search_flow),
    ("Regex search",               regex_search_flow),
    ("Safe (redacted) search",     redacted_search_flow),
    ("Estimate hit count",         estimate_flow),
    ("Suggest (type-ahead)",       suggest_flow),
    ("Query syntax help",          syntax_help),
    ("─" * 6,                      lambda: None),
    ("Current results: random sample", random_sample_flow),
    ("Current results: filter within", within_results_flow),
    ("Current results: group by…", grouped_view_flow),
    ("Current results: facets (narrow)", facets_flow),
    ("Current results: pivot (scope×status)", pivot_flow),
    ("Current results: cross-scope overlap", cross_scope_flow),
    ("Current results: new since last run", diff_last_flow),
    ("Current results: message students", message_flow),
    ("Compare: capture A/B",       compare_capture_flow),
    ("Compare: show A vs B",       compare_show_flow),
    ("─" * 6,                      lambda: None),
    ("Annotate: flag with reason", flag_flow),
    ("Annotate: tag",              tag_flow),
    ("Annotate: add note",         note_flow),
    ("Annotate: assign owner",     assign_owner_flow),
    ("Annotate: assign to workflow", assign_workflow_flow),
    ("Annotate: view for a record", view_annotations_flow),
    ("Annotate: undo last change", undo_annotation_flow),
    ("Bulk: change student status", bulk_status_flow),
    ("Watchlists: add current",    watchlist_add_flow),
    ("Watchlists: list",           watchlist_list_flow),
    ("Watchlists: load",           watchlist_load_flow),
    ("Watchlists: delete",         watchlist_delete_flow),
    ("Operator action log",        action_log_flow),
    ("─" * 6,                      lambda: None),
    ("List saved searches",        list_saved),
    ("Run saved search",           run_saved),
    ("New saved search",           new_saved),
    ("Edit saved search",          edit_saved),
    ("Delete saved search",        delete_saved),
    ("Export saved → JSON",        export_saved_flow),
    ("Import saved ← JSON",        import_saved_flow),
    ("─" * 6,                      lambda: None),
    ("Schedule a saved search",    schedule_saved_flow),
    ("List scheduled searches",    list_schedules_flow),
    ("Poll subscriptions now",     poll_subscriptions_flow),
    ("Subscription inbox",         inbox_flow),
    ("─" * 6,                      lambda: None),
    ("Pin a result",               pin_flow),
    ("List pinned",                list_pins_flow),
    ("Unpin a result",             unpin_flow),
    ("─" * 6,                      lambda: None),
    ("Cohorts: list",              list_cohorts_flow),
    ("Cohorts: save search as…",   save_cohort_flow),
    ("Cohorts: view members",      cohort_members_flow),
    ("Cohorts: delete",            delete_cohort_flow),
    ("Find relatives (family)",    family_flow),
    ("Class-group rollup",         group_rollup_flow),
    ("UCAS peers (same uni)",      ucas_peers_flow),
    ("UCAS choice clusters",       ucas_clusters_flow),
    ("Timetable clashes",          clashes_flow),
    ("Similar students",           similar_flow),
    ("─" * 6,                      lambda: None),
    ("Recent history",             show_history),
    ("Clear history",              clear_history_flow),
    ("Telemetry summary",          telemetry_flow),
    ("─" * 6,                      lambda: None),
    ("Rebuild FTS5 index",         refresh_index_flow),
    ("Index status / refresh stale", index_status_flow),
    ("Clear search cache",         clear_cache_flow),
    ("Cache stats",                cache_stats_flow),
    ("─" * 6,                      lambda: None),
    ("Dashboards: list",           list_dashboards_flow),
    ("Dashboards: create",         create_dashboard_flow),
    ("Dashboards: run",            run_dashboard_flow),
    ("Subscription digest",        digest_flow),
    ("Schedule delta (what changed)", schedule_delta_flow),
    ("Search volume by day",       volume_flow),
    ("Sensitive-access audit log", audit_flow),
    ("─" * 6,                      lambda: None),
    ("Export search → file",       export_search_flow),
    ("Contact sheet → HTML",       contact_sheet_flow),
    ("Duplicate students",         duplicates_flow),
    ("Data-gap search",            data_gaps_flow),
    ("Natural-language query",     nl_query_flow),
]


def run() -> None:
    while True:
        print("\n── Advanced Search ──")
        for i, (label, _) in enumerate(_MENU, 1):
            if label.startswith("─"):
                print(f"      {label * 3}")
            else:
                print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        label, handler = _MENU[int(choice) - 1]
        if label.startswith("─"):
            continue
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Advanced-search CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Advanced Search":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Advanced-search CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
