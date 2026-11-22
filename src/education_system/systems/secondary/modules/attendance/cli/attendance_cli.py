"""Registers & Attendance in the terminal. The old options 1-8 are kept in their
places (take register, single mark, pupil history, daily summary, pupil
summary, list a date, delete a record, codes); 9-15 are added. Rules live in
:mod:`modules.attendance.domain.attendance`."""

from __future__ import annotations

import datetime as _dt

from education_system.systems.secondary.modules.attendance.domain import attendance as AT
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import ATTENDANCE_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_problem = prompts.problem


def _ask_date(label: str = "Date") -> _dt.date | None:
    today = _dt.date.today().isoformat()
    raw = _prompt(f"  {label} (YYYY-MM-DD) [{today}]: ") or today
    try:
        return _dt.date.fromisoformat(raw)
    except ValueError:
        print("  Not a date.")
        return None


def _ask_session() -> str | None:
    default = "AM" if _dt.datetime.now().hour < 12 else "PM"
    s = (_prompt(f"  Session (AM/PM) [{default}]: ") or default).upper()
    if s not in AT.SESSIONS:
        print("  Session must be AM or PM.")
        return None
    return s


def _ask_pupil() -> P.Pupil | None:
    ref = _prompt("  Pupil admission no. / UPN: ")
    p = P.find_by_reference(ref) if ref else None
    if p is None and ref:
        print("  No such pupil.")
    return p


def _print_codes(principal: Principal | None = None) -> None:
    office = principal is None or principal.role in ATTENDANCE_EDITORS
    print("  Mark codes:" + ("" if office else "  (you can enter / L N; the office adds "
                                               "reasons)"))
    for code, (label, cat) in AT.CODES.items():
        print(f"   {code:<3} {label:<52} [{AT.CATEGORY_LABELS[cat].split(' (')[0]}]")


def menu(principal: Principal) -> None:
    office = principal.role in ATTENDANCE_EDITORS
    while True:
        activity_log.record("attendance.view")
        print("\n── Registers & Attendance ──")
        print("   1) Take register (bulk for a date/session)\n   2) Record a single mark"
              "\n   3) View pupil history\n   4) View daily summary\n   5) View pupil summary"
              "\n   6) List records for a date\n   7) Delete a record\n   8) Mark codes "
              "reference\n   9) Lesson registers\n  10) Register status & missing from lessons"
              "\n  11) Calling list (absent, no reason yet)\n  12) Late arrival"
              "\n  13) Absence over several days\n  14) Persistent absence report"
              "\n  15) Session times\n   0) Back")
        c = _prompt("Select: ")
        if c in {"0", ""}:
            return
        if c in {"7", "13"} and not office:
            print("  Only the attendance office can do this.")
            continue
        try:
            {"1": lambda: _take_register(principal), "2": lambda: _single_mark(principal),
             "3": lambda: _pupil_history(principal), "4": _daily_summary,
             "5": _pupil_summary, "6": _list_date, "7": lambda: _delete(principal),
             "8": lambda: (_print_codes(principal), _pause()),
             "9": lambda: _lessons(principal), "10": _status,
             "11": lambda: _calling(principal), "12": lambda: _late(principal),
             "13": lambda: _range(principal), "14": _persistent,
             "15": lambda: _times(principal, office),
             }.get(c, lambda: print("  Invalid selection."))()
        except (AT.ValidationError, AT.PermissionDenied, AT.NotFound) as e:
            _problem(e)


def _take_register(principal: Principal) -> None:
    d = _ask_date()
    s = _ask_session() if d else None
    if not s:
        return
    ok, what = AT.school_day(d)
    if not ok:
        print(f"  {d:%A %d %B %Y}: {what} - no register is taken.")
        return
    y = _prompt("  Year (7-11, Enter = all): ")
    form = _prompt("  Form (Enter = all): ") or None
    year = int(y) if y.isdigit() and int(y) in P.YEAR_GROUPS else None
    rows = AT.register(d, s, year_group=year, form=form)
    if not rows:
        print("  No pupils on roll for that register.")
        return
    print(f"\n  {d:%a %d %b %Y} {s} - {len(rows)} pupil(s). For each pupil type a code "
          f"(Enter = present, '=' keeps the current mark, 'q' stops and saves).")
    present = "/" if s == "AM" else "\\"
    marks: dict[int, str] = {}
    for r in rows:
        cur = r.mark.code if r.mark else None
        raw = _prompt(f"  {r.pupil.admission_no} {r.pupil.display_name[:28]:<28} "
                      f"{r.pupil.form_group or '':<5} [{cur or present}]: ")
        if raw.lower() == "q":
            break
        if raw == "=" or (not raw and cur):
            continue
        marks[r.pupil.pupil_id] = raw or present
    if not marks:
        print("  No marks entered.")
        return
    saved, notes = AT.save_register(d, s, marks, actor=principal, year_group=year, form=form)
    print(f"  Saved {saved} mark(s).")
    for n in notes:
        print(f"  ✗ {n}")
    _pause()


def _single_mark(principal: Principal) -> None:
    p = _ask_pupil()
    d = _ask_date() if p else None
    s = _ask_session() if d else None
    if not s:
        return
    cur = AT.get_for(p.pupil_id, d, s)
    if cur:
        print(f"  Current: {cur.code} {cur.label}")
    code = _prompt("  Mark code (8 in the menu lists them): ")
    if not code:
        return
    mins = _prompt("  Minutes late (Enter = none): ")
    notes = _prompt("  Notes: ")
    m = AT.record_mark(p.pupil_id, d, s, code, actor=principal, notes=notes,
                       minutes_late=mins or None)
    print(f"  ✓ Saved: {p.admission_no} {m.date}/{m.session} {m.code} ({m.label})")


def _pupil_history(principal: Principal) -> None:
    p = _ask_pupil()
    if not p:
        return
    rows = AT.pupil_history(p.pupil_id)
    print(f"\n  {len(rows)} record(s) for {p.display_name} ({p.admission_no}):")
    if rows:
        print(f"  {'ID':<6} {'Date':<11} {'Sess':<4} {'Code':<4} {'Status':<44} Notes")
        for m in rows[:60]:
            print(f"  {m.mark_id:<6} {m.date:<11} {m.session:<4} {m.code:<4} "
                  f"{m.label[:44]:<44} {m.notes or ''}")
        if len(rows) > 60:
            print(f"  … {len(rows) - 60} older")
    if _yes("  Show changes made to marks?"):
        for h in AT.history(p.pupil_id):
            if h["action"] in ("mark", "change", "delete"):
                print(f"  {h['at']}  {h['actor']}: {h['date']} {h['session']} "
                      f"{h['old'] or '-'} -> {h['new'] or '(removed)'}")
    _pause()


def _daily_summary() -> None:
    d = _ask_date()
    if not d:
        return
    print(f"\n  ── Daily summary: {d:%A %d %B %Y} - {AT.school_day(d)[1]} ──")
    for s, v in AT.daily_summary(d).items():
        print(f"\n  {s}: on roll {v['on_roll']}  marked {v['marked']}  unmarked "
              f"{v['unmarked']}  present {v['present']}  off-site {v['aea']}  authorised "
              f"{v['authorised']}  unauthorised {v['unauthorised']}")
        for code, n in sorted(v["codes"].items()):
            print(f"     {code:<3} {AT.code_label(code):<52} {n}")
    _pause()


def _pupil_summary() -> None:
    p = _ask_pupil()
    if not p:
        return
    start = _prompt(f"  From [{P.academic_year_start().isoformat()}]: ") or None
    end = _prompt("  To [today]: ") or None
    s = AT.pupil_summary(p.pupil_id, start, end)
    les = AT.lesson_summary(p.pupil_id, start, end)
    print(f"\n  ── Pupil summary: {p.display_name} ({p.admission_no}) ──")
    for label, v in (("Possible sessions", s.possible), ("Attended", s.attended),
                     ("  of which off-site education", s.aea),
                     ("Authorised absent", s.authorised), ("Unauthorised absent", s.unauthorised),
                     ("Late", s.late), ("Not counted", s.not_counted),
                     ("Unmarked school sessions", s.unmarked),
                     ("Attendance %", "-" if s.attendance_pct is None else s.attendance_pct),
                     ("Band", s.band.title() or "-")):
        print(f"  {label:<30} {v}")
    print(f"  Lessons: present {les['P']} · late {les['L']} · absent {les['A']} · "
          f"away {les['X']}")
    _pause()


def _list_date() -> None:
    d = _ask_date()
    if not d:
        return
    s = _prompt("  Session (AM/PM, Enter = both): ").upper() or None
    rows = AT.list_for_date(d, s)
    print(f"\n  {len(rows)} record(s) on {d.isoformat()}" + (f" {s}" if s else ""))
    if rows:
        print(f"  {'ID':<6} {'Pupil':<11} {'Sess':<4} {'Code':<4} Status")
        names = {}
        for m in rows:
            if m.pupil_id not in names:
                p = P.get_pupil(m.pupil_id)
                names[m.pupil_id] = p.admission_no if p else f"#{m.pupil_id}"
            print(f"  {m.mark_id:<6} {names[m.pupil_id]:<11} {m.session:<4} {m.code:<4} "
                  f"{m.label}")
    _pause()


def _delete(principal: Principal) -> None:
    raw = _prompt("  Record ID: ")
    if not raw.isdigit():
        print("  Record ID must be a number.")
        return
    m = AT.get(int(raw))
    print(f"  {m.date} {m.session} {m.code} ({m.label})")
    reason = _prompt("  Reason for removing it (kept in the audit): ")
    if not _yes("  Remove this mark?"):
        print("  Cancelled.")
        return
    AT.delete_mark(m.mark_id, actor=principal, reason=reason)
    print("  ✓ Removed.")


def _lessons(principal: Principal) -> None:
    d = _ask_date()
    if not d:
        return
    mine = _yes("  Only my lessons?")
    due, what = AT.lessons_due(d, teacher=principal.username if mine else None)
    print(f"\n  {d:%A %d %B %Y} - {what}")
    if not due:
        print("  No lessons.")
        _pause()
        return
    for i, (x, taken) in enumerate(due, 1):
        print(f"  {i:>2}) {x.slot_label.split()[-1]:<5} {x.subject_code:<8} {x.group_code:<12} "
              f"{(x.teacher or '')[:18]:<18} {'taken' if taken else 'NOT TAKEN'}")
    raw = _prompt("  Take which register (number, Enter = none): ")
    if not raw.isdigit() or not 1 <= int(raw) <= len(due):
        return
    x = due[int(raw) - 1][0]
    reg = AT.lesson_register(x.lesson_id, d)
    print(f"\n  {x.subject_name} {x.group_code} ({reg.session}). P present, L late, A absent, "
          "X away. Enter keeps the suggestion.")
    marks = {}
    for r in reg.rows:
        hint = f" (session: {r.session_code})" if r.session_code else ""
        raw = _prompt(f"  {r.pupil.admission_no} {r.pupil.display_name[:26]:<26}{hint} "
                      f"[{r.suggested}]: ").upper()
        marks[r.pupil.pupil_id] = raw or r.suggested
    n = AT.save_lesson_register(x.lesson_id, d, marks, actor=principal)
    print(f"  ✓ Saved {n} mark(s).")


def _status() -> None:
    d = _ask_date()
    s = _ask_session() if d else None
    if not s:
        return
    print(f"\n  {d:%A %d %B %Y} {s} - {AT.school_day(d)[1]}")
    print(f"  {'Year':<5} {'Form':<8} {'On roll':>7} {'Marked':>7}  Taken by")
    for r in AT.register_status(d, s):
        flag = "" if r.complete or not r.on_roll else "  ← incomplete"
        print(f"  {r.year_group:<5} {r.form_group or '(none)':<8} {r.on_roll:>7} {r.marked:>7}"
              f"  {r.taken_by or '-'}{flag}")
    miss = AT.missing_from_lessons(d)
    print(f"\n  Missing from lessons: {len(miss)}")
    for p, x, code in miss:
        print(f"  {p.admission_no} {p.display_name:<26} {x.slot_label} {x.group_code} "
              f"(session mark {code})")
    _pause()


def _calling(principal: Principal) -> None:
    d = _ask_date()
    s = _ask_session() if d else None
    if not s:
        return
    rows = AT.calling_list(d, s)
    print(f"\n  {len(rows)} pupil(s) absent with no reason yet")
    for p, _m, contacts in rows:
        print(f"  {p.admission_no} {p.display_name} (Y{p.year_group} {p.form_group or ''})")
        for c in contacts[:3]:
            print(f"      {c.priority}. {c.full_name} ({c.relationship}) {c.phone or 'no phone'}")
        if not contacts:
            print("      No contacts recorded")
    if rows and principal.role in ATTENDANCE_EDITORS and _yes("  Record reasons now?"):
        for p, m, _c in rows:
            code = _prompt(f"  {p.admission_no} {p.display_name} reason code (Enter = skip): ")
            if code:
                try:
                    AT.record_mark(p.pupil_id, d, s, code, actor=principal,
                                   notes=_prompt("    Notes: "))
                except AT.ValidationError as e:
                    _problem(e)
    _pause()


def _late(principal: Principal) -> None:
    p = _ask_pupil()
    d = _ask_date() if p else None
    s = _ask_session() if d else None
    if not s:
        return
    t = AT.session_times()
    now = _dt.datetime.now().strftime("%H:%M")
    arrived = _prompt(f"  Arrived (HH:MM) [{now}] (register closes "
                      f"{t['am_close'] if s == 'AM' else t['pm_close']}): ") or now
    m = AT.record_late(p.pupil_id, d, s, arrived, actor=principal,
                       notes=_prompt("  Reason: "))
    print(f"  ✓ {m.code} ({m.label}), {m.minutes_late} min late.")


def _range(principal: Principal) -> None:
    p = _ask_pupil()
    if not p:
        return
    start = _ask_date("From")
    end = _ask_date("To") if start else None
    if not end:
        return
    code = _prompt("  Code (e.g. I illness, C leave, S study leave): ")
    which = (_prompt("  Sessions (AM/PM/both) [both]: ") or "both").upper()
    sessions = AT.SESSIONS if which == "BOTH" else (which,)
    overwrite = _yes("  Replace existing marks too (not just N / unmarked)?")
    saved, skipped = AT.record_range(p.pupil_id, start, end, code, actor=principal,
                                     sessions=sessions, notes=_prompt("  Notes: "),
                                     overwrite=overwrite)
    print(f"  ✓ Recorded {saved} session(s); {skipped} left as they were.")


def _persistent() -> None:
    y = _prompt("  Year (7-11, Enter = all): ")
    rows = AT.persistent_absentees(year_group=int(y) if y.isdigit() else None)
    print(f"\n  {len(rows)} pupil(s) missing 10% or more this year")
    for p, s in rows:
        print(f"  {p.admission_no:<11} {p.display_name[:26]:<26} Y{p.year_group} "
              f"{p.form_group or '':<5} {s.attendance_pct:>5}%  auth {s.authorised:<3} "
              f"unauth {s.unauthorised:<3} {s.band}")
    _pause()


def _times(principal: Principal, office: bool) -> None:
    t = AT.session_times()
    for k, v in t.items():
        print(f"  {k.replace('_', ' '):<10} {v}")
    if office and _yes("  Change them?"):
        new = {k: _prompt(f"   {k.replace('_', ' ')} [{v}]: ") or v for k, v in t.items()}
        AT.set_session_times(new, actor=principal)
        print("  ✓ Saved.")
    else:
        _pause()
