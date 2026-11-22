"""CLI: module evaluation surveys — the same rules as the Module Evaluation
portal (``university/application/evaluation/module``). Imports only the
application layer."""

from __future__ import annotations

from contextlib import closing

from education_system.systems.university.application.evaluation import module as rules
from education_system.systems.university.application.teaching import (
    occurrences as timetable_occurrences,
)
from education_system.systems.university.infrastructure.database.db import get_connection

_STAFF = ("admin", "administrator", "superadmin", "staff", "instructor", "lecturer", "faculty")


def _run(fn, *args, write=False, **kwargs):
    try:
        with closing(get_connection(row_factory=False)) as conn:
            result = fn(conn, *args, **kwargs)
            if write:
                conn.commit()
    except ValueError as exc:
        print(f"Refused: {exc}")
        return None
    emails = result.get("emails") if isinstance(result, dict) else None
    if write and emails:
        timetable_occurrences.send_emails(emails)
    return True if result is None else result


def _user(auth):
    user = getattr(auth, "current_user", None) or {}
    if not isinstance(user, dict):
        user = {"username": getattr(user, "username", None), "role": getattr(user, "role", "")}
    return user.get("username") or "", str(user.get("role") or "").lower(), \
        user.get("student_id") or user.get("username")


def _student(student_id):
    rows = _run(rules.student_surveys, student_id, write=True) or []
    for i, r in enumerate(rows, 1):
        print(f"  {i}. {r['module_code']} {r['academic_year']} — {r['state']}")
    pick = input("Survey to answer (number, blank = back): ").strip()
    if not pick.isdigit() or not 0 < int(pick) <= len(rows):
        return
    survey = rows[int(pick) - 1]
    if survey["state"] != "open":
        print("That survey is not open.")
        return
    answers = {}
    for q in _run(rules.questions, survey["id"]) or []:
        if q["question_type"] == "text":
            answers[q["id"]] = (None, input(f"{q['question_text']} (optional): ").strip() or None)
            continue
        scale = "1 Strongly disagree … 5 Strongly agree" if q["question_type"] == "likert" \
            else "1 Poor … 5 Excellent"
        value = input(f"{q['question_text']} [{scale}]: ").strip()
        answers[q["id"]] = (int(value) if value in ("1", "2", "3", "4", "5") else None, None)
    result = _run(rules.submit, survey["id"], student_id, answers, write=True)
    if isinstance(result, dict):
        print("Thank you — recorded anonymously.")
    for r in _run(rules.published_for_student, student_id) or []:
        print(f"  {r['module_code']}: you said {r['you_said']} — we did {r['we_did']}")


def _staff(username, admin):
    rows = _run(rules.forms_for, staff=username, admin=admin) or []
    for i, f in enumerate(rows, 1):
        print(f"  {i}. {f['module_code']} {f['academic_year']} {f['state']} — "
              f"{f['responses']}/{f['invited']} responded")
    choice = input("1. Open a survey  2. Results  3. Respond to students  4. Close  "
                   "5. Send reminders  6. Review comments  0. Back: ").strip()
    if choice == "1":
        code = input("Module code: ").strip()
        window = _run(rules.default_window, code)
        start = input(f"Opens [{window[0] if window else ''}]: ").strip() or None
        end = input(f"Closes [{window[1] if window else ''}]: ").strip() or None
        made = _run(rules.open_survey, code, opens_at=start, closes_at=end, actor=username,
                    write=True)
        if isinstance(made, dict):
            print(f"Open {made['opens']} → {made['closes']}; {made['invited']} invited.")
        return
    if choice == "5":
        result = _run(rules.send_reminders, write=True)
        print(f"{result['sent']} reminder(s) sent." if isinstance(result, dict) else "")
        return
    if choice == "6":
        for c in _run(rules.review_queue) or []:
            print(f"  #{c['answer_id']} {c['module_code']} ({c['reason']}): {c['text_value']}")
            decision = input("  Release (r), withhold (w), skip: ").strip().lower()
            if decision in ("r", "w"):
                _run(rules.review_comment, c["answer_id"], decision == "r", username, write=True)
        return
    pick = input("Survey number: ").strip()
    if not pick.isdigit() or not 0 < int(pick) <= len(rows):
        return
    f = rows[int(pick) - 1]
    if choice == "2":
        res = _run(rules.results, f["id"], username, admin)
        if not isinstance(res, dict):
            return
        print(f"{res['responses']} of {res['invited']} answered.")
        if res["withheld"]:
            print(f"Results hidden until {res['threshold']} have answered.")
            return
        for q in res["questions"]:
            print(f"  {q['mean'] or '—':>5}  {q['question_text']}")
        for c in res["comments"]:
            print(f"  • {c}")
    elif choice == "3":
        values = [input(f"{label}: ").strip() for label in (
            "What the results told us", "Actions", "You said", "We did")]
        rid = _run(rules.respond, f["id"], *values, actor=username, write=True)
        if rid and input("Publish to students now? (y/N): ").strip().lower() == "y":
            _run(rules.publish, rid, username, write=True) and print("Published.")
    elif choice == "4":
        _run(rules.close_survey, f["id"], write=True) and print("Closed.")


def display_module_evaluation_menu(auth):
    username, role, student_id = _user(auth)
    if role in _STAFF:
        _staff(username, role in ("admin", "administrator", "superadmin"))
    else:
        _student(student_id)
