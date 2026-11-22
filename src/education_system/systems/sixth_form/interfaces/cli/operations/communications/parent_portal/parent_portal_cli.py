"""CLI flows for Sixth Form Parent Portal administration.

Staff-facing: list accounts / create account / edit details / link
student / unlink / reset password / enable-disable / delete / preview
child snapshot.
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
    print(f"\n  {'ID':>4}  {'Username':<20}{'Name':<24}{'Email':<30}{'Active':<8}"
          f"{'Children':>9}  {'Login':<7}")
    print("  " + "-" * 105)
    for a in accounts:
        print(f"  {a['account_id']:>4}  {a['username'][:18]:<20}{a['full_name'][:22]:<24}"
              f"{(a['email'] or '—')[:28]:<30}"
              f"{'yes' if a['is_active'] else 'no':<8}{a['linked_students']:>9}  "
              f"{'yes' if a.get('login_enabled') else 'RESET':<7}")
    if any(not a.get("login_enabled") for a in accounts):
        print("\n  Login 'RESET': this account predates the shared-auth mirror and "
              "cannot sign in\n  at the login screen yet. Reset its password to "
              "enable it.")
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


def _edit() -> None:
    """Change an account's name / email address (username is fixed)."""
    aid = _input("Account ID")
    if not aid.isdigit():
        return
    account = data.get_account(int(aid))
    if account is None:
        print(f"  ✗ Unknown account: {aid}")
        return _pause()
    print(f"\n  Editing '{account.username}'. Enter to keep the current value; "
          "type 'none'\n  to remove the email address.")
    full_name = _input("Full name", default=account.full_name)
    email = _input("Email", default=account.email or "none")
    try:
        data.update_account(int(aid), full_name=full_name,
                            email="" if email.lower() == "none" else email)
    except data.ValidationError as e:
        print(f"  ✗ {e}")
        return _pause()
    print("  ✓ Updated.")
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


def _who() -> str:
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        return access.current().username or "staff"
    except Exception:
        return "staff"


def _contact_requests() -> None:
    """Work through parents' contact-detail change requests."""
    while True:
        reqs = data.list_contact_requests()
        print(f"\n  Contact change requests — {len(reqs)} pending")
        if not reqs:
            return
        for i, r in enumerate(reqs, 1):
            changes = ", ".join(f"{data.CONTACT_REQUEST_FIELDS.get(k, k)}: {v}"
                                for k, v in r["changes"].items())
            print(f"  {i:>3}) #{r['request_id']} {r['parent_name']} "
                  f"({r.get('student_name') or r.get('student_id') or '—'}) "
                  f"{r['created_at'] or ''}")
            print(f"        {changes}")
            if r.get("note"):
                print(f"        Note: {r['note']}")
            if not r.get("contact_id"):
                print("        (no contact record linked — apply by hand)")
        pick = _input("Request number (Enter to go back)")
        if not pick:
            return
        if not pick.isdigit() or not 1 <= int(pick) <= len(reqs):
            print("  Invalid selection.")
            continue
        req = reqs[int(pick) - 1]
        action = _input("A)pply or R)eject", default="").lower()
        if action not in ("a", "r"):
            continue
        note = _input("Note (optional)")
        try:
            data.resolve_contact_request(req["request_id"], apply=action == "a",
                                         by=_who(), note=note)
            print("  ✓ Done.")
        except data.ValidationError as e:
            print(f"  ✗ {e}")


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List accounts", _list),
    ("Create account", _create),
    ("Edit account details", _edit),
    ("Link student", _link),
    ("Unlink student", _unlink),
    ("Reset password", _reset_pw),
    ("Enable / disable account", _toggle),
    ("Delete account", _delete),
    ("Preview child snapshot", _preview),
    ("Contact change requests", _contact_requests),
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
