"""CLI: the Programme Record — the same rules as Course Management's
Programme Record page (``university/application/programmes/record`` and
``programme_structure``).

Lives beside the course menu that calls it; it imports only the application
layer, so the slice's domain package gains no adapter dependency.
"""

from __future__ import annotations

from contextlib import closing

from education_system.systems.university.application.modules import enrolment as module_enrolment
from education_system.systems.university.application.programmes import record
from education_system.systems.university.application.programmes import structure
from education_system.systems.university.infrastructure.database.db import get_connection


def _actor(auth):
    user = getattr(auth, "current_user", None) or {}
    return (user.get("username") if isinstance(user, dict) else getattr(user, "username", None)) \
        or "course_management_cli"


def _run(action, done=None, write=False):
    try:
        with closing(get_connection()) as conn:
            result = action(conn)
            if write:
                conn.commit()
    except ValueError as exc:
        print(f"Refused: {exc}")
        return None
    if done:
        print(done(result) if callable(done) else done)
    return True if result is None else result


def _spec(code, auth):
    spec = _run(lambda c: record.get_spec(c, code)) or {}
    for key in record.SPEC_FIELDS:
        print(f"  {key.replace('_', ' '):<26} {spec.get(key) if spec.get(key) is not None else '—'}")
    if input("Edit? (y/N): ").strip().lower() != "y":
        return
    changes = {}
    for key in record.SPEC_FIELDS:
        value = input(f"{key.replace('_', ' ')} [{spec.get(key) or ''}]: ").strip()
        if value:
            changes[key] = value
    _run(lambda c: record.save_spec(c, code, changes, _actor(auth)),
         lambda r: f"{len(r)} field(s) saved.", write=True)


def _awards(code, auth):
    awards = _run(lambda c: record.exit_awards(c, code)) or []
    for a in awards:
        print(f"  #{a['id']} {a['award_name']:<34} {a['total_credits']} credits"
              + (f", {a['credits_at_level']} at level {a['at_level']}" if a["at_level"] else ""))
    choice = input("1. Add standard UK awards  2. Add one  3. Remove  "
                   "4. Check a student  0. Back: ").strip()
    if choice == "1":
        _run(lambda c: record.use_standard_exit_awards(c, code), lambda n: f"{n} added.",
             write=True)
    elif choice == "2":
        name, total = input("Award: ").strip(), input("Total credits: ").strip()
        at, level = input("Credits at level (0 = none): ").strip(), input("Level: ").strip()
        final = input("Final award? (y/N): ").strip().lower() == "y"
        _run(lambda c: record.add_exit_award(c, code, name, total, at, level, final), "Added.",
             write=True)
    elif choice == "3":
        aid = input("Award #: ").strip()
        if aid.isdigit():
            _run(lambda c: record.remove_exit_award(c, int(aid)), "Removed.", write=True)
    elif choice == "4":
        sid = input("Student ID: ").strip()
        award = _run(lambda c: record.eligible_exit_award(c, sid, code))
        print(f"Qualifies for: {award['award_name']}" if isinstance(award, dict)
              else "Does not yet qualify for an exit award.")


def _progression(code):
    sid = input("Student ID: ").strip()
    year = input("Year (stage): ").strip()
    result = _run(lambda c: record.progression(c, sid, code, int(year or 0)))
    if isinstance(result, dict):
        print(f"{result['outcome'].upper()}: {result['passed_credits']:g} of "
              f"{result['required']} credits passed; failed {', '.join(result['failed']) or 'none'}")


def _fees_and_intake(code, auth):
    for f in _run(lambda c: record.fees(c, code)) or []:
        print(f"  {f['academic_year']} {f['fee_status']:<13} £{f['amount']:,.2f}")
    for r in _run(lambda c: record.intake_report(c, code)) or []:
        print(f"  {r['academic_year']}: target {r['target'] or '—'}, {r['applications']} "
              f"applied, {r['offers']} offers, {r['accepted']} accepted, {r['started']} started")
    choice = input("1. Set a fee  2. Set an intake target  0. Back: ").strip()
    if choice == "1":
        year, status = input("Year (2026/27): ").strip(), input("home / international: ").strip()
        amount = input("Annual fee £: ").strip()
        _run(lambda c: record.set_fee(c, code, year, status, amount), "Saved.", write=True)
    elif choice == "2":
        year, target = input("Year: ").strip(), input("Target: ").strip()
        mode = input("Mode [full-time]: ").strip() or "full-time"
        _run(lambda c: record.set_intake_target(c, code, year, target, mode, _actor(auth)),
             "Saved.", write=True)


def _structure(code, auth):
    for s in _run(lambda c: structure.stages(c, code)) or []:
        print(f"\n  Year {s['year']}: required {s['required_credits']:g}, "
              f"offered {s['offered_credits']:g} credits")
        for issue in s["issues"]:
            print(f"    ! {issue}")
        for m in s["modules"]:
            print(f"    {m['module_code']:<12} {m['credits']:>3}  {m['designation']}")
    module = input("\nSet a designation — module code (blank to stop): ").strip()
    if module:
        category = input("core / compulsory / optional: ").strip()
        year = input("Year: ").strip()
        _run(lambda c: module_enrolment.set_designation(c, module, code, category, year,
                                                        _actor(auth)), "Saved.", write=True)


def _curriculum_map(code):
    result = _run(lambda c: structure.curriculum_map(c, code))
    if not isinstance(result, dict):
        return
    names = {o["id"]: o["outcome_code"] or str(o["id"]) for o in result["outcomes"]}
    for m in result["mappings"]:
        print(f"  #{m['id']} {names.get(m['outcome_id'])} ← {m['module_code']} "
              f"{m['module_outcome_code']} ({m['coverage']})")
    for gap in result["gaps"]:
        print(f"  ! {gap}")
    choice = input("1. Map an outcome  2. Remove a mapping  0. Back: ").strip()
    if choice == "1":
        for o in result["outcomes"]:
            print(f"  {o['id']}: {o['outcome_code']} {o['description']}")
        oid, module = input("Outcome id: ").strip(), input("Module code: ").strip()
        lo, cov = input("Module outcome (blank = none): ").strip(), input(
            "introduced / developed / assessed: ").strip()
        if oid.isdigit():
            _run(lambda c: structure.map_outcome(c, int(oid), module, cov, lo.upper()), "Mapped.",
                 write=True)
    elif choice == "2":
        mid = input("Mapping #: ").strip()
        if mid.isdigit():
            _run(lambda c: structure.unmap(c, int(mid)), "Removed.", write=True)


def _cohort(code):
    rows = _run(lambda c: structure.cohort(c, code)) or []
    for r in rows:
        print(f"  {r['student_id']:<10} {r['name'][:24]:<25} {r['filed_as']:<20} "
              f"yr {r['year_of_study'] or '-'} {r['status']:<10} {r['registration']}")
    counts = _run(lambda c: structure.live_counts(c)) or {}
    actual, stored = counts.get(code, (0, 0))
    print(f"{actual} active; stored count {stored}.")
    choice = input("1. Correct every stored count  2. File students under course codes  "
                   "0. Back: ").strip()
    if choice == "1":
        _run(structure.refresh_counters, lambda n: f"{n} course(s) corrected.", write=True)
    elif choice == "2":
        plan = _run(structure.name_fix_plan)
        if not isinstance(plan, dict):
            return
        for sid, was, to in plan["fix"]:
            print(f"  {sid}: '{was}' → {to}")
        for sid, was in plan["unknown"]:
            print(f"  {sid}: '{was}' matches no course (fix by hand)")
        if plan["fix"] and input("Apply? (y/N): ").strip().lower() == "y":
            _run(lambda c: structure.apply_name_fix(c, plan), lambda n: f"{n} updated.",
                 write=True)


def _results(code):
    for r in _run(lambda c: structure.cohort_outcomes(c, code)) or []:
        print(f"  entry {r['entry_year']}: {r['started']} started, continuation "
              f"{r['continuation_pct']}%, completion "
              f"{'too early' if r['completion_pct'] is None else str(r['completion_pct']) + '%'}")
    cls = _run(lambda c: structure.classifications(c, code))
    if isinstance(cls, dict) and cls["total"]:
        print(f"  classifications {cls['counts']}; good honours {cls['good_honours_pct']}%")
    for b in _run(lambda c: structure.b3_metrics(c, code)) or []:
        print(f"  B3 {b['cohort_year']} {b['metric_type']}: {b['value_pct']:.1f}%")
    for s in _run(lambda c: record.survey_results(c, code)) or []:
        print(f"  {s['survey']} {s['academic_year']} {s['theme']}: {s['agree_pct']:g}%")
    if input("Record a survey result? (y/N): ").strip().lower() == "y":
        year, theme = input("Year: ").strip(), input("Theme: ").strip()
        pct, n = input("% agree: ").strip(), input("Respondents: ").strip()
        _run(lambda c: record.set_survey_result(c, code, year, theme, pct, n), "Saved.",
             write=True)


def _examiners(code, auth):
    for e in _run(lambda c: record.examiners(c, code)) or []:
        print(f"  #{e['id']} {e['name']} {e['appointed_from']}→{e['appointed_to']} "
              f"report: {'OVERDUE' if e['report_overdue'] else e['report_summary'] or '—'}; "
              f"response: {e['response'] or ('outstanding' if e['response_outstanding'] else '—')}")
    gov = _run(lambda c: record.governed_id(c, code))
    print("On the governance register." if isinstance(gov, int)
          else "Not on the governance register.")
    choice = input("1. Appoint examiner  2. Record report  3. Record response  "
                   "4. Register for governance  0. Back: ").strip()
    if choice == "1":
        eid, start = input("Examiner id: ").strip(), input("From (YYYY-MM-DD): ").strip()
        end, due = input("To: ").strip(), input("Report due (blank = none): ").strip()
        _run(lambda c: record.appoint_examiner(c, code, int(eid or 0), start, end, due or None),
             "Appointed.", write=True)
    elif choice in ("2", "3"):
        aid = input("Appointment #: ").strip()
        text = input("Summary: " if choice == "2" else "Response: ").strip()
        if aid.isdigit():
            fn = (lambda c: record.record_report(c, int(aid), text)) if choice == "2" else \
                (lambda c: record.record_response(c, int(aid), text, _actor(auth)))
            _run(fn, "Recorded.", write=True)
    elif choice == "4":
        _run(lambda c: record.register_for_governance(c, code, _actor(auth)),
             lambda pid: f"Registered (programme #{pid}). Versions, accreditation and "
                         "teach-out are in Programme Governance.", write=True)


def display_programme_record_menu(auth):
    code = input("Course code: ").strip().upper()
    if not code or _run(lambda c: record._course(c, code)) is None:
        return
    actions = (("Specification & entry requirements", lambda: _spec(code, auth)),
               ("Exit awards", lambda: _awards(code, auth)),
               ("Check a student's progression", lambda: _progression(code)),
               ("Fees & intake", lambda: _fees_and_intake(code, auth)),
               ("Structure (years, core/optional, credits)", lambda: _structure(code, auth)),
               ("Curriculum map", lambda: _curriculum_map(code)),
               ("Cohort", lambda: _cohort(code)),
               ("Results", lambda: _results(code)),
               ("External examiners & governance", lambda: _examiners(code, auth)))
    while True:
        print(f"\nProgramme Record — {code}")
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
