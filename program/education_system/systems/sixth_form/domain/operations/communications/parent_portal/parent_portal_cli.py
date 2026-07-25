"""CLI flows for Sixth Form Parent Portal administration.

Staff-facing: list accounts / create account / link student / unlink /
reset password / enable-disable / delete / preview child snapshot.
"""

from __future__ import annotations

import getpass
import logging
from typing import Callable

from education_system.systems.sixth_form.domain.operations.communications.parent_portal import (
    parent_portal as data,
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


def _password(prompt: str) -> str:
    try:
        return getpass.getpass(f"  {prompt}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _list() -> None:
    accounts = data.list_accounts()
    if not accounts:
        print("\n  No parent accounts.")
        return _pause()
    print(f"\n  {'ID':>4}  {'Username':<20}{'Name':<24}{'Active':<8}{'Children':>9}")
    print("  " + "-" * 66)
    for a in accounts:
        print(f"  {a['account_id']:>4}  {a['username'][:18]:<20}{a['full_name'][:22]:<24}"
              f"{'yes' if a['is_active'] else 'no':<8}{a['linked_students']:>9}")
    _pause()


def _create() -> None:
    username = _input("Username")
    full_name = _input("Full name")
    email = _input("Email (optional)", default="")
    pw = _password("Password (min 8 chars)")
    try:
        aid = data.create_account(username=username, password=pw,
                                  full_name=full_name, email=email)
    except data.ValidationError as e:
        print(f"  ✗ {e}")
        return _pause()
    print(f"  ✓ Created account #{aid}.")
    if _input("Link a student now? (y/N)").lower() == "y":
        sid = _input("Student ID")
        rel = _input("Relationship", default="Parent")
        try:
            data.link_student(aid, sid, relationship=rel)
            print("  ✓ Linked.")
        except data.ValidationError as e:
            print(f"  ✗ {e}")
    _pause()


def _link() -> None:
    aid = _input("Account ID")
    sid = _input("Student ID")
    rel = _input("Relationship", default="Parent")
    if not aid.isdigit():
        return
    try:
        data.link_student(int(aid), sid, relationship=rel)
    except data.ValidationError as e:
        print(f"  ✗ {e}")
        return _pause()
    print("  ✓ Linked.")
    _pause()


def _unlink() -> None:
    aid = _input("Account ID")
    sid = _input("Student ID")
    if aid.isdigit():
        data.unlink_student(int(aid), sid)
        print("  ✓ Unlinked.")
    _pause()


def _reset_pw() -> None:
    aid = _input("Account ID")
    if not aid.isdigit():
        return
    pw = _password("New password (min 8 chars)")
    try:
        data.set_password(int(aid), pw)
    except data.ValidationError as e:
        print(f"  ✗ {e}")
        return _pause()
    print("  ✓ Password reset.")
    _pause()


def _toggle() -> None:
    aid = _input("Account ID")
    if not aid.isdigit():
        return
    active = _input("Active? (y/n)", default="y").lower() == "y"
    data.set_active(int(aid), active)
    print(f"  ✓ Account {'enabled' if active else 'disabled'}.")
    _pause()


def _delete() -> None:
    aid = _input("Account ID to delete")
    if aid.isdigit() and _input("Confirm delete? (y/N)").lower() == "y":
        data.delete_account(int(aid))
        print("  ✓ Deleted.")
    _pause()


def _preview() -> None:
    aid = _input("Account ID")
    if not aid.isdigit():
        return
    try:
        dash = data.account_dashboard(int(aid))
    except data.ValidationError as e:
        print(f"  ✗ {e}")
        return _pause()
    print(f"\n  Portal view for {dash['account']['full_name']} "
          f"({dash['account']['username']})")
    if not dash["children"]:
        print("    No linked children.")
        return _pause()
    for c in dash["children"]:
        print(f"\n  ── {c['full_name']} ({c['relationship']}) ──")
        print(f"    Attendance: {c['attendance_pct']}%   Risk band: {c['risk_band']}")
        b = c["behaviour_30d"]
        print(f"    Behaviour (30d): +{b['positive']} / -{b['negative']}")
        if c["ucas"]:
            print(f"    UCAS progress: {c['ucas']['percent']}%")
        for s in c["subjects"]:
            ot = "—" if s["on_target"] is None else ("on target" if s["on_target"] else "below target")
            print(f"      {s['subject'][:22]:<24} pred {s['predicted'] or '—'} / "
                  f"target {s['target'] or '—'} / forecast {s['forecast'] or '—'}  ({ot})")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List accounts", _list),
    ("Create account", _create),
    ("Link student", _link),
    ("Unlink student", _unlink),
    ("Reset password", _reset_pw),
    ("Enable / disable account", _toggle),
    ("Delete account", _delete),
    ("Preview child snapshot", _preview),
]


def run() -> None:
    while True:
        print("\n── Parent Portal (admin) ──")
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
            logger.exception("Parent-portal CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Parent Portal":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Parent-portal CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
