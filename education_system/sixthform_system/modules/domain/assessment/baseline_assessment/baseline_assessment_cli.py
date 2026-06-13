"""CLI flows for Sixth Form Baseline Assessment."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.assessment.baseline_assessment import (
    baseline_assessment as data,
)
from education_system.sixthform_system.modules.domain.students.students import (
    students as student_data,
)
from education_system.sixthform_system.modules.domain.assessment.baseline_assessment.baseline_assessment import (
    A_LEVEL_GRADES,
    ASSESSMENT_TYPES,
    BaselineRecord,
    CONFIDENCE,
    DEFAULT_ASSESSMENT_TYPE,
    DEFAULT_CONFIDENCE,
    GCSE_GRADES,
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


def _yes_no(prompt: str, *, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)",
                  default="y" if default else "n").strip().lower()
    return raw in ("y", "yes")


def _pick_from(label: str, options: list[str],
                default: str | None = None,
                allow_custom: bool = False) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    if allow_custom:
        print("        (or type a custom value)")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
        if default and raw == default:
            return default
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(options):
                return options[n - 1]
            print("    Out of range.")
            continue
        if allow_custom and raw:
            return raw
        print("    Enter a number (or 'cancel' to abort).")


def _pick_subject() -> str | None:
    try:
        from education_system.sixthform_system.modules.domain.academics.subjects import (
            subjects as _subjects,
        )
        names = [s.name for s in _subjects.list_subjects()]
    except Exception:
        names = []
    if not names:
        return _input("Subject") or None
    return _pick_from("Subject", [""] + names,
                        allow_custom=True) or None


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


def _pick_record() -> BaselineRecord:
    rows = data.list_records()
    if not rows:
        print("    No baseline records.")
        raise _UserAbort
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print("\n  Baseline records:")
    for i, r in enumerate(rows, 1):
        mark = "*" if r.is_primary else " "
        print(f"    {i:>3}){mark}#{r.record_id}  {r.student_id}  "
              f"{names.get(r.student_id, '?')[:18]:<18}  "
              f"{(r.subject_name or '—')[:18]:<18}  "
              f"{r.assessment_type[:14]:<14}  "
              f"{r.score_label}")
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

def _print_records(rows: list[BaselineRecord]) -> None:
    if not rows:
        print("\n  (no records)")
        return
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print()
    print(f"  {'#':>4}  {'P':<1}  {'Student':<10}  "
          f"{'Name':<20}  {'Subject':<20}  "
          f"{'Type':<16}  {'Score':<16}  Grade")
    print("  " + "-" * 110)
    for r in rows:
        mark = "*" if r.is_primary else " "
        print(f"  {r.record_id:>4}  {mark}  {r.student_id:<10}  "
              f"{names.get(r.student_id, '?')[:20]:<20}  "
              f"{(r.subject_name or '—')[:20]:<20}  "
              f"{r.assessment_type[:16]:<16}  "
              f"{r.score_label[:16]:<16}  "
              f"{r.baseline_grade or '—'}")
    print(f"\n  {len(rows)} record(s).")


# ── Flows ──────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Baseline Records ═══")
    _print_records(data.list_records())
    _pause()


def list_primary() -> None:
    print("\n═══ Primary Baselines ═══")
    _print_records(data.list_records(primary_only=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter Records ═══")
    try:
        sid = _input("Student id") or None
        subject = _input("Subject") or None
        atype = _input(
            f"Type ({'/'.join(ASSESSMENT_TYPES[:3])}…)") or None
        grade = _input("Grade") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt2 = _input("To (YYYY-MM-DD)") or None
        primary = _yes_no("Primary only?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_records(
            student_id=sid, subject_name=subject,
            assessment_type=atype, grade=grade,
            primary_only=primary,
            date_from=df, date_to=dt2,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_records(rows)
    _pause()


def per_student_flow() -> None:
    print("\n═══ Per-Student Baselines ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.records_for_student(sid)
    _print_records(rows)
    summ = data.student_summary(sid)
    print(f"\n  Summary for {sid}:")
    print(f"    Records         : {summ.total}")
    print(f"    Primary baselines: {summ.primary_count}")
    print(f"    Average %       : "
          f"{summ.average_percentage if summ.average_percentage is not None else '—'}")
    print(f"    Avg A-Level pts : "
          f"{summ.avg_a_level_points if summ.avg_a_level_points is not None else '—'}")
    _pause()


def view_record_flow() -> None:
    print("\n═══ View Record ═══")
    try:
        r = _pick_record()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print()
    print(f"    #{r.record_id}{' (PRIMARY)' if r.is_primary else ''}")
    print(f"    Student       : {r.student_id}")
    print(f"    Subject       : {r.subject_name or '—'}")
    print(f"    Type          : {r.assessment_type}")
    print(f"    Date          : {r.assessment_date or '—'}")
    print(f"    Raw / Max     : "
          f"{r.raw_score or '—'} / {r.max_score or '—'}")
    print(f"    Percentage    : "
          f"{r.percentage if r.percentage is not None else '—'}")
    print(f"    Standardised  : "
          f"{r.standardised_score if r.standardised_score is not None else '—'}")
    print(f"    Baseline grade: {r.baseline_grade or '—'}")
    print(f"    Confidence    : {r.confidence}")
    print(f"    Assessor      : {r.assessor or '—'}")
    if r.notes:
        print("\n    Notes:")
        for line in r.notes.splitlines():
            print(f"      {line}")
    _pause()


def _collect_form(existing: BaselineRecord | None
                   ) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        payload["student_id"] = existing.student_id
        print(f"\n  Editing for student {existing.student_id}")
    else:
        payload["student_id"] = _pick_student()
    payload["subject_name"] = _pick_subject() if not is_edit \
        else _input("Subject",
                      default=existing.subject_name or "")
    payload["assessment_type"] = _pick_from(
        "Type", list(ASSESSMENT_TYPES),
        default=(existing.assessment_type if is_edit
                  else DEFAULT_ASSESSMENT_TYPE))
    payload["assessment_date"] = _input(
        "Date (YYYY-MM-DD)",
        default=(existing.assessment_date or "") if is_edit
                  else _date.today().isoformat())
    payload["raw_score"] = _input(
        "Raw score",
        default=(str(existing.raw_score)
                  if is_edit and existing.raw_score is not None
                  else ""))
    payload["max_score"] = _input(
        "Max score",
        default=(str(existing.max_score)
                  if is_edit and existing.max_score is not None
                  else ""))
    payload["percentage"] = _input(
        "Percentage (auto-derived if blank)",
        default=(str(existing.percentage)
                  if is_edit and existing.percentage is not None
                  else ""))
    payload["standardised_score"] = _input(
        "Standardised score (e.g. CAT4)",
        default=(str(existing.standardised_score)
                  if is_edit and existing.standardised_score is not None
                  else ""))
    payload["baseline_grade"] = _pick_from(
        "Baseline grade",
        [""] + list(A_LEVEL_GRADES) + list(GCSE_GRADES),
        default=(existing.baseline_grade if is_edit else ""),
        allow_custom=True)
    payload["confidence"] = _pick_from(
        "Confidence", list(CONFIDENCE),
        default=(existing.confidence if is_edit
                  else DEFAULT_CONFIDENCE))
    payload["is_primary"] = _yes_no(
        "Primary baseline for this subject?",
        default=(existing.is_primary if is_edit else False))
    payload["assessor"] = _input(
        "Assessor",
        default=(existing.assessor or "") if is_edit else "")
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_record() -> None:
    print("\n═══ New Baseline Record ═══")
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
    print(f"\n  ✓ Created #{r.record_id} "
          f"(score={r.score_label}, grade={r.baseline_grade or '—'})")
    _pause()


def edit_record() -> None:
    print("\n═══ Edit Baseline Record ═══")
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


def set_primary_flow() -> None:
    print("\n═══ Mark as Primary ═══")
    try:
        r = _pick_record()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_primary(r.record_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{r.record_id} is now primary")
    _pause()


def delete_record_flow() -> None:
    print("\n═══ Delete Baseline Record ═══")
    try:
        r = _pick_record()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete record #{r.record_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_record(r.record_id):
        print(f"\n  ✓ Deleted #{r.record_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Baseline Summary ═══")
    summ = data.summary()
    print(f"\n  Total records      : {summ.total_records}")
    print(f"  Primary baselines  : {summ.primary_count}")
    print(f"  Distinct students  : {summ.distinct_students}")
    print(f"  Average percentage : "
          f"{summ.average_percentage if summ.average_percentage is not None else '—'}")
    print("\n  By type:")
    for t in ASSESSMENT_TYPES:
        n = summ.by_type.get(t, 0)
        if n:
            print(f"    {t:<22} : {n}")
    if summ.by_subject:
        print("\n  Top subjects:")
        for sub, n in list(summ.by_subject.items())[:10]:
            print(f"    {sub:<22} : {n}")
    if summ.by_grade:
        print("\n  By grade:")
        for g, n in summ.by_grade.items():
            print(f"    {g:<8} : {n}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",         list_all),
    ("List primary",     list_primary),
    ("Filter",           filter_flow),
    ("Per-student",      per_student_flow),
    ("View record",      view_record_flow),
    ("New record",       new_record),
    ("Edit record",      edit_record),
    ("Mark primary",     set_primary_flow),
    ("Delete record",    delete_record_flow),
    ("Summary",          summary_flow),
]


def run() -> None:
    while True:
        print("\n── Baseline Assessment ──")
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
            logger.exception("Baseline-assessment CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Baseline Assessment":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Baseline-assessment CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
