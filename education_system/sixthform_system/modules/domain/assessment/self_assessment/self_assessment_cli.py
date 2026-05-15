"""CLI flows for Sixth Form Self-Assessments."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.assessment.self_assessment import (
    self_assessment as data,
)
from education_system.sixthform_system.modules.domain.assessment.self_assessment.self_assessment import (
    ASSESSMENT_TYPES,
    DEFAULT_ASSESSMENT_TYPE,
    DEFAULT_STATUS,
    DIMENSIONS,
    SelfAssessment,
    STATUSES,
    ValidationError,
    dimension_label,
    likert_label,
)
from education_system.sixthform_system.modules.domain.students.students import students as _students

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


def _pick_student() -> str:
    rows = _students.list_students()
    if not rows:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(rows, 1):
        full = f"{getattr(s, 'first_name', '')} " \
               f"{getattr(s, 'last_name', '')}".strip()
        print(f"    {i:>3}) {s.student_id:<12}  {full}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].student_id
        match = next((s for s in rows if s.student_id == raw), None)
        if match:
            return match.student_id
        print("    No matching student.")


def _pick_assessment() -> SelfAssessment:
    rows = data.list_assessments()
    if not rows:
        print("    No self-assessments yet.")
        raise _UserAbort
    print("\n  Self-assessments:")
    for i, a in enumerate(rows, 1):
        avg = (f"{a.average_score:.2f}"
                if a.average_score is not None else "—")
        print(f"    {i:>3}) #{a.assessment_id}  "
              f"{a.assessment_date}  {a.student_id:<10}  "
              f"{a.assessment_type[:18]:<18}  "
              f"avg={avg}  [{a.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((a for a in rows
                            if a.assessment_id == n), None)
            if match:
                return match
        print("    No matching assessment.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_assessments(rows: list[SelfAssessment]) -> None:
    if not rows:
        print("\n  (no assessments)")
        return
    print()
    print(f"  {'#':>4}  {'Date':<10}  {'Student':<12}  "
          f"{'Type':<22}  Avg   {'Status':<14}  Reviewer")
    print("  " + "-" * 90)
    for a in rows:
        avg = (f"{a.average_score:.2f}"
                if a.average_score is not None else "  — ")
        print(f"  {a.assessment_id:>4}  "
              f"{a.assessment_date:<10}  "
              f"{a.student_id:<12}  "
              f"{a.assessment_type[:22]:<22}  "
              f"{avg}  {a.status:<14}  "
              f"{a.reviewer or '—'}")
    print(f"\n  {len(rows)} assessment(s).")


def _print_full(a: SelfAssessment) -> None:
    print()
    print(f"    #{a.assessment_id}")
    print(f"    Student          : {a.student_id}")
    print(f"    Date / term      : {a.assessment_date}  "
          f"{a.term or '—'}")
    print(f"    Year group       : {a.year_group or '—'}")
    print(f"    Type             : {a.assessment_type}")
    print(f"    Status           : {a.status}")
    print(f"    Average score    : "
          f"{a.average_score:.2f}" if a.average_score is not None
          else "    Average score    : —")
    print()
    print("    Ratings (1=Very Low .. 5=Excellent):")
    for d in DIMENSIONS:
        v = getattr(a, d)
        print(f"      {dimension_label(d):<22} : "
              f"{v if v is not None else '—'}"
              + (f"  ({likert_label(v)})" if v else ""))
    for label, val in (
            ("Strengths",          a.strengths),
            ("Areas to improve",   a.areas_to_improve),
            ("Action plan",        a.action_plan),
            ("Support needed",     a.support_needed),
            ("Proudest moment",    a.proudest_moment),
            ("Biggest challenge",  a.biggest_challenge),
    ):
        if val:
            print()
            print(f"    {label}:")
            for line in val.splitlines():
                print(f"      {line}")
    if a.reviewer or a.reviewer_feedback:
        print()
        print(f"    Reviewer         : {a.reviewer or '—'}")
        print(f"    Reviewed on      : {a.reviewed_on or '—'}")
        if a.reviewer_feedback:
            print("    Feedback:")
            for line in a.reviewer_feedback.splitlines():
                print(f"      {line}")
        if a.agreed_actions:
            print("    Agreed actions:")
            for line in a.agreed_actions.splitlines():
                print(f"      {line}")
    if a.notes:
        print()
        print("    Notes:")
        for line in a.notes.splitlines():
            print(f"      {line}")


# ── Flows ──────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Self-Assessments ═══")
    _print_assessments(data.list_assessments())
    _pause()


def list_open() -> None:
    print("\n═══ Open Self-Assessments ═══")
    _print_assessments(data.list_assessments(open_only=True))
    _pause()


def list_awaiting_review() -> None:
    print("\n═══ Awaiting Review ═══")
    _print_assessments(data.list_assessments(awaiting_review=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter ═══")
    try:
        student_id = _input("Student ID") or None
        type_in = _input("Type contains") or None
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        reviewer = _input("Reviewer contains") or None
        term = _input("Term") or None
        year = _input("Year group") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt2 = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_assessments(
            student_id=student_id, assessment_type=type_in,
            status=status, reviewer_like=reviewer,
            term=term, year_group=year,
            date_from=df, date_to=dt2,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_assessments(rows)
    _pause()


def per_student_flow() -> None:
    print("\n═══ Per-Student Self-Assessments ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.assessments_for_student(sid)
    _print_assessments(rows)
    summ = data.student_summary(sid)
    print(f"\n  Summary for {sid}:")
    print(f"    Total              : {summ.total}")
    print(f"    Most-recent score  : "
          f"{summ.most_recent_score if summ.most_recent_score is not None else '—'}")
    print(f"    Awaiting review    : {summ.awaiting_review}")
    print(f"    Reviewed           : {summ.reviewed}")
    _pause()


def view_flow() -> None:
    print("\n═══ View Self-Assessment ═══")
    try:
        a = _pick_assessment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_full(a)
    _pause()


def _collect_form(existing: SelfAssessment | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        payload["student_id"] = existing.student_id
    else:
        payload["student_id"] = _pick_student()
    payload["assessment_date"] = _input(
        "Date (YYYY-MM-DD)",
        default=(existing.assessment_date if is_edit
                  else _date.today().isoformat()),
        allow_empty=False)
    payload["assessment_type"] = _pick_from(
        "Type", list(ASSESSMENT_TYPES),
        default=(existing.assessment_type if is_edit
                  else DEFAULT_ASSESSMENT_TYPE))
    payload["term"] = _input(
        "Term (e.g. Autumn 1)",
        default=(existing.term or "") if is_edit else "")
    payload["year_group"] = _input(
        "Year group",
        default=(existing.year_group or "") if is_edit else "")

    print("\n  Ratings (1=Very Low .. 5=Excellent; blank = skip):")
    for d in DIMENSIONS:
        current = getattr(existing, d) if is_edit else None
        raw = _input(
            f"{dimension_label(d)}",
            default=(str(current) if current is not None else ""))
        if raw:
            try:
                payload[d] = int(raw)
            except ValueError:
                print(f"    ✗ {dimension_label(d)} must be 1-5.")
                payload[d] = None
        else:
            payload[d] = None

    try:
        payload["strengths"] = _multiline(
            "Strengths",
            default=(existing.strengths or "") if is_edit else "")
        payload["areas_to_improve"] = _multiline(
            "Areas to improve",
            default=(existing.areas_to_improve or "")
            if is_edit else "")
        payload["action_plan"] = _multiline(
            "Action plan",
            default=(existing.action_plan or "") if is_edit else "")
        payload["support_needed"] = _multiline(
            "Support needed",
            default=(existing.support_needed or "")
            if is_edit else "")
        payload["proudest_moment"] = _multiline(
            "Proudest moment",
            default=(existing.proudest_moment or "")
            if is_edit else "")
        payload["biggest_challenge"] = _multiline(
            "Biggest challenge",
            default=(existing.biggest_challenge or "")
            if is_edit else "")
    except _UserAbort:
        raise

    payload["reviewer"] = _input(
        "Reviewer (optional)",
        default=(existing.reviewer or "") if is_edit else "")
    if payload["reviewer"]:
        try:
            payload["reviewer_feedback"] = _multiline(
                "Reviewer feedback",
                default=(existing.reviewer_feedback or "")
                if is_edit else "")
            payload["agreed_actions"] = _multiline(
                "Agreed actions",
                default=(existing.agreed_actions or "")
                if is_edit else "")
        except _UserAbort:
            raise
        payload["reviewed_on"] = _input(
            "Reviewed on (YYYY-MM-DD)",
            default=(existing.reviewed_on or "") if is_edit else "")
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_assessment() -> None:
    print("\n═══ New Self-Assessment ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.create_assessment(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created assessment #{a.assessment_id}")
    _pause()


def edit_assessment() -> None:
    print("\n═══ Edit Self-Assessment ═══")
    try:
        a = _pick_assessment()
        payload = _collect_form(a)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_assessment(a.assessment_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{a.assessment_id}")
    _pause()


def submit_flow() -> None:
    print("\n═══ Submit Self-Assessment ═══")
    try:
        a = _pick_assessment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.submit(a.assessment_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.assessment_id} → Submitted")
    _pause()


def review_flow() -> None:
    print("\n═══ Record Review ═══")
    try:
        a = _pick_assessment()
        reviewer = _input("Reviewer", default=a.reviewer or "",
                            allow_empty=False)
        feedback = _multiline("Reviewer feedback",
                                default=a.reviewer_feedback or "")
        actions = _multiline("Agreed actions",
                                default=a.agreed_actions or "")
        when = _input("Reviewed on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.record_review(
            a.assessment_id,
            reviewer=reviewer,
            feedback=feedback,
            agreed_actions=actions,
            reviewed_on=when,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.assessment_id} → Reviewed")
    _pause()


def acknowledge_flow() -> None:
    print("\n═══ Acknowledge ═══")
    try:
        a = _pick_assessment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.acknowledge(a.assessment_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.assessment_id} → Acknowledged")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        a = _pick_assessment()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=a.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(a.assessment_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.assessment_id} → {new_status}")
    _pause()


def delete_flow() -> None:
    print("\n═══ Delete ═══")
    try:
        a = _pick_assessment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete assessment #{a.assessment_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_assessment(a.assessment_id):
        print(f"\n  ✓ Deleted #{a.assessment_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Self-Assessments Summary ═══")
    summ = data.summary()
    print(f"\n  Total              : {summ.total}")
    print(f"  Awaiting review    : {summ.awaiting_review}")
    print(f"  Reviewed           : {summ.reviewed}")
    print(f"  Distinct students  : {summ.distinct_students}")
    print("\n  By status:")
    for s in STATUSES:
        n = summ.by_status.get(s, 0)
        if n:
            print(f"    {s:<14} : {n}")
    print("\n  By type:")
    for t in ASSESSMENT_TYPES:
        n = summ.by_type.get(t, 0)
        if n:
            print(f"    {t:<22} : {n}")
    print("\n  Average per dimension:")
    for d in DIMENSIONS:
        v = summ.average_per_dimension.get(d)
        if v is not None:
            print(f"    {dimension_label(d):<22} : {v:.2f}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",                list_all),
    ("List open",               list_open),
    ("Awaiting review",         list_awaiting_review),
    ("Filter",                  filter_flow),
    ("Per-student",             per_student_flow),
    ("View",                    view_flow),
    ("─" * 6,                   lambda: None),
    ("New self-assessment",     new_assessment),
    ("Edit self-assessment",    edit_assessment),
    ("Submit",                  submit_flow),
    ("Record review",           review_flow),
    ("Acknowledge",             acknowledge_flow),
    ("Change status",           set_status_flow),
    ("Delete",                  delete_flow),
    ("─" * 6,                   lambda: None),
    ("Summary",                 summary_flow),
]


def run() -> None:
    while True:
        print("\n── Self-Assessments ──")
        for i, (label, _) in enumerate(_MENU, 1):
            if label.startswith("─"):
                print(f"      {label * 3}")
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
            logger.exception("SelfAssessment CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Self Assessment":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("SelfAssessment CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
