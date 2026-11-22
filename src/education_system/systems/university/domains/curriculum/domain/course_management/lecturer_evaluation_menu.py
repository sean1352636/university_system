"""CLI: lecturer evaluation — the same rules as the Lecturer Evaluation
window (``university/application/evaluation/lecturer`` and
``lecturer_feedback``). Imports only the application layer."""

from __future__ import annotations

from contextlib import closing

from education_system.systems.university.application.evaluation import lecturer as rules
from education_system.systems.university.application.evaluation import (
    lecturer_feedback as feedback,
)
from education_system.systems.university.application.teaching import (
    occurrences as timetable_occurrences,
)
from education_system.systems.university.infrastructure.database.db import get_connection

_STAFF = ("admin", "administrator", "superadmin", "staff", "instructor", "lecturer", "faculty",
          "teacher")


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
    rows = _run(rules.student_lecturers, student_id, write=True) or []
    if not rows:
        print("No module survey with lecturers yet.")
    for i, r in enumerate(rows, 1):
        print(f"  {i}. {r['module_code']} {r['academic_year']} — {r['name']}: {r['state']}")
    for r in _run(rules.published_for_student, student_id) or []:
        print(f"  {r['name']} ({r['module_code']}): you said {r['you_said']} — "
              f"we did {r['we_did']}")
    pick = input("Lecturer to rate (number, blank = back): ").strip()
    if not pick.isdigit() or not 0 < int(pick) <= len(rows):
        return
    r = rows[int(pick) - 1]
    if r["state"] != "open":
        print("You have already rated them — thank you." if r["state"] == "answered"
              else "Rating is not open for this module.")
        return
    print("This is anonymous. Rate 1 (poor) to 5 (excellent).")
    ratings = {}
    for key, label, desc in rules.CRITERIA:
        value = input(f"{label} — {desc}: ").strip()
        if value.isdigit():
            ratings[key] = int(value)
    comments = input("Comments (optional): ")
    if isinstance(_run(rules.submit, r["form_id"], r["lecturer"], student_id, ratings, comments,
                       write=True), dict):
        print("Thank you — recorded anonymously.")


def _show(lecturer, username, admin):
    res = _run(feedback.results, lecturer, username, admin)
    if not isinstance(res, dict):
        return
    comp = res["comparison"]
    print(f"{res['name']}: last year {comp['last_year'] or '—'} · department "
          f"{comp['department']['overall'] or '—'}")
    for t in res["trend"]:
        print(f"  {t['academic_year']}: overall {t['overall'] or '—'} ({t['responses']})")
    for m in res["modules"]:
        print(f"  {m['module_code']} {m['academic_year']}: {m['responses']}/{m['invited']}")
        if m["withheld"]:
            print(f"    hidden until {m['threshold']} have answered")
            continue
        for key, label, _d in rules.CRITERIA:
            print(f"    {label:<24} {m['means'][key]}")
        for c in m["comments"]:
            print(f"    • {c}")


def _reflect(lecturer, username, admin):
    res = _run(feedback.results, lecturer, username, admin)
    modules = res["modules"] if isinstance(res, dict) else []
    for i, m in enumerate(modules, 1):
        print(f"  {i}. {m['module_code']} {m['academic_year']}")
    pick = input("Module survey (number): ").strip()
    if not pick.isdigit() or not 0 < int(pick) <= len(modules):
        return
    values = [input(f"{label}: ").strip() for label in (
        "Reflection", "Actions", "You said (for students)", "We did (for students)")]
    rid = _run(rules.reflect, modules[int(pick) - 1]["form_id"], lecturer, *values,
               actor=username, admin=admin, write=True)
    if rid and input("Publish 'you said, we did' to students? (y/N): ").lower() == "y":
        _run(rules.publish_reflection, rid, username, admin, write=True) and print("Published.")


def _review(username):
    for c in _run(rules.review_queue) or []:
        print(f"  #{c['evaluation_id']} {c['lecturer']} {c['module_code']} ({c['reason']}): "
              f"{c['comments']}")
        decision = input("  Release (r), withhold (w), skip: ").strip().lower()
        if decision in ("r", "w"):
            _run(rules.review_comment, c["evaluation_id"], decision == "r", username, write=True)


def _staff(username, admin):
    _run(rules.send_reminders, write=True)
    people = _run(rules.visible_lecturers, username, admin) or []
    for i, p in enumerate(people, 1):
        print(f"  {i}. {p['name']} ({p['username']}) — {p['access']}")
    choice = input("1. Feedback  2. Reflect / respond  3. Review comments  0. Back: ").strip()
    if choice == "3":
        _review(username) if admin else print("Admins review comments.")
        return
    pick = input("Lecturer (number): ").strip() if choice in ("1", "2") else ""
    if not pick.isdigit() or not 0 < int(pick) <= len(people):
        return
    lecturer = people[int(pick) - 1]["username"]
    (_show if choice == "1" else _reflect)(lecturer, username, admin)


def display_lecturer_evaluation_menu(auth):
    username, role, student_id = _user(auth)
    if role in _STAFF:
        _staff(username, role in rules.ADMIN_ROLES)
    else:
        _student(student_id)
