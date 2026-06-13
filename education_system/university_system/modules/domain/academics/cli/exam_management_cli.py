"""Exam Management CLI — command-line interface for exam management and taking.

Provides menus for:
- Students: browse exams, take exams, view results
- Instructors: manage exams, manage questions, grade, analytics
- Admins: all instructor features plus deletion and export
"""

import logging
from datetime import datetime

from education_system.university_system.modules.domain.academics.services.exam_management import ExamPortalService
from education_system.university_system.modules.domain.academics.cli.exam_seating_cli import (
    display_seating_menu,
)

logger = logging.getLogger(__name__)


def display_exam_portal_menu(auth):
    """Main entry point for the exam portal CLI."""
    svc = ExamPortalService()
    user = auth.current_user if auth and auth.current_user else {}
    role = user.get("role", "student")
    username = user.get("username", "guest")

    # Auto-sync scheduled exams into the portal on entry
    try:
        svc.sync_from_scheduler(created_by=username)
    except Exception:
        pass

    while True:
        print(f"\nExam Management")
        print(f"Logged in as: {username} ({role})")
        print("=" * 50)
        print("1. Browse Available Exams")
        print("2. Take an Exam")
        print("3. My Results")
        if role in ("admin", "staff", "instructor"):
            print("4. Manage Exams")
            print("5. Manage Questions")
            print("6. Grade Submissions")
            print("7. Exam Analytics")
            print("8. Export Results (CSV)")
            print("9. Seating Plans")
        print("0. Back")

        choice = input("\nChoice: ").strip()

        if choice == "1":
            _browse_exams(svc, username)
        elif choice == "2":
            _take_exam(svc, username)
        elif choice == "3":
            _view_results(svc, username)
        elif choice == "4" and role in ("admin", "staff", "instructor"):
            _manage_exams(svc, username, role)
        elif choice == "5" and role in ("admin", "staff", "instructor"):
            _manage_questions(svc)
        elif choice == "6" and role in ("admin", "staff", "instructor"):
            _grade_submissions(svc, username)
        elif choice == "7" and role in ("admin", "staff", "instructor"):
            _show_analytics(svc)
        elif choice == "8" and role in ("admin", "staff", "instructor"):
            _export_results(svc)
        elif choice == "9" and role in ("admin", "staff", "instructor"):
            display_seating_menu(auth)
        elif choice == "0":
            break
        else:
            print("Invalid choice.")


# ── Browse Exams ────────────────────────────────────────────────────

def _browse_exams(svc, student_id):
    exams = svc.list_available_exams(student_id)
    if not exams:
        print("\nNo exams available.")
        input("Press Enter...")
        return

    print(f"\nAvailable Exams ({len(exams)}):")
    print(f"{'ID':<5} {'Title':<30} {'Module':<10} {'Duration':<10} {'Attempts':<10}")
    print("-" * 70)
    for e in exams:
        print(f"{e['id']:<5} {e['title'][:28]:<30} {e.get('module_code', ''):<10} "
              f"{e['duration_minutes']} min    {e.get('attempt_count', 0)}/{e['max_attempts']}")
    input("\nPress Enter...")


# ── Take Exam ───────────────────────────────────────────────────────

def _take_exam(svc, student_id):
    exams = svc.list_available_exams(student_id)
    if not exams:
        print("\nNo exams available to take.")
        input("Press Enter...")
        return

    _browse_exams(svc, student_id)
    exam_id = input("\nEnter exam ID to start (or 0 to cancel): ").strip()
    if exam_id == "0":
        return
    try:
        exam_id = int(exam_id)
    except ValueError:
        print("Invalid ID.")
        return

    exam = svc.get_exam(exam_id)
    if not exam:
        print("Exam not found.")
        return

    qcount = svc.get_question_count(exam_id)
    print(f"\n--- {exam['title']} ---")
    print(f"Duration: {exam['duration_minutes']} minutes")
    print(f"Questions: {qcount}")
    print(f"Pass mark: {exam.get('pass_mark', 50)}%")
    if exam.get("instructions"):
        print(f"\nInstructions: {exam['instructions']}")

    confirm = input("\nStart exam? (y/n): ").strip().lower()
    if confirm != "y":
        return

    attempt = svc.start_attempt(exam_id, student_id, student_name=student_id)
    if not attempt:
        print("Cannot start exam. Maximum attempts may have been reached.")
        return
    if attempt.get("error"):
        print(f"Cannot start exam: {attempt.get('reason', attempt['error'])}")
        return

    # Surface any applied accommodations so the candidate knows their timer is
    # correct and any extra support (scribe, separate room) is on record.
    if attempt.get("accommodation_summary"):
        mins = attempt.get("extra_seconds", 0) // 60
        baseline = exam["duration_minutes"]
        print()
        print(f"Accommodations applied: {attempt['accommodation_summary']}")
        if mins:
            print(f"Timer: {baseline} min baseline + {mins} min extra "
                  f"= {baseline + mins} min total")

    shuffle = bool(exam.get("shuffle_questions"))
    questions = svc.get_questions(exam_id, shuffle=shuffle)

    print(f"\nExam started! {len(questions)} questions. Answer each one.")
    print("Commands: 'skip' to skip, 'flag' to flag, 'review' to see flagged, 'submit' to finish.\n")

    answers = {}
    flagged = set()
    i = 0

    while i < len(questions):
        q = questions[i]
        flag_marker = " [FLAGGED]" if q["id"] in flagged else ""
        print(f"\nQuestion {i + 1}/{len(questions)} ({q['marks']} marks) [{q['question_type'].upper()}]{flag_marker}")
        print(f"  {q['question_text']}")

        if q["question_type"] in ("mcq", "true_false"):
            options = q.get("options", [])
            if q["question_type"] == "true_false":
                options = ["True", "False"]
            for j, opt in enumerate(options, 1):
                print(f"    {j}. {opt}")
            saved = answers.get(q["id"], "")
            ans = input(f"  Your answer [{saved}]: ").strip()
        else:
            saved = answers.get(q["id"], "")
            ans = input(f"  Your answer [{saved}]: ").strip()

        if ans.lower() == "skip":
            i += 1
            continue
        elif ans.lower() == "flag":
            flagged.add(q["id"])
            print("  Flagged for review.")
            continue
        elif ans.lower() == "review":
            if flagged:
                print("\n  Flagged questions:")
                for fi, fq in enumerate(questions):
                    if fq["id"] in flagged:
                        print(f"    Q{fi + 1}: {fq['question_text'][:60]}")
            else:
                print("  No flagged questions.")
            continue
        elif ans.lower() == "submit":
            break

        # Process MCQ answer by number
        if q["question_type"] in ("mcq", "true_false") and ans.isdigit():
            options = q.get("options", [])
            if q["question_type"] == "true_false":
                options = ["True", "False"]
            idx = int(ans) - 1
            if 0 <= idx < len(options):
                ans = options[idx]

        if ans:
            answers[q["id"]] = ans
            svc.save_answer(attempt["id"], q["id"], ans, flagged=q["id"] in flagged)

        i += 1

    # Submit
    total = len(questions)
    answered = len(answers)
    print(f"\nAnswered: {answered}/{total}")
    if flagged:
        print(f"Flagged: {len(flagged)}")

    confirm = input("Submit exam? (y/n): ").strip().lower()
    if confirm != "y":
        print("Exam NOT submitted. Your answers are saved — you can resume later.")
        return

    result = svc.submit_attempt(attempt["id"])
    print(f"\n{'='*40}")
    print(f"Score: {result['score']}/{result['total_marks']}")
    print(f"Percentage: {result['percentage']}%")
    print(f"Result: {'PASSED' if result['passed'] else 'FAILED'}")
    if result.get("needs_manual_grading"):
        print("Some questions require manual grading.")
    print("=" * 40)
    input("\nPress Enter...")


# ── View Results ────────────────────────────────────────────────────

def _view_results(svc, student_id):
    attempts = svc.get_student_attempts(student_id)
    if not attempts:
        print("\nNo exam results found.")
        input("Press Enter...")
        return

    print(f"\nMy Exam Results ({len(attempts)}):")
    print(f"{'ID':<5} {'Exam':<25} {'Score':<12} {'%':<8} {'Result':<8} {'Status':<10} {'Date':<16}")
    print("-" * 90)
    for a in attempts:
        result = "PASS" if a.get("passed") else ("FAIL" if a.get("passed") is not None else "Pending")
        print(f"{a['id']:<5} {(a.get('exam_title', '') or '')[:23]:<25} "
              f"{a.get('score', '-')}/{a.get('total_marks', '-')}   "
              f"{a.get('percentage', '-'):<8} {result:<8} {a['status']:<10} "
              f"{(a.get('submitted_at', '') or '')[:16]}")

    # Option to review
    choice = input("\nEnter attempt ID to review (or 0 to go back): ").strip()
    if choice == "0" or not choice:
        return
    try:
        attempt_id = int(choice)
    except ValueError:
        return

    attempt = svc.get_attempt(attempt_id)
    if not attempt:
        print("Attempt not found.")
        return

    exam = svc.get_exam(attempt["exam_id"])
    if not exam or not exam.get("allow_review"):
        print("Review is not available for this exam.")
        input("Press Enter...")
        return

    questions = svc.get_questions(attempt["exam_id"])
    answers_list = svc.get_answers(attempt_id)
    answer_map = {a["question_id"]: a for a in answers_list}

    print(f"\n--- Review: {exam['title']} ---")
    print(f"Score: {attempt.get('score', '-')}/{exam['total_marks']} ({attempt.get('percentage', '-')}%)\n")

    for i, q in enumerate(questions, 1):
        a = answer_map.get(q["id"], {})
        print(f"Q{i}. [{q['question_type'].upper()}] ({q['marks']} marks)")
        print(f"   {q['question_text']}")
        print(f"   Your answer: {a.get('answer_text', '(none)')}")
        if q.get("correct_answer"):
            print(f"   Correct: {q['correct_answer']}")
        print(f"   Marks: {a.get('marks_awarded', 0)}/{q['marks']}")
        if a.get("feedback"):
            print(f"   Feedback: {a['feedback']}")
        print()

    input("Press Enter...")


# ── Import from Scheduler ───────────────────────────────────────────

def _import_from_scheduler(svc, username):
    print("\nImporting exams from Exam Scheduler...")
    result = svc.sync_from_scheduler(created_by=username)

    if result.get("error"):
        print(f"Error: {result['error']}")
    else:
        print(f"\nImported: {result['imported']} exam(s)")
        print(f"Skipped (already imported): {result['skipped']}")
        if result['imported'] > 0:
            print("\nAdd questions with 'Manage Questions' and publish when ready.")
    input("\nPress Enter...")


# ── Manage Exams ────────────────────────────────────────────────────

def _manage_exams(svc, username, role):
    exams = svc.list_exams(created_by=username if role != "admin" else None)
    if not exams:
        print("\nNo exams found.")
        input("Press Enter...")
        return

    print(f"\nYour Exams ({len(exams)}):")
    print(f"{'ID':<5} {'Title':<30} {'Status':<10} {'Questions':<10} {'Duration':<10}")
    print("-" * 70)
    for e in exams:
        qcount = svc.get_question_count(e["id"])
        print(f"{e['id']:<5} {e['title'][:28]:<30} {e['status']:<10} {qcount:<10} {e['duration_minutes']} min")

    print("\nActions: [P]ublish  [U]npublish  [D]elete  [0] Back")
    action = input("Enter action + exam ID (e.g. P 3): ").strip()
    if action == "0":
        return

    parts = action.split()
    if len(parts) != 2:
        return
    cmd, eid = parts[0].upper(), int(parts[1])

    if cmd == "P":
        if svc.get_question_count(eid) == 0:
            print("Add questions before publishing.")
        else:
            svc.publish_exam(eid)
            print("Exam published.")
    elif cmd == "U":
        svc.unpublish_exam(eid)
        print("Exam unpublished (draft).")
    elif cmd == "D":
        confirm = input("Are you sure? (y/n): ").strip().lower()
        if confirm == "y":
            svc.delete_exam(eid)
            print("Exam deleted.")

    input("Press Enter...")


# ── Manage Questions ────────────────────────────────────────────────

def _manage_questions(svc):
    exam_id = input("\nEnter exam ID: ").strip()
    try:
        exam_id = int(exam_id)
    except ValueError:
        print("Invalid ID.")
        return

    exam = svc.get_exam(exam_id)
    if not exam:
        print("Exam not found.")
        return

    while True:
        questions = svc.get_questions(exam_id)
        print(f"\nQuestions for: {exam['title']} ({len(questions)} total)")
        print(f"{'#':<4} {'Type':<12} {'Marks':<7} Question")
        print("-" * 60)
        for i, q in enumerate(questions, 1):
            print(f"{i:<4} {q['question_type']:<12} {q['marks']:<7} {q['question_text'][:50]}")

        print("\n[A]dd  [D]elete #  [0] Back")
        action = input("Choice: ").strip()

        if action == "0":
            break
        elif action.upper() == "A":
            _add_question(svc, exam_id)
        elif action.upper().startswith("D"):
            parts = action.split()
            if len(parts) == 2:
                try:
                    idx = int(parts[1]) - 1
                    if 0 <= idx < len(questions):
                        svc.delete_question(questions[idx]["id"])
                        print("Question deleted.")
                except (ValueError, IndexError):
                    print("Invalid question number.")


def _add_question(svc, exam_id):
    print("\nQuestion types: mcq, true_false, short_answer, essay, fill_blank")
    qtype = input("Type: ").strip().lower()
    if qtype not in ("mcq", "true_false", "short_answer", "essay", "fill_blank"):
        print("Invalid type.")
        return

    text = input("Question text: ").strip()
    if not text:
        return

    options = None
    correct = None

    if qtype == "mcq":
        print("Enter options (one per line, empty line to finish):")
        options = []
        while True:
            opt = input(f"  Option {len(options) + 1}: ").strip()
            if not opt:
                break
            options.append(opt)
        correct = input("Correct answer (exact text): ").strip()
    elif qtype == "true_false":
        correct = input("Correct answer (True/False): ").strip()
    elif qtype in ("short_answer", "fill_blank"):
        correct = input("Correct answer: ").strip()

    marks = input("Marks [1]: ").strip()
    difficulty = input("Difficulty (easy/medium/hard) [medium]: ").strip()

    svc.add_question(
        exam_id, qtype, text,
        marks=float(marks) if marks else 1.0,
        options=options,
        correct_answer=correct or None,
        difficulty=difficulty or "medium",
    )
    print("Question added.")


# ── Grade Submissions ───────────────────────────────────────────────

def _grade_submissions(svc, grader_username):
    attempts = svc.get_ungraded_attempts()
    if not attempts:
        print("\nNo submissions awaiting grading.")
        input("Press Enter...")
        return

    print(f"\nUngraded Submissions ({len(attempts)}):")
    print(f"{'ID':<5} {'Exam':<25} {'Student':<15} {'Submitted':<16}")
    print("-" * 65)
    for a in attempts:
        print(f"{a['id']:<5} {(a.get('exam_title', '') or '')[:23]:<25} "
              f"{a.get('student_name', a['student_id']):<15} "
              f"{(a.get('submitted_at', '') or '')[:16]}")

    attempt_id = input("\nEnter attempt ID to grade (or 0): ").strip()
    if attempt_id == "0" or not attempt_id:
        return
    try:
        attempt_id = int(attempt_id)
    except ValueError:
        return

    attempt = svc.get_attempt(attempt_id)
    if not attempt:
        print("Attempt not found.")
        return

    questions = svc.get_questions(attempt["exam_id"])
    answers_list = svc.get_answers(attempt_id)
    answer_map = {a["question_id"]: a for a in answers_list}

    print(f"\nGrading: {attempt.get('student_name', attempt['student_id'])}")
    for i, q in enumerate(questions, 1):
        a = answer_map.get(q["id"], {})
        if q["question_type"] in ("mcq", "true_false", "fill_blank") and a.get("is_correct") is not None:
            print(f"  Q{i}: Auto-graded — {a.get('marks_awarded', 0)}/{q['marks']}")
            continue

        print(f"\n  Q{i}. [{q['question_type'].upper()}] ({q['marks']} marks)")
        print(f"  Question: {q['question_text']}")
        print(f"  Answer: {a.get('answer_text', '(none)')}")
        if q.get("correct_answer"):
            print(f"  Model answer: {q['correct_answer']}")

        marks = input(f"  Award marks (0-{q['marks']}): ").strip()
        feedback = input("  Feedback (optional): ").strip()
        if marks and a.get("id"):
            svc.grade_answer(a["id"], float(marks), feedback or None)

    result = svc.finalise_grading(attempt_id, grader_username)
    print(f"\nFinalised: {result['score']} points ({result['percentage']}%) — "
          f"{'PASSED' if result['passed'] else 'FAILED'}")
    input("Press Enter...")


# ── Analytics ───────────────────────────────────────────────────────

def _show_analytics(svc):
    exams = svc.list_exams()
    if not exams:
        print("\nNo exams found.")
        input("Press Enter...")
        return

    print("\nSelect exam for analytics:")
    for e in exams:
        print(f"  {e['id']}. {e['title']} ({e['status']})")

    eid = input("\nExam ID: ").strip()
    try:
        eid = int(eid)
    except ValueError:
        return

    analytics = svc.get_exam_analytics(eid)
    print(f"\nExam Analytics")
    print("=" * 50)
    print(f"Total Attempts:  {analytics['total_attempts']}")
    print(f"Average Score:   {analytics['average_score']}%")
    print(f"Min / Max:       {analytics['min_score']}% / {analytics['max_score']}%")
    print(f"Pass Rate:       {analytics['pass_rate']}%")

    print(f"\nQuestion Analysis:")
    print(f"{'#':<4} {'Type':<12} {'Marks':<7} {'Correct%':<10} {'Avg':<8} Question")
    print("-" * 75)
    for i, q in enumerate(analytics["questions"], 1):
        print(f"{i:<4} {q['type']:<12} {q['marks']:<7} {q['difficulty_pct']:<10} "
              f"{q['avg_marks']:<8} {q['text']}")

    input("\nPress Enter...")


# ── Export ──────────────────────────────────────────────────────────

def _export_results(svc):
    eid = input("\nExam ID to export: ").strip()
    try:
        eid = int(eid)
    except ValueError:
        print("Invalid ID.")
        return

    csv_data = svc.export_results_csv(eid)
    filename = f"exam_{eid}_results.csv"
    with open(filename, "w") as f:
        f.write(csv_data)
    print(f"Results exported to {filename}")
    input("Press Enter...")
