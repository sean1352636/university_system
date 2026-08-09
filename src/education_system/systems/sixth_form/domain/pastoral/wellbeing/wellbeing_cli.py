"""CLI flows for Sixth Form Wellbeing.

Three record types under one submenu:
* Check-ins  (mood/stress/sleep pulse)
* Sessions   (counselling, mentoring, study support, …)
* Flags      (long-running pastoral tags like Young Carer, Bereavement)
"""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.domain.pastoral.wellbeing import wellbeing as data
from education_system.systems.sixth_form.domain.pastoral.wellbeing.wellbeing import (
    CheckIn,
    DEFAULT_SESSION_STATUS,
    DEFAULT_SESSION_TYPE,
    FLAG_TYPES,
    Flag,
    SCORE_MAX,
    SCORE_MIN,
    SESSION_STATUSES,
    SESSION_TYPES,
    Session,
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
            print(f"    Out of range (1..{len(options)}).")
            continue
        return options[n - 1]


def _pick_score(label: str, default: int | None = None) -> int | None:
    raw = _input(f"{label} ({SCORE_MIN}-{SCORE_MAX}, blank=skip)",
                  default=str(default) if default is not None else "")
    if not raw:
        return None
    try:
        n = int(raw)
    except ValueError:
        print(f"    {label} must be a number {SCORE_MIN}-{SCORE_MAX}.")
        return _pick_score(label, default)
    if not (SCORE_MIN <= n <= SCORE_MAX):
        print(f"    {label} must be {SCORE_MIN}-{SCORE_MAX}.")
        return _pick_score(label, default)
    return n


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


def _yes_no(prompt: str, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)", default="y" if default else "n")
    return raw.lower() in ("y", "yes")


# ── Print helpers ──────────────────────────────────────────────────

def _fmt_score(n: int | None) -> str:
    return "—" if n is None else str(n)


def _print_checkins(rows: list[CheckIn]) -> None:
    if not rows:
        print("\n  (no check-ins)")
        return
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Date':<10}  "
          f"{'Mood':>4}  {'Stress':>6}  {'Sleep':>5}  By")
    print("  " + "-" * 64)
    for c in rows:
        print(f"  {c.checkin_id:>4}  {c.student_id:<10}  {c.checkin_date:<10}  "
              f"{_fmt_score(c.mood_score):>4}  "
              f"{_fmt_score(c.stress_score):>6}  "
              f"{_fmt_score(c.sleep_score):>5}  "
              f"{c.recorded_by or '—'}")
    print(f"\n  {len(rows)} check-in(s).")


def _print_sessions(rows: list[Session]) -> None:
    if not rows:
        print("\n  (no sessions)")
        return
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Date':<10}  "
          f"{'Type':<18}  {'Mins':>4}  {'Status':<10}  Provider")
    print("  " + "-" * 80)
    for s in rows:
        print(f"  {s.session_id:>4}  {s.student_id:<10}  {s.session_date:<10}  "
              f"{s.session_type[:18]:<18}  "
              f"{(str(s.duration_minutes) if s.duration_minutes else '—'):>4}  "
              f"{s.status:<10}  {s.provider or '—'}")
    print(f"\n  {len(rows)} session(s).")


def _print_flags(rows: list[Flag]) -> None:
    if not rows:
        print("\n  (no flags)")
        return
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Type':<25}  "
          f"{'Start':<10}  {'End':<10}  Status")
    print("  " + "-" * 76)
    for f in rows:
        print(f"  {f.flag_id:>4}  {f.student_id:<10}  "
              f"{f.flag_type[:25]:<25}  "
              f"{(f.start_date or '—'):<10}  "
              f"{(f.end_date or '—'):<10}  "
              f"{'Active' if f.active else 'Closed'}")
    print(f"\n  {len(rows)} flag(s).")


# ── Check-in flows ─────────────────────────────────────────────────

def list_checkins() -> None:
    print("\n═══ Wellbeing Check-ins ═══")
    rows = data.list_checkins()
    _print_checkins(rows)
    _pause()


def filter_checkins() -> None:
    print("\n═══ Filter Check-ins ═══")
    print("  (leave any field blank to skip; 'cancel' to abort)\n")
    try:
        sid = _input("Student ID") or None
        date_from = _input("From (YYYY-MM-DD)") or None
        date_to = _input("To (YYYY-MM-DD)") or None
        lm = _input("Mood ≤ (alert threshold, blank=skip)") or None
        hs = _input("Stress ≥ (alert threshold, blank=skip)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_checkins(
            student_id=sid, date_from=date_from, date_to=date_to,
            low_mood=int(lm) if lm else None,
            high_stress=int(hs) if hs else None,
        )
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_checkins(rows)
    _pause()


def new_checkin() -> None:
    print("\n═══ New Check-in ═══")
    today = _date.today().isoformat()
    try:
        sid = _pick_student()
        cdate = _input("Check-in date (YYYY-MM-DD)", default=today,
                        allow_empty=False)
        mood = _pick_score("Mood")
        stress = _pick_score("Stress")
        sleep = _pick_score("Sleep")
        notes = _input("Notes (optional)")
        by = _input("Recorded by (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        c = data.create_checkin({
            "student_id": sid, "checkin_date": cdate,
            "mood_score": mood, "stress_score": stress, "sleep_score": sleep,
            "notes": notes, "recorded_by": by,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created check-in #{c.checkin_id}")
    _pause()


def edit_checkin() -> None:
    print("\n═══ Edit Check-in ═══")
    try:
        cid = int(_input("Check-in ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_checkin(cid)
    if existing is None:
        print(f"  ✗ No check-in #{cid}")
        _pause()
        return
    try:
        cdate = _input("Check-in date", default=existing.checkin_date,
                        allow_empty=False)
        mood = _pick_score("Mood", default=existing.mood_score)
        stress = _pick_score("Stress", default=existing.stress_score)
        sleep = _pick_score("Sleep", default=existing.sleep_score)
        notes = _input("Notes", default=existing.notes or "")
        by = _input("Recorded by", default=existing.recorded_by or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_checkin(cid, {
            "checkin_date": cdate, "mood_score": mood,
            "stress_score": stress, "sleep_score": sleep,
            "notes": notes, "recorded_by": by,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{cid}")
    _pause()


def delete_checkin() -> None:
    print("\n═══ Delete Check-in ═══")
    try:
        cid = int(_input("Check-in ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_checkin(cid) is None:
        print(f"  ✗ No check-in #{cid}")
        _pause()
        return
    if _input(f"Delete check-in #{cid}? Type 'yes' to confirm",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_checkin(cid):
        print(f"\n  ✓ Deleted #{cid}")
    _pause()


# ── Session flows ──────────────────────────────────────────────────

def list_sessions() -> None:
    print("\n═══ Wellbeing Sessions ═══")
    _print_sessions(data.list_sessions())
    _pause()


def list_scheduled() -> None:
    print("\n═══ Scheduled (Upcoming) Sessions ═══")
    _print_sessions(data.list_sessions(status="Scheduled"))
    _pause()


def filter_sessions() -> None:
    print("\n═══ Filter Sessions ═══")
    try:
        sid = _input("Student ID") or None
        stype = _input(f"Session type ({'/'.join(SESSION_TYPES)})") or None
        status = _input(f"Status ({'/'.join(SESSION_STATUSES)})") or None
        prov = _input("Provider contains") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_sessions(
            student_id=sid, session_type=stype, status=status,
            provider_like=prov, date_from=df, date_to=dt,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_sessions(rows)
    _pause()


def view_session() -> None:
    print("\n═══ View Session ═══")
    try:
        sid = int(_input("Session ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
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
    print(f"    Type          : {s.session_type}")
    print(f"    Status        : {s.status}")
    print(f"    Duration (m)  : {s.duration_minutes or '—'}")
    print(f"    Provider      : {s.provider or '—'}")
    print(f"    Topics        : {s.topics or '—'}")
    print(f"    Follow-up     : {s.follow_up_date or '—'}")
    if s.action_plan:
        print("\n    Action plan:")
        for line in s.action_plan.splitlines() or [""]:
            print(f"      {line}")
    if s.notes:
        print("\n    Notes:")
        for line in s.notes.splitlines() or [""]:
            print(f"      {line}")
    _pause()


def _session_form(existing: Session | None) -> dict[str, Any]:
    today = _date.today().isoformat()
    is_edit = existing is not None
    if is_edit:
        print(f"\n  Editing session #{existing.session_id} "
              f"for {existing.student_id}")
        sid = existing.student_id
    else:
        sid = _pick_student()
    sdate = _input("Session date (YYYY-MM-DD)",
                    default=existing.session_date if is_edit else today,
                    allow_empty=False)
    stype = _pick_from("Session type", list(SESSION_TYPES),
                        default=existing.session_type
                                if is_edit else DEFAULT_SESSION_TYPE)
    status = _pick_from("Status", list(SESSION_STATUSES),
                         default=existing.status
                                 if is_edit else DEFAULT_SESSION_STATUS)
    dur = _input("Duration in minutes (optional)",
                  default=str(existing.duration_minutes)
                          if is_edit and existing.duration_minutes else "")
    provider = _input("Provider (counsellor, mentor, agency, …)",
                       default=existing.provider or "" if is_edit else "")
    topics = _input("Topics discussed (optional)",
                     default=existing.topics or "" if is_edit else "")
    action_plan = _input("Action plan (single line, optional)",
                          default=existing.action_plan or ""
                                  if is_edit else "")
    follow = _input("Follow-up date (optional)",
                     default=existing.follow_up_date or ""
                             if is_edit else "")
    notes = _input("Notes (optional)",
                    default=existing.notes or "" if is_edit else "")
    return {
        "student_id": sid, "session_date": sdate, "session_type": stype,
        "status": status, "duration_minutes": dur or None,
        "provider": provider, "topics": topics, "action_plan": action_plan,
        "follow_up_date": follow, "notes": notes,
    }


def new_session() -> None:
    print("\n═══ New Session ═══")
    try:
        payload = _session_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        s = data.create_session(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created session #{s.session_id}")
    _pause()


def edit_session() -> None:
    print("\n═══ Edit Session ═══")
    try:
        sid = int(_input("Session ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_session(sid)
    if existing is None:
        print(f"  ✗ No session #{sid}")
        _pause()
        return
    try:
        payload = _session_form(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_session(sid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{sid}")
    _pause()


def delete_session() -> None:
    print("\n═══ Delete Session ═══")
    try:
        sid = int(_input("Session ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_session(sid) is None:
        print(f"  ✗ No session #{sid}")
        _pause()
        return
    if _input(f"Delete session #{sid}? Type 'yes'", default="no").lower() \
            != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_session(sid):
        print(f"\n  ✓ Deleted #{sid}")
    _pause()


# ── Flag flows ─────────────────────────────────────────────────────

def list_flags() -> None:
    print("\n═══ Wellbeing Flags ═══")
    _print_flags(data.list_flags())
    _pause()


def list_active_flags() -> None:
    print("\n═══ Active Flags ═══")
    _print_flags(data.list_flags(active_only=True))
    _pause()


def filter_flags() -> None:
    print("\n═══ Filter Flags ═══")
    try:
        sid = _input("Student ID") or None
        ftype = _input(f"Flag type ({'/'.join(FLAG_TYPES)})") or None
        active = _yes_no("Active only?", default=True)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_flags(student_id=sid, flag_type=ftype,
                                active_only=active)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_flags(rows)
    _pause()


def new_flag() -> None:
    print("\n═══ New Flag ═══")
    today = _date.today().isoformat()
    try:
        sid = _pick_student()
        ftype = _pick_from("Flag type", list(FLAG_TYPES))
        start = _input("Start date (YYYY-MM-DD, optional)", default=today)
        end = _input("End date (YYYY-MM-DD, optional — blank = active)")
        notes = _input("Notes (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        f = data.create_flag({
            "student_id": sid, "flag_type": ftype,
            "start_date": start, "end_date": end, "notes": notes,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created flag #{f.flag_id}")
    _pause()


def edit_flag() -> None:
    print("\n═══ Edit Flag ═══")
    try:
        fid = int(_input("Flag ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_flag(fid)
    if existing is None:
        print(f"  ✗ No flag #{fid}")
        _pause()
        return
    try:
        ftype = _pick_from("Flag type", list(FLAG_TYPES),
                            default=existing.flag_type)
        start = _input("Start date", default=existing.start_date or "")
        end = _input("End date (blank=active)",
                      default=existing.end_date or "")
        notes = _input("Notes", default=existing.notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_flag(fid, {
            "flag_type": ftype, "start_date": start,
            "end_date": end, "notes": notes,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{fid}")
    _pause()


def close_flag_flow() -> None:
    print("\n═══ Close Flag ═══")
    try:
        fid = int(_input("Flag ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_flag(fid) is None:
        print(f"  ✗ No flag #{fid}")
        _pause()
        return
    end = _input("End date", default=_date.today().isoformat(),
                  allow_empty=False)
    try:
        data.close_flag(fid, end)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Closed flag #{fid} on {end}")
    _pause()


def reopen_flag_flow() -> None:
    print("\n═══ Re-open Flag ═══")
    try:
        fid = int(_input("Flag ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_flag(fid) is None:
        print(f"  ✗ No flag #{fid}")
        _pause()
        return
    data.reopen_flag(fid)
    print(f"\n  ✓ Re-opened flag #{fid}")
    _pause()


def delete_flag() -> None:
    print("\n═══ Delete Flag ═══")
    try:
        fid = int(_input("Flag ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_flag(fid) is None:
        print(f"  ✗ No flag #{fid}")
        _pause()
        return
    if _input(f"Delete flag #{fid}? Type 'yes'", default="no").lower() \
            != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_flag(fid):
        print(f"\n  ✓ Deleted #{fid}")
    _pause()


# ── Per-student & summary ─────────────────────────────────────────

def per_student() -> None:
    print("\n═══ Per-Student Wellbeing ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    student = student_data.get_student(sid)
    summ = data.per_student_summary(sid)
    print(f"\n  {student.student_id}  {student.full_name}")
    print(f"    Check-ins        : {summ.checkin_count}")
    print(f"    Sessions         : {summ.session_count}")
    print(f"    Active flags     : "
          f"{', '.join(summ.active_flags) if summ.active_flags else '—'}")
    print(f"    Latest check-in  : "
          f"{summ.latest_checkin_date or '—'}  "
          f"(mood={_fmt_score(summ.latest_mood)}  "
          f"stress={_fmt_score(summ.latest_stress)}  "
          f"sleep={_fmt_score(summ.latest_sleep)})")
    print(f"    Average scores   : "
          f"mood={summ.avg_mood if summ.avg_mood is not None else '—'}  "
          f"stress={summ.avg_stress if summ.avg_stress is not None else '—'}"
          f"  sleep={summ.avg_sleep if summ.avg_sleep is not None else '—'}")
    print("\n  Recent check-ins:")
    _print_checkins(data.list_checkins(student_id=sid)[:10])
    print("\n  Recent sessions:")
    _print_sessions(data.list_sessions(student_id=sid)[:10])
    print("\n  All flags:")
    _print_flags(data.list_flags(student_id=sid))
    _pause()


def summary() -> None:
    print("\n═══ Wellbeing Summary ═══")
    try:
        upcoming = int(_input("Upcoming window (days)", default="14"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    summ = data.summary(upcoming_window_days=upcoming)
    print("\n  Totals:")
    print(f"    Check-ins       : {summ.total_checkins}")
    print(f"    Sessions        : {summ.total_sessions}")
    print(f"    Flags active    : {summ.active_flags}")
    print(f"    Flags closed    : {summ.closed_flags}")
    print("\n  Alerts:")
    print(f"    Low-mood check-ins   : {summ.low_mood_count}")
    print(f"    High-stress check-ins: {summ.high_stress_count}")
    print(f"    Students with recent low mood: "
          f"{summ.students_low_recent_mood}")
    print(f"    Sessions scheduled in next {upcoming}d: "
          f"{summ.sessions_scheduled_upcoming}")
    print(f"    Follow-ups due in next {upcoming}d   : "
          f"{summ.upcoming_follow_ups}")
    print("\n  Cohort reach:")
    print(f"    Students with active flag   : {summ.students_with_flag}")
    print(f"    Students with any session   : {summ.students_with_session}")
    print("\n  Active flags by type:")
    for t in FLAG_TYPES:
        n = summ.by_flag_type.get(t, 0)
        if n:
            print(f"    {t:<28} : {n}")
    print("\n  Sessions by type:")
    for t in SESSION_TYPES:
        n = summ.by_session_type.get(t, 0)
        if n:
            print(f"    {t:<28} : {n}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List Check-ins",            list_checkins),
    ("Filter Check-ins",          filter_checkins),
    ("New Check-in",              new_checkin),
    ("Edit Check-in",             edit_checkin),
    ("Delete Check-in",           delete_checkin),
    ("List Sessions",             list_sessions),
    ("Upcoming (Scheduled)",      list_scheduled),
    ("Filter Sessions",           filter_sessions),
    ("View Session",              view_session),
    ("New Session",               new_session),
    ("Edit Session",              edit_session),
    ("Delete Session",            delete_session),
    ("List Active Flags",         list_active_flags),
    ("List All Flags",            list_flags),
    ("Filter Flags",              filter_flags),
    ("New Flag",                  new_flag),
    ("Edit Flag",                 edit_flag),
    ("Close Flag",                close_flag_flow),
    ("Re-open Flag",              reopen_flag_flow),
    ("Delete Flag",               delete_flag),
    ("Per-Student",               per_student),
    ("Summary",                   summary),
]


def run() -> None:
    while True:
        print("\n── Wellbeing ──")
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
            logger.exception("Wellbeing CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Wellbeing":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Wellbeing CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
