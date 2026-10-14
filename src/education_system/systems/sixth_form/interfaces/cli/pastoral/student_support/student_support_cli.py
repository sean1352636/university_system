"""CLI flows for Sixth Form Student Support."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.sixth_form.domain.pastoral.student_support import (
    student_support as data,
)
from education_system.systems.sixth_form.domain.pastoral.student_support.student_support import (
    DEFAULT_SOURCE,
    DEFAULT_STATUS,
    DEFAULT_SUPPORT_TYPE,
    PRIORITIES,
    Referral,
    SOURCES,
    STATUSES,
    SUPPORT_TYPES,
    ValidationError,
    priority_label,
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


def _pick_referral() -> Referral:
    rows = data.list_referrals()
    if not rows:
        print("    No referrals yet.")
        raise _UserAbort
    print("\n  Referrals:")
    for i, r in enumerate(rows, 1):
        flag = "!" if r.overdue else " "
        print(f"    {i:>3}){flag}#{r.referral_id}  "
              f"{r.referred_on}  {r.student_id:<12}  "
              f"{r.support_type[:22]:<22}  "
              f"P{r.priority}  [{r.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                            if r.referral_id == n), None)
            if match:
                return match
        print("    No matching referral.")


def _print_table(rows: list[Referral]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Referred':<10}  {'Student':<12}  "
          f"{'Type':<22}  P  {'Assigned':<14}  "
          f"{'Status':<12}  Target")
    print("  " + "-" * 110)
    for r in rows:
        target = r.target_close_date or "—"
        if r.overdue:
            target = f"OVERDUE ({target})"
        print(f"  {r.referral_id:>4}  {r.referred_on:<10}  "
              f"{r.student_id:<12}  "
              f"{r.support_type[:22]:<22}  "
              f"{r.priority}  "
              f"{(r.assigned_to or '—')[:14]:<14}  "
              f"{r.status:<12}  {target}")
    print(f"\n  {len(rows)} referral(s).")


def _print_full(r: Referral) -> None:
    print()
    print(f"    #{r.referral_id}  Student {r.student_id}")
    print(f"    Referred on       : {r.referred_on}")
    print(f"    Support type      : {r.support_type}")
    print(f"    Source            : {r.source}")
    print(f"    Referrer          : {r.referrer}")
    print(f"    Priority          : {r.priority}  "
          f"({r.priority_label})")
    print(f"    Subject context   : {r.subject_context or '—'}")
    print(f"    Assigned to       : {r.assigned_to or '—'}")
    print(f"    Target close      : {r.target_close_date or '—'}"
          + ("  (OVERDUE)" if r.overdue else ""))
    print(f"    Sessions          : "
          f"{r.sessions_completed} of "
          f"{r.sessions_planned if r.sessions_planned is not None else '—'}")
    print(f"    Status            : {r.status}")
    print(f"    Closed on         : {r.closed_on or '—'}")
    for label, val in (
            ("Presenting issue", r.presenting_issue),
            ("Agreed actions",   r.agreed_actions),
            ("Outcome",          r.outcome),
            ("Review notes",     r.review_notes),
    ):
        if val:
            print(f"\n    {label}:")
            for line in val.splitlines():
                print(f"      {line}")


# ── Flows ────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Referrals ═══")
    _print_table(data.list_referrals())
    _pause()


def list_open() -> None:
    print("\n═══ Open Referrals ═══")
    _print_table(data.list_referrals(open_only=True))
    _pause()


def list_urgent() -> None:
    print("\n═══ Urgent Open (priority 4-5) ═══")
    _print_table(data.list_referrals(urgent_only=True))
    _pause()


def list_overdue() -> None:
    print("\n═══ Overdue Open ═══")
    _print_table(data.list_referrals(overdue_only=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter ═══")
    try:
        student = _input("Student id") or None
        stype = _input(
            f"Type ({'/'.join(SUPPORT_TYPES[:3])}…)") or None
        source = _input(f"Source ({'/'.join(SOURCES[:3])}…)") or None
        status = _input(f"Status ({'/'.join(STATUSES[:3])}…)") or None
        pri_raw = _input("Min priority (1-5)") or None
        assigned = _input("Assigned-to contains") or None
        referrer = _input("Referrer contains") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt2 = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    pri = (int(pri_raw) if pri_raw and pri_raw.isdigit() else None)
    try:
        rows = data.list_referrals(
            student_id=student, support_type=stype, source=source,
            status=status, priority_min=pri,
            assigned_to_like=assigned, referrer_like=referrer,
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
    _print_table(data.referrals_for_student(sid))
    _pause()


def view_flow() -> None:
    print("\n═══ View Referral ═══")
    try:
        r = _pick_referral()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_full(r)
    _pause()


def _collect_form(existing: Referral | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        payload["student_id"] = existing.student_id
    else:
        payload["student_id"] = _pick_student()
    payload["referred_on"] = _input(
        "Referred on (YYYY-MM-DD)",
        default=(existing.referred_on if is_edit
                  else _date.today().isoformat()),
        allow_empty=False)
    payload["support_type"] = _pick_from(
        "Support type", list(SUPPORT_TYPES),
        default=(existing.support_type if is_edit
                  else DEFAULT_SUPPORT_TYPE))
    payload["source"] = _pick_from(
        "Source", list(SOURCES),
        default=(existing.source if is_edit else DEFAULT_SOURCE))
    payload["referrer"] = _input(
        "Referrer",
        default=(existing.referrer if is_edit else ""),
        allow_empty=False)
    payload["priority"] = _input(
        "Priority (1-5; 5=Urgent)",
        default=(str(existing.priority) if is_edit else "3"))
    payload["subject_context"] = _input(
        "Subject context",
        default=(existing.subject_context or "")
        if is_edit else "")
    payload["assigned_to"] = _input(
        "Assigned to",
        default=(existing.assigned_to or "") if is_edit else "")
    payload["target_close_date"] = _input(
        "Target close (YYYY-MM-DD)",
        default=(existing.target_close_date or "")
        if is_edit else "")
    payload["sessions_planned"] = _input(
        "Sessions planned",
        default=(str(existing.sessions_planned)
                  if is_edit and existing.sessions_planned is not None
                  else ""))
    payload["sessions_completed"] = _input(
        "Sessions completed so far",
        default=(str(existing.sessions_completed)
                  if is_edit else "0"))
    try:
        payload["presenting_issue"] = _multiline(
            "Presenting issue",
            default=(existing.presenting_issue or "")
            if is_edit else "")
        payload["agreed_actions"] = _multiline(
            "Agreed actions",
            default=(existing.agreed_actions or "")
            if is_edit else "")
        payload["outcome"] = _multiline(
            "Outcome",
            default=(existing.outcome or "") if is_edit else "")
        payload["review_notes"] = _multiline(
            "Review notes",
            default=(existing.review_notes or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    payload["closed_on"] = _input(
        "Closed on (YYYY-MM-DD)",
        default=(existing.closed_on or "") if is_edit else "")
    return payload


def new_referral() -> None:
    print("\n═══ New Referral ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.create_referral(payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created referral #{r.referral_id}")
    _pause()


def edit_referral() -> None:
    print("\n═══ Edit Referral ═══")
    try:
        r = _pick_referral()
        payload = _collect_form(r)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_referral(r.referral_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated #{r.referral_id}")
    _pause()


def triage_flow() -> None:
    print("\n═══ Triage ═══")
    try:
        r = _pick_referral()
        assigned = _input("Assigned to",
                            default=r.assigned_to or "",
                            allow_empty=False)
        pri_raw = _input("Priority (1-5, blank to keep)",
                            default=str(r.priority))
        target = _input("Target close (YYYY-MM-DD)",
                          default=r.target_close_date or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    pri = int(pri_raw) if pri_raw and pri_raw.isdigit() else None
    try:
        data.triage(r.referral_id, assigned_to=assigned,
                       priority=pri, target_close_date=target or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Triaged #{r.referral_id}")
    _pause()


def log_session_flow() -> None:
    print("\n═══ Log Session ═══")
    try:
        r = _pick_referral()
        note = _multiline("Session note (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.log_session(r.referral_id, note=note or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Session logged on #{r.referral_id}")
    _pause()


def resolve_flow() -> None:
    print("\n═══ Resolve ═══")
    try:
        r = _pick_referral()
        outcome = _multiline("Outcome",
                                default=r.outcome or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not outcome:
        print("  ✗ Outcome required.")
        _pause()
        return
    try:
        data.resolve(r.referral_id, outcome=outcome)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{r.referral_id} → Resolved")
    _pause()


def close_flow() -> None:
    print("\n═══ Close ═══")
    try:
        r = _pick_referral()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.close_referral(r.referral_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{r.referral_id} → Closed")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        r = _pick_referral()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=r.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(r.referral_id, new_status)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{r.referral_id} → {new_status}")
    _pause()


def delete_flow() -> None:
    print("\n═══ Delete ═══")
    try:
        r = _pick_referral()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete referral #{r.referral_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_referral(r.referral_id):
        print(f"\n  ✓ Deleted #{r.referral_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Student Support Summary ═══")
    s = data.summary()
    print(f"\n  Total              : {s.total}")
    print(f"  Open               : {s.open_count}")
    print(f"  Urgent open        : {s.urgent_open}")
    print(f"  Overdue            : {s.overdue}")
    print(f"  Distinct students  : {s.distinct_students}")
    print(f"  Sessions logged    : {s.total_sessions}")
    print("\n  By type:")
    for k in SUPPORT_TYPES:
        n = s.by_type.get(k, 0)
        if n:
            print(f"    {k:<26}: {n}")
    print("\n  By source:")
    for k in SOURCES:
        n = s.by_source.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    print("\n  By priority:")
    for p in PRIORITIES:
        n = s.by_priority.get(p, 0)
        if n:
            print(f"    {p}  {priority_label(p):<10}: {n}")
    print("\n  By status:")
    for k in STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",          list_all),
    ("List open",         list_open),
    ("Urgent open",       list_urgent),
    ("Overdue",           list_overdue),
    ("Filter",            filter_flow),
    ("Per-student",       per_student_flow),
    ("View",              view_flow),
    ("─" * 6,             lambda: None),
    ("New referral",      new_referral),
    ("Edit referral",     edit_referral),
    ("Triage",            triage_flow),
    ("Log session",       log_session_flow),
    ("Resolve",           resolve_flow),
    ("Close",             close_flow),
    ("Change status",     set_status_flow),
    ("Delete",            delete_flow),
    ("─" * 6,             lambda: None),
    ("Summary",           summary_flow),
]


def run() -> None:
    while True:
        print("\n── Student Support ──")
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
            logger.exception("Student Support CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Student Support":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Student Support CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
