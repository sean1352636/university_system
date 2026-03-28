"""
Course Planning Assistant CLI

Provides menu-driven interface for:
- Multi-semester course planning
- Prerequisite visualization
- Conflict detection
- Course recommendations
- Plan export
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from typing import Any, Optional

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.domain.course_planning.services.planning_service import PlanningService
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

try:
    from education_system.university_system.infrastructure.shared_context import get_auth
except ImportError:
    get_auth = lambda: None

logger = logging.getLogger(__name__)

# Global auth instance
auth = None
planning_service = None


def init_course_planning() -> bool:
    """Initialize Course Planning database tables."""
    try:
        global planning_service
        planning_service = PlanningService()
        logger.info("Course Planning initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing Course Planning: {e}")
        return False


def set_auth(auth_instance: Any) -> None:
    """Set the global auth instance for the module."""
    global auth
    auth = auth_instance


def display_course_planning_menu() -> None:
    """Display the main Course Planning menu."""
    global auth, planning_service

    if not auth:
        auth = get_auth()

    if not auth or not getattr(auth, 'current_user', None):
        print("\n" + "=" * 60)
        print("You must be logged in to access Course Planning features.")
        print("=" * 60)
        input("Press Enter to continue...")
        return

    if not planning_service:
        planning_service = PlanningService()

    current_user = auth.current_user
    user_id = current_user.get('id') or current_user.get('username')
    user_role = current_user.get('role', 'student')

    while True:
        print("\n" + "=" * 70)
        print("COURSE PLANNING ASSISTANT")
        print("=" * 70)
        print(f"User: {current_user.get('username', 'Unknown')} | Role: {user_role.capitalize()}")
        print("=" * 70)

        options = []
        option_num = 1

        def add_option(label: str, key: str) -> None:
            nonlocal option_num
            print(f"  {option_num}. {label}")
            options.append(key)
            option_num += 1

        # Student options
        add_option("Create New Course Plan", "create_plan")
        add_option("View My Course Plans", "view_plans")
        add_option("Edit Course Plan", "edit_plan")
        add_option("Add Course to Plan", "add_course")
        add_option("View Prerequisite Chain", "view_prereqs")
        add_option("Check Prerequisite Eligibility", "check_eligibility")
        add_option("Detect Schedule Conflicts", "detect_conflicts")
        add_option("Get Course Recommendations", "recommendations")
        add_option("Export Course Plan", "export_plan")
        add_option("Generate Auto-Plan", "auto_plan")

        # Admin options
        if user_role in ('admin', 'Admin', 'administrator', 'instructor', 'Instructor'):
            add_option("[Admin] Manage Prerequisites", "manage_prereqs")
            add_option("[Admin] Manage Course Offerings", "manage_offerings")
            add_option("[Admin] View Student Plans", "view_student_plans")

        print(f"  {option_num}. Back to Main Menu")
        print("=" * 70)

        choice = input("\nSelect option: ").strip()

        if not choice.isdigit():
            print("Invalid input. Please enter a number.")
            continue

        choice_idx = int(choice) - 1

        if choice_idx == len(options):
            break
        elif 0 <= choice_idx < len(options):
            option_key = options[choice_idx]

            try:
                if option_key == "create_plan":
                    create_plan_menu(user_id)
                elif option_key == "view_plans":
                    view_plans_menu(user_id)
                elif option_key == "edit_plan":
                    edit_plan_menu(user_id)
                elif option_key == "add_course":
                    add_course_to_plan_menu(user_id)
                elif option_key == "view_prereqs":
                    view_prerequisite_chain_menu()
                elif option_key == "check_eligibility":
                    check_eligibility_menu(user_id)
                elif option_key == "detect_conflicts":
                    detect_conflicts_menu(user_id)
                elif option_key == "recommendations":
                    get_recommendations_menu(user_id)
                elif option_key == "export_plan":
                    export_plan_menu(user_id)
                elif option_key == "auto_plan":
                    generate_auto_plan_menu(user_id)
                elif option_key == "manage_prereqs":
                    manage_prerequisites_menu()
                elif option_key == "manage_offerings":
                    manage_offerings_menu()
                elif option_key == "view_student_plans":
                    view_student_plans_admin_menu()
            except Exception as e:
                logger.error(f"Error in course planning menu: {e}")
                print(f"\nError: {e}")
                input("Press Enter to continue...")
        else:
            print("Invalid option. Please try again.")


def create_plan_menu(student_id: str) -> None:
    """Create a new course plan."""
    print("\n" + "=" * 60)
    print("CREATE NEW COURSE PLAN")
    print("=" * 60)

    plan_name = input("Plan name: ").strip()
    if not plan_name:
        print("Plan name cannot be empty.")
        return

    # Get student's major
    with get_connection() as conn:
        student = conn.execute("""
            SELECT major FROM students WHERE student_id = ?
        """, (student_id,)).fetchone()

    program_code = None
    if student and student['major']:
        program_code = student['major']
        print(f"Detected program: {program_code}")
    else:
        program_code = input("Program/Major code (e.g., CS, MATH): ").strip()

    start_semester = input("Start semester (e.g., Fall 2026) [Fall 2026]: ").strip() or "Fall 2026"
    total_semesters = input("Total semesters to plan [8]: ").strip()
    total_semesters = int(total_semesters) if total_semesters.isdigit() else 8

    credits_per_semester = input("Target credits per semester [15]: ").strip()
    credits_per_semester = int(credits_per_semester) if credits_per_semester.isdigit() else 15

    include_summer = input("Include summer sessions? (y/n) [n]: ").strip().lower() == 'y'

    try:
        plan_id = planning_service.create_semester_plan(
            student_id=student_id,
            plan_name=plan_name,
            program_code=program_code,
            start_semester=start_semester,
            total_semesters=total_semesters,
            credits_per_semester=credits_per_semester,
            include_summer=include_summer
        )

        print(f"\n✓ Course plan created successfully! (Plan ID: {plan_id})")
        log_activity('create', 'course_plan', user_id=student_id,
                    details={'plan_id': plan_id, 'name': plan_name})

    except Exception as e:
        print(f"\n✗ Error creating plan: {e}")

    input("\nPress Enter to continue...")


def view_plans_menu(student_id: str) -> None:
    """View all course plans for a student."""
    print("\n" + "=" * 60)
    print("MY COURSE PLANS")
    print("=" * 60)

    try:
        plans = planning_service.get_student_plans(student_id)

        if not plans:
            print("\nNo course plans found.")
            input("\nPress Enter to continue...")
            return

        for i, plan in enumerate(plans, 1):
            print(f"\n{i}. {plan['plan_name']}")
            print(f"   Plan ID: {plan['plan_id']}")
            print(f"   Program: {plan['program_code'] or 'N/A'}")
            print(f"   Start: {plan['start_semester']}")
            print(f"   Semesters: {plan['total_semesters']}")
            print(f"   Credits/Semester: {plan['credits_per_semester']}")
            print(f"   Status: {plan['status']}")
            print(f"   Created: {plan['created_at']}")

        # Option to view detailed plan
        view_detail = input("\nEnter plan number to view details (or press Enter to go back): ").strip()
        if view_detail.isdigit() and 1 <= int(view_detail) <= len(plans):
            plan_id = plans[int(view_detail) - 1]['plan_id']
            view_plan_details(plan_id)

    except Exception as e:
        print(f"\n✗ Error retrieving plans: {e}")

    input("\nPress Enter to continue...")


def view_plan_details(plan_id: int) -> None:
    """View detailed information about a course plan."""
    print("\n" + "=" * 60)
    print("COURSE PLAN DETAILS")
    print("=" * 60)

    try:
        plan_data = planning_service.get_semester_plan(plan_id)

        if not plan_data:
            print("\nPlan not found.")
            return

        plan = plan_data['plan']
        semesters = plan_data['semesters']

        print(f"\nPlan: {plan['plan_name']}")
        print(f"Program: {plan['program_code'] or 'N/A'}")
        print(f"Start: {plan['start_semester']}")
        print(f"Status: {plan['status']}")
        print(f"\nTotal Courses: {plan_data['total_courses']}")

        # Display courses by semester
        for semester_num in sorted(semesters.keys()):
            courses = semesters[semester_num]
            total_credits = sum(c['credits'] for c in courses)

            print(f"\n--- Semester {semester_num}: {courses[0]['semester_name'] if courses else 'N/A'} ---")
            print(f"Total Credits: {total_credits}")

            for course in courses:
                locked = " [LOCKED]" if course['is_locked'] else ""
                priority = f" (Priority: {course['priority']})" if course['priority'] > 0 else ""
                print(f"  • {course['course_id']}: {course['course_name']} ({course['credits']} cr){locked}{priority}")
                if course['notes']:
                    print(f"    Note: {course['notes']}")

    except Exception as e:
        print(f"\n✗ Error retrieving plan details: {e}")


def edit_plan_menu(student_id: str) -> None:
    """Edit an existing course plan."""
    print("\n" + "=" * 60)
    print("EDIT COURSE PLAN")
    print("=" * 60)

    try:
        plans = planning_service.get_student_plans(student_id)

        if not plans:
            print("\nNo course plans found.")
            input("\nPress Enter to continue...")
            return

        # List plans
        for i, plan in enumerate(plans, 1):
            print(f"{i}. {plan['plan_name']} (ID: {plan['plan_id']})")

        plan_choice = input("\nSelect plan to edit (or press Enter to cancel): ").strip()
        if not plan_choice.isdigit() or not (1 <= int(plan_choice) <= len(plans)):
            return

        plan_id = plans[int(plan_choice) - 1]['plan_id']

        # Edit options
        print("\nEdit Options:")
        print("1. Remove course from plan")
        print("2. Move course to different semester")
        print("3. Update plan status")
        print("4. Cancel")

        edit_choice = input("\nSelect option: ").strip()

        if edit_choice == "1":
            remove_course_from_plan(plan_id)
        elif edit_choice == "2":
            move_course_in_plan(plan_id)
        elif edit_choice == "3":
            update_plan_status(plan_id)

    except Exception as e:
        print(f"\n✗ Error editing plan: {e}")

    input("\nPress Enter to continue...")


def remove_course_from_plan(plan_id: int) -> None:
    """Remove a course from a plan."""
    plan_data = planning_service.get_semester_plan(plan_id)
    if not plan_data:
        print("\nPlan not found.")
        return

    semesters = plan_data['semesters']
    all_courses = []
    for courses in semesters.values():
        all_courses.extend(courses)

    if not all_courses:
        print("\nNo courses in plan.")
        return

    print("\nCourses in plan:")
    for i, course in enumerate(all_courses, 1):
        print(f"{i}. {course['course_id']}: {course['course_name']} (Semester {course['semester_number']})")

    course_choice = input("\nSelect course to remove (or press Enter to cancel): ").strip()
    if not course_choice.isdigit() or not (1 <= int(course_choice) <= len(all_courses)):
        return

    course = all_courses[int(course_choice) - 1]

    try:
        from education_system.university_system.infrastructure.database.db import transaction
        with transaction() as conn:
            conn.execute("""
                DELETE FROM planned_courses
                WHERE planned_course_id = ?
            """, (course['planned_course_id'],))

        print(f"\n✓ Removed {course['course_id']} from plan.")
        log_activity('delete', 'planned_course',
                    details={'plan_id': plan_id, 'course_id': course['course_id']})

    except Exception as e:
        print(f"\n✗ Error removing course: {e}")


def move_course_in_plan(plan_id: int) -> None:
    """Move a course to a different semester."""
    plan_data = planning_service.get_semester_plan(plan_id)
    if not plan_data:
        print("\nPlan not found.")
        return

    semesters = plan_data['semesters']
    all_courses = []
    for courses in semesters.values():
        all_courses.extend(courses)

    if not all_courses:
        print("\nNo courses in plan.")
        return

    print("\nCourses in plan:")
    for i, course in enumerate(all_courses, 1):
        print(f"{i}. {course['course_id']}: {course['course_name']} (Semester {course['semester_number']})")

    course_choice = input("\nSelect course to move: ").strip()
    if not course_choice.isdigit() or not (1 <= int(course_choice) <= len(all_courses)):
        return

    course = all_courses[int(course_choice) - 1]

    new_semester = input(f"New semester number (current: {course['semester_number']}): ").strip()
    if not new_semester.isdigit():
        print("Invalid semester number.")
        return

    new_semester_num = int(new_semester)
    new_semester_name = input("New semester name (e.g., Fall 2026): ").strip()

    try:
        from education_system.university_system.infrastructure.database.db import transaction
        with transaction() as conn:
            conn.execute("""
                UPDATE planned_courses
                SET semester_number = ?, semester_name = ?
                WHERE planned_course_id = ?
            """, (new_semester_num, new_semester_name, course['planned_course_id']))

        print(f"\n✓ Moved {course['course_id']} to Semester {new_semester_num}.")
        log_activity('update', 'planned_course',
                    details={'plan_id': plan_id, 'course_id': course['course_id'],
                            'new_semester': new_semester_num})

    except Exception as e:
        print(f"\n✗ Error moving course: {e}")


def update_plan_status(plan_id: int) -> None:
    """Update the status of a plan."""
    print("\nPlan Status:")
    print("1. Draft")
    print("2. Active")
    print("3. Completed")
    print("4. Archived")

    status_choice = input("\nSelect new status: ").strip()
    statuses = {
        '1': 'Draft',
        '2': 'Active',
        '3': 'Completed',
        '4': 'Archived'
    }

    if status_choice not in statuses:
        print("Invalid status.")
        return

    new_status = statuses[status_choice]

    try:
        from education_system.university_system.infrastructure.database.db import transaction
        with transaction() as conn:
            conn.execute("""
                UPDATE semester_plans
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE plan_id = ?
            """, (new_status, plan_id))

        print(f"\n✓ Plan status updated to {new_status}.")
        log_activity('update', 'semester_plan',
                    details={'plan_id': plan_id, 'status': new_status})

    except Exception as e:
        print(f"\n✗ Error updating status: {e}")


def add_course_to_plan_menu(student_id: str) -> None:
    """Add a course to a semester plan."""
    print("\n" + "=" * 60)
    print("ADD COURSE TO PLAN")
    print("=" * 60)

    try:
        plans = planning_service.get_student_plans(student_id)

        if not plans:
            print("\nNo course plans found. Create a plan first.")
            input("\nPress Enter to continue...")
            return

        # List plans
        for i, plan in enumerate(plans, 1):
            print(f"{i}. {plan['plan_name']} (ID: {plan['plan_id']})")

        plan_choice = input("\nSelect plan (or press Enter to cancel): ").strip()
        if not plan_choice.isdigit() or not (1 <= int(plan_choice) <= len(plans)):
            return

        plan_id = plans[int(plan_choice) - 1]['plan_id']

        # Get course details
        course_id = input("\nCourse ID (e.g., CS101): ").strip().upper()
        if not course_id:
            return

        # Verify course exists
        with get_connection() as conn:
            course = conn.execute("""
                SELECT * FROM courses WHERE course_id = ?
            """, (course_id,)).fetchone()

        if not course:
            print(f"\n✗ Course {course_id} not found.")
            input("\nPress Enter to continue...")
            return

        print(f"\nCourse: {course['course_name']} ({course['credits']} credits)")

        # Check eligibility
        eligibility = planning_service.check_prerequisite_eligibility(student_id, course_id)
        if not eligibility['eligible']:
            print("\n⚠ Warning: Prerequisites not met!")
            for prereq in eligibility['missing_prerequisites']:
                print(f"  • {prereq['course_id']}: {prereq['status']}")

            continue_anyway = input("\nAdd anyway? (y/n): ").strip().lower()
            if continue_anyway != 'y':
                return

        semester_number = input("Semester number (1-8): ").strip()
        if not semester_number.isdigit():
            print("Invalid semester number.")
            return

        semester_name = input("Semester name (e.g., Fall 2026): ").strip()
        if not semester_name:
            return

        is_locked = input("Lock this course? (y/n) [n]: ").strip().lower() == 'y'
        priority = input("Priority (0-10) [0]: ").strip()
        priority = int(priority) if priority.isdigit() else 0
        notes = input("Notes (optional): ").strip()

        # Add course to plan
        planned_course_id = planning_service.add_course_to_plan(
            plan_id=plan_id,
            course_id=course_id,
            semester_number=int(semester_number),
            semester_name=semester_name,
            is_locked=is_locked,
            priority=priority,
            notes=notes if notes else None
        )

        print(f"\n✓ Course added to plan! (Planned Course ID: {planned_course_id})")

        # Detect conflicts
        print("\n--- Checking for conflicts... ---")
        conflicts = planning_service.detect_plan_schedule_conflicts(plan_id)
        if conflicts:
            print(f"\n⚠ {len(conflicts)} conflict(s) detected:")
            for conflict in conflicts[:5]:
                print(f"  • [{conflict['severity']}] {conflict['type']}: {conflict['description']}")
        else:
            print("\n✓ No conflicts detected.")

    except Exception as e:
        print(f"\n✗ Error adding course: {e}")

    input("\nPress Enter to continue...")


def view_prerequisite_chain_menu() -> None:
    """View prerequisite chain for a course."""
    print("\n" + "=" * 60)
    print("VIEW PREREQUISITE CHAIN")
    print("=" * 60)

    course_id = input("\nCourse ID (e.g., CS301): ").strip().upper()
    if not course_id:
        return

    try:
        # Get prerequisite visualization
        chain = planning_service.visualize_prerequisite_chain(course_id)

        if not chain or len(chain) == 1:
            print(f"\n✓ {course_id} has no prerequisites.")
        else:
            print(f"\n--- Prerequisite Chain for {course_id} ---")
            print("(Showing foundation courses first)\n")

            for level, courses in enumerate(chain):
                if level == len(chain) - 1:
                    print(f"Level {level} (Target): {', '.join(courses)}")
                else:
                    print(f"Level {level}: {', '.join(courses)}")

        # Get detailed prerequisite tree
        tree = planning_service.build_prerequisite_tree(course_id)
        total_prereqs = len(planning_service.get_all_prerequisites(course_id))

        print(f"\nTotal Prerequisites (direct + indirect): {total_prereqs}")
        print(f"Prerequisite Depth: {tree.get('total_depth', 0)}")

    except Exception as e:
        print(f"\n✗ Error viewing prerequisites: {e}")

    input("\nPress Enter to continue...")


def check_eligibility_menu(student_id: str) -> None:
    """Check prerequisite eligibility for a course."""
    print("\n" + "=" * 60)
    print("CHECK PREREQUISITE ELIGIBILITY")
    print("=" * 60)

    course_id = input("\nCourse ID (e.g., CS301): ").strip().upper()
    if not course_id:
        return

    try:
        eligibility = planning_service.check_prerequisite_eligibility(student_id, course_id)

        print(f"\n--- Eligibility for {course_id} ---")
        print(f"Eligible: {'✓ Yes' if eligibility['eligible'] else '✗ No'}")
        print(f"Total Prerequisites: {eligibility['total_prerequisites']}")

        if eligibility['met_prerequisites']:
            print(f"\n✓ Met Prerequisites ({len(eligibility['met_prerequisites'])}):")
            for prereq in eligibility['met_prerequisites']:
                print(f"  • {prereq['course_id']}: Grade {prereq['grade']} (Required: {prereq['required_grade']})")

        if eligibility['missing_prerequisites']:
            print(f"\n✗ Missing Prerequisites ({len(eligibility['missing_prerequisites'])}):")
            for prereq in eligibility['missing_prerequisites']:
                print(f"  • {prereq['course_id']}: {prereq['reason']} ({prereq['status']})")

    except Exception as e:
        print(f"\n✗ Error checking eligibility: {e}")

    input("\nPress Enter to continue...")


def detect_conflicts_menu(student_id: str) -> None:
    """Detect scheduling conflicts in a plan."""
    print("\n" + "=" * 60)
    print("DETECT SCHEDULE CONFLICTS")
    print("=" * 60)

    try:
        plans = planning_service.get_student_plans(student_id)

        if not plans:
            print("\nNo course plans found.")
            input("\nPress Enter to continue...")
            return

        # List plans
        for i, plan in enumerate(plans, 1):
            print(f"{i}. {plan['plan_name']} (ID: {plan['plan_id']})")

        plan_choice = input("\nSelect plan to check (or press Enter to cancel): ").strip()
        if not plan_choice.isdigit() or not (1 <= int(plan_choice) <= len(plans)):
            return

        plan_id = plans[int(plan_choice) - 1]['plan_id']

        print("\n--- Analyzing schedule for conflicts... ---")
        conflicts = planning_service.detect_plan_schedule_conflicts(plan_id)

        if not conflicts:
            print("\n✓ No conflicts detected! Your schedule looks good.")
        else:
            print(f"\n⚠ {len(conflicts)} conflict(s) detected:\n")

            # Group by severity
            high = [c for c in conflicts if c['severity'] == 'High']
            medium = [c for c in conflicts if c['severity'] == 'Medium']
            low = [c for c in conflicts if c['severity'] == 'Low']

            if high:
                print(f"HIGH SEVERITY ({len(high)}):")
                for c in high:
                    print(f"  • {c['type']}: {c['description']}")
                    if c.get('suggestions'):
                        print(f"    Suggestions: {', '.join(c['suggestions'][:2])}")
                    print()

            if medium:
                print(f"MEDIUM SEVERITY ({len(medium)}):")
                for c in medium:
                    print(f"  • {c['type']}: {c['description']}")
                    print()

            if low:
                print(f"LOW SEVERITY ({len(low)}):")
                for c in low:
                    print(f"  • {c['type']}: {c['description']}")
                    print()

    except Exception as e:
        print(f"\n✗ Error detecting conflicts: {e}")

    input("\nPress Enter to continue...")


def get_recommendations_menu(student_id: str) -> None:
    """Get course recommendations."""
    print("\n" + "=" * 60)
    print("COURSE RECOMMENDATIONS")
    print("=" * 60)

    semester = input("\nTarget semester (e.g., Fall 2026): ").strip() or "Fall 2026"
    max_recs = input("Number of recommendations (1-20) [10]: ").strip()
    max_recs = int(max_recs) if max_recs.isdigit() else 10

    try:
        print("\n--- Generating recommendations... ---")
        recommendations = planning_service.recommend_courses(student_id, semester, max_recs)

        if not recommendations:
            print("\n✓ No recommendations available at this time.")
        else:
            print(f"\n--- Top {len(recommendations)} Recommended Courses ---\n")

            for i, rec in enumerate(recommendations, 1):
                score_bar = "★" * int(rec['relevance_score']) + "☆" * (5 - int(rec['relevance_score']))
                print(f"{i}. {rec['course_id']}: {rec['course_name']} ({rec['credits']} cr)")
                print(f"   Relevance: {score_bar} ({rec['relevance_score']})")
                print(f"   Reason: {rec['reason']}")
                print()

    except Exception as e:
        print(f"\n✗ Error getting recommendations: {e}")

    input("\nPress Enter to continue...")


def export_plan_menu(student_id: str) -> None:
    """Export a course plan."""
    print("\n" + "=" * 60)
    print("EXPORT COURSE PLAN")
    print("=" * 60)

    try:
        plans = planning_service.get_student_plans(student_id)

        if not plans:
            print("\nNo course plans found.")
            input("\nPress Enter to continue...")
            return

        # List plans
        for i, plan in enumerate(plans, 1):
            print(f"{i}. {plan['plan_name']} (ID: {plan['plan_id']})")

        plan_choice = input("\nSelect plan to export (or press Enter to cancel): ").strip()
        if not plan_choice.isdigit() or not (1 <= int(plan_choice) <= len(plans)):
            return

        plan_id = plans[int(plan_choice) - 1]['plan_id']
        plan_data = planning_service.get_semester_plan(plan_id)

        if not plan_data:
            print("\nPlan not found.")
            return

        # Export as JSON
        export_filename = f"course_plan_{plan_id}.json"
        export_path = os.path.join(tempfile.gettempdir(), export_filename)

        with open(export_path, 'w') as f:
            json.dump(plan_data, f, indent=2, default=str)

        print(f"\n✓ Plan exported to: {export_path}")
        print("\nExport Format: JSON")
        print(f"File Size: {len(json.dumps(plan_data, default=str))} bytes")

        log_activity('export', 'course_plan',
                    details={'plan_id': plan_id, 'format': 'json'})

    except Exception as e:
        print(f"\n✗ Error exporting plan: {e}")

    input("\nPress Enter to continue...")


def generate_auto_plan_menu(student_id: str) -> None:
    """Generate an automatic course plan."""
    print("\n" + "=" * 60)
    print("GENERATE AUTOMATIC COURSE PLAN")
    print("=" * 60)

    # Get student's major
    with get_connection() as conn:
        student = conn.execute("""
            SELECT major FROM students WHERE student_id = ?
        """, (student_id,)).fetchone()

    if not student or not student['major']:
        program_code = input("Program/Major code (e.g., CS, MATH): ").strip()
    else:
        program_code = student['major']
        print(f"Using your major: {program_code}")

    start_semester = input("Start semester (e.g., Fall 2026) [Fall 2026]: ").strip() or "Fall 2026"

    try:
        print("\n--- Generating optimized course plan... ---")
        plan_id = planning_service.generate_auto_plan(student_id, program_code, start_semester)

        print(f"\n✓ Auto-plan generated successfully! (Plan ID: {plan_id})")
        print("\nThe system has:")
        print("  • Analyzed your completed courses")
        print("  • Identified remaining degree requirements")
        print("  • Ordered courses based on prerequisites")
        print("  • Distributed courses across semesters")

        # Show summary
        plan_data = planning_service.get_semester_plan(plan_id)
        if plan_data:
            print(f"\nTotal Courses: {plan_data['total_courses']}")
            print(f"Semesters: {len(plan_data['semesters'])}")

        view_details = input("\nView plan details? (y/n): ").strip().lower()
        if view_details == 'y':
            view_plan_details(plan_id)

    except Exception as e:
        print(f"\n✗ Error generating auto-plan: {e}")

    input("\nPress Enter to continue...")


def manage_prerequisites_menu() -> None:
    """Manage course prerequisites (admin only)."""
    print("\n" + "=" * 60)
    print("MANAGE COURSE PREREQUISITES")
    print("=" * 60)

    print("\n1. Add Prerequisite")
    print("2. Remove Prerequisite")
    print("3. View Prerequisites for Course")
    print("4. Back")

    choice = input("\nSelect option: ").strip()

    if choice == "1":
        add_prerequisite()
    elif choice == "2":
        remove_prerequisite()
    elif choice == "3":
        view_course_prerequisites()


def add_prerequisite() -> None:
    """Add a prerequisite relationship."""
    course_id = input("\nCourse ID: ").strip().upper()
    prereq_id = input("Prerequisite Course ID: ").strip().upper()

    if not course_id or not prereq_id:
        print("Both course IDs are required.")
        return

    prereq_type = input("Type (Required/Recommended) [Required]: ").strip() or "Required"
    min_grade = input("Minimum grade (D/C/B/A) [D]: ").strip().upper() or "D"
    concurrent = input("Can be taken concurrently? (y/n) [n]: ").strip().lower() == 'y'

    try:
        from education_system.university_system.infrastructure.database.db import transaction
        with transaction() as conn:
            conn.execute("""
                INSERT INTO course_prerequisites
                (course_id, prerequisite_course_id, prerequisite_type,
                 minimum_grade, can_be_concurrent)
                VALUES (?, ?, ?, ?, ?)
            """, (course_id, prereq_id, prereq_type, min_grade, concurrent))

        print(f"\n✓ Prerequisite added: {course_id} requires {prereq_id}")
        log_activity('create', 'course_prerequisite',
                    details={'course': course_id, 'prerequisite': prereq_id})

    except Exception as e:
        print(f"\n✗ Error adding prerequisite: {e}")

    input("\nPress Enter to continue...")


def remove_prerequisite() -> None:
    """Remove a prerequisite relationship."""
    course_id = input("\nCourse ID: ").strip().upper()
    prereq_id = input("Prerequisite Course ID to remove: ").strip().upper()

    if not course_id or not prereq_id:
        return

    try:
        from education_system.university_system.infrastructure.database.db import transaction
        with transaction() as conn:
            conn.execute("""
                DELETE FROM course_prerequisites
                WHERE course_id = ? AND prerequisite_course_id = ?
            """, (course_id, prereq_id))

        print(f"\n✓ Prerequisite removed: {course_id} no longer requires {prereq_id}")
        log_activity('delete', 'course_prerequisite',
                    details={'course': course_id, 'prerequisite': prereq_id})

    except Exception as e:
        print(f"\n✗ Error removing prerequisite: {e}")

    input("\nPress Enter to continue...")


def view_course_prerequisites() -> None:
    """View all prerequisites for a course."""
    course_id = input("\nCourse ID: ").strip().upper()
    if not course_id:
        return

    try:
        with get_connection() as conn:
            prereqs = conn.execute("""
                SELECT * FROM course_prerequisites
                WHERE course_id = ?
                ORDER BY prerequisite_course_id
            """, (course_id,)).fetchall()

        if not prereqs:
            print(f"\n✓ {course_id} has no prerequisites.")
        else:
            print(f"\n--- Prerequisites for {course_id} ---\n")
            for prereq in prereqs:
                concurrent = " (Can be concurrent)" if prereq['can_be_concurrent'] else ""
                print(f"• {prereq['prerequisite_course_id']} - {prereq['prerequisite_type']}")
                print(f"  Minimum Grade: {prereq['minimum_grade']}{concurrent}")

    except Exception as e:
        print(f"\n✗ Error viewing prerequisites: {e}")

    input("\nPress Enter to continue...")


def manage_offerings_menu() -> None:
    """Manage course offering patterns (admin only)."""
    print("\n" + "=" * 60)
    print("MANAGE COURSE OFFERINGS")
    print("=" * 60)

    print("\n1. Set Course Offering Pattern")
    print("2. View Course Offerings")
    print("3. Back")

    choice = input("\nSelect option: ").strip()

    if choice == "1":
        set_offering_pattern()
    elif choice == "2":
        view_offering_pattern()


def set_offering_pattern() -> None:
    """Set offering pattern for a course."""
    course_id = input("\nCourse ID: ").strip().upper()
    if not course_id:
        return

    print("\nWhen is this course offered?")
    offered_fall = input("Fall semester? (y/n) [y]: ").strip().lower() != 'n'
    offered_spring = input("Spring semester? (y/n) [y]: ").strip().lower() != 'n'
    offered_summer = input("Summer session? (y/n) [n]: ").strip().lower() == 'y'

    offered_years = input("Offered: (Every/Odd/Even) [Every]: ").strip() or "Every"

    try:
        from education_system.university_system.infrastructure.database.db import transaction
        with transaction() as conn:
            conn.execute("""
                INSERT INTO course_offerings
                (course_id, offered_fall, offered_spring, offered_summer, offered_years)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(course_id) DO UPDATE SET
                    offered_fall = excluded.offered_fall,
                    offered_spring = excluded.offered_spring,
                    offered_summer = excluded.offered_summer,
                    offered_years = excluded.offered_years
            """, (course_id, offered_fall, offered_spring, offered_summer, offered_years))

        print(f"\n✓ Offering pattern updated for {course_id}")
        log_activity('update', 'course_offerings',
                    details={'course_id': course_id})

    except Exception as e:
        print(f"\n✗ Error updating offering pattern: {e}")

    input("\nPress Enter to continue...")


def view_offering_pattern() -> None:
    """View offering pattern for a course."""
    course_id = input("\nCourse ID: ").strip().upper()
    if not course_id:
        return

    try:
        with get_connection() as conn:
            offering = conn.execute("""
                SELECT * FROM course_offerings
                WHERE course_id = ?
            """, (course_id,)).fetchone()

        if not offering:
            print(f"\n✓ No offering pattern set for {course_id}.")
        else:
            print(f"\n--- Offering Pattern for {course_id} ---\n")
            semesters = []
            if offering['offered_fall']:
                semesters.append("Fall")
            if offering['offered_spring']:
                semesters.append("Spring")
            if offering['offered_summer']:
                semesters.append("Summer")

            print(f"Offered: {', '.join(semesters) if semesters else 'Never'}")
            print(f"Years: {offering['offered_years']}")

    except Exception as e:
        print(f"\n✗ Error viewing offering pattern: {e}")

    input("\nPress Enter to continue...")


def view_student_plans_admin_menu() -> None:
    """View course plans for any student (admin only)."""
    print("\n" + "=" * 60)
    print("VIEW STUDENT COURSE PLANS (Admin)")
    print("=" * 60)

    student_id = input("\nStudent ID: ").strip()
    if not student_id:
        return

    try:
        # Verify student exists
        with get_connection() as conn:
            student = conn.execute("""
                SELECT student_id, first_name, last_name, major
                FROM students WHERE student_id = ?
            """, (student_id,)).fetchone()

        if not student:
            print(f"\n✗ Student {student_id} not found.")
            input("\nPress Enter to continue...")
            return

        print(f"\nStudent: {student['first_name']} {student['last_name']}")
        print(f"Major: {student['major']}")

        # Show their plans
        view_plans_menu(student_id)

    except Exception as e:
        print(f"\n✗ Error viewing student plans: {e}")
        input("\nPress Enter to continue...")


# Wrapper class for compatibility with main CLI
class CoursePlanningCLI:
    """Wrapper class for Course Planning CLI."""

    def __init__(self):
        """Initialize the Course Planning CLI."""
        init_course_planning()

    def run(self):
        """Run the Course Planning CLI."""
        display_course_planning_menu()
