"""Support to Study — CLI twin of the Wellbeing Casework tab.

Support staff work every case; a student sees their own.
"""

from __future__ import annotations

from education_system.systems.university.domains.student_support.domain.wellbeing.casework import (
    access,
)
from education_system.systems.university.domains.student_support.domain.wellbeing.casework import (
    support_to_study as sts,
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

CASE_COLUMNS = (("case_id", "#", 5), ("student_id", "Student", 10), ("student_name", "Name", 22),
                ("stage", "Stage", 5), ("status", "Status", 7), ("next_meeting", "Next mtg", 11),
                ("open_actions", "Actions", 7))


def show_case(auth, case_id) -> dict | None:
    case = run(sts.case_detail, auth, case_id)
    if not case:
        return None
    print(f"\nCase #{case['case_id']} — {case['student_name']} ({case['student_id']})")
    print(f"{case['stage_label']} — {case['status']} — case manager "
          f"{case.get('case_manager') or '—'}")
    print(f"Concern: {case.get('reason') or ''}")
    print("\nMeetings:")
    table(case["meetings"], (("meeting_id", "#", 5), ("stage", "St", 3),
                             ("meeting_date", "Date", 11), ("meeting_time", "Time", 6),
                             ("status", "Status", 10), ("summary", "Summary", 50)))
    print("\nAction plan:")
    table(case["actions"], (("action_id", "#", 5), ("action_text", "Action", 46),
                            ("owner", "Owner", 12), ("due_date", "Due", 11),
                            ("status", "Status", 9)))
    print("\nOutcomes:")
    table(case["outcomes"], (("outcome_id", "#", 5), ("stage", "St", 3),
                             ("outcome_type", "Outcome", 26), ("decision", "Decision", 46)))
    print("\nLetters:")
    table(case["letters"], (("letter_id", "#", 5), ("kind", "Letter", 12), ("path", "File", 70)))
    print("\nLinked records:")
    table(case["links"], (("link_id", "#", 5), ("kind", "Record", 22), ("ref_id", "No.", 8),
                          ("note", "Note", 40)))
    return case


def _open_case(auth):
    sid = ask("Student number")
    stage = ask("Start at stage (1/2/3)", "1")
    reason = ask_text("The concern")
    manager = ask("Case manager username (blank = you)")
    case_id = run(sts.open_case, auth, sid, reason, stage=int(stage or 1),
                  case_manager=manager or None, done="Case opened.")
    if case_id:
        show_case(auth, case_id)


def _outcome(auth, case):
    options = [(o, sts.OUTCOME_LABELS[o]) for o in sts.OUTCOMES[case["stage"]]]
    kind = choose("Outcome", options)
    if not kind:
        return
    decision = ask_text("Decision and reasons")
    review = ask("Review date (YYYY-MM-DD, optional)")
    effective = returning = None
    if kind in sts.INTERRUPTING:
        print("This interrupts the student's studies through the student lifecycle.")
        if not yes("Continue"):
            return
        effective = ask("Interruption from (YYYY-MM-DD, blank = today)") or None
        returning = ask("Expected return (YYYY-MM-DD, optional)") or None
    run(sts.record_outcome, auth, case["case_id"], kind, decision, review_date=review or None,
        effective_date=effective, expected_return_date=returning, done="Outcome recorded.")


def _letter(auth, case):
    kind = choose("Letter", [("invitation", "Meeting invitation (latest meeting)"),
                             ("action_plan", "Action plan"), ("outcome", "Outcome (latest)")])
    if kind:
        path = run(sts.generate_letter, auth, case["case_id"], kind)
        if path:
            print(f"\n✅ Letter written to {path}")


def _link(auth, case):
    kind = choose("Record", [(k, v[2]) for k, v in sts.LINK_KINDS.items()])
    if kind:
        run(sts.link, auth, case["case_id"], kind, ask("Its number"), ask("Note (optional)"),
            done="Linked.")


def _work_case(auth, case_id):  # noqa: C901 - a flat menu
    while True:
        case = show_case(auth, case_id)
        if not case:
            return
        print("\n1. Schedule meeting   2. Record meeting   3. Add action   4. Update action")
        print("5. Record outcome     6. Escalate         7. Letter       8. Link record")
        print("9. Case manager      10. Close case       0. Back")
        choice = input("Choice: ").strip()
        if choice == "0":
            return
        if choice == "1":
            run(sts.schedule_meeting, auth, case_id, ask("Date (YYYY-MM-DD)"),
                meeting_time=ask("Time (HH:MM)"), location=ask("Where"),
                attendees=ask("Attendees"), panel_members=ask("Panel members (stage 3)"),
                done="Meeting scheduled; the student has been invited.")
        elif choice == "2":
            run(sts.record_meeting, auth, int(ask("Meeting #") or 0),
                status=ask("Status (held/cancelled/postponed)", "held"),
                student_attended=yes("Did the student attend"), summary=ask_text("Summary"),
                supporter=ask("Supporter (optional)"), done="Meeting recorded.")
        elif choice == "3":
            run(sts.add_action, auth, case_id, ask("Action"), owner=ask("Owner", "student"),
                due_date=ask("Due (YYYY-MM-DD)") or None, done="Action added.")
        elif choice == "4":
            run(sts.update_action, auth, int(ask("Action #") or 0),
                ask("Status (open/done/missed/cancelled)"), ask("Notes"), done="Updated.")
        elif choice == "5":
            _outcome(auth, case)
        elif choice == "6":
            run(sts.escalate, auth, case_id, ask_text("Why"), done="Moved to the next stage.")
        elif choice == "7":
            _letter(auth, case)
        elif choice == "8":
            _link(auth, case)
        elif choice == "9":
            run(sts.set_case_manager, auth, case_id, ask("Username"), done="Updated.")
        elif choice == "10":
            run(sts.close_case, auth, case_id, ask_text("Reason"), done="Closed.")


def run_menu(auth) -> None:
    try:
        staff = access.support_scope(auth) is None
    except PermissionError as exc:
        print(f"\n❌ {exc}")
        return
    if not staff:
        rows = run(sts.list_cases, auth, include_closed=True) or []
        if not rows:
            print("\nYou have no Support to Study case.")
        for row in rows:
            show_case(auth, row["case_id"])
        pause()
        return
    while True:
        print("\n" + "=" * 50 + "\n  SUPPORT TO STUDY\n" + "=" * 50)
        print("1. Open cases\n2. All cases (incl. closed)\n3. Open a case\n"
              "4. Work a case\n5. Overdue actions\n0. Back")
        choice = input("Choice: ").strip()
        if choice == "0":
            return
        if choice in ("1", "2"):
            table(run(sts.list_cases, auth, include_closed=choice == "2") or [], CASE_COLUMNS)
        elif choice == "3":
            _open_case(auth)
        elif choice == "4":
            case_id = ask("Case #")
            if case_id.isdigit():
                _work_case(auth, int(case_id))
        elif choice == "5":
            table(run(sts.overdue_actions, auth) or [],
                  (("case_id", "Case", 5), ("student_id", "Student", 10),
                   ("action_text", "Action", 46), ("due_date", "Due", 11)))
