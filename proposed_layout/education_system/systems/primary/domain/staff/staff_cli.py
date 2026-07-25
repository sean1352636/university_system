"""CLI flows for the Primary School Staff Directory."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.primary.domain.staff import staff as data
from education_system.systems.primary.domain.staff.staff import (
    DEFAULT_DEPARTMENT,
    DEFAULT_EMPLOYMENT_STATUS,
    DEFAULT_ROLE,
    DEPARTMENTS,
    EMPLOYMENT_STATUSES,
    ROLES,
    Staff,
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
            print("    Enter a number (or 'cancel' to abort).")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _yes_no(prompt: str, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)", default="y" if default else "n")
    return raw.lower() in ("y", "yes")


# ── Print helpers ──────────────────────────────────────────────────

def _print_rows(rows: list[Staff]) -> None:
    if not rows:
        print("\n  (no staff)")
        return
    print()
    print(f"  {'ID':<10}  {'Name':<28}  {'Role':<22}  "
          f"{'Dept':<22}  {'Status':<14}  {'Flags':<10}  Email")
    print("  " + "-" * 130)
    for s in rows:
        flags = "".join([
            "T" if s.is_tutor else "-",
            "D" if s.is_dsl else "-",
            "E" if s.is_examiner else "-",
        ])
        name = (s.full_name)[:28]
        print(f"  {s.staff_id:<10}  {name:<28}  "
              f"{s.role[:22]:<22}  {s.department[:22]:<22}  "
              f"{s.employment_status:<14}  {flags:<10}  {s.email}")
    print(f"\n  {len(rows)} staff. (Flags: T=Tutor D=DSL E=Examiner)")


# ── Flows ──────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ Staff Directory ═══")
    _print_rows(data.list_staff())
    _row_action_loop()


def list_active() -> None:
    print("\n═══ Active Staff ═══")
    _print_rows(data.list_staff(active_only=True))
    _row_action_loop()


def filter_staff() -> None:
    print("\n═══ Filter Staff ═══")
    print("  (blank to skip; 'cancel' to abort)\n")
    try:
        role = _input("Role") or None
        dept = _input("Department") or None
        status = _input(f"Status ({'/'.join(EMPLOYMENT_STATUSES)})") or None
        tutor = _input("Tutor only? (y/n)") or None
        dsl = _input("DSL only? (y/n)") or None
        active = _yes_no("Active only?", default=True)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_staff(
            role=role, department=dept, employment_status=status,
            is_tutor=True if (tutor or "").lower() in ("y", "yes") else None,
            is_dsl=True if (dsl or "").lower() in ("y", "yes") else None,
            active_only=active,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_rows(rows)
    _row_action_loop()


def search_staff() -> None:
    print("\n═══ Search Staff ═══")
    try:
        q = _input("Query (id / name / email / role / dept)",
                    allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_rows(data.search_staff(q))
    _row_action_loop()


def view_staff(staff_id: str | None = None) -> None:
    print("\n═══ View Staff ═══")
    try:
        sid = staff_id or _input("Staff ID", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    s = data.get_staff(sid)
    if s is None:
        print(f"  ✗ No staff {sid}")
        _pause()
        return
    print()
    print(f"    Staff ID         : {s.staff_id}")
    print(f"    Name             : {s.full_name}")
    print(f"    Role             : {s.role}")
    print(f"    Department       : {s.department}")
    print(f"    Employment       : {s.employment_status}")
    print(f"    Email            : {s.email}")
    print(f"    Work phone       : {s.work_phone or '—'}")
    print(f"    Personal phone   : {s.personal_phone or '—'}")
    print(f"    Room             : {s.room or '—'}")
    print(f"    Line manager     : {s.line_manager or '—'}")
    print(f"    Start / end      : "
          f"{s.start_date or '—'}  /  {s.end_date or '—'}")
    print(f"    Tutor / DSL / Examiner : "
          f"{'Y' if s.is_tutor else 'N'}  "
          f"{'Y' if s.is_dsl else 'N'}  "
          f"{'Y' if s.is_examiner else 'N'}")
    if s.qualifications:
        print("\n    Qualifications:")
        for line in s.qualifications.splitlines() or [""]:
            print(f"      {line}")
    if s.notes:
        print("\n    Notes:")
        for line in s.notes.splitlines() or [""]:
            print(f"      {line}")
    reports = data.reports_to(s.staff_id)
    if reports:
        print(f"\n    Direct reports ({len(reports)}):")
        for r in reports:
            print(f"      {r.staff_id}  {r.full_name}  ({r.role})")
    _pause()


def _collect_form(existing: Staff | None) -> dict[str, Any]:
    is_edit = existing is not None
    p: dict[str, Any] = {}
    p["title"] = _input("Title (Mr/Ms/Dr/…)",
                          default=(existing.title or "") if is_edit else "")
    p["first_name"] = _input("First name",
                                default=existing.first_name if is_edit else "",
                                allow_empty=False)
    p["last_name"] = _input("Last name",
                               default=existing.last_name if is_edit else "",
                               allow_empty=False)
    p["role"] = _pick_from("Role", list(ROLES),
                              default=existing.role if is_edit
                              else DEFAULT_ROLE)
    p["department"] = _pick_from("Department", list(DEPARTMENTS),
                                    default=existing.department if is_edit
                                    else DEFAULT_DEPARTMENT)
    p["employment_status"] = _pick_from(
        "Employment status", list(EMPLOYMENT_STATUSES),
        default=existing.employment_status if is_edit
        else DEFAULT_EMPLOYMENT_STATUS)
    if is_edit:
        p["email"] = _input("Email", default=existing.email,
                              allow_empty=False)
    p["work_phone"] = _input("Work phone",
                                default=(existing.work_phone or "")
                                        if is_edit else "")
    p["personal_phone"] = _input(
        "Personal phone",
        default=(existing.personal_phone or "") if is_edit else "")
    p["room"] = _input("Room / office",
                          default=(existing.room or "") if is_edit else "")
    p["line_manager"] = _input(
        "Line manager (staff ID, optional)",
        default=(existing.line_manager or "") if is_edit else "")
    today = _date.today().isoformat()
    p["start_date"] = _input(
        "Start date (YYYY-MM-DD)",
        default=(existing.start_date or "") if is_edit else today)
    p["end_date"] = _input(
        "End date (optional)",
        default=(existing.end_date or "") if is_edit else "")
    p["is_tutor"] = _yes_no("Is a tutor?",
                              default=existing.is_tutor if is_edit else False)
    p["is_dsl"] = _yes_no("Is a DSL?",
                            default=existing.is_dsl if is_edit else False)
    p["is_examiner"] = _yes_no(
        "Is an examiner?",
        default=existing.is_examiner if is_edit else False)
    p["qualifications"] = _input(
        "Qualifications (single line)",
        default=(existing.qualifications or "") if is_edit else "")
    p["notes"] = _input("Notes",
                          default=(existing.notes or "") if is_edit else "")
    return p


def new_staff() -> None:
    print("\n═══ New Staff ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        s = data.create_staff(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created {s.staff_id} — {s.full_name} ({s.role})")
    print(f"    Email: {s.email}")
    _pause()


def edit_staff(staff_id: str | None = None) -> None:
    print("\n═══ Edit Staff ═══")
    try:
        sid = staff_id or _input("Staff ID", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_staff(sid)
    if existing is None:
        print(f"  ✗ No staff {sid}")
        _pause()
        return
    try:
        payload = _collect_form(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_staff(existing.staff_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated {existing.staff_id}")
    _pause()


def mark_left_flow(staff_id: str | None = None) -> None:
    print("\n═══ Mark Staff as Left ═══")
    try:
        sid = staff_id or _input("Staff ID", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_staff(sid)
    if existing is None:
        print(f"  ✗ No staff {sid}")
        _pause()
        return
    today = _date.today().isoformat()
    try:
        end = _input("End date", default=today, allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.mark_left(existing.staff_id, end)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Marked {existing.staff_id} as Left ({end})")
    _pause()


def delete_staff_flow(staff_id: str | None = None) -> None:
    print("\n═══ Delete Staff ═══")
    print("  ⚠ This will also clear line-manager links pointing to them.")
    try:
        sid = staff_id or _input("Staff ID", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_staff(sid)
    if existing is None:
        print(f"  ✗ No staff {sid}")
        _pause()
        return
    if _input(f"Delete {existing.staff_id} ({existing.full_name})? "
              f"Type 'yes'", default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_staff(existing.staff_id):
        print(f"\n  ✓ Deleted {existing.staff_id}")
    _pause()


def summary() -> None:
    print("\n═══ Staff Summary ═══")
    summ = data.summary()
    print(f"\n  Total           : {summ.total}")
    print(f"  Active          : {summ.active}")
    print(f"  Left            : {summ.left}")
    print(f"  Tutors          : {summ.tutors}")
    print(f"  DSLs            : {summ.dsls}")
    print(f"  Examiners       : {summ.examiners}")
    if summ.unfilled_critical:
        print(f"\n  ⚠ Unfilled critical roles: "
              f"{', '.join(summ.unfilled_critical)}")
    print("\n  By status:")
    for st in EMPLOYMENT_STATUSES:
        n = summ.by_status.get(st, 0)
        if n:
            print(f"    {st:<18} : {n}")
    print("\n  By role (with at least one):")
    for r in ROLES:
        n = summ.by_role.get(r, 0)
        if n:
            print(f"    {r:<28} : {n}")
    print("\n  By department (with at least one):")
    for d in DEPARTMENTS:
        n = summ.by_department.get(d, 0)
        if n:
            print(f"    {d:<28} : {n}")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _row_action_loop() -> None:
    print()
    print("  Actions:  V) View   E) Edit   L) Mark Left   "
          "D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "l", "d"):
            print("    Pick V, E, L, D, or Enter.")
            continue
        try:
            sid = _input("Staff ID", allow_empty=False)
        except _UserAbort:
            return
        if choice == "v":
            view_staff(sid)
        elif choice == "e":
            edit_staff(sid)
        elif choice == "l":
            mark_left_flow(sid)
        elif choice == "d":
            delete_staff_flow(sid)
        return


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List Active Staff",  list_active),
    ("List All Staff",     list_all),
    ("Filter Staff",       filter_staff),
    ("Search",             search_staff),
    ("View",               view_staff),
    ("New",                new_staff),
    ("Edit",               edit_staff),
    ("Mark as Left",       mark_left_flow),
    ("Delete",             delete_staff_flow),
    ("Summary",            summary),
]


def run() -> None:
    while True:
        print("\n── Staff Directory ──")
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
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Staff CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Staff Directory":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Staff CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
