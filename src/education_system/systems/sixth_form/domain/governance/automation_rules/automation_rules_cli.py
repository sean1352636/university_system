"""CLI flows for the Sixth Form Automation Rules engine.

Submenu: list rules / add rule / enable-disable / delete / run engine /
action worklist / resolve action.
"""

from __future__ import annotations

import logging
from typing import Callable

from education_system.systems.sixth_form.domain.governance.automation_rules import (
    automation_rules as data,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


def _input(prompt: str, *, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    return s or default


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _list_rules() -> None:
    rules = data.list_rules()
    if not rules:
        print("\n  No rules defined.")
        return _pause()
    print(f"\n  {'ID':>3}  {'On':<3}{'Name':<22}{'Trigger':<34}{'Sev':<9}{'Matches':>8}")
    print("  " + "-" * 82)
    for r in rules:
        on = "✓" if r["enabled"] else "·"
        trig = f"{r['trigger_label']} {r['threshold']:g}"
        print(f"  {r['rule_id']:>3}  {on:<3}{r['name'][:20]:<22}{trig[:32]:<34}"
              f"{r['severity']:<9}{r['last_matches']:>8}")
    _pause()


def _add_rule() -> None:
    name = _input("Rule name")
    if not name:
        return
    print("\n  Triggers:")
    for i, t in enumerate(data.TRIGGERS, 1):
        print(f"    {i}) {t.label}  ({t.unit})")
    choice = _input("Trigger number")
    if not choice.isdigit() or not (1 <= int(choice) <= len(data.TRIGGERS)):
        print("  Invalid.")
        return _pause()
    trig = data.TRIGGERS[int(choice) - 1]
    threshold = _input(f"Threshold ({trig.unit})")
    try:
        threshold = float(threshold)
    except ValueError:
        print("  Threshold must be a number.")
        return _pause()
    action = _input("Action label (e.g. 'Notify tutor')")
    sev = _input(f"Severity ({'/'.join(data.SEVERITIES)})", default="Medium")
    try:
        rid = data.create_rule(name=name, trigger_key=trig.key, threshold=threshold,
                               action_label=action, severity=sev)
    except data.ValidationError as e:
        print(f"  ✗ {e}")
        return _pause()
    print(f"  ✓ Created rule #{rid}.")
    _pause()


def _toggle() -> None:
    rid = _input("Rule ID")
    if not rid.isdigit():
        return
    on = _input("Enable? (y/n)", default="y").lower() == "y"
    data.set_enabled(int(rid), on)
    print(f"  ✓ Rule #{rid} {'enabled' if on else 'disabled'}.")
    _pause()


def _delete() -> None:
    rid = _input("Rule ID to delete")
    if rid.isdigit():
        data.delete_rule(int(rid))
        print("  ✓ Deleted.")
    _pause()


def _run() -> None:
    print("\n  Running engine against all active students...")
    res = data.run_rules()
    print(f"  ✓ {res['rules_run']} rule(s) run, {res.get('matches', 0)} match(es), "
          f"{res['new_actions']} new action(s).")
    _pause()


def _worklist() -> None:
    actions = data.list_actions(status="Open")
    if not actions:
        print("\n  No open actions.")
        return _pause()
    print(f"\n  {len(actions)} open action(s):")
    for a in actions:
        print(f"   #{a['action_id']:<4}[{a['severity']:<8}] {a['message']}")
    _pause()


def _resolve() -> None:
    aid = _input("Action ID")
    if not aid.isdigit():
        return
    status = _input("New status (Done/Dismissed)", default="Done")
    by = _input("Resolved by", default="")
    try:
        data.resolve_action(int(aid), status=status, by=by)
    except data.ValidationError as e:
        print(f"  ✗ {e}")
        return _pause()
    print("  ✓ Updated.")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List rules", _list_rules),
    ("Add rule", _add_rule),
    ("Enable / disable rule", _toggle),
    ("Delete rule", _delete),
    ("Run engine now", _run),
    ("Action worklist (open)", _worklist),
    ("Resolve action", _resolve),
]


def run() -> None:
    while True:
        print("\n── Automation Rules ──")
        for i, (label, _) in enumerate(_MENU, 1):
            print(f"  {i}) {label}")
        print("  0) Back")
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
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Automation-rules CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Automation Rules":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Automation-rules CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
