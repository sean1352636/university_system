"""CLI handlers for peer mentoring."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.secondarysch_system.modules.domain.pastoral.peer_mentoring import (
    peer_mentoring as data,
)
from education_system.secondarysch_system.modules.domain.pastoral.peer_mentoring.peer_mentoring import (
    PAIRING_STATUSES, FOCUS_AREAS, FREQUENCIES, SESSION_OUTCOMES,
)
from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
    ValidationError,
)

logger = logging.getLogger(__name__)


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _safe(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            print(f"  Validation error: {e}")
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _print_pairings(rows: list[data.Pairing]) -> None:
    if not rows:
        print("  (no pairings)")
        return
    print(f"  {'ID':<4} {'AYear':<8} {'Mentor':<10} {'MYr':<3} "
          f"{'Mentee':<10} {'EYr':<3} {'Focus':<14} "
          f"{'Freq':<10} {'Status':<10}")
    print(f"  {'-'*4} {'-'*8} {'-'*10} {'-'*3} {'-'*10} {'-'*3} "
          f"{'-'*14} {'-'*10} {'-'*10}")
    for p in rows:
        print(f"  {p.pairing_id:<4} {p.academic_year:<8} "
              f"{p.mentor_id:<10} {(p.mentor_year or '-'):<3} "
              f"{p.mentee_id:<10} {(p.mentee_year or '-'):<3} "
              f"{p.focus[:14]:<14} {p.frequency[:10]:<10} "
              f"{p.status:<10}")


def _print_sessions(rows: list[data.Session]) -> None:
    if not rows:
        print("  (no sessions)")
        return
    print(f"  {'ID':<5} {'Date':<10} {'Time':<5} {'Dur':<4} "
          f"{'Outcome':<18} {'!':<2} {'Agenda':<32}")
    print(f"  {'-'*5} {'-'*10} {'-'*5} {'-'*4} {'-'*18} {'-'*2} "
          f"{'-'*32}")
    for s in rows:
        print(f"  {s.session_id:<5} {s.session_date:<10} "
              f"{(s.session_time or '-'):<5} "
              f"{(s.duration_min if s.duration_min else '-'):<4} "
              f"{s.outcome[:18]:<18} "
              f"{('!' if s.concerns_flag else ''):<2} "
              f"{(s.agenda or '-')[:32]:<32}")


@_safe
def open_peer_mentoring() -> None:
    logger.debug("CLI: open_peer_mentoring")
    while True:
        print("\n  ── Peer Mentoring ──")
        print("  Pairings")
        print("    1) New pairing")
        print("    2) List pairings")
        print("    3) View pairing + sessions")
        print("    4) Edit pairing")
        print("    5) Set status")
        print("    6) End pairing")
        print("    7) Delete pairing")
        print("  Sessions")
        print("    8) Log session")
        print("    9) Delete session")
        print("  Reports")
        print("   10) Cohort summary")
        print("    0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new_pairing, "2": _list, "3": _view,
            "4": _edit_pairing, "5": _set_status,
            "6": _end_pairing, "7": _delete_pairing,
            "8": _log_session, "9": _delete_session,
            "10": _summary,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect_pairing(existing: data.Pairing | None = None
                      ) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["mentor_id"]     = ask("Mentor ID",
                                  existing.mentor_id if existing
                                  else None)
    f["mentee_id"]     = ask("Mentee ID",
                                  existing.mentee_id if existing
                                  else None)
    f["academic_year"] = ask("Academic year (YYYY/YY)",
                                  existing.academic_year if existing
                                  else None)
    f["focus"]         = ask(f"Focus ({'/'.join(FOCUS_AREAS)})",
                                  existing.focus if existing
                                  else "Academic")
    f["frequency"]     = ask(f"Frequency ({'/'.join(FREQUENCIES)})",
                                  existing.frequency if existing
                                  else "Weekly")
    f["coordinator"]   = ask("Coordinator",
                                  existing.coordinator if existing
                                  else None)
    f["start_date"]    = ask("Start date (YYYY-MM-DD, blank = today)",
                                  existing.start_date if existing
                                  else None)
    f["end_date"]      = ask("End date (YYYY-MM-DD, blank ok)",
                                  existing.end_date if existing
                                  else None)
    f["status"]        = ask(f"Status ({'/'.join(PAIRING_STATUSES)})",
                                  existing.status if existing
                                  else "Proposed")
    f["goals"]         = ask("Goals",
                                  existing.goals if existing else None)
    f["notes"]         = ask("Notes",
                                  existing.notes if existing else None)
    return f


@_safe
def _new_pairing() -> None:
    print("\n  ── New Pairing ──")
    fields = _collect_pairing()
    p = data.create_pairing(fields)
    print(f"  Created pairing #{p.pairing_id}: "
          f"{p.mentor_id} → {p.mentee_id} ({p.focus}, {p.status})")


@_safe
def _list() -> None:
    mentor = _prompt("  Mentor ID (blank): ") or None
    mentee = _prompt("  Mentee ID (blank): ") or None
    ay = _prompt("  Academic year (blank): ") or None
    status = _prompt(
        f"  Status ({'/'.join(PAIRING_STATUSES)}, blank): ") or None
    focus = _prompt(f"  Focus ({'/'.join(FOCUS_AREAS)}, blank): ") or None
    rows = data.list_pairings(mentor_id=mentor, mentee_id=mentee,
                                academic_year=ay, status=status,
                                focus=focus)
    print(f"\n  {len(rows)} pairing(s):")
    _print_pairings(rows)
    _prompt("\n  Press Enter to continue...")


def _ask_id(label: str) -> int | None:
    raw = _prompt(f"  {label}: ")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print(f"  {label} must be a number.")
        return None


@_safe
def _view() -> None:
    pid = _ask_id("Pairing ID")
    if pid is None:
        return
    s = data.pairing_summary(pid)
    p = s["pairing"]
    print(f"\n  ── Pairing #{p.pairing_id} ──")
    print(f"  Mentor:     {p.mentor_id} ({p.mentor_name or '-'}, "
          f"Yr {p.mentor_year or '-'})")
    print(f"  Mentee:     {p.mentee_id} ({p.mentee_name or '-'}, "
          f"Yr {p.mentee_year or '-'})")
    print(f"  Year:       {p.academic_year}")
    print(f"  Focus:      {p.focus}    Frequency: {p.frequency}")
    print(f"  Coord:      {p.coordinator or '-'}")
    print(f"  Period:     {p.start_date} → {p.end_date or 'open'}")
    print(f"  Status:     {p.status}")
    print(f"  Goals:      {p.goals or '-'}")
    print(f"  Notes:      {p.notes or '-'}")
    print(f"\n  Sessions: {s['session_count']}    "
          f"Attended/productive: {s['attended']}    "
          f"Missed/cancelled: {s['missed']}    "
          f"Concerns: {s['concerns']}")
    if s["by_outcome"]:
        print("  By outcome:")
        for k, v in s["by_outcome"].items():
            print(f"    {k:<22} {v}")
    _print_sessions(s["sessions"])
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit_pairing() -> None:
    pid = _ask_id("Pairing ID")
    if pid is None:
        return
    existing = data.get_pairing(pid)
    if existing is None:
        print("  No pairing with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect_pairing(existing)
    p = data.update_pairing(pid, fields)
    print(f"  Updated pairing #{p.pairing_id} (status {p.status})")


@_safe
def _set_status() -> None:
    pid = _ask_id("Pairing ID")
    if pid is None:
        return
    p = data.get_pairing(pid)
    if p is None:
        print("  No pairing with that ID.")
        return
    print(f"  Current: {p.status}    Allowed: "
          f"{', '.join(PAIRING_STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    p = data.set_status(pid, new)
    print(f"  Status now: {p.status}")


@_safe
def _end_pairing() -> None:
    pid = _ask_id("Pairing ID")
    if pid is None:
        return
    end = _prompt("  End date (YYYY-MM-DD, blank = today): ") or None
    p = data.end_pairing(pid, end_date=end)
    print(f"  Ended pairing #{p.pairing_id} on {p.end_date}.")


@_safe
def _delete_pairing() -> None:
    pid = _ask_id("Pairing ID")
    if pid is None:
        return
    p = data.get_pairing(pid)
    if p is None:
        print("  No pairing with that ID.")
        return
    confirm = _prompt(
        f"  Delete pairing {p.mentor_id} → {p.mentee_id} "
        f"and ALL sessions? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete_pairing(pid)
    print(f"  Deleted pairing #{pid}.")


@_safe
def _log_session() -> None:
    pid = _ask_id("Pairing ID")
    if pid is None:
        return
    if data.get_pairing(pid) is None:
        print("  No pairing with that ID.")
        return
    f: dict[str, Any] = {"pairing_id": pid}
    f["session_date"] = _prompt(
        "  Session date (YYYY-MM-DD, blank = today): ") or None
    f["session_time"] = _prompt(
        "  Session time (HH:MM, blank ok): ") or None
    f["duration_min"] = _prompt(
        "  Duration in minutes (blank ok): ") or None
    f["location"]    = _prompt("  Location: ") or None
    f["agenda"]      = _prompt("  Agenda: ") or None
    f["outcome"]     = _prompt(
        f"  Outcome ({'/'.join(SESSION_OUTCOMES)}) [Attended]: "
    ) or "Attended"
    cf = _prompt("  Concerns raised? (y/N): ")
    f["concerns_flag"] = cf.lower().startswith("y")
    if f["concerns_flag"]:
        f["follow_up"] = _prompt("  Follow-up (required): ")
    else:
        f["follow_up"] = _prompt("  Follow-up (blank ok): ") or None
    f["notes"]       = _prompt("  Notes: ") or None
    s = data.log_session(f)
    print(f"  Logged session #{s.session_id} ({s.outcome}, "
          f"concerns={s.concerns_flag})")


@_safe
def _delete_session() -> None:
    sid = _ask_id("Session ID")
    if sid is None:
        return
    s = data.get_session(sid)
    if s is None:
        print("  No session with that ID.")
        return
    confirm = _prompt(f"  Delete session #{sid}? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete_session(sid)
    print(f"  Deleted session #{sid}.")


@_safe
def _summary() -> None:
    ay = _prompt("  Academic year (blank): ") or None
    s = data.cohort_summary(academic_year=ay)
    print(f"\n  Pairings: {s['total']}    Active: {s['active']}    "
          f"Mentors: {s['mentors']}    Mentees: {s['mentees']}")
    if s["by_status"]:
        print("  By status: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_status"].items()))
    if s["by_focus"]:
        print("  By focus:")
        for k, v in sorted(s["by_focus"].items(),
                            key=lambda kv: -kv[1]):
            print(f"    {k:<16} {v}")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Peer Mentoring": open_peer_mentoring}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching peer_mentoring CLI label: %s", label)
    handler()
    return True
