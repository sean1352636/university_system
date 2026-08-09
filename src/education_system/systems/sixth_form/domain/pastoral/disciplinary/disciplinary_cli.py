"""CLI flows for Sixth Form Disciplinary."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.sixth_form.domain.pastoral.disciplinary import (
    disciplinary as data,
)
from education_system.systems.sixth_form.domain.pastoral.disciplinary.disciplinary import (
    CASE_TYPES,
    DEFAULT_CASE_TYPE,
    DEFAULT_STATUS,
    DisciplinaryCase,
    SEVERITIES,
    STATUSES,
    ValidationError,
    severity_label,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as _students,
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


def _pick_case() -> DisciplinaryCase:
    rows = data.list_cases()
    if not rows:
        print("    No disciplinary cases yet.")
        raise _UserAbort
    print("\n  Cases:")
    for i, c in enumerate(rows, 1):
        flag = "!" if c.sanction_active else " "
        print(f"    {i:>3}){flag}#{c.case_id}  "
              f"{c.incident_date}  {c.student_id:<12}  "
              f"{c.case_type[:20]:<20}  sev={c.severity}  "
              f"[{c.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((c for c in rows if c.case_id == n), None)
            if match:
                return match
        print("    No matching case.")


def _print_table(rows: list[DisciplinaryCase]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Incident':<10}  {'Student':<12}  "
          f"{'Type':<22}  Sev  {'Title':<26}  "
          f"{'Status':<20}  Sanction")
    print("  " + "-" * 130)
    for c in rows:
        sanc = "—"
        if c.sanction_start or c.sanction_end:
            sanc = f"{c.sanction_start or '?'}→{c.sanction_end or '?'}"
            if c.sanction_active:
                sanc = f"ACTIVE {sanc}"
        print(f"  {c.case_id:>4}  "
              f"{c.incident_date:<10}  "
              f"{c.student_id:<12}  "
              f"{c.case_type[:22]:<22}  "
              f"{c.severity:>3}  "
              f"{c.title[:26]:<26}  "
              f"{c.status:<20}  {sanc}")
    print(f"\n  {len(rows)} case(s).")


def _print_full(c: DisciplinaryCase) -> None:
    print()
    print(f"    #{c.case_id}  {c.title}")
    print(f"    Student / incident: {c.student_id}  "
          f"{c.incident_date}")
    print(f"    Reported on       : {c.reported_on}")
    print(f"    Type / severity   : {c.case_type}  "
          f"({c.severity} {c.severity_label})")
    print(f"    Location          : {c.location or '—'}")
    print(f"    Status            : {c.status}")
    print(f"    Issued by         : {c.issued_by or '—'}")
    print(f"    Signed off by     : {c.signed_off_by or '—'}")
    if c.related_behaviour_id:
        print(f"    Linked behaviour  : #{c.related_behaviour_id}")
    if c.witnesses:
        print(f"    Witnesses         : {c.witnesses}")
    if c.sanction_summary:
        print()
        print(f"    Sanction          : {c.sanction_summary}")
        print(f"      Period          : {c.sanction_start or '—'} "
              f"→ {c.sanction_end or '—'}"
              + ("  (ACTIVE)" if c.sanction_active else ""))
        if c.sanction_days is not None:
            print(f"      Days            : {c.sanction_days}")
    print()
    print(f"    Parent informed   : "
          f"{'yes' if c.parent_informed else 'no'}"
          f"  on {c.parent_informed_on or '—'}")
    if c.parent_meeting_on:
        print(f"    Parent meeting    : {c.parent_meeting_on}")
    if c.appeal_submitted_on:
        print()
        print(f"    Appeal submitted  : {c.appeal_submitted_on}")
        if c.appeal_outcome:
            print(f"    Appeal outcome    : {c.appeal_outcome}")
    for label, val in (
            ("Description",         c.description),
            ("Reintegration plan",  c.reintegration_plan),
            ("Notes",               c.notes),
    ):
        if val:
            print(f"\n    {label}:")
            for line in val.splitlines():
                print(f"      {line}")


# ── Flows ────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Disciplinary Cases ═══")
    _print_table(data.list_cases())
    _pause()


def list_open() -> None:
    print("\n═══ Open Cases ═══")
    _print_table(data.list_cases(open_only=True))
    _pause()


def list_active_sanctions() -> None:
    print("\n═══ Active Sanctions ═══")
    _print_table(data.list_cases(active_sanction=True))
    _pause()


def list_appeals() -> None:
    print("\n═══ Appeals Pending ═══")
    _print_table(data.list_cases(appeal_pending=True))
    _pause()


def list_pm() -> None:
    print("\n═══ Pending Parent Meetings ═══")
    _print_table(data.list_cases(parent_meeting_pending=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter ═══")
    try:
        student = _input("Student id") or None
        ctype = _input(
            f"Type ({'/'.join(CASE_TYPES[:3])}…)") or None
        status = _input(f"Status ({'/'.join(STATUSES[:3])}…)") or None
        sev_raw = _input("Min severity (1-5)") or None
        issued = _input("Issued by contains") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt2 = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    sev = (int(sev_raw)
            if sev_raw and sev_raw.isdigit() else None)
    try:
        rows = data.list_cases(
            student_id=student, case_type=ctype,
            status=status, severity_min=sev,
            issued_by_like=issued,
            date_from=df, date_to=dt2)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_table(rows)
    _pause()


def per_student_flow() -> None:
    print("\n═══ Per-Student ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_table(data.cases_for_student(sid))
    _pause()


def view_flow() -> None:
    print("\n═══ View Case ═══")
    try:
        c = _pick_case()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_full(c)
    _pause()


def _collect_form(existing: DisciplinaryCase | None
                       ) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        payload["student_id"] = existing.student_id
    else:
        payload["student_id"] = _pick_student()
    payload["title"] = _input(
        "Title",
        default=(existing.title if is_edit else ""),
        allow_empty=False)
    payload["incident_date"] = _input(
        "Incident date (YYYY-MM-DD)",
        default=(existing.incident_date if is_edit
                  else _date.today().isoformat()),
        allow_empty=False)
    payload["reported_on"] = _input(
        "Reported on (YYYY-MM-DD)",
        default=(existing.reported_on if is_edit
                  else _date.today().isoformat()))
    payload["case_type"] = _pick_from(
        "Type", list(CASE_TYPES),
        default=(existing.case_type if is_edit
                  else DEFAULT_CASE_TYPE))
    payload["severity"] = _input(
        "Severity (1-5)",
        default=(str(existing.severity) if is_edit else "2"))
    payload["location"] = _input(
        "Location",
        default=(existing.location or "") if is_edit else "")
    payload["witnesses"] = _input(
        "Witnesses",
        default=(existing.witnesses or "") if is_edit else "")
    payload["related_behaviour_id"] = _input(
        "Linked behaviour id (optional)",
        default=(str(existing.related_behaviour_id)
                  if is_edit and existing.related_behaviour_id
                  else ""))
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    payload["issued_by"] = _input(
        "Issued by",
        default=(existing.issued_by or "") if is_edit else "")
    payload["signed_off_by"] = _input(
        "Signed off by",
        default=(existing.signed_off_by or "") if is_edit else "")
    try:
        payload["description"] = _multiline(
            "Description",
            default=(existing.description or "") if is_edit else "")
        payload["sanction_summary"] = _multiline(
            "Sanction summary",
            default=(existing.sanction_summary or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["sanction_start"] = _input(
        "Sanction start (YYYY-MM-DD)",
        default=(existing.sanction_start or "") if is_edit else "")
    payload["sanction_end"] = _input(
        "Sanction end (YYYY-MM-DD)",
        default=(existing.sanction_end or "") if is_edit else "")
    payload["sanction_days"] = _input(
        "Sanction days",
        default=(str(existing.sanction_days)
                  if is_edit and existing.sanction_days is not None
                  else ""))
    payload["parent_informed"] = _yes_no(
        "Parent informed?",
        default=(existing.parent_informed if is_edit else False))
    if payload["parent_informed"]:
        payload["parent_informed_on"] = _input(
            "Parent informed on (YYYY-MM-DD)",
            default=(existing.parent_informed_on or "")
            if is_edit else _date.today().isoformat())
    payload["parent_meeting_on"] = _input(
        "Parent meeting on (YYYY-MM-DD)",
        default=(existing.parent_meeting_on or "")
        if is_edit else "")
    payload["appeal_submitted_on"] = _input(
        "Appeal submitted on (YYYY-MM-DD)",
        default=(existing.appeal_submitted_on or "")
        if is_edit else "")
    payload["appeal_outcome"] = _input(
        "Appeal outcome",
        default=(existing.appeal_outcome or "")
        if is_edit else "")
    try:
        payload["reintegration_plan"] = _multiline(
            "Reintegration plan",
            default=(existing.reintegration_plan or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_case() -> None:
    print("\n═══ New Disciplinary Case ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        c = data.create_case(payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created case #{c.case_id}")
    _pause()


def edit_case() -> None:
    print("\n═══ Edit Case ═══")
    try:
        c = _pick_case()
        payload = _collect_form(c)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_case(c.case_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated #{c.case_id}")
    _pause()


def issue_sanction_flow() -> None:
    print("\n═══ Issue Sanction ═══")
    try:
        c = _pick_case()
        summary = _multiline("Sanction summary",
                                default=c.sanction_summary or "")
        if not summary:
            print("  ✗ Sanction summary required.")
            _pause()
            return
        issued_by = _input("Issued by",
                              default=c.issued_by or "",
                              allow_empty=False)
        start = _input("Start (YYYY-MM-DD)",
                          default=c.sanction_start or "")
        end = _input("End (YYYY-MM-DD)",
                        default=c.sanction_end or "")
        days_raw = _input("Days",
                            default=str(c.sanction_days)
                            if c.sanction_days is not None else "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    days = (int(days_raw) if days_raw and days_raw.isdigit()
             else None)
    try:
        data.issue_sanction(c.case_id, summary=summary,
                                 issued_by=issued_by,
                                 start=start or None,
                                 end=end or None, days=days)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Sanction issued on #{c.case_id}")
    _pause()


def mark_served_flow() -> None:
    print("\n═══ Mark Sanction Served ═══")
    try:
        c = _pick_case()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.mark_served(c.case_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{c.case_id} → Sanction Served")
    _pause()


def inform_parent_flow() -> None:
    print("\n═══ Inform Parent ═══")
    try:
        c = _pick_case()
        when = _input("Informed on (YYYY-MM-DD)",
                        default=c.parent_informed_on
                        or _date.today().isoformat())
        meeting = _input("Meeting on (optional)",
                            default=c.parent_meeting_on or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.inform_parent(c.case_id, informed_on=when,
                                meeting_on=meeting or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Parent informed on #{c.case_id}")
    _pause()


def submit_appeal_flow() -> None:
    print("\n═══ Submit Appeal ═══")
    try:
        c = _pick_case()
        when = _input("Submitted on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.submit_appeal(c.case_id, submitted_on=when)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{c.case_id} → Appealed")
    _pause()


def resolve_appeal_flow() -> None:
    print("\n═══ Resolve Appeal ═══")
    try:
        c = _pick_case()
        outcome = _multiline("Outcome",
                                default=c.appeal_outcome or "")
        if not outcome:
            print("  ✗ Outcome required.")
            _pause()
            return
        upheld = _yes_no("Appeal upheld (sanction stands)?")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.resolve_appeal(c.case_id, outcome=outcome,
                                 upheld=upheld)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    status = "Appeal Upheld" if upheld else "Appeal Overturned"
    print(f"\n  ✓ #{c.case_id} → {status}")
    _pause()


def close_case_flow() -> None:
    print("\n═══ Close Case ═══")
    try:
        c = _pick_case()
        plan = _multiline("Reintegration plan",
                            default=c.reintegration_plan or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.close_case(c.case_id,
                            reintegration_plan=plan or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{c.case_id} → Closed")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        c = _pick_case()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=c.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(c.case_id, new_status)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{c.case_id} → {new_status}")
    _pause()


def delete_flow() -> None:
    print("\n═══ Delete Case ═══")
    try:
        c = _pick_case()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete case #{c.case_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_case(c.case_id):
        print(f"\n  ✓ Deleted #{c.case_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Disciplinary Summary ═══")
    s = data.summary()
    print(f"\n  Total                : {s.total}")
    print(f"  Open                 : {s.open_count}")
    print(f"  Active sanctions     : {s.active_sanctions}")
    print(f"  Appeals pending      : {s.appeals_pending}")
    print(f"  Parent mtgs pending  : {s.pending_parent_meetings}")
    print(f"  Distinct students    : {s.distinct_students}")
    print(f"  Average severity     : "
          f"{s.average_severity if s.average_severity is not None else '—'}")
    print("\n  By status:")
    for k in STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    print("\n  By type:")
    for k in CASE_TYPES:
        n = s.by_type.get(k, 0)
        if n:
            print(f"    {k:<24}: {n}")
    print("\n  By severity:")
    for sev in SEVERITIES:
        n = s.by_severity.get(sev, 0)
        if n:
            print(f"    {sev}  {severity_label(sev):<12}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",              list_all),
    ("List open",             list_open),
    ("Active sanctions",      list_active_sanctions),
    ("Appeals pending",       list_appeals),
    ("Parent meetings pend.", list_pm),
    ("Filter",                filter_flow),
    ("Per-student",           per_student_flow),
    ("View",                  view_flow),
    ("─" * 6,                 lambda: None),
    ("New case",              new_case),
    ("Edit case",             edit_case),
    ("Issue sanction",        issue_sanction_flow),
    ("Mark sanction served",  mark_served_flow),
    ("Inform parent",         inform_parent_flow),
    ("Submit appeal",         submit_appeal_flow),
    ("Resolve appeal",        resolve_appeal_flow),
    ("Close case",            close_case_flow),
    ("Change status",         set_status_flow),
    ("Delete",                delete_flow),
    ("─" * 6,                 lambda: None),
    ("Summary",               summary_flow),
]


def run() -> None:
    while True:
        print("\n── Disciplinary ──")
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
            logger.exception("Disciplinary CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Disciplinary":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Disciplinary CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
