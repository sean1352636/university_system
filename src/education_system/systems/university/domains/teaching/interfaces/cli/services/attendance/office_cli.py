"""CLI: the attendance office — registers, self-certification, UKVI,
non-engagement cases and funding confirmations. Same rules as the GUI's
Attendance Office window (``university/application``)."""
from contextlib import closing

from education_system.systems.university.application.attendance import engagement as eng
from education_system.systems.university.application.attendance import registers as reg
from education_system.systems.university.infrastructure.database.db import get_connection


def _run(action, done=None):
    try:
        with closing(get_connection()) as conn:
            result = action(conn)
            conn.commit()
    except ValueError as e:
        print(f"Refused: {e}")
        return None
    if done:
        print(done(result) if callable(done) else done)
    return result if result is not None else True


def _window():
    with closing(get_connection()) as conn:
        start, end = reg.default_window(conn)
    s = input(f"From [{start}]: ").strip() or start.isoformat()
    e = input(f"To [{end}]: ").strip() or end.isoformat()
    return s, e


def registers_menu():
    print("1. Registers not taken  2. A student's attendance  0. Back")
    choice = input("Choice: ").strip()
    if choice not in ('1', '2'):
        return
    start, end = _window()
    with closing(get_connection()) as conn:
        if choice == '1':
            missing = reg.register_compliance(conn, start, end)
            print(f"\n{len(missing)} timetabled session(s) with no register:")
            for s in missing[:60]:
                print(f"  {s['date']} {s['start_time']}-{s['end_time']} {s['module_code']:<12} {s['instructor'] or ''}")
            return
        sid = input("Student ID: ").strip()
        s = reg.student_summary(conn, sid, start, end)
    print(f"\n{sid}: {s['expected']} expected; present {s['present']}, late {s['late']}, excused {s['excused']}, "
          f"absent {s['absent']}, no register {s['no_register']}")
    print(f"Attendance {s['attendance_pct'] if s['attendance_pct'] is not None else '—'}%   "
          f"register coverage {s['coverage_pct'] if s['coverage_pct'] is not None else '—'}%   "
          f"consecutive unexcused absences {s['consecutive_missed']}")


def self_cert_menu(default_student=None):
    sid = default_student or input("Student ID: ").strip()
    start = input("First day ill (YYYY-MM-DD): ").strip()
    end = input(f"Last day ill [{start}]: ").strip() or start
    reason = input("Illness: ").strip()
    _run(lambda c: eng.self_certify(c, sid, start, end, reason),
         "Self-certification recorded; covered absences are now authorised.")


def ukvi_menu(username):
    print("1. Scan sponsored students  2. List open alerts  3. Resolve an alert  "
          "4. Term time / work limit on a date  0. Back")
    choice = input("Choice: ").strip()
    if choice == '1':
        _run(lambda c: eng.ukvi_scan(c), lambda r: f"{len(r)} new alert(s).")
    elif choice == '4':
        from datetime import date as _date
        raw = input(f"Date (YYYY-MM-DD) [{_date.today()}]: ").strip() or _date.today().isoformat()
        try:
            day = _date.fromisoformat(raw)
        except ValueError:
            print("Enter a date like 2026-10-05.")
            return
        with closing(get_connection()) as conn:
            print("  " + eng.student_work_limit(conn, day)["message"])
    elif choice in ('2', '3'):
        with closing(get_connection()) as conn:
            alerts = eng.ukvi_alerts(conn)
        for a in alerts:
            print(f"  #{a['id']} {a['student_id']} {a['name'] or '':<22} missed {a['consecutive_missed']}, "
                  f"last engaged {a['last_engaged_on'] or 'never'}, report due {a['report_due']}"
                  + ("  OVERDUE" if a['overdue'] else ""))
        if choice == '3' and alerts:
            aid = input("Alert #: ").strip()
            outcome = input(f"Outcome ({', '.join(eng.UKVI_OUTCOMES)}): ").strip()
            ref = input("UKVI reference: ").strip() if outcome == 'reported' else None
            notes = input("Notes: ").strip() or None
            if aid.isdigit():
                _run(lambda c: eng.resolve_ukvi_alert(c, int(aid), outcome, username, ref, notes), "Resolved.")


def engagement_menu(username):
    print("1. Scan for non-engagement  2. List open cases  3. Advance a case  4. Resolve a case  "
          "5. Confirm withdrawal  0. Back")
    choice = input("Choice: ").strip()
    if choice == '1':
        start, end = _window()
        _run(lambda c: eng.engagement_scan(c, start, end, username), lambda r: f"{len(r)} case(s) opened.")
        return
    with closing(get_connection()) as conn:
        open_cases = eng.cases(conn)
    for c in open_cases:
        print(f"  #{c['id']} {c['student_id']} {c['name'] or '':<22} {c['stage']:<24} respond by {c['due_on']}"
              + ("  OVERDUE" if c['overdue'] else "") + f"  ({c['opened_reason']})")
    if choice not in ('3', '4', '5') or not open_cases:
        return
    cid = input("Case #: ").strip()
    if not cid.isdigit():
        return
    if choice == '3':
        notes = input("What happened at this stage: ").strip()
        _run(lambda c: eng.advance_case(c, int(cid), username, notes), lambda s: f"Moved to {s}.")
    elif choice == '4':
        reason = input("Why is it closing: ").strip()
        _run(lambda c: eng.resolve_case(c, int(cid), username, reason), "Resolved.")
    else:
        reason = input("Withdrawal reason for the record: ").strip()
        if reason and input("Withdraw this student now? (y/n): ").strip().lower() == 'y':
            try:
                eng.confirm_withdrawal(int(cid), username, reason)
                print("Student withdrawn and case closed.")
            except ValueError as e:
                print(f"Refused: {e}")


def funding_menu(username):
    with closing(get_connection()) as conn:
        terms = [r[0] for r in conn.execute("SELECT name FROM academic_terms ORDER BY start_date")]
    if not terms:
        print("No academic terms defined.")
        return
    for i, t in enumerate(terms, 1):
        print(f"  {i}. {t}")
    pick = input("Term number: ").strip()
    if not pick.isdigit() or not 0 < int(pick) <= len(terms):
        return
    term = terms[int(pick) - 1]
    rows = _run(lambda c: eng.funding_candidates(c, term))
    if not rows:
        return
    for r in rows:
        print(f"  {r['student_id']:<10} {r['name'][:24]:<25} {r['suggested']:<10} {r['why']}")
    if input("Record these suggestions as confirmations? (y/n): ").strip().lower() == 'y':
        decisions = {r['student_id']: r['suggested'] for r in rows}
        _run(lambda c: eng.confirm_funding(c, term, decisions, username, rows[0]['academic_year']),
             lambda n: f"{n} confirmation(s) recorded.")
    path = input("Export CSV to (Enter to skip): ").strip()
    if path:
        _run(lambda c: eng.export_funding(c, term, path), lambda n: f"{n} row(s) exported.")


def display_office_menu(username="attendance_office"):
    actions = (("Registers & student attendance", registers_menu),
               ("Record a self-certification", self_cert_menu),
               ("UKVI engagement monitoring", lambda: ukvi_menu(username)),
               ("Non-engagement cases", lambda: engagement_menu(username)),
               ("Student funding attendance confirmation", lambda: funding_menu(username)))
    while True:
        print("\nAttendance Office")
        print("=" * 40)
        for i, (label, _) in enumerate(actions, 1):
            print(f"{i}. {label}")
        print("0. Back")
        choice = input("Choice: ").strip()
        if choice == '0' or not choice:
            return
        if choice.isdigit() and 0 < int(choice) <= len(actions):
            actions[int(choice) - 1][1]()
        else:
            print("Invalid choice.")
