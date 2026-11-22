"""CLI flows for Sixth Form Safeguarding.

⚠ Confidential data. Access is enforced in the domain layer: staff
without the safeguarding capability get only "Report a Concern".
Concerns are never deleted — "Close Concern (retain)" replaces the old
delete, and chronology entries are retracted with a reason.
"""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.sixth_form.domain.safeguarding import safeguarding
from education_system.systems.sixth_form.domain.safeguarding import safeguarding as data
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.domain.safeguarding.safeguarding import (
    ARCHIVED_STATUS,
    CATEGORIES,
    LINK_ROLES,
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
          f"{'Category':<22}  {'Risk':<8}  {'Status':<17}  Follow-up")
    print("  " + "-" * 92)
    for c in rows:
        print(f"  {c.concern_id:>4}  {c.student_id:<10}  "
              f"{c.concern_date:<10}  "
              f"{c.category[:22]:<22}  {c.risk_level:<8}  "
              f"{c.status:<17}  {c.follow_up_date or '—'}"
              + ("  [18+]" if c.adult_safeguarding else ""))
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
        category = _input("Category (exact)") or None
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
    print("    DSL notified       : "
          + ("Yes" + (f" — {c.dsl_name or '—'}"
                       + (f" ({c.dsl_notified_at})" if c.dsl_notified_at else ""))
              if c.dsl_notified else "No"))
    print("    Parents informed   : "
          + ("Yes" + (f" ({c.parents_informed_at})"
                       if c.parents_informed_at else "")
              if c.parents_informed else "No"))
    print(f"    External agencies  : {c.external_agencies or '—'}")
    print("    Referral made      : "
          + ("Yes" + (f" — {c.referral_ref or '—'}"
                       + (f" ({c.referral_date})" if c.referral_date else ""))
              if c.referral_made else "No"))
    print(f"    Follow-up date     : {c.follow_up_date or '—'}")
    age = c.age_at_concern
    print(f"    Age at concern     : {age if age is not None else '—'}"
          + ("  — ADULT SAFEGUARDING (Care Act 2014)"
             if c.adult_safeguarding else ""))
    print(f"    Suggested agencies : {', '.join(c.suggested_agencies)}")
    linked = data.linked_students(c.concern_id)
    if linked:
        print("    Linked learners    : " + "; ".join(
            f"{x.student_id} {x.student_name or ''} ({x.link_role})"
            for x in linked))
    prev = data.prevent_links(c.concern_id)
    if prev:
        print("    Linked Prevent     : " + "; ".join(
            f"#{pc.concern_id} {pc.concern_type} ({pc.status})"
            for pc in prev))
    if c.body_map_ref or c.body_map_notes:
        print(f"    Body map           : {c.body_map_ref or '—'} "
              f"{c.body_map_notes or ''}")
    if c.access_level == "Restricted":
        print(f"    Restricted notes   : {c.restricted_notes or '—'}")
    if c.is_archived:
        print(f"    Closed — retained  : {c.archived_reason} "
              f"(by {c.archived_by}, {c.archived_at})")
    print()
    print("    Description:")
    for line in c.description.splitlines() or [""]:
        print(f"      {line}")
    if c.action_taken:
        print("\n    Action taken:")
        for line in c.action_taken.splitlines() or [""]:
            print(f"      {line}")
    if c.notes:
        print("\n    Notes:")
        for line in c.notes.splitlines() or [""]:
            print(f"      {line}")

    updates = data.list_updates(c.concern_id)
    print(f"\n    Chronology ({len(updates)} entry/entries):")
    if not updates:
        print("      (none)")
    for u in updates:
        print(f"      [{u.update_date}] (by {u.updated_by or '—'}) "
              f"#{u.update_id}"
              + (f"  [RETRACTED by {u.retracted_by}: {u.retracted_reason}]"
                 if u.retracted else ""))
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
    payload["body_map_ref"] = _input(
        "Body map reference (optional)",
        default=(existing.body_map_ref or "") if is_edit else "",
    )
    payload["body_map_notes"] = _input(
        "Body map notes (optional)",
        default=(existing.body_map_notes or "") if is_edit else "",
    )
    if data.can_see_restricted():
        payload["restricted_notes"] = _input(
            "Restricted notes — DSL only (optional)",
            default=(existing.restricted_notes or "") if is_edit else "",
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
    print("\n═══ Close Concern (retain) ═══")
    print("  Safeguarding records are kept, never deleted. The concern is "
          f"marked '{ARCHIVED_STATUS}' with your reason.")
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
    if existing.is_archived:
        print(f"  Concern #{cid} is already {ARCHIVED_STATUS}.")
        _pause()
        return
    try:
        reason = _input(
            f"Reason for closing #{cid} ({existing.category}, "
            f"{existing.risk_level})", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.archive_concern(cid, reason=reason)
        print(f"\n  ✓ Concern #{cid} closed — retained")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except Exception as e:
        logger.exception("archive_concern crashed")
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
    print("\n═══ Retract Chronology Entry ═══")
    print("  The entry stays on the file, struck through with your reason.")
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
    try:
        reason = _input(f"Reason for retracting entry #{uid}",
                        allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.retract_update(uid, reason=reason)
        print(f"\n  ✓ Entry #{uid} retracted")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except Exception as e:
        logger.exception("retract_update crashed")
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
    print(f"    Unreviewed reports : {summ.unreviewed_reports}")
    print(f"    Open — learner 18+ : {summ.adult_open}")
    print(f"    Closed — retained  : {summ.archived}")
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
          "D) Close (retain)   (Enter to go back)")
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


# ── Report a concern (any member of staff) ───────────────────────

def report_concern_flow() -> None:
    print("\n═══ Report a Safeguarding Concern ═══")
    print("  If a learner is in immediate danger call 999, then tell the DSL")
    print("  in person. Record what you saw or were told, in the learner's")
    print("  words where you can. You will not be able to open the record")
    print("  afterwards — it goes straight to the DSL team.")
    try:
        sid = _pick_student()
        age = data.student_age(sid)
        if age is not None and age >= data.ADULT_AGE:
            print(f"    Learner is {age}: adult safeguarding — the DSL will "
                  "consider adult social care (Care Act 2014).")
        when = _input("When did it happen (YYYY-MM-DD)",
                      default=_date.today().isoformat(), allow_empty=False)
        category = _pick_from("What kind of concern", list(CATEGORIES),
                              default="Other")
        ctype = _pick_from("How you know", list(CONCERN_TYPES),
                           default="Disclosure")
        risk = _pick_from("How worried are you", list(RISK_LEVELS),
                          default="Medium")
        desc = _input("What you saw / were told", allow_empty=False)
        action = _input("Anything you did (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        receipt = data.report_concern(
            sid, desc, category=category, concern_type=ctype,
            risk_level=risk, concern_date=when, action_taken=action)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {receipt.message}")
    _pause()


def my_reports_flow() -> None:
    print("\n═══ Concerns I Have Filed ═══")
    rows = data.my_reports()
    if not rows:
        print("  (none)")
    for r in rows:
        print(f"  #{r.concern_id:>4}  {r.student_id:<10}  filed {r.reported_at}")
    _pause()


def run_report() -> None:
    """Menu for staff without safeguarding access."""
    menu = [("Report a Concern", report_concern_flow),
            ("Concerns I Have Filed", my_reports_flow)]
    while True:
        print("\n── Report a Safeguarding Concern ──")
        for i, (label, _) in enumerate(menu, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(menu)):
            print("  Invalid selection.")
            continue
        try:
            menu[int(choice) - 1][1]()
        except _UserAbort:
            print("\n  Cancelled.")


def dispatch_report(label: str) -> bool:
    if label != "Report a Safeguarding Concern":
        return False
    run_report()
    return True


def unreviewed_flow() -> None:
    print("\n═══ Unreviewed Reports ═══")
    rows = data.list_unreviewed()
    _print_concerns(rows)
    if not rows:
        _pause()
        return
    try:
        raw = _input("Acknowledge concern # (blank to skip)")
    except _UserAbort:
        return
    if raw.isdigit():
        try:
            data.acknowledge_report(int(raw))
            print(f"  ✓ Concern #{raw} acknowledged")
        except ValidationError as e:
            print(f"  ✗ {e}")
    _pause()


def _ask_concern_id() -> int:
    raw = _input("Concern ID", allow_empty=False)
    if not raw.isdigit():
        print("  ✗ Concern ID must be a number.")
        raise _UserAbort
    return int(raw)


def link_student_flow() -> None:
    print("\n═══ Link Learner to Concern ═══")
    try:
        cid = _ask_concern_id()
        for x in data.linked_students(cid):
            print(f"    linked #{x.link_id}: {x.student_id} "
                  f"{x.student_name or ''} ({x.link_role})")
        if _yes_no("Remove an existing link instead?"):
            lid = int(_input("Link #", allow_empty=False))
            reason = _input("Reason", allow_empty=False)
            print("  ✓ Removed" if data.unlink_student(lid, reason=reason)
                  else "  ✗ No such link")
            _pause()
            return
        sid = _pick_student()
        role = _pick_from("Role", list(LINK_ROLES), default=LINK_ROLES[0])
    except (_UserAbort, ValueError):
        print("\n  Cancelled.")
        return
    try:
        data.link_student(cid, sid, link_role=role)
        print(f"\n  ✓ Linked {sid} to concern #{cid}")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    _pause()


def link_prevent_flow() -> None:
    print("\n═══ Link Prevent Concern ═══")
    from education_system.systems.sixth_form.domain.safeguarding.prevent_duty import (
        prevent_duty as _pd,
    )
    try:
        cid = _ask_concern_id()
        c = data.get_concern(cid)
        if c is None:
            print(f"  ✗ No concern #{cid}")
            _pause()
            return
        rows = _pd.list_concerns(student_id=c.student_id)
        if not rows:
            print("  This learner has no Prevent concerns.")
            _pause()
            return
        for pc in rows:
            print(f"    #{pc.concern_id}  {pc.report_date}  "
                  f"{pc.concern_type}  ({pc.status})")
        pid = int(_input("Prevent concern #", allow_empty=False))
        note = _input("Note (optional)")
    except (_UserAbort, ValueError):
        print("\n  Cancelled.")
        return
    try:
        data.link_prevent_concern(cid, pid, note=note)
        print(f"\n  ✓ Prevent #{pid} linked to concern #{cid}")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    _pause()


def attachments_flow() -> None:
    print("\n═══ Attachments / Body Map ═══")
    try:
        cid = _ask_concern_id()
        for a in data.list_attachments(cid):
            print(f"    #{a.attachment_id}  {a.title}  {a.file_ref}  "
                  f"({a.uploaded_by or '—'}, {a.uploaded_on})")
        choice = _pick_from("Action", ["Add attachment", "Set body map",
                                       "Back"], default="Back")
        if choice == "Add attachment":
            title = _input("Title", allow_empty=False)
            ref = _input("File reference (path / document id)",
                         allow_empty=False)
            data.add_attachment(cid, title=title, file_ref=ref)
            print("  ✓ Attached")
        elif choice == "Set body map":
            c = data.get_concern(cid)
            ref = _input("Body map reference",
                         default=(c.body_map_ref or "") if c else "")
            notes = _input("What it shows",
                           default=(c.body_map_notes or "") if c else "")
            data.set_body_map(cid, body_map_ref=ref, body_map_notes=notes)
            print("  ✓ Body map recorded")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    _pause()


def restricted_notes_flow() -> None:
    print("\n═══ Restricted Notes (DSL only) ═══")
    try:
        cid = _ask_concern_id()
        c = data.get_concern(cid)
        notes = _input("Restricted notes",
                       default=(c.restricted_notes or "") if c else "")
        data.set_restricted_notes(cid, notes)
        print("  ✓ Saved")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    except (ValidationError, data.AccessDenied) as e:
        print(f"\n  ✗ {e}")
    _pause()


def chronology_flow() -> None:
    print("\n═══ Learner Safeguarding Chronology ═══")
    try:
        sid = _input("Student ID (leavers too)", allow_empty=False)
    except _UserAbort:
        return
    rows = data.student_chronology(sid)
    if not rows:
        print("  (no entries)")
    for e in rows:
        print(f"  {e.date or '—':<10}  {e.kind:<9} {e.ref:<12} {e.title}"
              + ("  [RETRACTED]" if e.retracted else ""))
        if e.by:
            print(f"              by {e.by}")
        for line in (e.detail or "").splitlines():
            print(f"              {line}")
    _pause()


def who_viewed_flow() -> None:
    print("\n═══ Who Viewed a Record ═══")
    try:
        raw = _input("Concern # (blank for a learner)")
        sid = None if raw else _input("Student ID", allow_empty=False)
    except _UserAbort:
        return
    rows = data.who_viewed(concern_id=int(raw) if raw.isdigit() else None,
                           student_id=sid)
    if not rows:
        print("  (no entries)")
    for r in rows:
        print(f"  {r.get('at')}  {r.get('username'):<16} "
              f"{r.get('action'):<22} {r.get('student_id') or '':<10} "
              f"{r.get('record_ref') or '':<14} "
              + ("" if r.get("allowed") else "REFUSED"))
    _pause()


def _casework(name: str) -> Callable[[], None]:
    def run_area() -> None:
        from education_system.systems.sixth_form.interfaces.cli.safeguarding import (
            safeguarding_casework_cli as _cw_cli,
        )
        getattr(_cw_cli, name)()
    return run_area


# ── Submenu dispatcher ────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List Open Concerns",      list_open),
    ("List All Concerns",       list_all),
    ("Filter Concerns",         filter_concerns),
    ("Per-Student",             per_student),
    ("View Concern",            view_concern),
    ("New Concern",             new_concern),
    ("Edit Concern",            edit_concern),
    ("Close Concern (retain)",  delete_concern_flow),
    ("Add Chronology Entry",    add_update_flow),
    ("Edit Chronology Entry",   edit_update_flow),
    ("Retract Chronology Entry", delete_update_flow),
    ("Summary",                 summary),
    ("Report a Concern",        report_concern_flow),
    ("Unreviewed Reports",      unreviewed_flow),
    ("Link Learner to Concern", link_student_flow),
    ("Link Prevent Concern",    link_prevent_flow),
    ("Attachments / Body Map",  attachments_flow),
    ("Restricted Notes",        restricted_notes_flow),
    ("Learner Chronology",      chronology_flow),
    ("Who Viewed a Record",     who_viewed_flow),
    ("Referrals",               _casework("run_referrals")),
    ("Plans (CP / CIN / EH)",   _casework("run_plans")),
    ("LADO Register",           _casework("run_lado")),
    ("File Transfers",          _casework("run_transfers")),
    ("Casework Summary",        _casework("casework_summary_flow")),
]


def run() -> None:
    if not data.can_read():
        # KCSIE: anyone can report; only the DSL team reads the record.
        run_report()
        return
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
        except data.AccessDenied as e:
            print(f"\n  ✗ {e}")
            _pause()
        except Exception as e:
            logger.exception("Safeguarding CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if dispatch_report(label):
        return True
    if label == "LADO Allegations":
        from education_system.systems.sixth_form.interfaces.cli.safeguarding import (
            safeguarding_casework_cli as _cw_cli,
        )
        _cw_cli.run_lado()
        return True
    if label != "Safeguarding":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Safeguarding CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
