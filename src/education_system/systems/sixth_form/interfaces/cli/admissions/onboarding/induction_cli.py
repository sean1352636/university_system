"""CLI: induction sessions — list / create / edit / cancel, booking (one
or more learners, or the whole cohort) and taking the register (Present
ticks the session's onboarding task)."""

from __future__ import annotations

import datetime as _dt
from typing import Any

from education_system.systems.sixth_form.domain.admissions.onboarding import (
    induction as ind,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as data,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    templates as tpl,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.onboarding.onboarding_cli import (
    _REFUSED,
    _ask_text,
    _input,
    _pause,
    _pick_from,
    _pick_student,
    _refused,
    _UserAbort,
    _writer,
    _yes_no,
)

_NONE = "(none)"
_MARK_KEYS = {"p": "Present", "a": "Absent", "e": "Excused"}


# ── Showing / picking ─────────────────────────────────────────────

def _print_sessions(rows: list[ind.Session]) -> None:
    if not rows:
        print("\n  (no sessions)")
        return
    print(f"\n  {'#':>3}  {'Id':>4}  {'Date':<10}  {'Time':<11}  "
          f"{'Room':<10}  {'Yr':<3}  {'Booked':>7}  {'Here':>4}  "
          f"{'Status':<9}  Title / task")
    print("  " + "-" * 104)
    for n, s in enumerate(rows, 1):
        cap = f"{s.booked}/{s.capacity}" if s.capacity else str(s.booked)
        time = s.start_time + (f"-{s.end_time}" if s.end_time else "")
        task = f"  → {s.task_key}" if s.task_key else ""
        print(f"  {n:>3}  {s.session_id:>4}  {s.session_date:<10}  "
              f"{time:<11}  {(s.room or '—')[:10]:<10}  "
              f"{str(s.year_group or 'all'):<3}  {cap:>7}  {s.present:>4}  "
              f"{s.status:<9}  {s.title}{task}")


def _pick_session(*, include_cancelled: bool = False,
                  only: Any = None) -> ind.Session:
    rows = ind.list_sessions(include_cancelled=include_cancelled)
    if only is not None:
        rows = [s for s in rows if only(s)]
    if not rows:
        print("    No matching sessions.")
        raise _UserAbort
    _print_sessions(rows)
    while True:
        raw = _input(f"Pick 1..{len(rows)} (or #id)", allow_empty=False)
        if raw.startswith("#") and raw[1:].isdigit():
            hit = next((s for s in rows if s.session_id == int(raw[1:])),
                       None)
            if hit:
                return hit
        elif raw.isdigit() and 1 <= int(raw) <= len(rows):
            return rows[int(raw) - 1]
        print("    No matching session.")


def _print_register(s: ind.Session) -> list[ind.Attendance]:
    rows = ind.register(s.session_id)
    print(f"\n  {s.title} — {s.session_date} {s.start_time}"
          + (f" ({s.room})" if s.room else "")
          + (f"  [CANCELLED: {s.status_reason}]" if s.is_cancelled else ""))
    if s.task_key:
        print(f"  Present ticks: {s.task_key}")
    if not rows:
        print("    (nobody booked)")
    for n, a in enumerate(rows, 1):
        by = f"  marked by {a.marked_by}" if a.marked_by else ""
        note = f"  — {a.note}" if a.note else ""
        print(f"    {n:>3}) {a.student_id:<10} {a.student_name[:24]:<24} "
              f"{a.status:<8}{by}{note}")
    left = s.places_left
    print(f"  {s.booked} booked" + (f", {left} place(s) left"
                                    if left is not None else ""))
    return rows


def _task_keys() -> list[str]:
    keys: set[str] = set()
    for t in tpl.list_templates():
        keys.update(i.key for i in t.items)
    return sorted(k for k in keys
                  if k not in data.ID_ITEMS and k not in data.CONSENT_ITEMS)


def _ask_session(cur: ind.Session | None = None) -> dict[str, Any]:
    g = (lambda k: getattr(cur, k) if cur else None)
    p: dict[str, Any] = {}
    p["title"] = _input("Title", default=g("title") or "",
                        allow_empty=False)
    p["session_date"] = _input("Date (YYYY-MM-DD)",
                               default=g("session_date") or "",
                               allow_empty=False)
    p["start_time"] = _input("Start time (HH:MM)",
                             default=g("start_time") or "",
                             allow_empty=False)
    p["end_time"] = _input("End time (HH:MM, optional)",
                           default=g("end_time") or "") or None
    p["room"] = _input("Room", default=g("room") or "") or None
    p["capacity"] = _input("Capacity (blank = no limit)",
                           default=str(g("capacity") or "")) or None
    yg = _pick_from("For year group", ["All", "12", "13"],
                    default=str(g("year_group") or "All"))
    p["year_group"] = None if yg == "All" else int(yg)
    if cur is None:
        year = _input("Academic year (blank = from the date)")
        if year:
            p["academic_year"] = year
    else:
        p["academic_year"] = _input("Academic year",
                                    default=cur.academic_year or "") or None
    keys = [_NONE, *_task_keys()]
    cur_key = g("task_key")
    if cur_key and cur_key not in keys:
        keys.append(cur_key)
    key = _pick_from("Onboarding task attending it satisfies", keys,
                     default=cur_key or _NONE)
    p["task_key"] = None if key == _NONE else key
    p["notes"] = _input("Notes", default=g("notes") or "") or None
    return p


# ── Flows ─────────────────────────────────────────────────────────

def list_flow() -> None:
    print("\n═══ Induction Sessions ═══")
    upcoming = _yes_no("Upcoming only?", default=False)
    cancelled = _yes_no("Include cancelled?", default=False)
    _print_sessions(ind.list_sessions(upcoming_only=upcoming,
                                      include_cancelled=cancelled))
    _pause()


def view_flow() -> None:
    print("\n═══ Session Register ═══")
    s = _pick_session(include_cancelled=True)
    _print_register(s)
    if s.notes:
        print(f"  Notes: {s.notes}")
    _pause()


def create_flow() -> None:
    print("\n═══ New Induction Session ═══")
    if not _writer():
        return
    p = _ask_session()
    try:
        s = ind.create_session(p)
    except _REFUSED as e:
        return _refused(e)
    print(f"\n  ✓ Session #{s.session_id} '{s.title}' on {s.session_date} "
          f"({s.academic_year})")
    _pause()


def edit_flow() -> None:
    print("\n═══ Edit Induction Session ═══")
    if not _writer():
        return
    s = _pick_session()
    p = _ask_session(s)
    try:
        out = ind.update_session(s.session_id, p)
    except _REFUSED as e:
        return _refused(e)
    print(f"\n  ✓ Updated session #{out.session_id}")
    _pause()


def cancel_flow() -> None:
    print("\n═══ Cancel Induction Session ═══")
    if not _writer():
        return
    s = _pick_session()
    reason = _ask_text(f"Why is '{s.title}' cancelled?")
    if not _yes_no(f"Cancel session #{s.session_id}?", default=False):
        raise _UserAbort
    try:
        ind.cancel_session(s.session_id, reason=reason)
    except _REFUSED as e:
        return _refused(e)
    print(f"\n  ✓ Session #{s.session_id} cancelled (kept with its "
          "register)")
    _pause()


def _ask_students() -> list[str]:
    rows = student_data.list_students()
    if not rows:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for n, st in enumerate(rows, 1):
        print(f"    {n:>3}) {st.student_id}  {st.full_name}")
    by_id = {st.student_id.lower(): st.student_id for st in rows}
    while True:
        raw = _input("Learners (positions or student IDs, comma separated)",
                     allow_empty=False)
        out: list[str] = []
        bad = []
        for tok in (t.strip() for t in raw.split(",")):
            if not tok:
                continue
            if tok.isdigit() and 1 <= int(tok) <= len(rows):
                out.append(rows[int(tok) - 1].student_id)
            elif tok.lower() in by_id:
                out.append(by_id[tok.lower()])
            else:
                bad.append(tok)
        if bad:
            print(f"    Not found: {', '.join(bad)}")
            continue
        if out:
            return list(dict.fromkeys(out))


def _show_booking(res: ind.BookingResult) -> None:
    print()
    lines = res.lines()
    print(f"  ✓ {lines[0]}")
    for ln in lines[1:]:
        print(f"  · skipped {ln}")
    _pause()


def book_flow() -> None:
    print("\n═══ Book Learners on a Session ═══")
    if not _writer():
        return
    s = _pick_session(only=lambda x: not x.is_cancelled)
    ids = _ask_students()
    try:
        res = ind.book(s.session_id, ids)
    except _REFUSED as e:
        return _refused(e)
    _show_booking(res)


def book_cohort_flow() -> None:
    print("\n═══ Book the Cohort on a Session ═══")
    if not _writer():
        return
    s = _pick_session(only=lambda x: not x.is_cancelled)
    who = (f"Year {s.year_group}" if s.year_group else "every year group")
    if not _yes_no(f"Book every learner enrolled in {s.academic_year} "
                   f"({who}) who is not booked yet?", default=True):
        raise _UserAbort
    try:
        res = ind.book_cohort(s.session_id)
    except _REFUSED as e:
        return _refused(e)
    _show_booking(res)


def unbook_flow() -> None:
    print("\n═══ Remove a Booking ═══")
    if not _writer():
        return
    s = _pick_session()
    rows = [a for a in _print_register(s) if a.status == ind.BOOKED]
    if not rows:
        print("    Nobody is waiting to be marked.")
        raise _UserAbort
    raw = _input("Student ID to take off", allow_empty=False)
    sid = next((a.student_id for a in rows
                if a.student_id.lower() == raw.lower()), raw)
    try:
        ok = ind.unbook(s.session_id, sid)
    except _REFUSED as e:
        return _refused(e)
    print(f"\n  ✓ {sid} taken off" if ok else f"\n  {sid} was not booked.")
    _pause()


def register_flow() -> None:
    print("\n═══ Take the Register ═══")
    if not _writer():
        return
    s = _pick_session(only=lambda x: not x.is_cancelled
                      and x.session_date <= _dt.date.today().isoformat())
    rows = _print_register(s)
    if not rows:
        raise _UserAbort
    print("\n  For each learner: p = Present, a = Absent, e = Excused, "
          "blank = leave as is.")
    marks: dict[str, str] = {}
    for a in rows:
        while True:
            raw = _input(f"{a.student_id} {a.student_name[:20]} "
                         f"[{a.status}]").lower()
            if not raw:
                break
            if raw in _MARK_KEYS:
                if _MARK_KEYS[raw] != a.status:
                    marks[a.student_id] = _MARK_KEYS[raw]
                break
            print("    p, a, e or blank.")
    if not marks:
        print("\n  No marks changed.")
        return _pause()
    note = _input("Note for these marks (optional)") or None
    try:
        res = ind.mark_register(s.session_id, marks, note=note)
    except _REFUSED as e:
        return _refused(e)
    print()
    for ln in res.lines():
        print(f"  {ln}")
    _pause()


def learner_flow() -> None:
    print("\n═══ A Learner's Induction Sessions ═══")
    sid = _pick_student()
    rows = ind.learner_sessions(sid)
    if not rows:
        print("\n    Not booked on any session.")
    for s, a in rows:
        print(f"    {s.session_date} {s.start_time}  {s.title:<30} "
              f"{a.status:<8}" + ("  (session cancelled)"
                                  if s.is_cancelled else ""))
    _pause()


_MENU = [
    ("List sessions", list_flow),
    ("View a session's register", view_flow),
    ("New session", create_flow),
    ("Edit session", edit_flow),
    ("Cancel session", cancel_flow),
    ("Book learner(s)", book_flow),
    ("Book the cohort", book_cohort_flow),
    ("Remove a booking", unbook_flow),
    ("Take the register", register_flow),
    ("A learner's sessions", learner_flow),
]


def run() -> None:
    while True:
        print("\n── Induction Sessions ──")
        for n, (label, _) in enumerate(_MENU, 1):
            print(f"  {n:>2}) {label}")
        print("   0) Back")
        try:
            raw = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if raw == "0":
            return
        if not raw.isdigit() or not 1 <= int(raw) <= len(_MENU):
            print("  Invalid selection.")
            continue
        try:
            _MENU[int(raw) - 1][1]()
        except _UserAbort:
            print("\n  Cancelled.")
        except _REFUSED as e:
            _refused(e)
