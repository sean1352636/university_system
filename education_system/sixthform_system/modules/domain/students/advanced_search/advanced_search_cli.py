"""CLI flows for Sixth Form Advanced Search."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.students.advanced_search import (
    advanced_search as data,
)
from education_system.sixthform_system.modules.domain.students.advanced_search.advanced_search import (
    ALL_SCOPES,
    DEFAULT_LIMIT_PER_SCOPE,
    Hit,
    SavedSearch,
    SCOPE_LABELS,
    SearchResults,
    ValidationError,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


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


# ── Flows ──────────────────────────────────────────────────────────

def quick_search() -> None:
    print("\n═══ Quick Search (all scopes) ═══")
    try:
        q = _input("Query (empty = list everything)")
        n = int(_input("Per-scope limit", default=str(DEFAULT_LIMIT_PER_SCOPE)))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = data.run_search(q, limit_per_scope=n)
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
        r = data.run_search(q, scopes=scopes, limit_per_scope=n)
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
        r = data.run_search(q, scopes=scopes, limit_per_scope=n)
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


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Quick search (all scopes)", quick_search),
    ("Scoped search",             scoped_search),
    ("Single-scope search",       search_one_scope),
    ("─" * 6,                     lambda: None),
    ("List saved searches",       list_saved),
    ("Run saved search",          run_saved),
    ("New saved search",          new_saved),
    ("Edit saved search",         edit_saved),
    ("Delete saved search",       delete_saved),
    ("─" * 6,                     lambda: None),
    ("Recent history",            show_history),
    ("Clear history",             clear_history_flow),
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
