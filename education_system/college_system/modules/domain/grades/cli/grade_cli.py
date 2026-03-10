"""CLI interface for grade management."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.modules.domain.grades.services.grade_service import GradeService
from education_system.college_system.modules.domain.students.services.student_service import StudentService
from education_system.college_system.modules.domain.courses.services.course_service import CourseService
from education_system.college_system.infrastructure.auth.core import UserAuth


def grade_menu(auth: UserAuth):
    """Grade management menu."""
    grade_svc = GradeService(auth._db_path)
    student_svc = StudentService(auth._db_path)
    course_svc = CourseService(auth._db_path)

    while True:
        print_header("Grade Management")
        options = [
            ("1", "Record Grade"),
            ("2", "View Student Grades"),
            ("3", "View UCAS Points"),
            ("4", "View Transcript"),
            ("5", "Course Grade Report"),
            ("6", "Class Statistics"),
            ("7", "Record Predicted Grade"),
            ("8", "View Predicted Grades"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _record_grade(grade_svc, student_svc, course_svc, auth)
        elif choice == "2":
            _view_student_grades(grade_svc, student_svc)
        elif choice == "3":
            _view_ucas_points(grade_svc, student_svc)
        elif choice == "4":
            _view_transcript(grade_svc, student_svc)
        elif choice == "5":
            _course_grades(grade_svc, course_svc)
        elif choice == "6":
            _class_stats(grade_svc, course_svc)
        elif choice == "7":
            _record_predicted_grade(grade_svc, student_svc, course_svc, auth)
        elif choice == "8":
            _view_predicted_grades(grade_svc, student_svc)
        elif choice == "0":
            break


def _record_grade(grade_svc, student_svc, course_svc, auth):
    print_header("Record Grade")
    sid = input("  Student ID: ").strip()
    student = student_svc.get_student_by_student_id(sid)
    if not student:
        print("\n  Student not found.")
        return

    code = input("  Course Code: ").strip()
    course = course_svc.get_course_by_code(code)
    if not course:
        print("\n  Course not found.")
        return

    score_str = input("  Score (0-100): ").strip()
    try:
        score = float(score_str)
    except ValueError:
        print("\n  Invalid score.")
        return

    term = input("  Term (Autumn/Spring/Summer, optional): ").strip() or None

    try:
        grade = grade_svc.record_grade(
            student["id"], course["id"], score,
            term=term,
            recorded_by=auth.current_user["username"],
        )
        print(f"\n  Grade recorded: {grade['score']} ({grade['letter_grade']}) for {sid} in {code}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_student_grades(grade_svc, student_svc):
    sid = input("  Student ID: ").strip()
    student = student_svc.get_student_by_student_id(sid)
    if not student:
        print("\n  Student not found.")
        return

    grades = grade_svc.get_student_grades(student["id"])
    if not grades:
        print(f"\n  No grades found for {sid}.")
        return

    print(f"\n  Grades for {sid} - {student['first_name']} {student['last_name']}:")
    print(f"  {'Course':<10} {'Title':<25} {'Score':<8} {'Grade':<6} {'Qual':<10}")
    print(f"  {'-'*59}")
    for g in grades:
        print(f"  {g['course_code']:<10} {g['title']:<25} {g['score']:<8.1f} {g['letter_grade']:<6} {g['qualification_type'] or 'N/A':<10}")


def _view_ucas_points(grade_svc, student_svc):
    sid = input("  Student ID: ").strip()
    student = student_svc.get_student_by_student_id(sid)
    if not student:
        print("\n  Student not found.")
        return

    ucas_points = grade_svc.calculate_ucas_points(student["id"])
    print(f"\n  UCAS Tariff Points for {sid}: {ucas_points}")


def _view_transcript(grade_svc, student_svc):
    sid = input("  Student ID: ").strip()
    student = student_svc.get_student_by_student_id(sid)
    if not student:
        print("\n  Student not found.")
        return

    transcript = grade_svc.get_transcript(student["id"])
    s = transcript["student"]
    print(f"\n  === TRANSCRIPT ===")
    print(f"  Student: {s['student_id']} - {s['first_name']} {s['last_name']}")
    print(f"  Year Group: {s['year_group'] or 'N/A'}")
    print()

    if transcript["grades"]:
        print(f"  {'Course':<10} {'Title':<25} {'Score':<8} {'Grade':<6} {'Qual':<10}")
        print(f"  {'-'*59}")
        for g in transcript["grades"]:
            print(f"  {g['course_code']:<10} {g['title']:<25} {g['score']:<8.1f} {g['letter_grade']:<6} {g['qualification_type'] or 'N/A':<10}")
    else:
        print("  No grades recorded yet.")

    print(f"\n  UCAS Tariff Points: {transcript['ucas_points']}")
    print(f"  Total Subjects: {transcript['total_subjects']}")
    print(f"  Total Courses: {transcript['total_courses']}")


def _record_predicted_grade(grade_svc, student_svc, course_svc, auth):
    print_header("Record Predicted Grade")
    sid = input("  Student ID: ").strip()
    student = student_svc.get_student_by_student_id(sid)
    if not student:
        print("\n  Student not found.")
        return

    code = input("  Course Code: ").strip()
    course = course_svc.get_course_by_code(code)
    if not course:
        print("\n  Course not found.")
        return

    predicted = input("  Predicted Grade (A*/A/B/C/D/E/U): ").strip()
    term = input("  Term (Autumn/Spring/Summer, optional): ").strip() or None

    try:
        result = grade_svc.record_predicted_grade(
            student["id"], course["id"], predicted,
            term=term,
            recorded_by=auth.current_user["username"],
        )
        print(f"\n  Predicted grade '{result['predicted_grade']}' recorded for {sid} in {code}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_predicted_grades(grade_svc, student_svc):
    sid = input("  Student ID: ").strip()
    student = student_svc.get_student_by_student_id(sid)
    if not student:
        print("\n  Student not found.")
        return

    grades = grade_svc.get_student_predicted_grades(student["id"])
    if not grades:
        print(f"\n  No predicted grades found for {sid}.")
        return

    print(f"\n  Predicted Grades for {sid} - {student['first_name']} {student['last_name']}:")
    print(f"  {'Course':<10} {'Title':<25} {'Predicted':<10} {'Qual':<10}")
    print(f"  {'-'*55}")
    for g in grades:
        print(f"  {g['course_code']:<10} {g['title']:<25} {g['predicted_grade'] or 'N/A':<10} {g['qualification_type'] or 'N/A':<10}")


def _course_grades(grade_svc, course_svc):
    code = input("  Course Code: ").strip()
    course = course_svc.get_course_by_code(code)
    if not course:
        print("\n  Course not found.")
        return

    grades = grade_svc.get_course_grades(course["id"])
    if not grades:
        print(f"\n  No grades for {code}.")
        return

    print(f"\n  Grades for {code} - {course['title']}:")
    for g in grades:
        print(f"  {g['sid']} {g['first_name']} {g['last_name']}: {g['score']:.1f} ({g['letter_grade']})")


def _class_stats(grade_svc, course_svc):
    code = input("  Course Code: ").strip()
    course = course_svc.get_course_by_code(code)
    if not course:
        print("\n  Course not found.")
        return

    stats = grade_svc.get_class_statistics(course["id"])
    print(f"\n  Statistics for {code}:")
    print(f"  Students graded: {stats['count']}")
    print(f"  Average: {stats['average']:.1f}")
    print(f"  Median: {stats['median']:.1f}")
    print(f"  Min: {stats['min']:.1f}")
    print(f"  Max: {stats['max']:.1f}")


def view_my_grades(auth: UserAuth):
    """View grades for the currently logged-in student."""
    grade_svc = GradeService(auth._db_path)

    conn = grade_svc._conn()
    try:
        student = conn.execute(
            "SELECT * FROM students WHERE user_id = ?",
            (auth.current_user["user_id"],),
        ).fetchone()
    finally:
        conn.close()

    if not student:
        print("\n  No student record linked to your account.")
        return

    grades = grade_svc.get_student_grades(student["id"])
    ucas_points = grade_svc.calculate_ucas_points(student["id"])

    if not grades:
        print("\n  No grades recorded yet.")
        return

    print(f"\n  Your Grades:")
    for g in grades:
        print(f"  {g['course_code']} - {g['title']}: {g['score']:.1f} ({g['letter_grade']})")
    print(f"\n  UCAS Tariff Points: {ucas_points}")
