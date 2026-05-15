"""CLI flows for Sixth Form Value Added."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.assessment.value_added import (
    value_added as data,
)
from education_system.sixthform_system.modules.domain.students.students import (
    students as student_data,
)
from education_system.sixthform_system.modules.domain.assessment.value_added.value_added import (
    ALPS_INDICATORS,
    A_LEVEL_GRADES,
    DEFAULT_STATUS,
    STATUSES,
    VARecord,
    ValidationError,
    YEAR_GROUPS,
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
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
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


def _pick_grade(label: str, *, default: str | None = None,
                 allow_empty: bool = False) -> str | None:
    opts = list(A_LEVEL_GRADES) if not allow_empty \
        else [""] + list(A_LEVEL_GRADES)
    res = _pick_from(label, opts, default=default or "")
    return res or None


def _pick_student() -> str:
    rows = student_data.list_students()
    if not rows:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(rows, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or student id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].student_id
            continue
        match = next((s for s in rows
                       if s.student_id.lower() == raw.lower()), None)
        if match:
            return match.student_id
        print("    No matching student.")


def _pick_subject() -> str:
    try:
        from education_system.sixthform_system.modules.domain.academics.subjects import (
            subjects as _subjects,
        )
        names = [s.name for s in _subjects.list_subjects()]
    except Exception:
        names = []
    if not names:
        return _input("Subject", allow_empty=False)
    return _pick_from("Subject", names)


def _pick_record() -> VARecord:
    rows = data.list_records()
    if not rows:
        print("    No VA records.")
        raise _UserAbort
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print("\n  VA records:")
    for i, r in enumerate(rows, 1):
        print(f"    {i:>3}) #{r.record_id}  {r.student_id}  "
              f"{names.get(r.student_id, '?')[:14]:<14}  "
              f"{r.subject_name[:18]:<18}  "
              f"{r.exam_session[:12]:<12}  "
              f"E={r.expected_grade or '—'} A={r.actual_grade or '—'} "
              f"va={r.va_label}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows if r.record_id == n), None)
            if match:
                return match
        print("    No matching record.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_records(rows: list[VARecord]) -> None:
    if not rows:
        print("\n  (no records)")
        return
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Name':<18}  "
          f"{'Subject':<16}  {'Session':<14}  "
          f"{'Exp':<4}  {'Tgt':<4}  {'Pred':<5}  "
          f"{'Act':<4}  {'VA':<7}  {'ALPS':<5}  Status")
    print("  " + "-" * 130)
    for r in rows:
        print(f"  {r.record_id:>4}  {r.student_id:<10}  "
              f"{names.get(r.student_id, '?')[:18]:<18}  "
              f"{r.subject_name[:16]:<16}  "
              f"{r.exam_session[:14]:<14}  "
              f"{(r.expected_grade or '—'):<4}  "
              f"{(r.target_grade or '—'):<4}  "
              f"{(r.predicted_grade or '—'):<5}  "
              f"{(r.actual_grade or '—'):<4}  "
              f"{r.va_label:<7}  "
              f"{(str(r.alps_indicator) if r.alps_indicator is not None else '—'):<5}  "
              f"{r.status}")
    print(f"\n  {len(rows)} record(s).")


def _print_record_full(r: VARecord) -> None:
    print()
    print(f"    #{r.record_id}")
    print(f"    Student          : {r.student_id}")
    print(f"    Subject          : {r.subject_name}")
    print(f"    Exam session     : {r.exam_session}")
    print(f"    Year group       : {r.year_group or '—'}")
    print(f"    Prior attainment : "
          f"{r.prior_attainment if r.prior_attainment is not None else '—'}")
    print(f"    Expected grade   : {r.expected_grade or '—'}")
    print(f"    Target grade     : {r.target_grade or '—'}")
    print(f"    Predicted grade  : {r.predicted_grade or '—'}")
    print(f"    Actual grade     : {r.actual_grade or '—'}")
    print(f"    VA score         : {r.va_label}")
    print(f"    ALPS indicator   : "
          f"{r.alps_indicator if r.alps_indicator is not None else '—'}")
    print(f"    Status           : {r.status}")
    print(f"    Teacher          : {r.teacher or '—'}")
    if r.actual_vs_target is not None:
        print(f"    Actual vs target : "
              f"{r.actual_vs_target:+d}")
    if r.predicted_vs_target is not None:
        print(f"    Pred vs target   : "
              f"{r.predicted_vs_target:+d}")
    if r.notes:
        print()
        print("    Notes:")
        for line in r.notes.splitlines():
            print(f"      {line}")


# ── Flows ──────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All VA Records ═══")
    _print_records(data.list_records())
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter VA Records ═══")
    try:
        sid = _input("Student id") or None
        subject = _input("Subject (exact)") or None
        session = _input("Exam session") or None
        year = _input(f"Year ({'/'.join(YEAR_GROUPS)})") or None
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        teacher = _input("Teacher contains") or None
        pos_raw = _input("Positive VA only? (y/n)", default="n")
        neg_raw = _input("Negative VA only? (y/n)", default="n")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_records(
            student_id=sid, subject_name=subject,
            exam_session=session, year_group=year, status=status,
            teacher_like=teacher,
            positive_only=pos_raw.lower() in ("y", "yes"),
            negative_only=neg_raw.lower() in ("y", "yes"),
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_records(rows)
    _pause()


def per_student_flow() -> None:
    print("\n═══ Per-Student ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_records(data.records_for_student(sid))
    ssum = data.student_summary(sid)
    print(f"\n  Summary for {sid}:")
    print(f"    Records      : {ssum.total}")
    print(f"    Average VA   : "
          f"{ssum.average_va if ssum.average_va is not None else '—'}")
    if ssum.by_subject:
        print("    By subject:")
        for sub, val in ssum.by_subject.items():
            print(f"      {sub:<22} : {val:+.2f}")
    _pause()


def view_flow() -> None:
    print("\n═══ View VA Record ═══")
    try:
        r = _pick_record()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_record_full(r)
    _pause()


def _collect_form(existing: VARecord | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        payload["student_id"] = existing.student_id
        payload["subject_name"] = existing.subject_name
        payload["exam_session"] = existing.exam_session
        print(f"\n  Editing {existing.student_id} × "
              f"{existing.subject_name} × {existing.exam_session}")
    else:
        payload["student_id"] = _pick_student()
        payload["subject_name"] = _pick_subject()
        payload["exam_session"] = _input(
            "Exam session (e.g. 'Summer 2026')",
            allow_empty=False)
    payload["year_group"] = _pick_from(
        "Year group", [""] + list(YEAR_GROUPS),
        default=(existing.year_group if is_edit else ""))
    payload["prior_attainment"] = _input(
        "Prior attainment (avg GCSE points, 0-10)",
        default=(str(existing.prior_attainment)
                  if is_edit and existing.prior_attainment is not None
                  else ""))
    payload["expected_grade"] = _pick_grade(
        "Expected grade",
        default=(existing.expected_grade if is_edit else None),
        allow_empty=True)
    payload["target_grade"] = _pick_grade(
        "Target grade (MTE)",
        default=(existing.target_grade if is_edit else None),
        allow_empty=True)
    payload["predicted_grade"] = _pick_grade(
        "Predicted grade",
        default=(existing.predicted_grade if is_edit else None),
        allow_empty=True)
    payload["actual_grade"] = _pick_grade(
        "Actual grade (if known)",
        default=(existing.actual_grade if is_edit else None),
        allow_empty=True)
    payload["alps_indicator"] = _input(
        "ALPS indicator (1-9)",
        default=(str(existing.alps_indicator)
                  if is_edit and existing.alps_indicator is not None
                  else ""))
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    payload["teacher"] = _input(
        "Teacher",
        default=(existing.teacher or "") if is_edit else "")
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_record() -> None:
    print("\n═══ New VA Record ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.create_record(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created VA #{r.record_id} (va_score={r.va_label})")
    _pause()


def edit_record() -> None:
    print("\n═══ Edit VA Record ═══")
    try:
        r = _pick_record()
        payload = _collect_form(r)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_record(r.record_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{r.record_id}")
    _pause()


def set_actual_flow() -> None:
    print("\n═══ Record Actual Grade ═══")
    try:
        r = _pick_record()
        grade = _pick_grade("Actual grade",
                              default=r.actual_grade,
                              allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        upd = data.set_actual_grade(r.record_id, grade)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{r.record_id} actual={upd.actual_grade}, "
          f"VA={upd.va_label}, status={upd.status}")
    _pause()


def set_predicted_flow() -> None:
    print("\n═══ Update Predicted Grade ═══")
    try:
        r = _pick_record()
        grade = _pick_grade("Predicted grade",
                              default=r.predicted_grade,
                              allow_empty=True)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_predicted_grade(r.record_id, grade)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated predicted to {grade}")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        r = _pick_record()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=r.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(r.record_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{r.record_id} → {new_status}")
    _pause()


def delete_flow() -> None:
    print("\n═══ Delete VA Record ═══")
    try:
        r = _pick_record()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete VA record #{r.record_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_record(r.record_id):
        print(f"\n  ✓ Deleted #{r.record_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Value Added Summary ═══")
    summ = data.summary()
    print(f"\n  Total records       : {summ.total_records}")
    print(f"  Distinct students   : {summ.distinct_students}")
    print(f"  Average VA          : "
          f"{summ.average_va if summ.average_va is not None else '—'}")
    print(f"  Average ALPS        : "
          f"{summ.average_alps if summ.average_alps is not None else '—'}")
    print(f"  Positive VA         : {summ.positive_va}")
    print(f"  Negative VA         : {summ.negative_va}")
    print(f"  Actual ≥ target     : {summ.above_target}")
    print(f"  Actual < target     : {summ.below_target}")
    print("\n  By status:")
    for s in STATUSES:
        n = summ.by_status.get(s, 0)
        if n:
            print(f"    {s:<14} : {n}")
    print("\n  By session:")
    for sess, n in summ.by_session.items():
        print(f"    {sess:<16} : {n}")
    if summ.by_subject:
        print("\n  Top subjects:")
        for sub, n in list(summ.by_subject.items())[:10]:
            print(f"    {sub:<22} : {n}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",           list_all),
    ("Filter",             filter_flow),
    ("Per-student",        per_student_flow),
    ("View",               view_flow),
    ("New record",         new_record),
    ("Edit record",        edit_record),
    ("Record actual grade", set_actual_flow),
    ("Update predicted",   set_predicted_flow),
    ("Change status",      set_status_flow),
    ("Delete record",      delete_flow),
    ("Summary",            summary_flow),
]


def run() -> None:
    while True:
        print("\n── Value Added ──")
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
            logger.exception("Value-added CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Value Added":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Value-added CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
