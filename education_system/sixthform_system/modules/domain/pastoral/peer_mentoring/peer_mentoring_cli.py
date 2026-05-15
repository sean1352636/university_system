"""CLI flows for Sixth Form Peer Mentoring."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.pastoral.peer_mentoring import (
    peer_mentoring as data,
)
from education_system.sixthform_system.modules.domain.pastoral.peer_mentoring.peer_mentoring import (
    DEFAULT_FREQUENCY,
    DEFAULT_PROGRAMME,
    DEFAULT_STATUS,
    FREQUENCIES,
    PROGRAMMES,
    Pairing,
    STATUSES,
    Session,
    ValidationError,
)
from education_system.sixthform_system.modules.domain.students.students import (
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


def _pick_student(role: str) -> str:
    rows = _students.list_students()
    if not rows:
        print("    No students.")
        raise _UserAbort
    print(f"\n  Pick {role}:")
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


def _pick_pairing() -> Pairing:
    rows = data.list_pairings()
    if not rows:
        print("    No pairings yet.")
        raise _UserAbort
    print("\n  Pairings:")
    for i, p in enumerate(rows, 1):
        print(f"    {i:>3}) #{p.pairing_id}  {p.start_date}  "
              f"{p.mentor_id:<10}→{p.mentee_id:<10}  "
              f"{p.programme[:22]:<22}  [{p.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((p for p in rows
                            if p.pairing_id == n), None)
            if match:
                return match
        print("    No matching pairing.")


def _pick_session(pairing_id: int) -> Session:
    rows = data.list_sessions(pairing_id)
    if not rows:
        print("    No sessions logged yet.")
        raise _UserAbort
    print("\n  Sessions:")
    for i, s in enumerate(rows, 1):
        mark = "✓" if s.attended else "✗"
        print(f"    {i:>3}) #{s.session_id}  {s.session_date}  "
              f"{s.duration_minutes}m  {mark}  "
              f"{(s.focus or '—')[:30]}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((s for s in rows
                            if s.session_id == n), None)
            if match:
                return match
        print("    No matching session.")


def _print_table(rows: list[Pairing]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Start':<10}  {'Programme':<20}  "
          f"{'Mentor':<10}→{'Mentee':<10}  "
          f"{'Freq':<11}  {'Status':<14}  Sess")
    print("  " + "-" * 110)
    for p in rows:
        stats = data.pairing_session_stats(p.pairing_id)
        sess = f"{stats['attended']}/{stats['total']}"
        print(f"  {p.pairing_id:>4}  {p.start_date:<10}  "
              f"{p.programme[:20]:<20}  "
              f"{p.mentor_id:<10}→{p.mentee_id:<10}  "
              f"{p.frequency:<11}  {p.status:<14}  {sess}")
    print(f"\n  {len(rows)} pairing(s).")


def _print_full(p: Pairing) -> None:
    stats = data.pairing_session_stats(p.pairing_id)
    print()
    print(f"    #{p.pairing_id}  {p.programme}")
    print(f"    Mentor → Mentee   : "
          f"{p.mentor_id} → {p.mentee_id}")
    print(f"    Coordinator       : {p.coordinator or '—'}")
    print(f"    Frequency         : {p.frequency}")
    print(f"    Start / planned   : "
          f"{p.start_date}  →  {p.planned_end or '—'}")
    print(f"    Actual end        : {p.actual_end or '—'}")
    print(f"    Location          : {p.location or '—'}")
    print(f"    Subject focus     : {p.subject_focus or '—'}")
    print(f"    Status            : {p.status}")
    print(f"    Sessions          : "
          f"{stats['attended']} attended of {stats['total']} "
          f"({stats['total_hours']}h logged); "
          f"planned: "
          f"{p.sessions_planned if p.sessions_planned is not None else '—'}")
    print(f"    Mentor rating     : "
          f"{p.mentor_rating or '—'}/5")
    print(f"    Mentee rating     : "
          f"{p.mentee_rating or '—'}/5")
    for label, val in (
            ("Goals",            p.goals),
            ("Mentor feedback",  p.mentor_feedback),
            ("Mentee feedback",  p.mentee_feedback),
            ("Notes",            p.notes),
    ):
        if val:
            print(f"\n    {label}:")
            for line in val.splitlines():
                print(f"      {line}")


def _print_sessions(rows: list[Session]) -> None:
    if not rows:
        print("\n  (no sessions)")
        return
    print()
    print(f"  {'#':>4}  {'Date':<10}  {'Mins':>5}  Att.  "
          f"{'Focus':<24}  Notes")
    print("  " + "-" * 90)
    for s in rows:
        mark = "✓" if s.attended else "✗"
        n = (s.notes.splitlines()[0]
              if s.notes else "—")
        print(f"  {s.session_id:>4}  {s.session_date:<10}  "
              f"{s.duration_minutes:>5}  {mark:>3}   "
              f"{(s.focus or '—')[:24]:<24}  {n[:30]}")
    print(f"\n  {len(rows)} session(s).")


# ── Flows ────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Pairings ═══")
    _print_table(data.list_pairings())
    _pause()


def list_active() -> None:
    print("\n═══ Active Pairings ═══")
    _print_table(data.list_pairings(active_only=True))
    _pause()


def list_open() -> None:
    print("\n═══ Open Pairings ═══")
    _print_table(data.list_pairings(open_only=True))
    _pause()


def list_pending() -> None:
    print("\n═══ Pending Match ═══")
    _print_table(data.list_pairings(status="Pending Match"))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter ═══")
    try:
        prog = _input(
            f"Programme ({'/'.join(PROGRAMMES[:2])}…)") or None
        status = _input(f"Status ({'/'.join(STATUSES[:3])}…)") or None
        freq = _input(
            f"Frequency ({'/'.join(FREQUENCIES)})") or None
        mentor = _input("Mentor id") or None
        mentee = _input("Mentee id") or None
        either = _input("Either id") or None
        coord = _input("Coordinator contains") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_pairings(
            programme=prog, status=status, frequency=freq,
            mentor_id=mentor, mentee_id=mentee,
            either_id=either, coordinator_like=coord)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_table(rows)
    _pause()


def per_student_flow() -> None:
    print("\n═══ Per-Student ═══")
    try:
        sid = _pick_student("student")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_table(data.pairings_for_student(sid))
    _pause()


def view_flow() -> None:
    print("\n═══ View Pairing ═══")
    try:
        p = _pick_pairing()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_full(p)
    print(f"\n  Sessions:")
    _print_sessions(data.list_sessions(p.pairing_id))
    _pause()


def _collect_pairing_form(
        existing: Pairing | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        payload["mentor_id"] = existing.mentor_id
        payload["mentee_id"] = existing.mentee_id
    else:
        payload["mentor_id"] = _pick_student("mentor")
        payload["mentee_id"] = _pick_student("mentee")
    payload["programme"] = _pick_from(
        "Programme", list(PROGRAMMES),
        default=(existing.programme if is_edit
                  else DEFAULT_PROGRAMME))
    payload["frequency"] = _pick_from(
        "Frequency", list(FREQUENCIES),
        default=(existing.frequency if is_edit
                  else DEFAULT_FREQUENCY))
    payload["start_date"] = _input(
        "Start date (YYYY-MM-DD)",
        default=(existing.start_date if is_edit
                  else _date.today().isoformat()),
        allow_empty=False)
    payload["planned_end"] = _input(
        "Planned end (YYYY-MM-DD)",
        default=(existing.planned_end or "") if is_edit else "")
    payload["actual_end"] = _input(
        "Actual end (YYYY-MM-DD)",
        default=(existing.actual_end or "") if is_edit else "")
    payload["sessions_planned"] = _input(
        "Sessions planned",
        default=(str(existing.sessions_planned)
                  if is_edit and existing.sessions_planned is not None
                  else ""))
    payload["coordinator"] = _input(
        "Coordinator",
        default=(existing.coordinator or "") if is_edit else "")
    payload["location"] = _input(
        "Location",
        default=(existing.location or "") if is_edit else "")
    payload["subject_focus"] = _input(
        "Subject focus",
        default=(existing.subject_focus or "")
        if is_edit else "")
    try:
        payload["goals"] = _multiline(
            "Goals",
            default=(existing.goals or "") if is_edit else "")
        payload["mentor_feedback"] = _multiline(
            "Mentor feedback",
            default=(existing.mentor_feedback or "")
            if is_edit else "")
        payload["mentee_feedback"] = _multiline(
            "Mentee feedback",
            default=(existing.mentee_feedback or "")
            if is_edit else "")
        payload["notes"] = _multiline(
            "Notes",
            default=(existing.notes or "") if is_edit else "")
    except _UserAbort:
        raise
    payload["mentor_rating"] = _input(
        "Mentor rating (1-5, blank = none)",
        default=(str(existing.mentor_rating)
                  if is_edit and existing.mentor_rating is not None
                  else ""))
    payload["mentee_rating"] = _input(
        "Mentee rating (1-5, blank = none)",
        default=(str(existing.mentee_rating)
                  if is_edit and existing.mentee_rating is not None
                  else ""))
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    return payload


def new_pairing() -> None:
    print("\n═══ New Pairing ═══")
    try:
        payload = _collect_pairing_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        p = data.create_pairing(payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created pairing #{p.pairing_id}")
    _pause()


def edit_pairing() -> None:
    print("\n═══ Edit Pairing ═══")
    try:
        p = _pick_pairing()
        payload = _collect_pairing_form(p)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_pairing(p.pairing_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated #{p.pairing_id}")
    _pause()


def add_session_flow() -> None:
    print("\n═══ Add Session ═══")
    try:
        p = _pick_pairing()
        when = _input("Session date (YYYY-MM-DD)",
                        default=_date.today().isoformat(),
                        allow_empty=False)
        dur = _input("Duration (mins)", default="30",
                        allow_empty=False)
        focus = _input("Focus")
        attended = _yes_no("Attended?", default=True)
        notes = _multiline("Notes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        s = data.add_session(p.pairing_id, {
            "session_date": when,
            "duration_minutes": dur,
            "focus": focus or None,
            "attended": attended,
            "notes": notes or None,
        })
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Session #{s.session_id} logged")
    _pause()


def edit_session_flow() -> None:
    print("\n═══ Edit Session ═══")
    try:
        p = _pick_pairing()
        s = _pick_session(p.pairing_id)
        when = _input("Date", default=s.session_date,
                        allow_empty=False)
        dur = _input("Duration (mins)",
                        default=str(s.duration_minutes),
                        allow_empty=False)
        focus = _input("Focus", default=s.focus or "")
        attended = _yes_no("Attended?", default=s.attended)
        notes = _multiline("Notes", default=s.notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_session(s.session_id, {
            "session_date": when,
            "duration_minutes": dur,
            "focus": focus or None,
            "attended": attended,
            "notes": notes or None,
        })
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Session #{s.session_id} updated")
    _pause()


def delete_session_flow() -> None:
    print("\n═══ Delete Session ═══")
    try:
        p = _pick_pairing()
        s = _pick_session(p.pairing_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete session #{s.session_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_session(s.session_id):
        print(f"\n  ✓ Deleted #{s.session_id}")
    _pause()


def activate_flow() -> None:
    print("\n═══ Activate ═══")
    try:
        p = _pick_pairing()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.activate(p.pairing_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{p.pairing_id} → Active")
    _pause()


def pause_flow() -> None:
    print("\n═══ Pause ═══")
    try:
        p = _pick_pairing()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.pause(p.pairing_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{p.pairing_id} → Paused")
    _pause()


def complete_flow() -> None:
    print("\n═══ Complete Pairing ═══")
    try:
        p = _pick_pairing()
        mentor_fb = _multiline("Mentor feedback",
                                  default=p.mentor_feedback or "")
        mentee_fb = _multiline("Mentee feedback",
                                  default=p.mentee_feedback or "")
        mr_raw = _input("Mentor rating (1-5, blank)",
                            default=str(p.mentor_rating)
                            if p.mentor_rating else "")
        me_raw = _input("Mentee rating (1-5, blank)",
                            default=str(p.mentee_rating)
                            if p.mentee_rating else "")
        when = _input("Ended on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    mr = int(mr_raw) if mr_raw and mr_raw.isdigit() else None
    me = int(me_raw) if me_raw and me_raw.isdigit() else None
    try:
        data.complete(p.pairing_id,
                          mentor_feedback=mentor_fb or None,
                          mentee_feedback=mentee_fb or None,
                          mentor_rating=mr, mentee_rating=me,
                          ended_on=when)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{p.pairing_id} → Completed")
    _pause()


def withdraw_flow() -> None:
    print("\n═══ Withdraw ═══")
    try:
        p = _pick_pairing()
        reason = _multiline("Reason")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.withdraw(p.pairing_id, reason=reason or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{p.pairing_id} → Withdrawn")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        p = _pick_pairing()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=p.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(p.pairing_id, new_status)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{p.pairing_id} → {new_status}")
    _pause()


def delete_pairing_flow() -> None:
    print("\n═══ Delete Pairing ═══")
    try:
        p = _pick_pairing()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete pairing #{p.pairing_id} "
                "(and all its sessions)? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_pairing(p.pairing_id):
        print(f"\n  ✓ Deleted #{p.pairing_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Peer Mentoring Summary ═══")
    s = data.summary()
    print(f"\n  Total pairings        : {s.total}")
    print(f"  Active                : {s.active}")
    print(f"  Pending match         : {s.pending}")
    print(f"  Completed             : {s.completed}")
    print(f"  Distinct mentors      : {s.distinct_mentors}")
    print(f"  Distinct mentees      : {s.distinct_mentees}")
    print(f"  Total sessions logged : {s.total_sessions}")
    print(f"  Total hours           : {s.total_hours}")
    print(f"  Average mentee rating : "
          f"{s.average_mentee_rating if s.average_mentee_rating is not None else '—'}")
    print("\n  By programme:")
    for k in PROGRAMMES:
        n = s.by_programme.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    print("\n  By status:")
    for k in STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<16}: {n}")
    print("\n  By frequency:")
    for k in FREQUENCIES:
        n = s.by_frequency.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",          list_all),
    ("Active",            list_active),
    ("Open",              list_open),
    ("Pending match",     list_pending),
    ("Filter",            filter_flow),
    ("Per-student",       per_student_flow),
    ("View pairing",      view_flow),
    ("─" * 6,             lambda: None),
    ("New pairing",       new_pairing),
    ("Edit pairing",      edit_pairing),
    ("Add session",       add_session_flow),
    ("Edit session",      edit_session_flow),
    ("Delete session",    delete_session_flow),
    ("Activate",          activate_flow),
    ("Pause",             pause_flow),
    ("Complete",          complete_flow),
    ("Withdraw",          withdraw_flow),
    ("Change status",     set_status_flow),
    ("Delete pairing",    delete_pairing_flow),
    ("─" * 6,             lambda: None),
    ("Summary",           summary_flow),
]


def run() -> None:
    while True:
        print("\n── Peer Mentoring ──")
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
            logger.exception("Peer Mentoring CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Peer Mentoring":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Peer Mentoring CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
