"""CLI: the exam office — timetable publication, results, absentees,
invigilation, incidents and papers. Same rules as the GUI's Exam Office and
Results tabs (``university/application``)."""
from contextlib import closing

from education_system.systems.university.application.exams import (
    office as exam_office,
    results as exam_results,
    timetable as exam_timetable,
)
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


def _list_exams(conn, drafts_only=False):
    where = "WHERE COALESCE(status, 'published') = 'draft' " if drafts_only else ""
    rows = conn.execute(
        "SELECT id, module_code, date, start_time, end_time, room, COALESCE(status, 'published') "
        f"FROM exams {where}ORDER BY date, start_time").fetchall()  # nosec B608 - fixed clause
    print(f"\n{'ID':<5} {'Module':<12} {'Date':<11} {'Time':<12} {'Room':<16} Status")
    print("-" * 66)
    for r in rows:
        print(f"{r[0]:<5} {str(r[1])[:11]:<12} {r[2]:<11} {r[3]}-{r[4]:<6} {str(r[5] or '')[:15]:<16} {r[6]}")
    return [r[0] for r in rows]


def _pick(conn, drafts_only=False):
    ids = _list_exams(conn, drafts_only)
    if not ids:
        print("No exams.")
        return None
    choice = input("\nExam ID: ").strip()
    if not choice.isdigit() or int(choice) not in ids:
        print("Invalid exam ID.")
        return None
    return int(choice)


def timetable_menu(username):
    with closing(get_connection()) as conn:
        _list_exams(conn)
        clashes = exam_timetable.student_clashes(conn)
    if clashes:
        print(f"\nStudent clashes ({len(clashes)}):")
        for c in clashes[:20]:
            print(f"  {c['student_id']}: {'same time' if c['kind'] == 'overlap' else 'heavy day'} — "
                  + " | ".join(c['exams']))
    print("\n1. Publish drafts  2. Return a sitting to draft  0. Back")
    choice = input("Choice: ").strip()
    if choice == '1':
        with closing(get_connection()) as conn:
            ids = _list_exams(conn, drafts_only=True)
        if not ids:
            print("No drafts.")
            return
        picks = input("IDs to publish (comma-separated, 'all'): ").strip().lower()
        chosen = ids if picks == 'all' else [int(p) for p in picks.split(',') if p.strip().isdigit()]
        force = input("Publish even with clashes? (y/n): ").strip().lower() == 'y'
        try:
            # The same path as the GUI: publish, then calendar entry and
            # student notifications for what was published.
            from education_system.systems.university.domains.assessment.interfaces.gui.exam_management.data_manager import (
                DataManager,
            )
            outcome = DataManager().publish_exams(chosen, username, force=force)
        except Exception as e:
            print(f"Publish failed: {e}")
            return
        print(f"Published: {outcome['published'] or 'none'}; {outcome['notified']} notification(s) sent.")
        for eid, reasons in outcome['blocked'].items():
            print(f"  kept in draft #{eid}: {'; '.join(reasons)}")
    elif choice == '2':
        with closing(get_connection()) as conn:
            eid = _pick(conn)
        if eid:
            _run(lambda c: exam_timetable.unpublish(c, eid), "Returned to draft.")


def results_menu(username):
    with closing(get_connection()) as conn:
        eid = _pick(conn)
        if not eid:
            return
        exam = conn.execute("SELECT * FROM exams WHERE id = ?", (eid,)).fetchone()
        cols = [d[1] for d in conn.execute("PRAGMA table_info(exams)")]
        exam = dict(zip(cols, exam))
        students = exam_results.roster(conn, exam)
        existing = exam_results.existing_results(conn, eid)
        anonymous = exam_results.is_anonymous(conn, eid)
        numbers = exam_results.candidate_numbers(conn, eid, students)
        conn.commit()
    print("\nEnter a percentage, ABS or ABS-MC; Enter to skip or keep.")
    results = {}
    for sid in students:
        label = f"Candidate {numbers.get(sid)}" if anonymous else sid
        value = input(f"  {label} [{existing.get(sid, '')}]: ").strip()
        if value:
            results[sid] = value
    if not results:
        return
    with closing(get_connection()) as conn:
        changed = exam_results.changed_students(conn, eid, results)
    reason = None
    if changed:
        reason = input(f"{len(changed)} recorded result(s) change. Reason (required): ").strip()
        if not reason:
            print("Not saved: a reason is required.")
            return
    outcome = _run(lambda c: exam_results.record_results(c, eid, results, username, reason))
    if outcome:
        print(f"Saved {outcome['written']} result(s)."
              + ("" if outcome['released'] else " Students see them once released."))
        for sid, err in outcome['errors']:
            print(f"  not saved {sid}: {err}")


def absentees_menu(username):
    with closing(get_connection()) as conn:
        eid = _pick(conn)
        if not eid:
            return
        rows = exam_results.absentees(conn, eid)
        conn.commit()
    if not rows:
        print("Nobody without a result (or the exam has not happened yet).")
        return
    for r in rows:
        print(f"  {r['student_id']}: {r['code']}")
    if input("Record these absences? (y/n): ").strip().lower() == 'y':
        _run(lambda c: exam_results.record_absentees(c, eid, username), lambda n: f"{n} recorded.")


def invigilation_menu():
    with closing(get_connection()) as conn:
        for r in exam_timetable.staffing_report(conn):
            print(f"  {r['label']}: {r['candidates']} candidates, {r['invigilators']}/{r['needed']} "
                  f"invigilators{' — ' + '; '.join(r['issues']) if r['issues'] else ''}")
        eid = _pick(conn)
    if not eid:
        return
    with closing(get_connection()) as conn:
        for s in exam_timetable.invigilators(conn, eid):
            print(f"  {s['staff_id']} {s['staff_name'] or ''} ({s['role']})")
    print("1. Add  2. Remove  0. Back")
    choice = input("Choice: ").strip()
    staff_id = input("Staff ID: ").strip() if choice in ('1', '2') else ''
    if choice == '1' and staff_id:
        name = input("Name: ").strip() or None
        role = input("Role (lead/invigilator/support) [invigilator]: ").strip().lower() or 'invigilator'
        _run(lambda c: exam_timetable.assign_invigilator(c, eid, staff_id, name, role), "Added.")
    elif choice == '2' and staff_id:
        _run(lambda c: exam_timetable.remove_invigilator(c, eid, staff_id), "Removed.")


def incidents_menu(username):
    with closing(get_connection()) as conn:
        eid = _pick(conn)
        if not eid:
            return
        for i in exam_office.incidents(conn, eid):
            print(f"  #{i['id']} {str(i['occurred_at'])[:16]} {i['incident_type']} "
                  f"{i['student_id'] or ''}: {i['description']}  case {i['case_id'] or '—'}")
    print("1. Log incident  2. Refer malpractice to a misconduct case  0. Back")
    choice = input("Choice: ").strip()
    if choice == '1':
        print("Types: " + ", ".join(exam_office.INCIDENT_TYPES))
        kind = input("Type: ").strip()
        student = input("Student ID (blank if none): ").strip() or None
        minutes = input("Minutes late (late arrivals): ").strip() or None
        desc = input("What happened: ").strip()
        action = input("Action taken: ").strip() or None
        _run(lambda c: exam_office.log_incident(c, eid, kind, desc, student_id=student, minutes_late=minutes,
                                                action_taken=action, reported_by=username), "Logged.")
    elif choice == '2':
        iid = input("Incident #: ").strip()
        if iid.isdigit():
            outbox = []
            if _run(lambda c: exam_office.refer_to_misconduct(c, int(iid), username, outbox),
                    lambda case: f"Academic integrity case {case} opened.") and outbox:
                from education_system.systems.university.infrastructure.ui.record_screens import (
                    send_emails,
                )
                send_emails(outbox)


def papers_menu(username):
    with closing(get_connection()) as conn:
        for r in exam_office.paper_deadline_report(conn):
            flags = [f for f, on in (("print deadline passed", r['overdue']),
                                     ("no external approval", r['needs_external'])) if on]
            print(f"  #{r['exam_id']} {r['module_code']} {r['date']}: {r['status']} "
                  f"(print by {r['print_deadline'] or '—'}){' — ' + '; '.join(flags) if flags else ''}")
        eid = _pick(conn)
        if not eid:
            return
        p = exam_office.paper(conn, eid)
        conn.commit()
    states = exam_office.PAPER_STATES
    print(f"Current stage: {p['status']}   ({' → '.join(states)})")
    nxt = states[states.index(p['status']) + 1] if states.index(p['status']) + 1 < len(states) else None
    choice = input(f"Move to [{nxt or '—'}] or 'draft' (Enter to cancel): ").strip().lower()
    target = nxt if choice in ('y', 'yes', nxt or '#') else ('draft' if choice == 'draft' else None)
    if not target:
        return
    examiner = input("External examiner: ").strip() if target == 'externally_approved' else None
    location = input("Secured where: ").strip() if target == 'secured' else None
    notes = input("Notes: ").strip() or None
    _run(lambda c: exam_office.advance_paper(c, eid, target, username, external_examiner=examiner,
                                             secured_location=location, notes=notes),
         f"Paper moved to {target}.")


def display_exam_office_menu(username):
    actions = (("Timetable: clashes and publishing", lambda: timetable_menu(username)),
               ("Enter exam results", lambda: results_menu(username)),
               ("Record absentees (ABS / ABS-MC)", lambda: absentees_menu(username)),
               ("Invigilation", invigilation_menu),
               ("Incidents", lambda: incidents_menu(username)),
               ("Exam papers", lambda: papers_menu(username)))
    while True:
        print("\nExam Office")
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
