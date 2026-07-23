"""CLI flows for Sixth Form Careers Guidance."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.post_16.sixthform_system.modules.domain.progression.careers import careers
from education_system.post_16.sixthform_system.modules.domain.progression.careers import careers as data
from education_system.post_16.sixthform_system.modules.domain.students.students import students as student_data
from education_system.post_16.sixthform_system.modules.domain.progression.careers.careers import (
    CareerAspiration,
    CareerSession,
    DEFAULT_PATHWAY,
    DEFAULT_SESSION_STATUS,
    DEFAULT_SESSION_TYPE,
    GATSBY_BENCHMARKS,
    PATHWAYS,
    SESSION_STATUSES,
    SESSION_TYPES,
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


def _pick_benchmark(default: int | None = None) -> int | None:
    options = ["(none)"] + [f"{k} — {v}"
                              for k, v in GATSBY_BENCHMARKS.items()]
    default_label = ("(none)" if default is None
                     else f"{default} — {GATSBY_BENCHMARKS[default]}")
    chosen = _pick_from("Gatsby benchmark", options, default=default_label)
    if chosen == "(none)":
        return None
    try:
        return int(chosen.split("—")[0].strip())
    except (ValueError, IndexError):
        return None


# ── Sessions: print + listing ─────────────────────────────────────

def _print_sessions(rows: list[CareerSession]) -> None:
    if not rows:
        print("\n  (no sessions)")
        return
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Date':<10}  "
          f"{'Type':<18}  {'Advisor':<14}  {'BM':>2}  "
          f"{'Status':<10}  Follow-up")
    print("  " + "-" * 92)
    for s in rows:
        print(f"  {s.session_id:>4}  {s.student_id:<10}  "
              f"{s.session_date:<10}  "
              f"{s.session_type[:18]:<18}  "
              f"{(s.advisor or '—')[:14]:<14}  "
              f"{(str(s.gatsby_benchmark) if s.gatsby_benchmark else '—'):>2}  "
              f"{s.status:<10}  {(s.follow_up_date or '—')}")
    print(f"\n  {len(rows)} session(s).")


def list_sessions() -> None:
    print("\n═══ Careers Sessions ═══")
    rows = data.list_sessions()
    _print_sessions(rows)
    _row_action_loop_sessions(rows)


def filter_sessions() -> None:
    print("\n═══ Filter Sessions ═══")
    print("  (leave any field blank to skip; 'cancel' to abort)\n")
    try:
        sid = _input("Student ID") or None
        advisor = _input("Advisor substring") or None
        stype = _input(f"Type ({'/'.join(SESSION_TYPES)})") or None
        bm_raw = _input("Gatsby benchmark (1-8)")
        status = _input(f"Status ({'/'.join(SESSION_STATUSES)})") or None
        date_from = _input("From (YYYY-MM-DD)") or None
        date_to = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    bench = None
    if bm_raw:
        try:
            bench = int(bm_raw)
        except ValueError:
            print("  ✗ Benchmark must be a number.")
            _pause()
            return
    try:
        rows = data.list_sessions(
            student_id=sid, advisor_like=advisor,
            session_type=stype, benchmark=bench, status=status,
            date_from=date_from, date_to=date_to,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_sessions(rows)
    _row_action_loop_sessions(rows)


def view_session(session_id: int | None = None) -> None:
    print("\n═══ View Session ═══")
    try:
        sid = session_id if session_id is not None else int(
            _input("Session ID", allow_empty=False))
    except ValueError:
        print("  ✗ Session ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    s = data.get_session(sid)
    if s is None:
        print(f"  ✗ No session #{sid}")
        _pause()
        return
    print()
    print(f"    Session ID    : #{s.session_id}")
    print(f"    Student       : {s.student_id}")
    print(f"    Date          : {s.session_date}")
    print(f"    Advisor       : {s.advisor or '—'}")
    print(f"    Type          : {s.session_type}")
    print(f"    Duration      : "
          f"{s.duration_minutes} mins" if s.duration_minutes else "—")
    if s.gatsby_benchmark:
        print(f"    Gatsby bench. : {s.gatsby_benchmark} — "
              f"{GATSBY_BENCHMARKS[s.gatsby_benchmark]}")
    else:
        print("    Gatsby bench. : —")
    print(f"    Status        : {s.status}")
    print(f"    Follow-up     : {s.follow_up_date or '—'}")
    if s.topics:
        print("\n    Topics:")
        for line in s.topics.splitlines():
            print(f"      {line}")
    if s.action_plan:
        print("\n    Action plan:")
        for line in s.action_plan.splitlines():
            print(f"      {line}")
    if s.notes:
        print(f"\n    Notes: {s.notes}")
    _pause()


def _collect_session(existing: CareerSession | None) -> dict[str, Any]:
    is_edit = existing is not None
    payload: dict[str, Any] = {}

    if is_edit:
        print(f"\n  Editing session #{existing.session_id} for "
              f"{existing.student_id}")
        payload["student_id"] = existing.student_id
    else:
        print("\n  ── Student ──")
        payload["student_id"] = _pick_student()

    print("\n  ── Session details ──")
    today = _date.today().isoformat()
    payload["session_date"] = _input(
        "Date (YYYY-MM-DD)",
        default=(existing.session_date if is_edit else today),
        allow_empty=False,
    )
    payload["advisor"] = _input(
        "Advisor",
        default=(existing.advisor or "") if is_edit else "",
    )
    payload["session_type"] = _pick_from(
        "Session type", list(SESSION_TYPES),
        default=(existing.session_type if is_edit else DEFAULT_SESSION_TYPE),
    )
    payload["duration_minutes"] = _input(
        "Duration (minutes, optional)",
        default=(str(existing.duration_minutes)
                 if is_edit and existing.duration_minutes else "30"),
    )
    payload["gatsby_benchmark"] = _pick_benchmark(
        default=existing.gatsby_benchmark if is_edit else None)
    payload["status"] = _pick_from(
        "Status", list(SESSION_STATUSES),
        default=(existing.status if is_edit else DEFAULT_SESSION_STATUS),
    )
    payload["follow_up_date"] = _input(
        "Follow-up date (YYYY-MM-DD, optional)",
        default=(existing.follow_up_date or "") if is_edit else "",
    )
    payload["topics"] = _input(
        "Topics (optional, single line)",
        default=(existing.topics or "") if is_edit else "",
    )
    payload["action_plan"] = _input(
        "Action plan (optional, single line)",
        default=(existing.action_plan or "") if is_edit else "",
    )
    payload["notes"] = _input(
        "Notes (optional)",
        default=(existing.notes or "") if is_edit else "",
    )
    return payload


def new_session() -> None:
    print("\n═══ New Careers Session ═══")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        payload = _collect_session(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        s = data.create_session(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("create_session crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Created session #{s.session_id} "
          f"({s.student_id}, {s.session_date}, {s.session_type})")
    _pause()


def edit_session(session_id: int | None = None) -> None:
    print("\n═══ Edit Careers Session ═══")
    try:
        sid = session_id if session_id is not None else int(
            _input("Session ID", allow_empty=False))
    except ValueError:
        print("  ✗ Session ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_session(sid)
    if existing is None:
        print(f"  ✗ No session #{sid}")
        _pause()
        return
    try:
        payload = _collect_session(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_session(sid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("update_session crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Updated session #{sid}")
    _pause()


def delete_session_flow(session_id: int | None = None) -> None:
    print("\n═══ Delete Session ═══")
    try:
        sid = session_id if session_id is not None else int(
            _input("Session ID", allow_empty=False))
    except ValueError:
        print("  ✗ Session ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_session(sid)
    if existing is None:
        print(f"  ✗ No session #{sid}")
        _pause()
        return
    confirm = _input(
        f"Delete session #{sid} ({existing.student_id}, "
        f"{existing.session_date})? Type 'yes'",
        default="no")
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_session(sid):
            print(f"\n  ✓ Deleted #{sid}")
    except Exception as e:
        logger.exception("delete_session crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Aspirations ──────────────────────────────────────────────────

def list_aspirations() -> None:
    print("\n═══ Aspirations ═══")
    try:
        rows = data.list_aspirations()
    except Exception as e:
        logger.exception("list_aspirations failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    if not rows:
        print("\n  (no aspirations)")
        _pause()
        return
    print()
    print(f"  {'Student':<10}  {'Pathway':<14}  {'Target career':<24}  "
          f"{'Sector':<22}  Employer / Course")
    print("  " + "-" * 92)
    for a in rows:
        emp_or_course = a.target_employer or a.target_course or "—"
        print(f"  {a.student_id:<10}  {a.primary_pathway:<14}  "
              f"{(a.target_career or '—')[:24]:<24}  "
              f"{(a.target_sector or '—')[:22]:<22}  "
              f"{emp_or_course}")
    print(f"\n  {len(rows)} aspiration(s).")
    _pause()


def save_aspiration_flow() -> None:
    print("\n═══ Save Aspiration ═══")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_aspiration_for_student(sid)
    try:
        pathway = _pick_from(
            "Primary pathway", list(PATHWAYS),
            default=(existing.primary_pathway if existing else DEFAULT_PATHWAY),
        )
        career = _input("Target career (optional)",
                         default=(existing.target_career or "")
                                 if existing else "")
        sector = _input("Target sector (optional)",
                         default=(existing.target_sector or "")
                                 if existing else "")
        employer = _input("Target employer (optional)",
                           default=(existing.target_employer or "")
                                   if existing else "")
        course = _input("Target course (optional)",
                         default=(existing.target_course or "")
                                 if existing else "")
        notes = _input("Notes (optional)",
                        default=(existing.notes or "")
                                if existing else "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.save_aspiration({
            "student_id":      sid,
            "primary_pathway": pathway,
            "target_career":   career,
            "target_sector":   sector,
            "target_employer": employer,
            "target_course":   course,
            "notes":           notes,
        })
        print(f"\n  ✓ Saved aspiration for {sid}")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except Exception as e:
        logger.exception("save_aspiration crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


def clear_aspiration_flow() -> None:
    print("\n═══ Clear Aspiration ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if data.get_aspiration_for_student(sid) is None:
        print(f"  ✗ {sid} has no aspiration recorded.")
        _pause()
        return
    confirm = _input(f"Clear aspiration for {sid}? Type 'yes'",
                     default="no")
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_aspiration(sid):
            print(f"\n  ✓ Cleared aspiration for {sid}")
    except Exception as e:
        logger.exception("delete_aspiration crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Per-student ──────────────────────────────────────────────────

def per_student() -> None:
    print("\n═══ Per-Student ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    student = student_data.get_student(sid)
    asp = data.get_aspiration_for_student(sid)
    sessions = data.sessions_for_student(sid)

    print(f"\n  {student.student_id}  {student.full_name}")
    print("\n  Aspiration:")
    if asp:
        print(f"    Pathway          : {asp.primary_pathway}")
        print(f"    Target career    : {asp.target_career or '—'}")
        print(f"    Target sector    : {asp.target_sector or '—'}")
        print(f"    Target employer  : {asp.target_employer or '—'}")
        print(f"    Target course    : {asp.target_course or '—'}")
        if asp.notes:
            print(f"    Notes            : {asp.notes}")
    else:
        print("    (no aspiration recorded)")

    print(f"\n  Sessions ({len(sessions)}):")
    _print_sessions(sessions)
    _row_action_loop_sessions(sessions)


# ── Summary ───────────────────────────────────────────────────────

def summary() -> None:
    print("\n═══ Careers Summary ═══")
    try:
        no_session = int(_input("No-session window in days",
                                 default="180"))
        upcoming = int(_input("Upcoming window in days",
                                default="14"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    summ = data.summary(
        no_session_window_days=no_session,
        upcoming_window_days=upcoming)

    print(f"\n  Total sessions: {summ.total_sessions}")
    print(f"  Aspirations recorded: {summ.students_with_aspiration}")

    print("\n  Sessions by Gatsby benchmark:")
    for k, title in GATSBY_BENCHMARKS.items():
        print(f"    {k}. {title[:46]:<46} : {summ.by_benchmark.get(k, 0)}")

    print("\n  By session type:")
    for t in SESSION_TYPES:
        n = summ.by_type.get(t, 0)
        if n:
            print(f"    {t:<22} : {n}")

    print("\n  By session status:")
    for s in SESSION_STATUSES:
        print(f"    {s:<14} : {summ.by_status.get(s, 0)}")

    print("\n  Aspirations by pathway:")
    for p in PATHWAYS:
        print(f"    {p:<16} : {summ.by_pathway.get(p, 0)}")

    print("\n  Alerts:")
    print(f"    Students with no completed session in last "
          f"{no_session}d : {summ.students_no_session}")
    print(f"    Upcoming scheduled sessions ({upcoming}d) : "
          f"{summ.upcoming_scheduled}")
    print(f"    Upcoming follow-ups ({upcoming}d) : "
          f"{summ.upcoming_follow_ups}")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _row_action_loop_sessions(rows: list[CareerSession]) -> None:
    if not rows:
        _pause()
        return
    print()
    print("  Actions:  V) View   E) Edit   D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "d"):
            print("    Pick V, E, D, or Enter.")
            continue
        try:
            raw = _input("Session ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            sid = int(raw)
        except ValueError:
            print("    Session ID must be a whole number.")
            continue
        if choice == "v":
            view_session(sid)
        elif choice == "e":
            edit_session(sid)
        elif choice == "d":
            delete_session_flow(sid)
        return


# ── Submenu dispatcher ────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List Sessions",        list_sessions),
    ("Filter Sessions",      filter_sessions),
    ("New Session",          new_session),
    ("View Session",         view_session),
    ("Edit Session",         edit_session),
    ("Delete Session",       delete_session_flow),
    ("List Aspirations",     list_aspirations),
    ("Save Aspiration",      save_aspiration_flow),
    ("Clear Aspiration",     clear_aspiration_flow),
    ("Per-Student",          per_student),
    ("Summary",              summary),
]


def run() -> None:
    while True:
        print("\n── Careers Guidance ──")
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
            logger.exception("Careers CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Careers Guidance":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Careers CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
