"""CLI flows for Sixth Form Safeguarding.

⚠ Confidential data: access should be restricted to DSL / safeguarding
staff by the auth layer.
"""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.pastoral.safeguarding import safeguarding
from education_system.sixthform_system.modules.domain.pastoral.safeguarding import safeguarding as data
from education_system.sixthform_system.modules.domain.students.students import students as student_data
from education_system.sixthform_system.modules.domain.pastoral.safeguarding.safeguarding import (
    CATEGORIES,
    CONCERN_TYPES,
    Concern,
    DEFAULT_STATUS,
    OPEN_STATUSES,
    RISK_LEVELS,
    STATUSES,
    Update,
    ValidationError,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Prompt helpers ─────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "", allow_empty: bool = True) -> str:
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


def _pick_from(label: str, options: list[str], default: str | None = None) -> str:
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
            print(f"    Out of range (1..{len(options)}).")
            continue
        return options[n - 1]


def _yes_no(prompt: str, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)", default="y" if default else "n")
    return raw.lower() in ("y", "yes")


def _pick_student() -> str:
    students = student_data.list_students()
    if not students:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(students, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    while True:
        raw = _input(f"  Pick #1..{len(students)} (or student ID)",
                     allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(students):
                return students[n - 1].student_id
            print(f"    Out of range (1..{len(students)}).")
            continue
        match = next((s for s in students
                      if s.student_id.lower() == raw.lower()), None)
        if match:
            return match.student_id
        print("    No matching student.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_concerns(rows: list[Concern]) -> None:
    if not rows:
        print("\n  (no concerns)")
        return
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Date':<10}  "
          f"{'Category':<22}  {'Risk':<8}  {'Status':<14}  Follow-up")
    print("  " + "-" * 88)
    for c in rows:
        print(f"  {c.concern_id:>4}  {c.student_id:<10}  "
              f"{c.concern_date:<10}  "
              f"{c.category[:22]:<22}  {c.risk_level:<8}  "
              f"{c.status:<14}  {c.follow_up_date or '—'}")
    print(f"\n  {len(rows)} concern(s).")


# ── CRUD entry points ──────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ Safeguarding Concerns ═══")
    print("  ⚠ Confidential — DSL / safeguarding leads only.")
    rows = data.list_concerns()
    _print_concerns(rows)
    _row_action_loop(rows)


def list_open() -> None:
    print("\n═══ Open Safeguarding Concerns ═══")
    rows = data.list_concerns(open_only=True)
    _print_concerns(rows)
    _row_action_loop(rows)


def filter_concerns() -> None:
    print("\n═══ Filter Concerns ═══")
    print("  (leave any field blank to skip; 'cancel' to abort)\n")
    try:
        sid = _input("Student ID") or None
        risk = _input(f"Risk level ({'/'.join(RISK_LEVELS)})") or None
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        category = _input(f"Category (exact)") or None
        date_from = _input("From (YYYY-MM-DD)") or None
        date_to = _input("To (YYYY-MM-DD)") or None
        open_only = _yes_no("Open only?", default=True)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_concerns(
            student_id=sid, risk_level=risk, status=status,
            category=category, date_from=date_from, date_to=date_to,
            open_only=open_only,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_concerns(rows)
    _row_action_loop(rows)


def per_student() -> None:
    print("\n═══ Per-Student Concerns ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    student = student_data.get_student(sid)
    rows = data.concerns_for_student(sid)
    print(f"\n  {student.student_id}  {student.full_name}")
    _print_concerns(rows)
    _row_action_loop(rows)


def view_concern(concern_id: int | None = None) -> None:
    print("\n═══ View Concern ═══")
    try:
        cid = concern_id if concern_id is not None else int(
            _input("Concern ID", allow_empty=False))
    except ValueError:
        print("  ✗ Concern ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    c = data.get_concern(cid)
    if c is None:
        print(f"  ✗ No concern #{cid}")
        _pause()
        return
    print()
    print(f"    Concern ID         : #{c.concern_id}")
    print(f"    Student            : {c.student_id}")
    print(f"    Concern date       : {c.concern_date}")
    print(f"    Reported date      : {c.reported_date}")
    print(f"    Type               : {c.concern_type}")
    print(f"    Category           : {c.category}")
    print(f"    Risk level         : {c.risk_level}")
    print(f"    Status             : {c.status}")
    print(f"    Reported by        : {c.reported_by}")
    print(f"    DSL notified       : "
          + ("Yes" + (f" — {c.dsl_name or '—'}"
                       + (f" ({c.dsl_notified_at})" if c.dsl_notified_at else ""))
              if c.dsl_notified else "No"))
    print(f"    Parents informed   : "
          + ("Yes" + (f" ({c.parents_informed_at})"
                       if c.parents_informed_at else "")
              if c.parents_informed else "No"))
    print(f"    External agencies  : {c.external_agencies or '—'}")
    print(f"    Referral made      : "
          + ("Yes" + (f" — {c.referral_ref or '—'}"
                       + (f" ({c.referral_date})" if c.referral_date else ""))
              if c.referral_made else "No"))
    print(f"    Follow-up date     : {c.follow_up_date or '—'}")
    print()
    print(f"    Description:")
    for line in c.description.splitlines() or [""]:
        print(f"      {line}")
    if c.action_taken:
        print(f"\n    Action taken:")
        for line in c.action_taken.splitlines() or [""]:
            print(f"      {line}")
    if c.notes:
        print(f"\n    Notes:")
        for line in c.notes.splitlines() or [""]:
            print(f"      {line}")

    updates = data.list_updates(c.concern_id)
    print(f"\n    Chronology ({len(updates)} entry/entries):")
    if not updates:
        print("      (none)")
    for u in updates:
        print(f"      [{u.update_date}] (by {u.updated_by or '—'}) "
              f"#{u.update_id}")
        for line in u.update_text.splitlines() or [""]:
            print(f"          {line}")
    _pause()


def _collect_form(existing: Concern | None) -> dict[str, Any]:
    is_edit = existing is not None
    payload: dict[str, Any] = {}

    if is_edit:
        print(f"\n  Editing concern #{existing.concern_id} "
              f"for {existing.student_id}")
        payload["student_id"] = existing.student_id
    else:
        print("\n  ── Student ──")
        payload["student_id"] = _pick_student()

    print("\n  ── Concern details ──")
    today = _date.today().isoformat()
    payload["concern_date"] = _input(
        "Concern date (YYYY-MM-DD)",
        default=(existing.concern_date if is_edit else today),
        allow_empty=False,
    )
    payload["reported_date"] = _input(
        "Reported date (YYYY-MM-DD)",
        default=(existing.reported_date if is_edit else today),
        allow_empty=False,
    )
    payload["concern_type"] = _pick_from(
        "Concern type", list(CONCERN_TYPES),
        default=(existing.concern_type if is_edit else CONCERN_TYPES[0]),
    )
    payload["category"] = _pick_from(
        "Category", list(CATEGORIES),
        default=(existing.category if is_edit else CATEGORIES[0]),
    )
    payload["risk_level"] = _pick_from(
        "Risk level", list(RISK_LEVELS),
        default=(existing.risk_level if is_edit else "Medium"),
    )
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS),
    )
    payload["reported_by"] = _input(
        "Reported by",
        default=(existing.reported_by if is_edit else ""),
        allow_empty=False,
    )
    print("\n  Description (single line — use the GUI for multi-line):")
    payload["description"] = _input(
        "Description",
        default=(existing.description if is_edit else ""),
        allow_empty=False,
    )
    payload["action_taken"] = _input(
        "Action taken (optional)",
        default=(existing.action_taken or "") if is_edit else "",
    )

    print("\n  ── DSL & notifications ──")
    payload["dsl_notified"] = _yes_no(
        "DSL notified?",
        default=(existing.dsl_notified if is_edit else False),
    )
    if payload["dsl_notified"]:
        payload["dsl_name"] = _input(
            "DSL name",
            default=(existing.dsl_name or "") if is_edit else "",
        )
        payload["dsl_notified_at"] = _input(
            "DSL notified date (YYYY-MM-DD, optional)",
            default=(existing.dsl_notified_at or today)
                   if is_edit else today,
        )
    else:
        payload["dsl_name"] = ""
        payload["dsl_notified_at"] = ""

    payload["parents_informed"] = _yes_no(
        "Parents informed?",
        default=(existing.parents_informed if is_edit else False),
    )
    if payload["parents_informed"]:
        payload["parents_informed_at"] = _input(
            "Parents informed date (optional)",
            default=(existing.parents_informed_at or today)
                   if is_edit else today,
        )
    else:
        payload["parents_informed_at"] = ""

    payload["external_agencies"] = _input(
        "External agencies (comma-separated, optional)",
        default=(existing.external_agencies or "") if is_edit else "",
    )
    payload["referral_made"] = _yes_no(
        "Referral made?",
        default=(existing.referral_made if is_edit else False),
    )
    if payload["referral_made"]:
        payload["referral_date"] = _input(
            "Referral date (optional)",
            default=(existing.referral_date or today)
                   if is_edit else today,
        )
        payload["referral_ref"] = _input(
            "Referral reference (optional)",
            default=(existing.referral_ref or "") if is_edit else "",
        )
    else:
        payload["referral_date"] = ""
        payload["referral_ref"] = ""

    payload["follow_up_date"] = _input(
        "Follow-up date (YYYY-MM-DD, optional)",
        default=(existing.follow_up_date or "") if is_edit else "",
    )
    payload["notes"] = _input(
        "Notes (optional)",
        default=(existing.notes or "") if is_edit else "",
    )
    return payload


def new_concern() -> None:
    print("\n═══ New Safeguarding Concern ═══")
    print("  ⚠ Confidential. Type 'cancel' at any prompt to abort.")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        c = data.create_concern(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("create_concern crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Created concern #{c.concern_id} "
          f"({c.category}, risk={c.risk_level}, {c.status})")
    _pause()


def edit_concern(concern_id: int | None = None) -> None:
    print("\n═══ Edit Concern ═══")
    try:
        cid = concern_id if concern_id is not None else int(
            _input("Concern ID", allow_empty=False))
    except ValueError:
        print("  ✗ Concern ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_concern(cid)
    if existing is None:
        print(f"  ✗ No concern #{cid}")
        _pause()
        return
    try:
        payload = _collect_form(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_concern(cid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("update_concern crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Updated concern #{cid}")
    _pause()


def delete_concern_flow(concern_id: int | None = None) -> None:
    print("\n═══ Delete Concern ═══")
    print("  ⚠ This will also remove the chronology of updates.")
    try:
        cid = concern_id if concern_id is not None else int(
            _input("Concern ID", allow_empty=False))
    except ValueError:
        print("  ✗ Concern ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_concern(cid)
    if existing is None:
        print(f"  ✗ No concern #{cid}")
        _pause()
        return
    confirm = _input(
        f"Delete concern #{cid} ({existing.category}, {existing.risk_level})? "
        f"Type 'yes' to confirm",
        default="no")
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_concern(cid):
            print(f"\n  ✓ Deleted #{cid}")
    except Exception as e:
        logger.exception("delete_concern crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Chronology / updates ──────────────────────────────────────────

def add_update_flow() -> None:
    print("\n═══ Add Chronology Entry ═══")
    try:
        cid = int(_input("Concern ID", allow_empty=False))
    except ValueError:
        print("  ✗ Concern ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if data.get_concern(cid) is None:
        print(f"  ✗ No concern #{cid}")
        _pause()
        return
    today = _date.today().isoformat()
    try:
        date_s = _input("Update date (YYYY-MM-DD)", default=today,
                        allow_empty=False)
        by = _input("Updated by")
        print("\n  Entry text (single line — use the GUI for multi-line):")
        text = _input("Entry", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        u = data.add_update(cid, {
            "update_date": date_s, "updated_by": by, "update_text": text,
        })
        print(f"\n  ✓ Added chronology entry #{u.update_id}")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except Exception as e:
        logger.exception("add_update crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


def edit_update_flow() -> None:
    print("\n═══ Edit Chronology Entry ═══")
    try:
        uid = int(_input("Update ID", allow_empty=False))
    except ValueError:
        print("  ✗ Update ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_update(uid)
    if existing is None:
        print(f"  ✗ No update #{uid}")
        _pause()
        return
    try:
        date_s = _input("Update date", default=existing.update_date,
                        allow_empty=False)
        by = _input("Updated by", default=existing.updated_by or "")
        text = _input("Entry", default=existing.update_text,
                      allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.edit_update(uid, {
            "update_date": date_s, "updated_by": by, "update_text": text,
        })
        print(f"\n  ✓ Updated chronology entry #{uid}")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except Exception as e:
        logger.exception("edit_update crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


def delete_update_flow() -> None:
    print("\n═══ Delete Chronology Entry ═══")
    try:
        uid = int(_input("Update ID", allow_empty=False))
    except ValueError:
        print("  ✗ Update ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if data.get_update(uid) is None:
        print(f"  ✗ No update #{uid}")
        _pause()
        return
    confirm = _input(
        f"Delete chronology entry #{uid}? Type 'yes'",
        default="no")
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_update(uid):
            print(f"\n  ✓ Deleted #{uid}")
    except Exception as e:
        logger.exception("delete_update crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Summary ───────────────────────────────────────────────────────

def summary() -> None:
    print("\n═══ Safeguarding Summary ═══")
    try:
        upcoming = int(_input("Follow-up window in days", default="14"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    summ = data.summary(upcoming_window_days=upcoming)
    print(f"\n  Total concerns : {summ.total}")
    print(f"  Open           : {summ.open_count}")
    print("\n  Alerts:")
    print(f"    High/Critical open : {summ.high_risk_open}")
    print(f"    Overdue follow-ups : {summ.overdue_follow_ups}")
    print(f"    Upcoming ({upcoming}d)   : {summ.upcoming_follow_ups}")
    print("\n  By risk:")
    for r in RISK_LEVELS:
        print(f"    {r:<10} : {summ.by_risk.get(r, 0)}")
    print("\n  By status:")
    for s in STATUSES:
        print(f"    {s:<22} : {summ.by_status.get(s, 0)}")
    if summ.by_category:
        print("\n  Top categories:")
        for cat, n in sorted(summ.by_category.items(),
                              key=lambda kv: -kv[1])[:10]:
            print(f"    {cat[:30]:<30} : {n}")
    print("\n  Notifications & referrals:")
    print(f"    DSL notified     : {summ.dsl_notified}")
    print(f"    Parents informed : {summ.parents_informed}")
    print(f"    Referrals made   : {summ.referrals}")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _row_action_loop(rows: list[Concern]) -> None:
    if not rows:
        _pause()
        return
    print()
    print("  Actions:  V) View   E) Edit   A) Add chronology   "
          "D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "a", "d"):
            print("    Pick V, E, A, D, or Enter.")
            continue
        try:
            raw = _input("Concern ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            cid = int(raw)
        except ValueError:
            print("    Concern ID must be a whole number.")
            continue
        if choice == "v":
            view_concern(cid)
        elif choice == "e":
            edit_concern(cid)
        elif choice == "a":
            _add_update_for(cid)
        elif choice == "d":
            delete_concern_flow(cid)
        return


def _add_update_for(concern_id: int) -> None:
    """Variant that skips the concern_id prompt."""
    if data.get_concern(concern_id) is None:
        print(f"  ✗ No concern #{concern_id}")
        _pause()
        return
    today = _date.today().isoformat()
    try:
        date_s = _input("Update date (YYYY-MM-DD)", default=today,
                        allow_empty=False)
        by = _input("Updated by")
        text = _input("Entry", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        u = data.add_update(concern_id, {
            "update_date": date_s, "updated_by": by, "update_text": text,
        })
        print(f"\n  ✓ Added chronology entry #{u.update_id}")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except Exception as e:
        logger.exception("add_update crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Submenu dispatcher ────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List Open Concerns",      list_open),
    ("List All Concerns",       list_all),
    ("Filter Concerns",         filter_concerns),
    ("Per-Student",             per_student),
    ("View Concern",            view_concern),
    ("New Concern",             new_concern),
    ("Edit Concern",            edit_concern),
    ("Delete Concern",          delete_concern_flow),
    ("Add Chronology Entry",    add_update_flow),
    ("Edit Chronology Entry",   edit_update_flow),
    ("Delete Chronology Entry", delete_update_flow),
    ("Summary",                 summary),
]


def run() -> None:
    while True:
        print("\n── Safeguarding ──")
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
            logger.exception("Safeguarding CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Safeguarding":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Safeguarding CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
