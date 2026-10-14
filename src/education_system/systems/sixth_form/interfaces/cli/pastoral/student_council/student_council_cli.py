"""CLI flows for Sixth Form Student Council."""

from __future__ import annotations

import logging
from datetime import date as _date
from datetime import datetime as _dt
from typing import Any, Callable
from education_system.systems.sixth_form.domain.pastoral.student_council import (
    student_council as data,
)
from education_system.systems.sixth_form.domain.pastoral.student_council.student_council import (
    DEFAULT_MEETING_STATUS,
    DEFAULT_MEETING_TYPE,
    DEFAULT_MEMBER_STATUS,
    DEFAULT_MOTION_OUTCOME,
    DEFAULT_ROLE,
    MEETING_STATUSES,
    MEETING_TYPES,
    MEMBER_STATUSES,
    MOTION_OUTCOMES,
    Meeting,
    Member,
    Motion,
    ROLES,
    ValidationError,
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


def _pick_member() -> Member:
    rows = data.list_members()
    if not rows:
        print("    No members yet.")
        raise _UserAbort
    print("\n  Members:")
    for i, m in enumerate(rows, 1):
        print(f"    {i:>3}) #{m.member_id}  {m.student_id:<12}  "
              f"{m.role[:18]:<18}  "
              f"{m.term_start}..{m.term_end or '—'}  "
              f"[{m.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                            if r.member_id == n), None)
            if match:
                return match
        print("    No matching member.")


def _pick_meeting() -> Meeting:
    rows = data.list_meetings()
    if not rows:
        print("    No meetings yet.")
        raise _UserAbort
    print("\n  Meetings:")
    for i, m in enumerate(rows, 1):
        print(f"    {i:>3}) #{m.meeting_id}  "
              f"{m.meeting_date}  {m.meeting_type[:14]:<14}  "
              f"{m.title[:30]:<30}  [{m.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                            if r.meeting_id == n), None)
            if match:
                return match
        print("    No matching meeting.")


def _pick_motion(meeting_id: int) -> Motion:
    rows = data.list_motions(meeting_id=meeting_id)
    if not rows:
        print("    No motions yet.")
        raise _UserAbort
    print("\n  Motions:")
    for i, m in enumerate(rows, 1):
        print(f"    {i:>3}) M{m.motion_number}  #{m.motion_id}  "
              f"{m.title[:36]:<36}  {m.outcome}  "
              f"({m.votes_for}-{m.votes_against}-"
              f"{m.votes_abstain})")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                            if r.motion_id == n), None)
            if match:
                return match
        print("    No matching motion.")


# ── Members ───────────────────────────────────────────────────

def _print_members(rows: list[Member]) -> None:
    if not rows:
        print("\n  (no members)")
        return
    print()
    print(f"  {'#':>4}  {'Student':<12}  {'Role':<18}  "
          f"{'Term':<22}  {'Status':<12}  Portfolio")
    print("  " + "-" * 110)
    for m in rows:
        print(f"  {m.member_id:>4}  {m.student_id:<12}  "
              f"{m.role[:18]:<18}  "
              f"{m.term_start} → "
              f"{m.term_end or '—':<10}  "
              f"{m.status:<12}  {m.portfolio or '—'}")
    print(f"\n  {len(rows)} member(s).")


def members_list() -> None:
    print("\n═══ All Members ═══")
    _print_members(data.list_members())
    _pause()


def members_active() -> None:
    print("\n═══ Active Members ═══")
    _print_members(data.list_members(active_only=True))
    _pause()


def members_filter() -> None:
    print("\n═══ Filter Members ═══")
    try:
        sid = _input("Student id") or None
        role = _input(f"Role ({'/'.join(ROLES[:3])}…)") or None
        status = _input(
            f"Status ({'/'.join(MEMBER_STATUSES[:3])}…)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_members(student_id=sid, role=role,
                                  status=status)
    _print_members(rows)
    _pause()


def _collect_member_form(
        existing: Member | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        payload["student_id"] = existing.student_id
    else:
        payload["student_id"] = _pick_student()
    payload["role"] = _pick_from(
        "Role", list(ROLES),
        default=(existing.role if is_edit else DEFAULT_ROLE))
    payload["term_start"] = _input(
        "Term start (YYYY-MM-DD)",
        default=(existing.term_start if is_edit
                  else _date.today().isoformat()),
        allow_empty=False)
    payload["term_end"] = _input(
        "Term end (YYYY-MM-DD)",
        default=(existing.term_end or "") if is_edit else "")
    payload["elected_on"] = _input(
        "Elected on (YYYY-MM-DD)",
        default=(existing.elected_on or "") if is_edit else "")
    payload["portfolio"] = _input(
        "Portfolio",
        default=(existing.portfolio or "") if is_edit else "")
    payload["status"] = _pick_from(
        "Status", list(MEMBER_STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_MEMBER_STATUS))
    try:
        payload["notes"] = _multiline(
            "Notes",
            default=(existing.notes or "") if is_edit else "")
    except _UserAbort:
        raise
    return payload


def members_new() -> None:
    print("\n═══ New Member ═══")
    try:
        payload = _collect_member_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        m = data.create_member(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created member #{m.member_id}")
    _pause()


def members_edit() -> None:
    print("\n═══ Edit Member ═══")
    try:
        m = _pick_member()
        payload = _collect_member_form(m)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_member(m.member_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{m.member_id}")
    _pause()


def members_end_term() -> None:
    print("\n═══ End Member Term ═══")
    try:
        m = _pick_member()
        when = _input("Ended on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.end_term(m.member_id, ended_on=when)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{m.member_id} → Term Ended")
    _pause()


def members_set_status() -> None:
    print("\n═══ Change Member Status ═══")
    try:
        m = _pick_member()
        new_status = _pick_from("New status",
                                  list(MEMBER_STATUSES),
                                  default=m.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_member_status(m.member_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{m.member_id} → {new_status}")
    _pause()


def members_delete() -> None:
    print("\n═══ Delete Member ═══")
    try:
        m = _pick_member()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete member #{m.member_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_member(m.member_id):
        print(f"\n  ✓ Deleted #{m.member_id}")
    _pause()


# ── Meetings ───────────────────────────────────────────────────

def _print_meetings(rows: list[Meeting]) -> None:
    if not rows:
        print("\n  (no meetings)")
        return
    print()
    print(f"  {'#':>4}  {'Date':<10} {'Time':<5}  "
          f"{'Type':<14}  {'Title':<30}  "
          f"{'Chair':<14}  Status")
    print("  " + "-" * 110)
    for m in rows:
        print(f"  {m.meeting_id:>4}  "
              f"{m.meeting_date:<10} {(m.meeting_time or '—'):<5}  "
              f"{m.meeting_type[:14]:<14}  "
              f"{m.title[:30]:<30}  "
              f"{(m.chair or '—')[:14]:<14}  {m.status}")
    print(f"\n  {len(rows)} meeting(s).")


def _print_meeting_full(m: Meeting) -> None:
    print()
    print(f"    #{m.meeting_id}  {m.title}")
    print(f"    Date / time  : {m.meeting_date}  "
          f"{m.meeting_time or '—'}")
    print(f"    Type         : {m.meeting_type}")
    print(f"    Location     : {m.location or '—'}")
    print(f"    Chair        : {m.chair or '—'}")
    print(f"    Secretary    : {m.secretary or '—'}")
    print(f"    Status       : {m.status}")
    print(f"    Next meeting : {m.next_meeting_on or '—'}")
    for label, val in (
            ("Attendees",   m.attendees),
            ("Apologies",   m.apologies),
            ("Agenda",      m.agenda),
            ("Minutes",     m.minutes),
            ("Decisions",   m.decisions),
            ("Actions",     m.actions),
            ("Notes",       m.notes),
    ):
        if val:
            print(f"\n    {label}:")
            for line in val.splitlines():
                print(f"      {line}")
    motions = data.list_motions(meeting_id=m.meeting_id)
    if motions:
        print(f"\n    Motions ({len(motions)}):")
        for mo in motions:
            print(f"      M{mo.motion_number}. {mo.title}  "
                  f"[{mo.outcome}]  "
                  f"votes: {mo.votes_for}-"
                  f"{mo.votes_against}-{mo.votes_abstain}")


def meetings_list() -> None:
    print("\n═══ All Meetings ═══")
    _print_meetings(data.list_meetings())
    _pause()


def meetings_upcoming() -> None:
    print("\n═══ Upcoming Meetings ═══")
    _print_meetings(data.list_meetings(upcoming_only=True))
    _pause()


def meetings_filter() -> None:
    print("\n═══ Filter Meetings ═══")
    try:
        mt = _input(
            f"Type ({'/'.join(MEETING_TYPES[:3])}…)") or None
        status = _input(
            f"Status ({'/'.join(MEETING_STATUSES[:3])}…)") or None
        chair = _input("Chair contains") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt2 = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_meetings(
            meeting_type=mt, status=status,
            chair_like=chair, date_from=df, date_to=dt2)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_meetings(rows)
    _pause()


def meetings_view() -> None:
    print("\n═══ View Meeting ═══")
    try:
        m = _pick_meeting()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_meeting_full(m)
    _pause()


def _collect_meeting_form(
        existing: Meeting | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["title"] = _input(
        "Title",
        default=(existing.title if is_edit else ""),
        allow_empty=False)
    payload["meeting_date"] = _input(
        "Date (YYYY-MM-DD)",
        default=(existing.meeting_date if is_edit
                  else _date.today().isoformat()),
        allow_empty=False)
    payload["meeting_time"] = _input(
        "Time (HH:MM)",
        default=(existing.meeting_time if is_edit
                  and existing.meeting_time
                  else _dt.now().strftime("%H:%M")))
    payload["meeting_type"] = _pick_from(
        "Type", list(MEETING_TYPES),
        default=(existing.meeting_type if is_edit
                  else DEFAULT_MEETING_TYPE))
    payload["location"] = _input(
        "Location",
        default=(existing.location or "") if is_edit else "")
    payload["chair"] = _input(
        "Chair",
        default=(existing.chair or "") if is_edit else "")
    payload["secretary"] = _input(
        "Secretary",
        default=(existing.secretary or "") if is_edit else "")
    try:
        payload["attendees"] = _multiline(
            "Attendees",
            default=(existing.attendees or "")
            if is_edit else "")
        payload["apologies"] = _multiline(
            "Apologies",
            default=(existing.apologies or "")
            if is_edit else "")
        payload["agenda"] = _multiline(
            "Agenda",
            default=(existing.agenda or "") if is_edit else "")
        payload["minutes"] = _multiline(
            "Minutes",
            default=(existing.minutes or "")
            if is_edit else "")
        payload["decisions"] = _multiline(
            "Decisions",
            default=(existing.decisions or "")
            if is_edit else "")
        payload["actions"] = _multiline(
            "Actions",
            default=(existing.actions or "") if is_edit else "")
    except _UserAbort:
        raise
    payload["next_meeting_on"] = _input(
        "Next meeting on (YYYY-MM-DD)",
        default=(existing.next_meeting_on or "")
        if is_edit else "")
    payload["status"] = _pick_from(
        "Status", list(MEETING_STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_MEETING_STATUS))
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def meetings_new() -> None:
    print("\n═══ New Meeting ═══")
    try:
        payload = _collect_meeting_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        m = data.create_meeting(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created meeting #{m.meeting_id}")
    _pause()


def meetings_edit() -> None:
    print("\n═══ Edit Meeting ═══")
    try:
        m = _pick_meeting()
        payload = _collect_meeting_form(m)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_meeting(m.meeting_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{m.meeting_id}")
    _pause()


def meetings_confirm() -> None:
    print("\n═══ Confirm Meeting ═══")
    try:
        m = _pick_meeting()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.confirm_meeting(m.meeting_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{m.meeting_id} → Confirmed")
    _pause()


def meetings_complete() -> None:
    print("\n═══ Complete Meeting ═══")
    try:
        m = _pick_meeting()
        minutes = _multiline("Minutes",
                                default=m.minutes or "")
        decisions = _multiline("Decisions",
                                  default=m.decisions or "")
        actions = _multiline("Actions",
                                default=m.actions or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.complete_meeting(m.meeting_id,
                                  minutes=minutes or None,
                                  decisions=decisions or None,
                                  actions=actions or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{m.meeting_id} → Completed")
    _pause()


def meetings_cancel() -> None:
    print("\n═══ Cancel Meeting ═══")
    try:
        m = _pick_meeting()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.cancel_meeting(m.meeting_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{m.meeting_id} → Cancelled")
    _pause()


def meetings_delete() -> None:
    print("\n═══ Delete Meeting ═══")
    try:
        m = _pick_meeting()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete meeting #{m.meeting_id} "
              "and all its motions? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_meeting(m.meeting_id):
        print(f"\n  ✓ Deleted #{m.meeting_id}")
    _pause()


# ── Motions ────────────────────────────────────────────────

def motions_add() -> None:
    print("\n═══ Add Motion ═══")
    try:
        meeting = _pick_meeting()
        title = _input("Title", allow_empty=False)
        proposer = _input("Proposer")
        seconder = _input("Seconder")
        description = _multiline("Description")
        outcome = _pick_from("Outcome", list(MOTION_OUTCOMES),
                                default=DEFAULT_MOTION_OUTCOME)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        mo = data.add_motion(meeting.meeting_id, {
            "title": title,
            "proposer": proposer or None,
            "seconder": seconder or None,
            "description": description or None,
            "outcome": outcome,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Motion M{mo.motion_number} #{mo.motion_id}")
    _pause()


def motions_record_vote() -> None:
    print("\n═══ Record Vote ═══")
    try:
        meeting = _pick_meeting()
        mo = _pick_motion(meeting.meeting_id)
        f = _input("Votes for", allow_empty=False)
        a = _input("Votes against", allow_empty=False)
        ab = _input("Votes abstain", default="0")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.record_vote(mo.motion_id,
                            votes_for=int(f),
                            votes_against=int(a),
                            votes_abstain=int(ab))
    except (ValueError, ValidationError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    new_mo = data.get_motion(mo.motion_id)
    print(f"\n  ✓ Outcome: {new_mo.outcome}")
    _pause()


def motions_edit() -> None:
    print("\n═══ Edit Motion ═══")
    try:
        meeting = _pick_meeting()
        mo = _pick_motion(meeting.meeting_id)
        title = _input("Title", default=mo.title,
                          allow_empty=False)
        proposer = _input("Proposer",
                              default=mo.proposer or "")
        seconder = _input("Seconder",
                              default=mo.seconder or "")
        description = _multiline("Description",
                                      default=mo.description or "")
        outcome = _pick_from("Outcome",
                                  list(MOTION_OUTCOMES),
                                  default=mo.outcome)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_motion(mo.motion_id, {
            "title": title,
            "proposer": proposer or None,
            "seconder": seconder or None,
            "description": description or None,
            "votes_for": mo.votes_for,
            "votes_against": mo.votes_against,
            "votes_abstain": mo.votes_abstain,
            "outcome": outcome,
            "decided_on": mo.decided_on,
            "notes": mo.notes,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{mo.motion_id}")
    _pause()


def motions_delete() -> None:
    print("\n═══ Delete Motion ═══")
    try:
        meeting = _pick_meeting()
        mo = _pick_motion(meeting.meeting_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete motion #{mo.motion_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_motion(mo.motion_id):
        print(f"\n  ✓ Deleted #{mo.motion_id}")
    _pause()


def motions_list() -> None:
    print("\n═══ List Motions ═══")
    try:
        meeting = _pick_meeting()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_motions(meeting_id=meeting.meeting_id)
    if not rows:
        print("\n  (no motions)")
    for mo in rows:
        print(f"  M{mo.motion_number}  #{mo.motion_id}  "
              f"{mo.title}")
        print(f"     proposer: {mo.proposer or '—'}  "
              f"seconder: {mo.seconder or '—'}")
        print(f"     votes: {mo.votes_for}-"
              f"{mo.votes_against}-{mo.votes_abstain}  "
              f"outcome: {mo.outcome}")
    _pause()


# ── Summary ───────────────────────────────────────────────

def summary_flow() -> None:
    print("\n═══ Student Council Summary ═══")
    s = data.summary()
    print(f"\n  Total members        : {s.total_members}")
    print(f"  Active members       : {s.active_members}")
    print(f"  Total meetings       : {s.total_meetings}")
    print(f"  Completed meetings   : {s.completed_meetings}")
    print(f"  Total motions        : {s.total_motions}")
    print(f"  Motions passed       : {s.motions_passed}")
    print(f"  Motions failed       : {s.motions_failed}")
    print(f"  Motions pending      : {s.motions_pending}")
    print("\n  By role:")
    for k in ROLES:
        n = s.by_role.get(k, 0)
        if n:
            print(f"    {k:<18}: {n}")
    print("\n  By meeting type:")
    for k in MEETING_TYPES:
        n = s.by_meeting_type.get(k, 0)
        if n:
            print(f"    {k:<18}: {n}")
    print("\n  By motion outcome:")
    for k in MOTION_OUTCOMES:
        n = s.by_outcome.get(k, 0)
        if n:
            print(f"    {k:<12}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("── Members ──",     lambda: None),
    ("List all",          members_list),
    ("List active",       members_active),
    ("Filter",            members_filter),
    ("New member",        members_new),
    ("Edit member",       members_edit),
    ("End term",          members_end_term),
    ("Change status",     members_set_status),
    ("Delete member",     members_delete),
    ("── Meetings ──",    lambda: None),
    ("List all",          meetings_list),
    ("Upcoming",          meetings_upcoming),
    ("Filter",            meetings_filter),
    ("View",              meetings_view),
    ("New meeting",       meetings_new),
    ("Edit meeting",      meetings_edit),
    ("Confirm",           meetings_confirm),
    ("Complete",          meetings_complete),
    ("Cancel",            meetings_cancel),
    ("Delete meeting",    meetings_delete),
    ("── Motions ──",     lambda: None),
    ("List motions",      motions_list),
    ("Add motion",        motions_add),
    ("Record vote",       motions_record_vote),
    ("Edit motion",       motions_edit),
    ("Delete motion",     motions_delete),
    ("──",                lambda: None),
    ("Summary",           summary_flow),
]


def run() -> None:
    while True:
        print("\n── Student Council ──")
        for i, (label, _) in enumerate(_MENU, 1):
            if label.startswith("─"):
                print(f"      {label}")
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
            logger.exception("Student Council CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Student Council":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Student Council CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
