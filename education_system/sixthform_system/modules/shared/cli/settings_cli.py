"""CLI flows for Sixth Form Settings."""

from __future__ import annotations

import logging
from typing import Any, Callable
from education_system.sixthform_system.modules.shared import settings as data
from education_system.sixthform_system.modules.shared.settings import (
    SettingError,
    SettingSpec,
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


def _pick_from(label: str, options: list[str],
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}", default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel').")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


# ── Print helpers ──────────────────────────────────────────────────

def _format_value(spec: SettingSpec, v: Any) -> str:
    if spec.type == "bool":
        return "Yes" if v else "No"
    if v == "" or v is None:
        return "(unset)"
    return str(v)


def _print_setting_row(spec: SettingSpec, value: Any,
                         *, show_default: bool = False) -> None:
    scope_tag = "[G]" if spec.scope == "global" else "   "
    line = f"  {scope_tag} {spec.label:<38}  = {_format_value(spec, value)}"
    if show_default and value != spec.default:
        line += f"   (default: {_format_value(spec, spec.default)})"
    print(line)


def _print_category(label: str, specs: list[SettingSpec],
                      auth: Any) -> None:
    print(f"\n  ── {label} ──")
    for s in specs:
        if s.scope == "global" and auth is None:
            value = "(needs sign-in)"
            print(f"  [G] {s.label:<38}  = {value}")
            continue
        try:
            v = data.get(s.key, auth=auth)
        except SettingError as e:
            v = f"(error: {e})"
        _print_setting_row(s, v, show_default=True)


# ── Flows ──────────────────────────────────────────────────────────

def list_all_flow(auth: Any) -> None:
    print("\n═══ All Settings ═══")
    print("  [G] = global (auth-policy); blank = local")
    for cat in data.categories():
        _print_category(cat,
                          [s for s in data.list_settings()
                           if s.category == cat],
                          auth)
    _pause()


def list_local_flow(auth: Any) -> None:
    print("\n═══ Local Settings ═══")
    for cat in data.categories():
        specs = [s for s in data.list_settings(scope="local")
                  if s.category == cat]
        if specs:
            _print_category(cat, specs, auth)
    _pause()


def list_global_flow(auth: Any) -> None:
    print("\n═══ Global (Auth) Settings ═══")
    if auth is None:
        print("  ✗ Global settings need an active session.")
        _pause()
        return
    for cat in data.categories():
        specs = [s for s in data.list_settings(scope="global")
                  if s.category == cat]
        if specs:
            _print_category(cat, specs, auth)
    _pause()


def _pick_setting(scope: str | None = None) -> SettingSpec:
    specs = data.list_settings(scope=scope)
    print("\n  Settings:")
    for i, s in enumerate(specs, 1):
        tag = "[G]" if s.scope == "global" else "   "
        print(f"    {i:>2}) {tag} {s.label:<38}  ({s.key})")
    while True:
        raw = _input(f"Pick #1..{len(specs)} (or key)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(specs):
                return specs[n - 1]
        try:
            return data.get_spec(raw)
        except SettingError as e:
            print(f"    ✗ {e}")


def view_flow(auth: Any) -> None:
    print("\n═══ View Setting ═══")
    try:
        spec = _pick_setting()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        v = data.get(spec.key, auth=auth)
    except SettingError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print()
    print(f"  Key         : {spec.key}")
    print(f"  Label       : {spec.label}")
    print(f"  Scope       : {spec.scope}")
    print(f"  Category    : {spec.category}")
    print(f"  Type        : {spec.type}"
          + (f" ({', '.join(spec.choices)})"
              if spec.choices else ""))
    if spec.min is not None or spec.max is not None:
        print(f"  Range       : {spec.min}..{spec.max}")
    print(f"  Default     : {_format_value(spec, spec.default)}")
    print(f"  Current     : {_format_value(spec, v)}")
    print(f"\n  {spec.description}")
    _pause()


def edit_flow(auth: Any) -> None:
    print("\n═══ Edit Setting ═══")
    try:
        spec = _pick_setting()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        cur = data.get(spec.key, auth=auth)
    except SettingError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  {spec.label}")
    print(f"  {spec.description}")
    print(f"  Current: {_format_value(spec, cur)}")
    try:
        if spec.type == "bool":
            new_raw = _pick_from("New value",
                                   ["true", "false"],
                                   default="true" if cur else "false")
        elif spec.type == "choice":
            new_raw = _pick_from("New value",
                                   list(spec.choices or ()),
                                   default=str(cur))
        else:
            new_raw = _input(
                f"New value (type {spec.type})",
                default=str(cur) if cur not in (None, "") else "",
                allow_empty=spec.type == "str")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        v = data.set(spec.key, new_raw, auth=auth)
    except SettingError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {spec.label} → {_format_value(spec, v)}")
    _pause()


def reset_one_flow(auth: Any) -> None:
    print("\n═══ Reset Setting to Default ═══")
    try:
        spec = _pick_setting()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        v = data.reset_to_default(spec.key, auth=auth)
    except SettingError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {spec.label} → default "
          f"({_format_value(spec, v)})")
    _pause()


def reset_all_flow(auth: Any) -> None:
    print("\n═══ Reset All Local Settings ═══")
    print("  This wipes locally-overridden values, restoring "
          "every local setting to its default. Global "
          "(auth-policy) settings are not affected.")
    if _input("Type 'yes' to confirm", default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    n = data.reset_all_local()
    print(f"\n  ✓ Reset {n} override(s).")
    _pause()


def export_flow(auth: Any) -> None:
    print("\n═══ Show All Effective Values ═══")
    snapshot = data.export_all(auth=auth)
    if not snapshot:
        print("\n  (no settings)")
        _pause()
        return
    by_cat: dict[str, list[tuple[SettingSpec, Any]]] = {}
    for key, val in snapshot.items():
        try:
            spec = data.get_spec(key)
        except SettingError:
            continue
        by_cat.setdefault(spec.category, []).append((spec, val))
    for cat in data.categories():
        rows = by_cat.get(cat, [])
        if not rows:
            continue
        print(f"\n  ── {cat} ──")
        for spec, val in rows:
            _print_setting_row(spec, val)
    if not auth:
        print("\n  (global settings hidden — sign in to see them)")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[Any], None]]] = [
    ("Show all (by category)",   list_all_flow),
    ("Show local only",          list_local_flow),
    ("Show global (auth) only",  list_global_flow),
    ("View one",                 view_flow),
    ("Edit one",                 edit_flow),
    ("Reset one to default",     reset_one_flow),
    ("Reset all local",          reset_all_flow),
    ("Effective snapshot",       export_flow),
]


def run(auth: Any = None) -> None:
    while True:
        print("\n── Settings ──")
        for i, (label, _) in enumerate(_MENU, 1):
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
        _, handler = _MENU[int(choice) - 1]
        try:
            handler(auth)
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Settings CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str, auth=None) -> bool:
    if label != "Settings":
        return False
    try:
        run(auth)
    except Exception as e:
        logger.exception("Settings CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
