"""School settings in the terminal.

The old Settings menu keeps its options in place: 1 Show all (by
category), 2 Show local only, 3 Show global (auth) only, 4 View one, 5 Edit
one, 6 Reset one to default, 7 Reset all local, 8 Effective snapshot. New:
9 School details, 10 Other areas' settings, 11 Change another area's
setting, 12 Term dates, 13 History, 14 Export snapshot to a file, 15 Import
snapshot from a file, 16 Change sign-in policy, 17 Reset a sign-in setting
(settings shared by every system ask first). Rules live in :mod:`modules.administration.domain.settings`.
"""

from __future__ import annotations

import json

from education_system.systems.secondary.modules.administration.domain import settings as ST
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (ST.ValidationError, ST.PermissionDenied, ST.NotFound)
_problem = prompts.problem
_pick = prompts.pick


def _row(s: ST.Setting) -> None:
    print(f"    {s.spec.label:<46} {s.shown:<24}"
          + ("" if s.is_default else f" (changed by {s.updated_by})"))


def _show(principal: Principal, categories: list[str]) -> None:
    rows = ST.list_settings(actor=principal)
    for cat in categories:
        print(f"\n  ── {cat} ──")
        for s in (r for r in rows if r.spec.category == cat):
            _row(s)


def _all(principal: Principal) -> None:
    print(ST.summary_text(actor=principal))


def _local(principal: Principal) -> None:
    _show(principal, ST.categories())


def _global(_principal: Principal) -> None:
    pol = ST.auth_policy()
    print("\n  ── Sign-in policy ──")
    for i, s in enumerate(ST.AUTH_POLICY, 1):
        where = "this school" if s.scope == "system" else "all systems"
        print(f"   {i}) {s.label:<46} {ST.format_value(s, pol[s.key]):<8} [{where}]")


def _pick_policy() -> ST.SettingSpec | None:
    _global(None)  # type: ignore[arg-type]
    n = prompts.ask_int("  Setting #: ")
    if n is None or not 1 <= n <= len(ST.AUTH_POLICY):
        return None
    spec = ST.AUTH_POLICY[n - 1]
    if spec.scope != "system" and not _yes(f"  '{spec.label}' applies to every system on "
                                           "this platform, not just this school. Go on?"):
        return None
    return spec


def _edit_policy(principal: Principal) -> None:
    spec = _pick_policy()
    if spec is None:
        return
    hint = f" ({int(spec.min)}-{int(spec.max)})" if spec.min is not None else \
        " (yes/no)" if spec.type == "bool" else ""
    raw = _prompt(f"  {spec.label}{hint} [{ST.format_value(spec, ST.auth_policy()[spec.key])}]: ")
    if raw:
        new = ST.set_auth_policy(spec.key, raw, actor=principal)
        print(f"  Saved: {ST.format_value(spec, new)}")


def _reset_policy(principal: Principal) -> None:
    spec = _pick_policy()
    if spec is not None:
        new = ST.reset_auth_policy(spec.key, actor=principal)
        print(f"  Back to the default: {ST.format_value(spec, new)}")


def _key() -> str | None:
    cat = _pick("Category", ST.categories())
    if not cat:
        return None
    specs = ST.list_specs(category=cat)
    label = _pick("Setting", [s.label for s in specs])
    spec = next((s for s in specs if label in (s.label, s.key)), None)
    if spec is None:
        print("  No such setting.")
    return spec.key if spec else None


def _view(principal: Principal) -> None:
    key = _key()
    if not key:
        return
    s = ST.get(key, actor=principal)
    print(f"\n  {s.spec.label} ({s.spec.key})\n  {s.spec.description}")
    print(f"  Value:   {s.shown}\n  Default: {ST.format_value(s.spec, s.spec.default)}")
    if s.spec.choices:
        print(f"  Choices: {', '.join(s.spec.choices)}")
    if not s.is_default:
        print(f"  Changed by {s.updated_by} at {s.updated_at}")


def _edit(principal: Principal) -> None:
    key = _key()
    if not key:
        return
    s = ST.get(key, actor=principal)
    if s.spec.type == "choice":
        v = _pick(s.spec.label, s.spec.choices or (), str(s.value))
    elif s.spec.type == "bool":
        v = "yes" if _yes(f"  {s.spec.label} - on?") else "no"
    else:
        v = _prompt(f"  {s.spec.label} [{s.shown}] ('-' clears): ")
        if v == "":
            return
        v = "" if v == prompts.CLEAR else v
    out = ST.set_setting(key, v, actor=principal)
    print(f"  Saved {s.spec.label} = {ST.format_value(s.spec, out)}")


def _reset_one(principal: Principal) -> None:
    key = _key()
    if key and _yes(f"  Reset {key} to its default?"):
        v = ST.reset(key, actor=principal)
        print(f"  Reset to {ST.format_value(ST.get_spec(key), v)}")


def _reset_all(principal: Principal) -> None:
    if _yes("  Reset every school setting to its default?"):
        print(f"  Reset {ST.reset_all(actor=principal)} setting(s).")


def _snapshot(principal: Principal) -> None:
    print(json.dumps(ST.snapshot(actor=principal), indent=2, default=str))


def _school(principal: Principal) -> None:
    """Every School field in turn: Enter keeps, '-' clears; saved together."""
    current = {s.spec.key: s for s in ST.list_settings(actor=principal, category=ST.SCHOOL)}
    changes = {}
    for key, s in current.items():
        v = prompts.ask(s.spec.label, None if s.value in ("", None) else str(s.value))
        if v is not None:
            changes[key] = v
    if changes:
        changed = ST.set_many(changes, actor=principal)
        print(f"  Saved {len(changed)} change(s).")
    for w in ST.warnings():
        print(f"  ! {w}")


def _linked(_principal: Principal) -> None:
    vals = ST.linked_values()
    print(f"\n  {'Area':<12} {'Setting':<40} {'Value':<10} Allowed")
    for x in ST.LINKED:
        print(f"  {x.area:<12} {x.label:<40} {str(vals.get(x.key)):<10} {x.hint}")


def _change_linked(principal: Principal) -> None:
    label = _pick("Setting", [f"{x.area}: {x.label}" for x in ST.LINKED])
    x = next((i for i in ST.LINKED if label in (f"{i.area}: {i.label}", i.key)), None)
    if x is None:
        return
    v = _prompt(f"  {x.label} ({x.hint}) [{ST.linked_values().get(x.key)}]: ")
    if v:
        print(f"  Saved: {ST.set_linked(x.key, v, actor=principal)}")


def _terms(_principal: Principal) -> None:
    td = ST.term_dates()
    if not td["year"]:
        print("  No current school year - set it up in Academic Year & Calendar.")
        return
    y = td["year"]
    print(f"\n  {y['name']}: {y['start']} to {y['end']} ({y['status']})")
    for t in td["terms"]:
        print(f"    {t['name']:<20} {t['start']} to {t['end']}")
    print("  (Change them in Academic Year & Calendar.)")


def _history(_principal: Principal) -> None:
    for h in ST.history(limit=50):
        print(f"  {h['at']}  {h['actor'] or '':<12} {h['action']:<7} {h['key'] or '':<32} "
              f"{h['old']!r} -> {h['new']!r}")


def _export(principal: Principal) -> None:
    path = _prompt("  Save to (e.g. settings.json): ")
    if path:
        print(f"  Wrote {ST.export_json(path, actor=principal)} setting(s).")


def _import(principal: Principal) -> None:
    path = _prompt("  Read from: ")
    if path and _yes("  Replace the school settings with the file's values?"):
        print(f"  Imported {len(ST.import_json(path, actor=principal))} change(s).")


_OPTIONS = {"1": _all, "2": _local, "3": _global, "4": _view, "5": _edit, "6": _reset_one,
            "7": _reset_all, "8": _snapshot, "9": _school, "10": _linked,
            "11": _change_linked, "12": _terms, "13": _history, "14": _export, "15": _import,
            "16": _edit_policy, "17": _reset_policy}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("settings.open")
        print("\n  ── Settings ──")
        print("    1) Show all (by category)\n    2) Show local only\n    3) Show global "
              "(auth) only\n    4) View one\n    5) Edit one\n    6) Reset one to default"
              "\n    7) Reset all local\n    8) Effective snapshot")
        print("  More")
        print("    9) School details\n   10) Other areas' settings\n   11) Change another "
              "area's setting\n   12) Term dates\n   13) History\n   14) Export snapshot to a "
              "file\n   15) Import snapshot from a file\n   16) Change sign-in policy"
              "\n   17) Reset a sign-in setting to default")
        print("    0) Back")
        choice = _prompt("Select: ")
        if choice in ("0", ""):
            return
        fn = _OPTIONS.get(choice)
        if fn is None:
            print("  Invalid selection.")
            continue
        try:
            fn(principal)
        except (*_ERRORS, OSError) as e:
            _problem(e)
        _pause()
