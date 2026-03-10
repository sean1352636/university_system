"""Functional Skills & GCSE Resits CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.functional_skills.services.functional_skills_service import (
    FunctionalSkillsService,
)
from education_system.college_system.infrastructure.auth.core import UserAuth


def functional_skills_menu(auth: UserAuth):
    """Functional Skills & GCSE Resits management menu."""
    svc = FunctionalSkillsService(auth._db_path)

    while True:
        print_header("Functional Skills & GCSE Resits")
        options = [
            ("1", "List Enrollments"),
            ("2", "View Enrollment"),
            ("3", "Enroll Student"),
            ("4", "Update Enrollment"),
            ("5", "Book Exam"),
            ("6", "Record Result"),
            ("7", "Delete Enrollment"),
            ("8", "List Assessments"),
            ("9", "New Assessment"),
            ("10", "Update Assessment"),
            ("11", "Student Progress"),
            ("12", "Condition of Funding Report"),
            ("13", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            _list_enrollments(svc)
        elif choice == "2":
            _view_enrollment(svc)
        elif choice == "3":
            _enroll_student(svc)
        elif choice == "4":
            _update_enrollment(svc)
        elif choice == "5":
            _book_exam(svc)
        elif choice == "6":
            _record_result(svc)
        elif choice == "7":
            _delete_enrollment(svc)
        elif choice == "8":
            _list_assessments(svc)
        elif choice == "9":
            _new_assessment(svc)
        elif choice == "10":
            _update_assessment(svc)
        elif choice == "11":
            _student_progress(svc)
        elif choice == "12":
            _condition_of_funding(svc)
        elif choice == "13":
            _statistics(svc)
        else:
            print("\n  Invalid option.")


# ------------------------------------------------------------------ #
# Enrollments
# ------------------------------------------------------------------ #

def _list_enrollments(svc):
    print_header("List Enrollments")
    try:
        subject = input("  Filter by subject (blank for all): ").strip() or None
        status = input("  Filter by status (blank for all): ").strip() or None
        qual_type = input("  Filter by qual type (blank for all): ").strip() or None
        rows = svc.list_enrollments(subject=subject, status=status,
                                    qualification_type=qual_type)
        if not rows:
            print("\n  No enrollments found.")
            return
        print(f"\n  {'ID':<5} {'Student':<8} {'Name':<20} {'Subject':<10} "
              f"{'Qual Type':<16} {'Level':<6} {'Status':<12} {'Exam Date'}")
        print(f"  {'-'*90}")
        for r in rows:
            name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or "-"
            print(f"  {r['id']:<5} {r['student_id']:<8} {name:<20} "
                  f"{r.get('subject', '-'):<10} {r.get('qualification_type', '-'):<16} "
                  f"{r.get('level', '-'):<6} {r.get('status', '-'):<12} "
                  f"{r.get('exam_date') or '-'}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_enrollment(svc):
    print_header("View Enrollment")
    try:
        eid = int(input("  Enrollment ID: ").strip())
        enr = svc.get_enrollment(eid)
        if not enr:
            print("\n  Enrollment not found.")
            return
        name = f"{enr.get('first_name', '')} {enr.get('last_name', '')}".strip() or "-"
        print(f"\n  ID:                {enr['id']}")
        print(f"  Student:           {enr['student_id']} - {name}")
        print(f"  Subject:           {enr.get('subject', '-')}")
        print(f"  Qualification:     {enr.get('qualification_type', '-')}")
        print(f"  Level:             {enr.get('level', '-')}")
        print(f"  Entry Grade:       {enr.get('entry_grade') or '-'}")
        print(f"  Target Grade:      {enr.get('target_grade') or '-'}")
        print(f"  Current Grade:     {enr.get('current_grade') or '-'}")
        print(f"  Exam Board:        {enr.get('exam_board') or '-'}")
        print(f"  Exam Series:       {enr.get('exam_series') or '-'}")
        print(f"  Exam Date:         {enr.get('exam_date') or '-'}")
        print(f"  Result:            {enr.get('result') or '-'}")
        print(f"  Attendance %:      {enr.get('attendance_pct') if enr.get('attendance_pct') is not None else '-'}")
        print(f"  Status:            {enr.get('status', '-')}")
        print(f"  Notes:             {enr.get('notes') or '-'}")
        print(f"  Created:           {enr.get('created_at') or '-'}")
        print(f"  Updated:           {enr.get('updated_at') or '-'}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _enroll_student(svc):
    print_header("Enroll Student")
    try:
        student_id = int(input("  Student PK: ").strip())
        subject = input("  Subject (e.g. Maths, English): ").strip()
        if not subject:
            print("\n  Subject is required.")
            return
        qual_type = input("  Qualification Type (gcse_resit/functional_skills/stepping_stone) [gcse_resit]: ").strip() or "gcse_resit"
        level = input("  Level (entry1/entry2/entry3/1/2) [2]: ").strip() or "2"
        entry_grade = input("  Entry Grade: ").strip() or None
        target_grade = input("  Target Grade: ").strip() or None
        exam_board = input("  Exam Board: ").strip() or None
        notes = input("  Notes: ").strip() or None

        enr = svc.create_enrollment(
            student_id, subject,
            qualification_type=qual_type, level=level,
            entry_grade=entry_grade, target_grade=target_grade,
            exam_board=exam_board, notes=notes,
        )
        print(f"\n  Enrollment created (ID: {enr['id']}).")
    except ValueError:
        print("\n  Invalid student ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_enrollment(svc):
    print_header("Update Enrollment")
    try:
        eid = int(input("  Enrollment ID: ").strip())
        enr = svc.get_enrollment(eid)
        if not enr:
            print("\n  Enrollment not found.")
            return
        print("  (Press Enter to keep current value)")
        kwargs = {}
        for field, prompt in [
            ("subject", "Subject"),
            ("qualification_type", "Qual Type"),
            ("level", "Level"),
            ("entry_grade", "Entry Grade"),
            ("target_grade", "Target Grade"),
            ("current_grade", "Current Grade"),
            ("exam_board", "Exam Board"),
            ("status", "Status (enrolled/in_progress/exam_booked/completed/withdrawn)"),
            ("notes", "Notes"),
        ]:
            current = enr.get(field) or ""
            val = input(f"  {prompt} [{current}]: ").strip()
            if val:
                kwargs[field] = val
        att_str = input(f"  Attendance % [{enr.get('attendance_pct') or ''}]: ").strip()
        if att_str:
            kwargs["attendance_pct"] = float(att_str)
        if not kwargs:
            print("\n  No changes.")
            return
        svc.update_enrollment(eid, **kwargs)
        print("\n  Enrollment updated.")
    except ValueError:
        print("\n  Invalid input.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _book_exam(svc):
    print_header("Book Exam")
    try:
        eid = int(input("  Enrollment ID: ").strip())
        exam_date = input("  Exam Date (YYYY-MM-DD): ").strip()
        if not exam_date:
            print("\n  Exam date is required.")
            return
        series = input("  Exam Series (optional): ").strip() or None
        svc.book_exam(eid, exam_date, series)
        print("\n  Exam booked.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _record_result(svc):
    print_header("Record Result")
    try:
        eid = int(input("  Enrollment ID: ").strip())
        result = input("  Result (Pass/Fail/Achieved/Not Achieved/Distinction/Merit): ").strip()
        if not result:
            print("\n  Result is required.")
            return
        grade = input("  Grade (optional): ").strip() or None
        svc.record_result(eid, result, grade)
        print("\n  Result recorded.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_enrollment(svc):
    print_header("Delete Enrollment")
    try:
        eid = int(input("  Enrollment ID: ").strip())
        confirm = input(f"  Delete enrollment #{eid} and all assessments? (y/n): ").strip().lower()
        if confirm != "y":
            print("\n  Cancelled.")
            return
        svc.delete_enrollment(eid)
        print("\n  Enrollment deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ------------------------------------------------------------------ #
# Assessments
# ------------------------------------------------------------------ #

def _list_assessments(svc):
    print_header("List Assessments")
    try:
        enr_str = input("  Filter by Enrollment ID (blank for all): ").strip()
        enr_id = int(enr_str) if enr_str else None
        atype = input("  Filter by type (mock/coursework/exam/practice/diagnostic, blank for all): ").strip() or None
        rows = svc.list_assessments(enrollment_id=enr_id, assessment_type=atype)
        if not rows:
            print("\n  No assessments found.")
            return
        print(f"\n  {'ID':<5} {'Enroll':<8} {'Type':<12} {'Date':<12} "
              f"{'Score':<8} {'Grade':<8} {'Feedback'}")
        print(f"  {'-'*70}")
        for r in rows:
            score = str(r["score"]) if r.get("score") is not None else "-"
            print(f"  {r['id']:<5} {r['enrollment_id']:<8} "
                  f"{r.get('assessment_type', '-'):<12} "
                  f"{r.get('assessment_date') or '-':<12} "
                  f"{score:<8} {r.get('grade') or '-':<8} "
                  f"{(r.get('feedback') or '-')[:40]}")
    except ValueError:
        print("\n  Invalid Enrollment ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_assessment(svc):
    print_header("New Assessment")
    try:
        enr_id = int(input("  Enrollment ID: ").strip())
        atype = input("  Type (mock/coursework/exam/practice/diagnostic) [mock]: ").strip() or "mock"
        adate = input("  Date (YYYY-MM-DD): ").strip() or None
        score_str = input("  Score: ").strip()
        score = float(score_str) if score_str else None
        grade = input("  Grade: ").strip() or None
        feedback = input("  Feedback: ").strip() or None

        kwargs = {"assessment_type": atype}
        if adate:
            kwargs["assessment_date"] = adate
        if score is not None:
            kwargs["score"] = score
        if grade:
            kwargs["grade"] = grade
        if feedback:
            kwargs["feedback"] = feedback

        asmt = svc.create_assessment(enr_id, **kwargs)
        print(f"\n  Assessment created (ID: {asmt['id']}).")
    except ValueError:
        print("\n  Invalid input (ID must be a number, score must be numeric).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_assessment(svc):
    print_header("Update Assessment")
    try:
        aid = int(input("  Assessment ID: ").strip())
        asmt = svc.get_assessment(aid)
        if not asmt:
            print("\n  Assessment not found.")
            return
        print("  (Press Enter to keep current value)")
        kwargs = {}
        atype = input(f"  Type [{asmt.get('assessment_type', '')}]: ").strip()
        if atype:
            kwargs["assessment_type"] = atype
        adate = input(f"  Date [{asmt.get('assessment_date') or ''}]: ").strip()
        if adate:
            kwargs["assessment_date"] = adate
        score_str = input(f"  Score [{asmt.get('score') or ''}]: ").strip()
        if score_str:
            kwargs["score"] = float(score_str)
        grade = input(f"  Grade [{asmt.get('grade') or ''}]: ").strip()
        if grade:
            kwargs["grade"] = grade
        feedback = input(f"  Feedback [{(asmt.get('feedback') or '')[:40]}]: ").strip()
        if feedback:
            kwargs["feedback"] = feedback
        if not kwargs:
            print("\n  No changes.")
            return
        svc.update_assessment(aid, **kwargs)
        print("\n  Assessment updated.")
    except ValueError:
        print("\n  Invalid input.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ------------------------------------------------------------------ #
# Reporting
# ------------------------------------------------------------------ #

def _student_progress(svc):
    print_header("Student Progress")
    try:
        student_id = int(input("  Student PK: ").strip())
        progress = svc.get_student_progress(student_id)
        if not progress:
            print("\n  No enrollments found for this student.")
            return
        for enr in progress:
            name = f"{enr.get('first_name', '')} {enr.get('last_name', '')}".strip() or "-"
            print(f"\n  --- Enrollment #{enr['id']}: {enr.get('subject', '-')} "
                  f"({enr.get('qualification_type', '-')}) ---")
            print(f"  Student:       {enr['student_id']} - {name}")
            print(f"  Level:         {enr.get('level', '-')}")
            print(f"  Entry Grade:   {enr.get('entry_grade') or '-'}")
            print(f"  Current Grade: {enr.get('current_grade') or '-'}")
            print(f"  Target Grade:  {enr.get('target_grade') or '-'}")
            print(f"  Status:        {enr.get('status', '-')}")
            print(f"  Result:        {enr.get('result') or '-'}")
            print(f"  Attendance:    {enr.get('attendance_pct') if enr.get('attendance_pct') is not None else '-'}%")

            assessments = enr.get("assessments", [])
            if assessments:
                print(f"\n  Assessments ({len(assessments)}):")
                print(f"    {'Type':<12} {'Date':<12} {'Score':<8} {'Grade':<8} {'Feedback'}")
                print(f"    {'-'*55}")
                for a in assessments:
                    score = str(a["score"]) if a.get("score") is not None else "-"
                    print(f"    {a.get('assessment_type', '-'):<12} "
                          f"{a.get('assessment_date') or '-':<12} "
                          f"{score:<8} {a.get('grade') or '-':<8} "
                          f"{(a.get('feedback') or '-')[:30]}")
            else:
                print("  No assessments recorded.")
    except ValueError:
        print("\n  Invalid student ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _condition_of_funding(svc):
    print_header("Condition of Funding Report")
    try:
        rows = svc.condition_of_funding_report()
        if not rows:
            print("\n  All students have met maths/english requirements (or none enrolled).")
            return
        print(f"\n  Students requiring maths/english: {len(rows)}")
        print(f"\n  {'Student':<8} {'Name':<20} {'Subject':<12} {'Qual Type':<16} "
              f"{'Level':<6} {'Status':<12} {'Attend%'}")
        print(f"  {'-'*85}")
        for r in rows:
            name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or "-"
            att = f"{r['attendance_pct']:.0f}" if r.get("attendance_pct") is not None else "-"
            print(f"  {r['student_id']:<8} {name:<20} {r.get('subject', '-'):<12} "
                  f"{r.get('qualification_type', '-'):<16} {r.get('level', '-'):<6} "
                  f"{r.get('status', '-'):<12} {att}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _statistics(svc):
    print_header("Functional Skills Statistics")
    try:
        stats = svc.get_stats()
        print(f"\n  Total Enrollments:   {stats['total_enrollments']}")
        print(f"  Total Assessments:   {stats['total_assessments']}")
        print(f"  Average Score:       {stats['avg_score']}")
        print(f"  Pass Rate:           {stats['pass_rate']}%")

        print("\n  By Subject:")
        for subj, cnt in stats["by_subject"].items():
            print(f"    {subj}: {cnt}")

        print("\n  By Status:")
        for st, cnt in stats["by_status"].items():
            print(f"    {st}: {cnt}")

        print("\n  By Qualification Type:")
        for qt, cnt in stats["by_qualification_type"].items():
            print(f"    {qt}: {cnt}")
    except Exception as e:
        print(f"\n  Error: {e}")
