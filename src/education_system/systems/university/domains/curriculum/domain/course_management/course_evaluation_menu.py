"""CLI: course evaluation surveys — the same rules as the Course Evaluation
window (``university/application/evaluation/course``). Imports only the
application layer."""

from __future__ import annotations

from contextlib import closing

from education_system.systems.university.application.evaluation import course as rules
from education_system.systems.university.application.teaching import (
    occurrences as timetable_occurrences,
)
from education_system.systems.university.infrastructure.database.db import get_connection

_STAFF = ("admin", "administrator", "superadmin", "staff", "instructor", "lecturer", "faculty",
          "teacher")
_ADMIN = ("admin", "administrator", "superadmin")


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


def _ask(q):
    kind = q["question_type"]
    optional = "" if q["is_required"] else " (optional, blank to skip)"
    if kind in rules.NUMERIC:
        value = input(f"{q['question_text']} [{q['scale_min']}–{q['scale_max']}]{optional}: ")
        return int(value) if value.strip().isdigit() else None
    if q["choices"]:
        value = input(f"{q['question_text']} [{' / '.join(q['choices'])}]{optional}: ")
        return value.strip() or None
    return input(f"{q['question_text']}{optional}: ").strip() or None


def _student(student_id):
    rows = _run(rules.student_surveys, student_id, write=True) or []
    if not rows:
        print("There is no course survey for you yet.")
    for i, r in enumerate(rows, 1):
        print(f"  {i}. {r['course_code']} {r['academic_year']} — {r['state']} "
              f"(closes {r['end_date']})")
    for r in _run(rules.published_for_student, student_id) or []:
        print(f"  {r['academic_year']}: you said {r['you_said']} — we did {r['we_did']}")
    pick = input("Survey to answer (number, blank = back): ").strip()
    if not pick.isdigit() or not 0 < int(pick) <= len(rows):
        return
    survey = rows[int(pick) - 1]
    if survey["state"] != "open":
        print("You have already answered it — thank you." if survey["state"] == "answered"
              else "That survey is not open.")
        return
    print("This survey is anonymous.")
    answers = {}
    for q in _run(rules.questions, survey["evaluation_id"]) or []:
        if rules.should_show(q, answers):
            value = _ask(q)
            if value is not None:
                answers[q["question_id"]] = value
    result = _run(rules.submit, survey["evaluation_id"], student_id, answers, write=True)
    if isinstance(result, dict):
        print("Thank you — recorded anonymously.")


def _results(survey, username, admin):
    res = _run(rules.results, survey["evaluation_id"], username, admin)
    if not isinstance(res, dict):
        return
    print(f"{res['responses']} of {res['invited']} answered.")
    if res["withheld"]:
        print(f"Results hidden until {res['threshold']} have answered.")
    else:
        comp = res["comparison"]
        print(f"Overall {res['overall'] or '—'} · last year {comp['last_year'] or '—'} · "
              f"department {comp['department'] or '—'}")
        for q in res["questions"]:
            print(f"  {q['mean'] or '—':>5}  {q['question_text']}")
        for c in res["comments"]:
            print(f"  • {c}")
    for m in res["modules"]:
        print(f"  module {m['module_code']}: {'hidden' if m['withheld'] else m['overall']}")


def _open(username, admin):
    code = input("Course code: ").strip()
    window = _run(rules.default_window)
    start = input(f"Opens [{window[0] if window else ''}]: ").strip() or None
    end = input(f"Closes [{window[1] if window else ''}]: ").strip() or None
    made = _run(rules.open_survey, code, opens_at=start, closes_at=end, actor=username,
                admin=admin, write=True)
    if isinstance(made, dict):
        print(f"Open {made['opens']} → {made['closes']}; {made['invited']} invited.")


def _review(username):
    for c in _run(rules.review_queue) or []:
        print(f"  #{c['answer_id']} {c['course_code']} ({c['reason']}): {c['text_value']}")
        decision = input("  Release (r), withhold (w), skip: ").strip().lower()
        if decision in ("r", "w"):
            _run(rules.review_comment, c["answer_id"], decision == "r", username, write=True)


def _team(username, admin):
    code = input("Course code: ").strip()
    for p in _run(rules.team, code) or []:
        print(f"  {p['username']:<16} {p['role']:<14} {p['name']}")
    who = input("Add staff username (blank = back): ").strip()
    if who:
        role = "leader" if admin and input("As leader? (y/N): ").lower() == "y" else "member"
        if admin or _run(rules.leader, code) == username:
            _run(rules.set_team_member, code, who, role, username, write=True)
        else:
            print("Only the course leader or an admin edits the team.")


def _respond(survey, username, admin):
    values = [input(f"{label}: ").strip() for label in (
        "What the results told us", "Actions", "You said", "We did")]
    rid = _run(rules.respond, survey["evaluation_id"], *values, actor=username, admin=admin,
               write=True)
    if rid and input("Publish to students now? (y/N): ").strip().lower() == "y":
        _run(rules.publish, rid, username, admin, write=True) and print("Published.")


def _staff(username, admin):
    _run(rules.send_reminders, write=True)
    rows = _run(rules.surveys, viewer=username, admin=admin) or []
    for i, s in enumerate(rows, 1):
        print(f"  {i}. {s['course_code']} {s['academic_year']} {s['state']} — "
              f"{s['responses']}/{s['invited']} responded ({s['access']})")
    choice = input("1. Open a survey  2. Results  3. Respond to students  4. Close  "
                   "5. Send reminders  6. Course team  7. Review comments  0. Back: ").strip()
    simple = {"1": lambda: _open(username, admin), "6": lambda: _team(username, admin),
              "5": lambda: print(f"{(_run(rules.send_reminders, write=True) or {}).get('sent', 0)}"
                                 " reminder(s) sent."),
              "7": lambda: _review(username) if admin else print("Admins review comments.")}
    if choice in simple:
        simple[choice]()
        return
    pick = input("Survey number: ").strip() if choice in ("2", "3", "4") else ""
    if not pick.isdigit() or not 0 < int(pick) <= len(rows):
        return
    survey = rows[int(pick) - 1]
    if choice == "2":
        _results(survey, username, admin)
    elif choice == "3":
        _respond(survey, username, admin)
    else:
        _run(rules.close_survey, survey["evaluation_id"], username, admin, write=True) and \
            print("Closed.")


def display_course_evaluation_menu(auth):
    username, role, student_id = _user(auth)
    if role in _STAFF:
        _staff(username, role in _ADMIN)
    else:
        _student(student_id)
