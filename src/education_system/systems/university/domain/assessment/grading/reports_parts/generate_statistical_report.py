"""Extracted function implementation."""

from .. import reports_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def generate_statistical_report():
    """Generate a statistical report for assessments and/or modules"""
    select_assessment, calculate_student_gpa, GRADE_SYSTEMS = _get_grading_imports()
    from education_system.systems.university.domain.assessment.grading.grade_calculation.visualization import generate_assessment_stats_report

    print("\n" + get_text("academics.reports.generate_statistical_report"))

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Choose report type
        print("\n" + get_text("academics.reports.report_type"))
        print(get_text("academics.reports.option_assessment_statistics"))
        print(get_text("academics.reports.option_module_statistics"))
        print(get_text("academics.reports.option_course_statistics"))
        print(get_text("academics.reports.option_comprehensive_statistics"))

        report_type = input("Select report type (1-4): ")

        # Create the reports directory if it doesn't exist
        reports_dir = os.path.join(_DATA_REPORTS_DIR, 'statistical_reports')
        if not os.path.exists(reports_dir):
            os.makedirs(reports_dir)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if report_type == "1":
            # Assessment Statistics
            assessment_id = select_assessment(cursor)
            if not assessment_id:
                conn.close()
                return

            generate_assessment_stats_report(cursor, assessment_id, reports_dir, timestamp)

        elif report_type == "2":
            # Module Statistics
            # Get list of modules
            cursor.execute('''
            SELECT module_code, module_name
            FROM modules
            WHERE module_code IN (SELECT DISTINCT module_code FROM module_grades)
            ORDER BY module_name
            ''')

            modules = cursor.fetchall()

            if not modules:
                print(get_text("academics.reports.no_modules_with_grades"))
                conn.close()
                return

            print("\n" + get_text("academics.reports.available_modules"))
            for i, (code, name) in enumerate(modules):
                print(f"{i+1}. {code} - {name}")

            module_index = input("Enter module number (or 0 for all modules): ")

            try:
                if module_index == "0":
                    # Generate report for all modules
                    generate_all_modules_stats_report(cursor, modules, reports_dir, timestamp)
                else:
                    index = int(module_index) - 1
                    if index < 0 or index >= len(modules):
                        print("Invalid module number.")
                        conn.close()
                        return

                    module_code = modules[index][0]
                    generate_module_stats_report(cursor, module_code, reports_dir, timestamp)

            except ValueError:
                print("Invalid input. Please enter a number.")
                conn.close()
                return

        elif report_type == "3":
            # Course Statistics
            # Get list of courses
            cursor.execute('''
            SELECT DISTINCT course
            FROM students
            WHERE student_id IN (SELECT DISTINCT student_id FROM module_grades)
            ORDER BY course
            ''')

            courses = cursor.fetchall()

            if not courses:
                print("No courses with grades found.")
                conn.close()
                return

            print("\nAvailable Courses:")
            for i, (course,) in enumerate(courses):
                print(f"{i+1}. {course}")

            course_index = input("Enter course number (or 0 for all courses): ")

            try:
                if course_index == "0":
                    # Generate report for all courses
                    courses_list = [c[0] for c in courses]
                    generate_all_courses_stats_report(cursor, courses_list, reports_dir, timestamp)
                else:
                    index = int(course_index) - 1
                    if index < 0 or index >= len(courses):
                        print("Invalid course number.")
                        conn.close()
                        return

                    course = courses[index][0]
                    generate_course_stats_report(cursor, course, reports_dir, timestamp)

            except ValueError:
                print("Invalid input. Please enter a number.")
                conn.close()
                return

        elif report_type == "4":
            # Comprehensive Statistics
            # This will include stats for all assessments, modules, and courses
            generate_comprehensive_stats_report(cursor, reports_dir, timestamp)

        else:
            print("Invalid report type.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")
