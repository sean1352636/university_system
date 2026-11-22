"""CLI: module catalogue — specification and outcomes, change requests,
programme designations, exclusions, waitlist, cohort enrolment, teaching team
and external examiners, deliveries and timetable, evaluation results, and
filling missing credits / levels.

Same rules as the Module Management window
(``university/application/modules/specification``, ``module_enrolment``,
``module_delivery``). Wired into ``module_operations`` via :data:`HANDLERS`.
"""

from __future__ import annotations

from contextlib import closing

from education_system.systems.university.application.modules import delivery
from education_system.systems.university.application.modules import enrolment
from education_system.systems.university.application.modules import specification as spec
from education_system.systems.university.application.teaching import occurrences
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.shell.cli.imports import get_auth


def _user():
    auth = get_auth()
    user = getattr(auth, "current_user", None) or {}
    username = user.get("username") if isinstance(user, dict) else getattr(user, "username", None)
    return auth, username or "module_management_cli"


def _can(permission):
    auth, _ = _user()
    try:
        return bool(auth and auth.check_permission(permission))
    except Exception:
        return False


def _run(action, done=None):
    """Run ``action(conn)`` in one transaction; print a refusal instead of raising."""
    try:
        with closing(get_connection()) as conn:
            result = action(conn)
            conn.commit()
    except ValueError as exc:
        print(f"Refused: {exc}")
        return None
    if done:
        print(done(result) if callable(done) else done)
    return result if result is not None else True


def _module():
    code = input("Module code (blank to go back): ").strip().upper()
    if not code:
        return None
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT module_name FROM modules WHERE module_code = ?",
                           (code,)).fetchone()
    if row is None:
        print(f"No module {code}.")
        return None
    print(f"\n{code} — {row[0]}")
    return code


def _may_edit(code):
    if _can("manage_modules"):
        return True
    _, username = _user()
    with closing(get_connection()) as conn:
        if delivery.is_leader(conn, code, username):
            return True
    print("Only the module leader or a catalogue manager can change this module.")
    return False


def _menu(title, actions):
    while True:
        print(f"\n{title}")
        for i, (label, _fn) in enumerate(actions, 1):
            print(f"  {i}. {label}")
        print("  0. Back")
        choice = input("Choice: ").strip()
        if choice in ("0", ""):
            return
        if choice.isdigit() and 0 < int(choice) <= len(actions):
            actions[int(choice) - 1][1]()
        else:
            print("Invalid choice.")


# ── specification ───────────────────────────────────────────────────────


def _show_spec(code):
    with closing(get_connection()) as conn:
        values = spec.current_values(conn, code)
        outcomes = spec.list_outcomes(conn, code)
        plan = spec.list_plan(conn, code)
        issues = spec.spec_issues(conn, code)
    print(f"Level {values.get('level') or '—'}, {values.get('credits') or 0} credits")
    for key in ("aims", "indicative_content", "teaching_methods", "reading_list"):
        print(f"{spec.FIELD_LABELS['spec.' + key]}: {values.get('spec.' + key) or '—'}")
    print("Hours: " + ", ".join(f"{spec.FIELD_LABELS['spec.' + k]} "
                                f"{values.get('spec.' + k) or 0:g}" for k in spec.HOUR_FIELDS))
    print("Learning outcomes:")
    for o in outcomes:
        print(f"  {o['outcome_code']}: {o['description']} ({o['bloom_level']})")
    print("Assessment plan:")
    for p in plan:
        print(f"  #{p['id']} {p['component']} {p['assessment_type'] or ''} {p['weight']:g}% "
              f"assesses {p['outcomes'] or '—'}")
    print("To complete: " + ("; ".join(issues) if issues else "nothing"))


def _edit_spec(code):
    if not _may_edit(code):
        return
    print("Press Enter to keep a value.")
    with closing(get_connection()) as conn:
        current = spec.current_values(conn, code)
    changes = {}
    for key in [k for k in spec.FIELD_LABELS if k.startswith("spec.")] + ["level", "credits"]:
        value = input(f"{spec.FIELD_LABELS[key]} [{current.get(key) or ''}]: ").strip()
        if value:
            changes[key] = value
    if not changes:
        return
    _, username = _user()
    if _can("manage_modules"):
        _run(lambda c: spec.apply_changes(c, code, changes, username),
             lambda r: f"{len(r)} field(s) changed.")
    else:
        summary = input("What is the change, and why? ").strip()
        _run(lambda c: spec.propose_change(c, code, changes, username, summary),
             lambda r: f"Change request #{r} is waiting for approval.")


def _outcomes(code):
    if not _may_edit(code):
        return
    _, username = _user()
    choice = input("1. Add an outcome  2. Remove one: ").strip()
    if choice == "1":
        text = input("On completion a student can: ").strip()
        bloom = input(f"Level of learning ({', '.join(spec.BLOOM_LEVELS)}) [understand]: ")
        _run(lambda c: spec.add_outcome(c, code, text, bloom.strip() or "understand", username),
             lambda r: f"Added {r}.")
    elif choice == "2":
        with closing(get_connection()) as conn:
            for o in spec.list_outcomes(conn, code):
                print(f"  id {o['outcome_id']}: {o['outcome_code']} {o['description']}")
        oid = input("Outcome id: ").strip()
        if oid.isdigit():
            _run(lambda c: spec.delete_outcome(c, code, int(oid), username), "Removed.")


def _plan(code):
    if not _may_edit(code):
        return
    _, username = _user()
    choice = input("1. Add a component  2. Remove one: ").strip()
    if choice == "1":
        name = input("Component (e.g. Exam): ").strip()
        kind = input("Type: ").strip()
        weight = input("Weight %: ").strip()
        size = input("Size (e.g. 2 hours, 3000 words): ").strip()
        outcomes = input("Outcomes assessed (e.g. LO1, LO2): ").strip()
        _run(lambda c: spec.add_component(c, code, name, kind, weight, size, outcomes, username),
             "Added.")
    elif choice == "2":
        cid = input("Component # (see the plan): ").strip()
        if cid.isdigit():
            _run(lambda c: spec.delete_component(c, code, int(cid), username), "Removed.")


def specification_menu():
    code = _module()
    if code:
        _menu(f"{code} specification", [
            ("Show specification", lambda: _show_spec(code)),
            ("Edit specification / level / credits", lambda: _edit_spec(code)),
            ("Learning outcomes", lambda: _outcomes(code)),
            ("Assessment plan", lambda: _plan(code)),
        ])


# ── change requests ─────────────────────────────────────────────────────


def changes_menu():
    _, username = _user()
    manager = _can("manage_modules")
    with closing(get_connection()) as conn:
        pending = spec.list_requests(conn)
    print(f"\n{len(pending)} pending change request(s):")
    for r in pending:
        print(f"  #{r['id']} {r['module_code']} by {r['proposed_by']} {r['proposed_at']}: "
              f"{r['summary']}")
        for key, (old, new) in r["changes"].items():
            print(f"      {spec.FIELD_LABELS.get(key, key)}: {old or '—'} → {new or '—'}")
    options = "1. Approve  2. Reject  3. Withdraw my request  4. Module history  0. Back"
    choice = input((options if manager else options.replace("1. Approve  2. Reject  ", ""))
                   + "\nChoice: ").strip()
    if choice in ("1", "2") and manager:
        rid = input("Request #: ").strip()
        note = input("Reason: ").strip() if choice == "2" else None
        if rid.isdigit():
            _run(lambda c: spec.decide_request(c, int(rid), choice == "1", username, note),
                 lambda r: f"Request #{rid} {r['status']}.")
    elif choice == "3":
        rid = input("Request #: ").strip()
        if rid.isdigit():
            _run(lambda c: spec.withdraw_request(c, int(rid), username), "Withdrawn.")
    elif choice == "4":
        code = _module()
        if code:
            with closing(get_connection()) as conn:
                for h in spec.history(conn, code, limit=60):
                    print(f"  {h['changed_at']} {spec.FIELD_LABELS.get(h['field'], h['field'])}: "
                          f"{h['old_value'] or '—'} → {h['new_value'] or '—'} "
                          f"({h['changed_by'] or '?'})")


# ── programmes, exclusions, waitlist, cohorts ───────────────────────────


def designations_menu():
    code = _module()
    if not code:
        return
    with closing(get_connection()) as conn:
        for course, d in enrolment.designations(conn, code).items():
            print(f"  {course}: {d['category']}, year {d['year_of_study'] or '—'}")
    course = input("Programme code to set (blank to stop): ").strip()
    if not course:
        return
    category = input("core / compulsory / optional (or 'clear'): ").strip().lower()
    if category == "clear":
        _run(lambda c: enrolment.clear_designation(c, code, course), "Cleared.")
        return
    year = input("Year of study: ").strip()
    _, username = _user()
    _run(lambda c: enrolment.set_designation(c, code, course, category, year, username), "Saved.")
    with closing(get_connection()) as conn:
        for issue in enrolment.programme_credit_issues(conn, course):
            print(f"  ! {issue}")


def exclusions_menu():
    code = _module()
    if not code:
        return
    with closing(get_connection()) as conn:
        rules = enrolment.exclusions(conn, code)
    for e in rules:
        print(f"  #{e['id']} {e['other']} {e['other_name']} — {e['reason'] or ''}")
    choice = input("1. Add  2. Remove  0. Back: ").strip()
    _, username = _user()
    if choice == "1":
        other = input("Module it excludes: ").strip().upper()
        reason = input("Why: ").strip()
        _run(lambda c: enrolment.add_exclusion(c, code, other, reason, username), "Added.")
    elif choice == "2":
        rid = input("Rule #: ").strip()
        if rid.isdigit():
            _run(lambda c: enrolment.remove_exclusion(c, int(rid)), "Removed.")


def waitlist_menu():
    code = _module()
    if not code:
        return
    with closing(get_connection()) as conn:
        for w in enrolment.waitlist(conn, code):
            print(f"  #{w['id']} position {w['position']}: {w['student_id']} {w['name']} "
                  f"(since {w['added_at']})")
    choice = input("1. Add a student  2. Enrol one now  3. Remove  4. Fill free places  "
                   "0. Back: ").strip()
    _, username = _user()
    if choice == "1":
        sid = input("Student ID: ").strip()
        _run(lambda c: enrolment.join_waitlist(c, code, sid), lambda p: f"Position {p}.")
    elif choice in ("2", "3"):
        wid = input("Entry #: ").strip()
        if wid.isdigit() and choice == "2":
            _run(lambda c: enrolment.enrol_from_waitlist(c, code, int(wid), username), "Enrolled.")
        elif wid.isdigit():
            _run(lambda c: enrolment.remove_from_waitlist(c, int(wid), username), "Removed.")
    elif choice == "4":
        _run(lambda c: enrolment.promote_all(c, code, username),
             lambda r: "Enrolled: " + (", ".join(r) if r else "nobody (no place, or nobody "
                                                              "waiting meets the rules)"))


def cohort_menu():
    code = _module()
    if not code:
        return
    course = input("Programme code: ").strip()
    year = input("Year of study (blank = all): ").strip()
    with closing(get_connection()) as conn:
        members = enrolment.cohort(conn, course, year)
    print(f"{len(members)} active student(s).")
    if not members or input("Enrol them? (y/n): ").strip().lower() != "y":
        return
    override = input("Override unmet rules? (y/n): ").strip().lower() == "y"
    result = _run(lambda c: enrolment.bulk_enrol(c, code, [m["student_id"] for m in members],
                                                 override=override))
    if result:
        print(f"Enrolled {len(result['enrolled'])}, already {len(result['already'])}, "
              f"waitlisted {len(result['waitlisted'])}, overridden {len(result['overridden'])}.")
        for sid, why in result["blocked"]:
            print(f"  not enrolled {sid}: {why.splitlines()[0]}")


# ── team, examiners, deliveries, timetable ──────────────────────────────


def team_menu():
    code = _module()
    if not code:
        return
    with closing(get_connection()) as conn:
        print(f"Leader: {delivery.leader(conn, code) or 'none'}")
        for m in delivery.team(conn, code):
            print(f"  #{m['id']} {m['username']:<12} {m['role']:<10} {m['hours'] or 0:g} h "
                  f"{m['academic_year'] or 'all years'}")
        for e in delivery.module_examiners(conn, code):
            print(f"  examiner #{e['id']} {e['name']} ({e['institution'] or ''})")
    if not (_can("manage_modules") or _can("assign_instructors")):
        return
    choice = input("1. Add member  2. Remove member  3. Workload of a person  "
                   "4. Assign examiner  5. Unassign examiner  0. Back: ").strip()
    _, username = _user()
    if choice == "1":
        user = input("Username: ").strip()
        role = input(f"Role ({', '.join(delivery.schema.STAFF_ROLES)}): ").strip()
        hours = input("Hours: ").strip() or 0
        year = input("Academic year (blank = all): ").strip()
        _run(lambda c: delivery.add_member(c, code, user, role, hours, year, username), "Added.")
    elif choice == "2":
        mid = input("Member #: ").strip()
        if mid.isdigit():
            _run(lambda c: delivery.remove_member(c, code, int(mid), username), "Removed.")
    elif choice == "3":
        who = input("Username: ").strip()
        with closing(get_connection()) as conn:
            load = delivery.workload(conn, who)
        for r in load["rows"]:
            print(f"  {r['module_code']} {r['role']} {r['hours'] or 0:g} h {r['academic_year']}")
        print(f"Total {load['total_hours']:g} hours.")
    elif choice == "4":
        with closing(get_connection()) as conn:
            for e in delivery.examiner_choices(conn):
                print(f"  {e['examiner_id']}: {e['name']} ({e['institution'] or ''})")
        eid = input("Examiner id: ").strip()
        year = input("Academic year (blank = all): ").strip()
        _run(lambda c: delivery.assign_examiner(c, code, eid, year, username), "Assigned.")
    elif choice == "5":
        lid = input("Examiner link #: ").strip()
        if lid.isdigit():
            _run(lambda c: delivery.unassign_examiner(c, code, int(lid), username), "Removed.")


def _add_slot(code, username):
    day = input(f"Day ({', '.join(delivery.DAYS[:5])}…): ").strip().title()
    start, end = input("Start HH:MM: ").strip(), input("End HH:MM: ").strip()
    kind = input("Session type [Lecture]: ").strip() or "Lecture"
    room = input("Room id (blank = none): ").strip() or None
    semester = input("Semester (blank = any): ").strip() or None
    weeks = input("Teaching weeks, e.g. 1-5,7-11 (blank = every week): ").strip() or None
    section = input("Delivery # (blank = all deliveries): ").strip() or None
    link = input("Online link (blank = none): ").strip() or None
    kwargs = dict(session_type=kind, room_id=room, semester=semester, week_pattern=weeks,
                  section_id=int(section) if section and section.isdigit() else None,
                  online_url=link, actor=username)
    try:
        with closing(get_connection()) as conn:
            made = delivery.add_slot(conn, code, day, start, end, **kwargs)
            conn.commit()
        print(f"Added; {occurrences.send_emails(made['emails'])} email(s) sent.")
    except ValueError as exc:
        print(f"Refused: {exc}")
        if str(exc).startswith("Clashes with") and \
                input("Add it anyway? (y/n): ").strip().lower() == "y":
            made = _run(lambda c: delivery.add_slot(c, code, day, start, end, force=True,
                                                    **kwargs), "Added.")
            if isinstance(made, dict):
                occurrences.send_emails(made["emails"])


def delivery_menu():
    code = _module()
    if not code:
        return
    with closing(get_connection()) as conn:
        for d in delivery.deliveries(conn, code):
            print(f"  delivery #{d['id']} {d['term']} {d['section_number']} "
                  f"{d['enrolled']}/{d['capacity']} {d['delivery_mode']} {d['status']}")
        for s in delivery.slots(conn, code):
            print(f"  session #{s['id']} {s['day_of_week']} {s['start_time']}-{s['end_time']} "
                  f"{s['session_type'] or ''} {s['room'] or ''}")
    if not _can("manage_modules"):
        return
    choice = input("1. Add delivery  2. Change places/status  3. Add weekly session  "
                   "4. Cancel session  0. Back: ").strip()
    _, username = _user()
    if choice == "1":
        with closing(get_connection()) as conn:
            for t in delivery.term_choices(conn):
                print(f"  {t['id']}: {t['name']}")
        term = input("Term id: ").strip()
        places = input("Places: ").strip()
        _run(lambda c: delivery.add_delivery(c, code, term, places, delivery.leader(c, code),
                                             actor=username), "Added.")
    elif choice == "2":
        did = input("Delivery #: ").strip()
        places = input("New places (blank = keep): ").strip() or None
        status = input("Status Open/Closed/Cancelled (blank = keep): ").strip().title() or None
        if did.isdigit():
            _run(lambda c: delivery.update_delivery(c, code, int(did), capacity=places,
                                                    status=status, actor=username), "Saved.")
    elif choice == "3":
        _add_slot(code, username)
    elif choice == "4":
        sid = input("Session #: ").strip()
        if sid.isdigit():
            done = _run(lambda c: delivery.cancel_slot(c, code, int(sid), username),
                        "Withdrawn; students told.")
            if isinstance(done, dict):
                occurrences.send_emails(done["emails"])


def feedback_menu():
    code = _module()
    if not code:
        return
    with closing(get_connection()) as conn:
        runs = delivery.evaluations(conn, code)
        ysw = delivery.you_said_we_did(conn, code)
    for e in runs:
        score = "—" if e["mean_score"] is None else f"{e['mean_score']:.2f}"
        print(f"  {e['academic_year']} {e['semester']}: {e['response_count'] or 0} responses, "
              f"mean {score}")
    for y in ysw:
        print(f"  You said ({y['theme']}): {y['you_said']}\n    We did: {y['we_did'] or '—'}")
    if not runs and not ysw:
        print("No evaluations recorded for this module.")


def fill_menu():
    with closing(get_connection()) as conn:
        plan = delivery.fill_plan(conn)
    if not plan:
        print("Nothing to fill.")
        return
    for p in plan[:20]:
        print(f"  {p['module_code']}: " + ", ".join(f"{k} {p[k]}" for k in ("credits", "level")
                                                     if k in p))
    print(f"{len(plan)} module(s). Credits = programme total ÷ its module count; "
          "level = year of study + 3.")
    if input("Apply? (y/n): ").strip().lower() == "y":
        _, username = _user()
        _run(lambda c: delivery.apply_fill(c, plan, username), lambda n: f"Updated {n} module(s).")


HANDLERS = {
    "spec": specification_menu,
    "changes": changes_menu,
    "designations": designations_menu,
    "exclusions": exclusions_menu,
    "waitlist": waitlist_menu,
    "cohort": cohort_menu,
    "team": team_menu,
    "delivery": delivery_menu,
    "feedback": feedback_menu,
    "fill": fill_menu,
}
