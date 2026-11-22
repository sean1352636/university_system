"""Counselling — CLI twin of the Counselling Service panel.

The counselling team works the referral-to-discharge pathway; a student refers
themselves and sees their own referral's progress; other staff can only refer.
Everything goes through ``domain/mental_health/counselling_pathway``.
"""

from __future__ import annotations

from datetime import date

from education_system.systems.university.domains.student_support.domain.mental_health import (
    counselling_pathway as pathway,
    counselling_reports as reports,
    outcome_measures,
)
from education_system.systems.university.domains.student_support.domain.wellbeing.casework import (
    access,
)
from education_system.systems.university.domains.student_support.interfaces.cli.wellbeing.casework.prompts import (
    ask,
    ask_text,
    choose,
    pause,
    run,
    table,
    yes,
)

CRISIS_TEXT = ("In an emergency call 999. Samaritans: 116 123 (free, 24 hours). "
               "Shout: text SHOUT to 85258. NHS 111 (option 2 for mental health).")

TRIAGE_COLUMNS = (("referral_id", "#", 5), ("student_id", "Student", 10),
                  ("student_name", "Name", 22), ("source", "Source", 7),
                  ("presenting_issue", "About", 20), ("referred_at", "Referred", 16),
                  ("days_waiting", "Days", 4))
WAITING_COLUMNS = (("position", "Pos", 3), ("referral_id", "#", 5), ("student_id", "Student", 10),
                   ("student_name", "Name", 22), ("risk_rating", "Risk", 8),
                   ("pathway", "Pathway", 9), ("days_waiting", "Days", 4))
CASELOAD_COLUMNS = (("referral_id", "#", 5), ("student_id", "Student", 10),
                    ("student_name", "Name", 22), ("counsellor_name", "Counsellor", 18),
                    ("sessions_used", "Used", 4), ("session_cap", "Cap", 3),
                    ("next_session", "Next", 11))
SESSION_COLUMNS = (("id", "ID", 5), ("session_number", "No", 3), ("session_date", "Date", 11),
                   ("session_time", "Time", 6), ("mode", "Mode", 10),
                   ("session_stage", "Stage", 9), ("status", "Status", 10))
MEASURE_COLUMNS = (("recorded_at", "Recorded", 17), ("measure", "Measure", 8), ("stage", "Stage", 7),
                   ("total", "Total", 5), ("band", "Band", 18), ("risk_flag", "Risk", 4))
NOTE_COLUMNS = (("created_at", "When", 17), ("note_type", "Type", 11), ("author", "By", 14),
                ("note", "Note", 70))
COUNSELLOR_COLUMNS = (("counselor_id", "#", 4), ("name", "Name", 24), ("user_id", "Username", 14),
                      ("specialization", "Specialism", 22), ("open_caseload", "Open", 4),
                      ("is_active", "Active", 6))


def _referral_id(label="Referral #"):
    raw = ask(label)
    if raw.isdigit():
        return int(raw)
    print("\n❌ That is not a referral number.")
    return None


def _refer(auth, self_referral: bool) -> None:
    student = None if self_referral else ask("Student number")
    if not self_referral and not student:
        return
    issue = choose("What is it mainly about", [(i, i) for i in pathway.PRESENTING_ISSUES]) or ""
    reason = ask_text("Tell us a little about what is going on" if self_referral
                      else "Reason for the referral")
    consent = yes("May the counselling team contact me about this?" if self_referral
                  else "Does the student know about and agree to this referral?")
    if not self_referral and not consent and not yes("Refer them anyway?"):
        return
    referral_id = run(pathway.refer, auth, student, reason, presenting_issue=issue,
                      consent_to_contact=consent)
    if referral_id is not None:
        print(f"\n✅ Referral #{referral_id} has been sent to the counselling team.")
    print(f"\n{CRISIS_TEXT}")


# ------------------------------------------------------------------ the student

def _my_counselling(auth) -> None:
    refs = run(pathway.my_referrals, auth)
    if refs is None:
        return
    if not refs:
        print("\nYou have not been referred to counselling.")
    for ref in refs:
        print(f"\nReferral #{ref['referral_id']} — {ref['status_label']}")
        print(f"  Referred: {str(ref['referred_at'])[:10]}")
        if ref["position"]:
            print(f"  Place on the waiting list: {ref['position']}")
        if ref["days_waiting"] is not None:
            print(f"  Waiting: {ref['days_waiting']} days")
        if ref["counsellor_name"]:
            print(f"  Counsellor: {ref['counsellor_name']} (up to {ref['session_cap']} sessions)")
        for sess in ref["sessions"]:
            print(f"  Session {sess['session_number']}: {sess['session_date']} "
                  f"{sess['session_time'] or ''} — {sess['status']}")


def _our_counsellors() -> None:
    people = run(pathway.active_counsellors_public) or []
    if not people:
        print("\nThe counsellor list has not been set up yet.")
    for person in people:
        print(f"\n{person['name']}" + (f" — {person['specialization']}"
                                       if person["specialization"] else ""))
        if person["qualifications"]:
            print(f"  {person['qualifications']}")
        if person["availability_schedule"]:
            print(f"  Available: {person['availability_schedule']}")


def _student_menu(auth) -> None:
    while True:
        print("\n" + "=" * 50 + "\n  COUNSELLING\n" + "=" * 50)
        print("1. Refer myself\n2. My counselling\n3. Our counsellors\n0. Return")
        print(f"\n{CRISIS_TEXT}")
        choice = input("\nEnter your choice: ").strip()
        if choice == "0":
            return
        if choice == "1":
            _refer(auth, True)
        elif choice == "2":
            _my_counselling(auth)
        elif choice == "3":
            _our_counsellors()
        else:
            continue
        pause()


# ------------------------------------------------------------------ the team

def _triage(auth) -> None:
    table(run(pathway.triage_queue, auth) or [], TRIAGE_COLUMNS, "No referrals awaiting triage")
    referral_id = _referral_id("Referral # to triage (blank to leave)") if yes("Triage one?") else None
    if referral_id is None:
        return
    risk = choose("Risk rating", [(r, r.title()) for r in pathway.RISK_LEVELS])
    if not risk:
        return
    print("High or urgent risk puts the student on the same-day pathway and raises a "
          "safeguarding concern.")
    result = run(pathway.triage, auth, referral_id, risk, notes=ask_text("Triage notes"),
                 triage_clinician=ask("Triage clinician (blank = you)"))
    if result is None:
        return
    if result["same_day"] and result["concern_error"]:
        print(f"\n⚠️  Same-day pathway, but the safeguarding concern could not be raised "
              f"({result['concern_error']}). Raise it by hand in Safeguarding now.")
    elif result["same_day"]:
        print(f"\n⚠️  Same-day pathway: safeguarding concern #{result['concern_id']} raised. "
              "Allocate today.")
    else:
        print("\n✅ Triaged.")


def _waiting(auth) -> None:
    rows = run(pathway.waiting_list, auth) or []
    table(rows, WAITING_COLUMNS, "Nobody is waiting")
    if not rows or not yes("Allocate one?"):
        return
    referral_id = _referral_id()
    people = run(pathway.counsellors, auth, active_only=True) or []
    if referral_id is None:
        return
    if not people:
        print("\nNo active counsellors. Add one first.")
        return
    counsellor = choose("Counsellor", [(p["counselor_id"],
                                        f"{p['name']} ({p['open_caseload']} open)")
                                       for p in people])
    if counsellor is not None:
        run(pathway.allocate, auth, referral_id, counsellor,
            session_cap=ask("Session cap", pathway.DEFAULT_SESSION_CAP), done="Allocated.")


def _show_case(auth, referral_id) -> dict | None:
    case = run(pathway.case_detail, auth, referral_id)
    if not case:
        return None
    ref, student = case["referral"], case["student"]
    print(f"\nReferral #{ref['referral_id']} — {student['name']} ({ref['student_id']}) — "
          f"{ref['status_label']}")
    print(f"Risk: {ref.get('risk_rating') or 'not triaged'}; pathway "
          f"{ref.get('pathway') or 'none'}; counsellor "
          f"{case['counsellor'].get('name') or 'not allocated'}; cap "
          f"{ref.get('session_cap') or 'not set'}")
    for key, label in (("reason", "Reason"), ("triage_notes", "Triage notes"),
                       ("discharge_summary", "Discharge summary")):
        if ref.get(key):
            print(f"{label}: {ref[key]}")
    print("\nSessions:")
    table(case["sessions"], SESSION_COLUMNS)
    print("\nOutcome measures:")
    table(case["measures"], MEASURE_COLUMNS)
    print("\nCase notes:")
    table(case["notes"], NOTE_COLUMNS)
    return case


def _record_measure(auth, referral_id) -> None:
    code = choose("Measure", [(c, m.title) for c, m in outcome_measures.MEASURES.items()])
    stage = choose("Stage", [(s, s) for s in outcome_measures.STAGES])
    if not code or not stage:
        return
    measure = outcome_measures.get(code)
    print("Answers: " + ", ".join(f"{i} = {a}" for i, a in enumerate(measure.answers)))
    answers = [ask(f"{number}. {item}") for number, item in enumerate(measure.items, start=1)]
    result = run(pathway.record_measure, auth, referral_id, code, stage, answers)
    if result is None:
        return
    print(f"\n{result['measure']}: {result['total']} of {result['max_total']} ({result['band']}).")
    if result["risk_flag"]:
        print(f"⚠️  The risk item was scored {result['risk_item_score']}. Review the risk now "
              "and escalate if needed.")


def _case_menu(auth) -> None:
    referral_id = _referral_id()
    if referral_id is None:
        return
    while True:
        if not _show_case(auth, referral_id):
            return
        print("\n1. Book a session\n2. Record a session\n3. Add an outcome measure"
              "\n4. Add a case note\n5. Change the session cap\n6. Escalate to crisis"
              "\n0. Return")
        choice = input("\nEnter your choice: ").strip()
        if choice == "0":
            return
        if choice == "1":
            run(pathway.book_session, auth, referral_id,
                ask("Date (YYYY-MM-DD)", date.today().isoformat()), ask("Time (HH:MM)", "10:00"),
                mode=ask("Mode (in-person / online / telephone)", "in-person"),
                done="Session booked.")
        elif choice == "2":
            raw = ask("Session ID")
            status = choose("Status", [(s, s) for s in pathway.SESSION_STATUSES[1:]])
            if raw.isdigit() and status:
                run(pathway.record_session, auth, int(raw), status,
                    notes=ask_text("Clinical notes") or None,
                    outcome=ask("Outcome") or None, done="Recorded.")
        elif choice == "3":
            _record_measure(auth, referral_id)
        elif choice == "4":
            run(pathway.add_case_note, auth, referral_id, ask_text("Note"), done="Saved.")
        elif choice == "5":
            run(pathway.extend_cap, auth, referral_id, ask("New cap"),
                ask_text("Clinical reason"), done="Cap changed.")
        elif choice == "6":
            result = run(pathway.escalate, auth, referral_id, ask_text("The risk identified"))
            if result and result["concern_error"]:
                print(f"\n⚠️  Escalated, but the safeguarding concern could not be raised "
                      f"({result['concern_error']}). Raise it by hand now.")
            elif result:
                print(f"\n✅ Safeguarding concern #{result['concern_id']} raised.")


def _caseload(auth) -> None:
    table(run(pathway.caseload, auth) or [], CASELOAD_COLUMNS, "No allocated episodes")


def _decline(auth) -> None:
    referral_id = _referral_id()
    if referral_id is not None:
        run(pathway.decline, auth, referral_id,
            ask_text("Where has the student been signposted, and why?"), done="Referral closed.")


def _discharge(auth) -> None:
    _caseload(auth)
    referral_id = _referral_id()
    if referral_id is None:
        return
    reason = choose("Reason", [(r, r) for r in pathway.DISCHARGE_REASONS])
    if not reason:
        return
    print("Remember the last-session outcome measures before discharging.")
    summary = ask_text("Discharge summary")
    if not yes(f"Discharge referral #{referral_id}? Future sessions are cancelled"):
        return
    cancelled = run(pathway.discharge, auth, referral_id, reason, summary=summary)
    if cancelled is not None:
        print(f"\n✅ Discharged; {cancelled} future session(s) cancelled.")


def _reports(auth) -> None:
    start = ask("From (YYYY-MM-DD, blank for all)") or None
    end = ask("To (YYYY-MM-DD, blank for all)") or None
    waits = run(reports.wait_times, auth, start, end)
    results = run(reports.outcomes, auth, start, end)
    if waits is not None and results is not None:
        print("\n" + reports.as_text(waits, results))


def _counsellors(auth) -> None:
    table(run(pathway.counsellors, auth) or [], COUNSELLOR_COLUMNS, "No counsellors registered")
    print("\n1. Add a counsellor\n2. Activate / deactivate\n0. Return")
    choice = input("\nEnter your choice: ").strip()
    if choice == "1":
        raw = ask("Max appointments a day", 8)
        if not raw.isdigit():
            print("\n❌ That must be a whole number.")
            return
        run(pathway.register_counsellor, auth, ask("Username (sign-in)"), ask("Name"),
            specialization=ask("Specialism"), qualifications=ask("Qualifications"),
            availability_schedule=ask("Availability"), max_daily_appointments=int(raw),
            done="Counsellor added.")
    elif choice == "2":
        raw = ask("Counsellor #")
        if raw.isdigit():
            run(pathway.set_counsellor_active, auth, int(raw), yes("Active?"), done="Saved.")


def _team_menu(auth) -> None:
    options = (("1", "Referrals awaiting triage", _triage),
               ("2", "New referral", lambda a: _refer(a, False)),
               ("3", "Close a referral with signposting", _decline),
               ("4", "Waiting list", _waiting),
               ("5", "Caseload", _caseload),
               ("6", "Open a case (sessions, measures, notes)", _case_menu),
               ("7", "Discharge", _discharge),
               ("8", "Reports", _reports),
               ("9", "Counsellors", _counsellors))
    while True:
        print("\n" + "=" * 50 + "\n  COUNSELLING SERVICE\n" + "=" * 50)
        print("Counselling records are confidential to the counselling team.")
        for key, label, _fn in options:
            print(f"{key}. {label}")
        print("0. Return")
        choice = input("\nEnter your choice: ").strip()
        if choice == "0":
            return
        for key, _label, fn in options:
            if choice == key:
                fn(auth)
                pause()
                break


def run_menu(auth=None) -> None:
    """The menu for whoever is signed in (see the module)."""
    if auth is None:
        from education_system.systems.university.infrastructure.shared_context import get_auth
        auth = get_auth()
    if access.is_counselling_team(auth):
        _team_menu(auth)
    elif access.own_student_id(auth):
        _student_menu(auth)
    elif access.is_staff(auth):
        print("\nYou can refer a student to the counselling team. You will not see the "
              "referral's progress or any clinical record.")
        _refer(auth, False)
        pause()
    else:
        print("\nSign in as a student or a member of staff to use the counselling service.")
