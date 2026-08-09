"""CLI flows for Sixth Form Departments."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.sixth_form.domain.staff.departments import (
    departments as data,
)
from education_system.systems.sixth_form.domain.staff.departments.departments import (
    DEFAULT_DEPT_ROLE,
    DEFAULT_FACULTY,
    DEFAULT_STATUS,
    DEPT_ROLES,
    Department,
    FACULTIES,
    Membership,
    STATUSES,
    ValidationError,
)
from education_system.systems.sixth_form.domain.staff import (
    staff as _staff,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


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
            return _input(prompt, default=default,
                            allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _yes_no(prompt: str, *, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)",
                  default="y" if default else "n").strip().lower()
    return raw in ("y", "yes")


def _multiline(prompt: str, *, default: str = "") -> str:
    print(f"\n  {prompt} (end with '.'; ENTER for default)")
    if default:
        for line in default.splitlines():
            print(f"    | {line}")
    lines: list[str] = []
    try:
        while True:
            ln = input("  > ")
            if ln.strip() == ".":
                break
            if not lines and not ln:
                return default
            lines.append(ln)
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    return "\n".join(lines)


def _pick_from(label: str, options: list[str],
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt or '(none)'}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number.")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_staff(*, optional: bool = False) -> str | None:
    rows = _staff.list_staff()
    if not rows:
        if optional:
            return None
        print("    No staff.")
        raise _UserAbort
    print("\n  Staff:")
    if optional:
        print("    0) (none)")
    for i, s in enumerate(rows, 1):
        full = f"{getattr(s, 'first_name', '')} " \
               f"{getattr(s, 'last_name', '')}".strip()
        print(f"    {i:>3}) {s.staff_id:<12}  {full}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)}"
                      + (" (0 for none)" if optional else "")
                      + " (or id)",
                      allow_empty=optional)
        if optional and (not raw or raw == "0"):
            return None
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].staff_id
        match = next((s for s in rows
                        if s.staff_id == raw.upper()), None)
        if match:
            return match.staff_id
        print("    No matching staff.")


def _pick_department() -> Department:
    rows = data.list_departments()
    if not rows:
        print("    No departments yet.")
        raise _UserAbort
    print("\n  Departments:")
    for i, d in enumerate(rows, 1):
        print(f"    {i:>3}) #{d.department_id}  "
              f"{d.name[:30]:<30}  "
              f"{d.faculty[:22]:<22}  [{d.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                            if r.department_id == n), None)
            if match:
                return match
        print("    No matching department.")


def _pick_membership(department_id: int) -> Membership:
    rows = data.list_memberships(department_id)
    if not rows:
        print("    No memberships in this department.")
        raise _UserAbort
    print("\n  Memberships:")
    for i, m in enumerate(rows, 1):
        flag = "*" if m.is_primary else " "
        print(f"    {i:>3}){flag} #{m.membership_id}  "
              f"{m.staff_id:<12}  "
              f"{m.role_in_department[:22]:<22}  "
              f"joined {m.joined_on}  "
              f"left {m.left_on or '—'}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                            if r.membership_id == n), None)
            if match:
                return match
        print("    No matching membership.")


# ── Department print ─────────────────────────────────────

def _print_departments(rows: list[Department]) -> None:
    if not rows:
        print("\n  (no departments)")
        return
    print()
    print(f"  {'#':>4}  {'Name':<24}  {'Faculty':<26}  "
          f"{'HoD':<12}  {'Budget':<22}  Members  Status")
    print("  " + "-" * 130)
    for d in rows:
        if d.budget_total is not None:
            spent = d.budget_spent or 0.0
            budget = (f"£{spent:.0f}/£{d.budget_total:.0f}"
                       + ("  OVER" if d.budget_over else ""))
        else:
            budget = "—"
        members = data.member_count(d.department_id)
        print(f"  {d.department_id:>4}  "
              f"{d.name[:24]:<24}  "
              f"{d.faculty[:26]:<26}  "
              f"{(d.head_of_department or '—'):<12}  "
              f"{budget:<22}  "
              f"{members:>7}  {d.status}")
    print(f"\n  {len(rows)} department(s).")


def _print_department_full(d: Department) -> None:
    print()
    print(f"    #{d.department_id}  {d.name}")
    print(f"    Code               : {d.code or '—'}")
    print(f"    Faculty            : {d.faculty}")
    print(f"    Head of Department : "
          f"{d.head_of_department or '—'}")
    print(f"    Deputy             : {d.deputy_head or '—'}")
    print(f"    Location           : {d.location or '—'}")
    print(f"    Status             : {d.status}")
    if d.budget_total is not None:
        spent = d.budget_spent or 0.0
        print(f"    Budget year        : {d.budget_year or '—'}")
        print(f"    Budget total       : £{d.budget_total:.2f}")
        print(f"    Budget allocated   : "
              f"£{d.budget_allocated:.2f}"
              if d.budget_allocated is not None
              else "    Budget allocated   : —")
        print(f"    Budget spent       : £{spent:.2f}")
        print(f"    Budget remaining   : "
              f"£{d.budget_remaining:.2f}"
              + ("  (OVER)" if d.budget_over else ""))
    if d.subject_codes:
        print(f"    Subjects           : {d.subject_codes}")
    for label, val in (
            ("Aims",     d.aims),
            ("Policies", d.policies),
            ("Notes",    d.notes),
    ):
        if val:
            print(f"\n    {label}:")
            for line in val.splitlines():
                print(f"      {line}")
    members = data.list_memberships(d.department_id)
    if members:
        print(f"\n    Members ({len(members)}):")
        for m in members:
            flag = "*" if m.is_primary else " "
            print(f"      {flag} {m.staff_id:<12}  "
                  f"{m.role_in_department[:24]:<24}  "
                  f"joined {m.joined_on}  "
                  f"left {m.left_on or '—'}")


# ── Department flows ─────────────────────────────────────

def departments_list() -> None:
    print("\n═══ All Departments ═══")
    _print_departments(data.list_departments())
    _pause()


def departments_active() -> None:
    print("\n═══ Active Departments ═══")
    _print_departments(data.list_departments(active_only=True))
    _pause()


def departments_over_budget() -> None:
    print("\n═══ Over Budget ═══")
    _print_departments(data.list_departments(over_budget=True))
    _pause()


def departments_filter() -> None:
    print("\n═══ Filter Departments ═══")
    try:
        fac = _input(
            f"Faculty ({'/'.join(FACULTIES[:3])}…)") or None
        status = _input(
            f"Status ({'/'.join(STATUSES)})") or None
        name = _input("Name contains") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_departments(faculty=fac, status=status,
                                       name_like=name)
    _print_departments(rows)
    _pause()


def departments_view() -> None:
    print("\n═══ View Department ═══")
    try:
        d = _pick_department()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_department_full(d)
    _pause()


def _collect_department_form(
        existing: Department | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["name"] = _input(
        "Name",
        default=(existing.name if is_edit else ""),
        allow_empty=False)
    payload["code"] = _input(
        "Code (e.g. MAT)",
        default=(existing.code or "") if is_edit else "")
    payload["faculty"] = _pick_from(
        "Faculty", list(FACULTIES),
        default=(existing.faculty if is_edit
                  else DEFAULT_FACULTY))
    if _yes_no("Set Head of Department?",
               default=is_edit and bool(existing.head_of_department)):
        try:
            sid = _pick_staff(optional=True)
            payload["head_of_department"] = sid
        except _UserAbort:
            payload["head_of_department"] = None
    else:
        payload["head_of_department"] = None
    if _yes_no("Set Deputy Head?",
               default=is_edit and bool(existing.deputy_head)):
        try:
            sid = _pick_staff(optional=True)
            payload["deputy_head"] = sid
        except _UserAbort:
            payload["deputy_head"] = None
    else:
        payload["deputy_head"] = None
    payload["location"] = _input(
        "Location",
        default=(existing.location or "") if is_edit else "")
    payload["budget_year"] = _input(
        "Budget year (e.g. 2025-26)",
        default=(existing.budget_year or "")
        if is_edit else "")
    payload["budget_total"] = _input(
        "Budget total (£)",
        default=(str(existing.budget_total)
                  if is_edit and existing.budget_total is not None
                  else ""))
    payload["budget_allocated"] = _input(
        "Budget allocated (£)",
        default=(str(existing.budget_allocated)
                  if is_edit
                  and existing.budget_allocated is not None
                  else ""))
    payload["budget_spent"] = _input(
        "Budget spent (£)",
        default=(str(existing.budget_spent)
                  if is_edit
                  and existing.budget_spent is not None
                  else ""))
    payload["subject_codes"] = _input(
        "Subjects (comma-separated)",
        default=(existing.subject_codes or "")
        if is_edit else "")
    try:
        payload["aims"] = _multiline(
            "Aims",
            default=(existing.aims or "") if is_edit else "")
        payload["policies"] = _multiline(
            "Policies",
            default=(existing.policies or "")
            if is_edit else "")
        payload["notes"] = _multiline(
            "Notes",
            default=(existing.notes or "") if is_edit else "")
    except _UserAbort:
        raise
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    return payload


def departments_new() -> None:
    print("\n═══ New Department ═══")
    try:
        payload = _collect_department_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        d = data.create_department(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created department #{d.department_id}")
    _pause()


def departments_edit() -> None:
    print("\n═══ Edit Department ═══")
    try:
        d = _pick_department()
        payload = _collect_department_form(d)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_department(d.department_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{d.department_id}")
    _pause()


def departments_set_status() -> None:
    print("\n═══ Change Status ═══")
    try:
        d = _pick_department()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=d.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(d.department_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{d.department_id} → {new_status}")
    _pause()


def departments_add_spend() -> None:
    print("\n═══ Add Spend ═══")
    try:
        d = _pick_department()
        amount = _input("Amount (£)", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        d2 = data.add_spend(d.department_id,
                                amount=float(amount))
    except (ValueError, ValidationError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Spent £{amount} on #{d.department_id}"
          f"  (now £{d2.budget_spent:.2f}; remaining "
          f"£{d2.budget_remaining:.2f})")
    _pause()


def departments_delete() -> None:
    print("\n═══ Delete Department ═══")
    try:
        d = _pick_department()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete department #{d.department_id} "
              "(and all memberships)? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_department(d.department_id):
        print(f"\n  ✓ Deleted #{d.department_id}")
    _pause()


# ── Membership flows ─────────────────────────────────────

def memberships_list() -> None:
    print("\n═══ List Memberships ═══")
    try:
        d = _pick_department()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_memberships(d.department_id)
    if not rows:
        print("\n  (no memberships)")
    for m in rows:
        flag = "*" if m.is_primary else " "
        end = m.left_on or "—"
        print(f"  {flag} #{m.membership_id}  "
              f"{m.staff_id:<12}  "
              f"{m.role_in_department:<22}  "
              f"{m.joined_on} → {end}")
    _pause()


def memberships_add() -> None:
    print("\n═══ Add Member ═══")
    try:
        d = _pick_department()
        sid = _pick_staff()
        role = _pick_from("Role", list(DEPT_ROLES),
                             default=DEFAULT_DEPT_ROLE)
        primary = _yes_no("Primary department for this staff?")
        joined = _input("Joined on (YYYY-MM-DD)",
                           default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        m = data.add_member(d.department_id, {
            "staff_id": sid,
            "role_in_department": role,
            "is_primary": primary,
            "joined_on": joined,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Added membership #{m.membership_id}")
    _pause()


def memberships_edit() -> None:
    print("\n═══ Edit Membership ═══")
    try:
        d = _pick_department()
        m = _pick_membership(d.department_id)
        role = _pick_from("Role", list(DEPT_ROLES),
                             default=m.role_in_department)
        primary = _yes_no("Primary?", default=m.is_primary)
        joined = _input("Joined on", default=m.joined_on,
                           allow_empty=False)
        left = _input("Left on (YYYY-MM-DD, blank = current)",
                         default=m.left_on or "")
        notes = _multiline("Notes",
                              default=m.notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_membership(m.membership_id, {
            "staff_id": m.staff_id,
            "role_in_department": role,
            "is_primary": primary,
            "joined_on": joined,
            "left_on": left or None,
            "notes": notes or None,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{m.membership_id}")
    _pause()


def memberships_end() -> None:
    print("\n═══ End Membership ═══")
    try:
        d = _pick_department()
        m = _pick_membership(d.department_id)
        when = _input("Left on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.end_membership(m.membership_id, left_on=when)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Ended #{m.membership_id}")
    _pause()


def memberships_delete() -> None:
    print("\n═══ Delete Membership ═══")
    try:
        d = _pick_department()
        m = _pick_membership(d.department_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete membership #{m.membership_id}? "
              "Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_membership(m.membership_id):
        print(f"\n  ✓ Deleted #{m.membership_id}")
    _pause()


def memberships_per_staff() -> None:
    print("\n═══ Per-Staff Memberships ═══")
    try:
        sid = _pick_staff()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.memberships_for_staff(sid)
    if not rows:
        print("\n  (none)")
    for m in rows:
        d = data.get_department(m.department_id)
        name = d.name if d else f"#{m.department_id}"
        flag = "*" if m.is_primary else " "
        print(f"  {flag} {name:<30}  "
              f"{m.role_in_department:<22}  "
              f"{m.joined_on} → {m.left_on or '—'}")
    _pause()


# ── Summary ─────────────────────────────────────────────

def summary_flow() -> None:
    print("\n═══ Departments Summary ═══")
    s = data.summary()
    print(f"\n  Total departments   : {s.total}")
    print(f"  Active              : {s.active}")
    print(f"  Restructuring       : {s.restructuring}")
    print(f"  Disbanded           : {s.disbanded}")
    print(f"  Total members       : {s.total_members}")
    print(f"  Distinct staff      : {s.distinct_staff}")
    print(f"  Budget total        : £{s.budget_total:.2f}")
    print(f"  Budget spent        : £{s.budget_spent:.2f}")
    print(f"  Over budget         : {s.budget_over_count}")
    print("\n  By faculty:")
    for k in FACULTIES:
        n = s.by_faculty.get(k, 0)
        if n:
            print(f"    {k:<26}: {n}")
    print("\n  By status:")
    for k in STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("── Departments ──",   lambda: None),
    ("List all",            departments_list),
    ("Active only",         departments_active),
    ("Over budget",         departments_over_budget),
    ("Filter",              departments_filter),
    ("View",                departments_view),
    ("New department",      departments_new),
    ("Edit department",     departments_edit),
    ("Change status",       departments_set_status),
    ("Add spend",           departments_add_spend),
    ("Delete department",   departments_delete),
    ("── Members ──",       lambda: None),
    ("List memberships",    memberships_list),
    ("Add member",          memberships_add),
    ("Edit membership",     memberships_edit),
    ("End membership",      memberships_end),
    ("Delete membership",   memberships_delete),
    ("Per-staff",           memberships_per_staff),
    ("──",                  lambda: None),
    ("Summary",             summary_flow),
]


def run() -> None:
    while True:
        print("\n── Departments ──")
        for i, (label, _) in enumerate(_MENU, 1):
            if label.startswith("─"):
                print(f"      {label}")
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
            logger.exception("Departments CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Departments":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Departments CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
