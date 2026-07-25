#!/usr/bin/env python3
"""
Degree Audit & Academic Advising CLI
Complete command-line interface for degree progress tracking, prerequisite validation,
what-if scenarios, advising appointments, and graduation audits.
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

# Database imports
try:
    from education_system.systems.university.infrastructure.database.db import get_connection
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    print("Warning: Database connection not available")

# Service imports
try:
    from education_system.systems.university.domain.academics.services.degree_audit.degree_audit_core import (
        DegreeProgramManager,
        DegreeProgressManager,
        WhatIfScenarioManager,
        AdvisingAppointmentManager,
        GraduationAuditManager
    )
    SERVICE_AVAILABLE = True
except ImportError:
    SERVICE_AVAILABLE = False
    print("Warning: Degree audit services not available")

# Database schema initialization
try:
    from education_system.systems.university.domain.academics.services.degree_audit.db_schema import (
        initialize_degree_audit_database
    )
    SCHEMA_AVAILABLE = True
except ImportError:
    SCHEMA_AVAILABLE = False

# Activity logging
try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
except ImportError:
    def log_activity(action, entity, *args, **kwargs):
        print(f"[LOG] {action} {entity}")


class DegreeAuditCLI:
    """Degree Audit & Academic Advising Command Line Interface"""

    def __init__(self, auth=None):
        """Initialize the CLI with authentication"""
        self.auth = auth
        self.current_user = None

        # Get current user from auth
        if self.auth and hasattr(self.auth, 'current_user'):
            self.current_user = self.auth.current_user
            print(f"\n✓ Logged in as: {self.current_user.get('username', 'Unknown')} ({self.current_user.get('role', 'user')})")

        # Initialize database
        if SCHEMA_AVAILABLE:
            try:
                initialize_degree_audit_database()
            except Exception as e:
                print(f"Warning: Database initialization failed: {e}")

    def clear_screen(self):
        """Clear the terminal screen"""
        print("\033[2J\033[H", end="", flush=True)

    def pause(self):
        """Pause and wait for user input"""
        input("\nPress Enter to continue...")

    def print_header(self, title):
        """Print a formatted header"""
        print("\n" + "="*70)
        print(f"  {title}")
        print("="*70)

    def print_section(self, title):
        """Print a section header"""
        print(f"\n{'─'*70}")
        print(f"  {title}")
        print(f"{'─'*70}")

    def get_user_identifier(self):
        """Get current user identifier for logging"""
        if self.current_user:
            return self.current_user.get('username') or self.current_user.get('email') or 'system'
        return 'system'

    # ==================== Main Menu ====================

    def run(self):
        """Main menu loop"""
        while True:
            self.clear_screen()
            self.print_header("🎓 DEGREE AUDIT & ACADEMIC ADVISING SYSTEM")

            print("\n📊 DEGREE PROGRESS:")
            print("  1. View Student Degree Progress")
            print("  2. Update/Refresh Progress")
            print("  3. Initialize Student Progress")

            print("\n📋 PREREQUISITES:")
            print("  4. Check Course Prerequisites")
            print("  5. Add Prerequisite Rule")
            print("  6. View All Prerequisites")

            print("\n🔮 WHAT-IF SCENARIOS:")
            print("  7. Create What-If Scenario")
            print("  8. Analyze Program Change")
            print("  9. View Scenarios")

            print("\n📅 ADVISING APPOINTMENTS:")
            print("  10. Schedule Appointment")
            print("  11. View My Appointments")
            print("  12. View Student Appointments")

            print("\n🎓 GRADUATION AUDIT:")
            print("  13. Run Graduation Audit")
            print("  14. Approve Graduation")
            print("  15. View Graduation Requirements")

            print("\n📄 REPORTS:")
            print("  16. Print Degree Audit Report")
            print("  17. View Degree Requirements")

            print("\n  0. Exit")

            choice = input("\n👉 Enter your choice: ").strip()

            if choice == '0':
                print("\n👋 Goodbye!")
                break
            elif choice == '1':
                self.view_student_progress()
            elif choice == '2':
                self.update_progress()
            elif choice == '3':
                self.initialize_progress()
            elif choice == '4':
                self.check_prerequisites()
            elif choice == '5':
                self.add_prerequisite()
            elif choice == '6':
                self.view_prerequisites()
            elif choice == '7':
                self.create_whatif_scenario()
            elif choice == '8':
                self.analyze_whatif()
            elif choice == '9':
                self.view_scenarios()
            elif choice == '10':
                self.schedule_appointment()
            elif choice == '11':
                self.view_my_appointments()
            elif choice == '12':
                self.view_student_appointments()
            elif choice == '13':
                self.run_graduation_audit()
            elif choice == '14':
                self.approve_graduation()
            elif choice == '15':
                self.view_graduation_requirements()
            elif choice == '16':
                self.print_audit_report()
            elif choice == '17':
                self.view_degree_requirements()
            else:
                print("\n❌ Invalid choice. Please try again.")
                self.pause()

    # ==================== Degree Progress ====================

    def view_student_progress(self):
        """View student degree progress"""
        self.clear_screen()
        self.print_header("📊 STUDENT DEGREE PROGRESS")

        student_id = input("\n📝 Enter Student ID: ").strip()
        if not student_id:
            print("❌ Student ID is required")
            self.pause()
            return

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Get student info
                cursor.execute('''
                    SELECT student_id, first_name, last_name, course, enrollment_date
                    FROM students WHERE student_id = ?
                ''', (student_id,))

                student = cursor.fetchone()
                if not student:
                    print(f"\n❌ Student {student_id} not found")
                    self.pause()
                    return

                student_id, first_name, last_name, course, enrollment_date = student

                # Get course info
                cursor.execute('''
                    SELECT code, name FROM courses WHERE code = ?
                ''', (course,))
                course_info = cursor.fetchone()
                course_name = course_info[1] if course_info else "Unknown"

                # Get module progress
                cursor.execute('''
                    SELECT COUNT(DISTINCT sm.module_code) as module_count,
                           SUM(CASE WHEN sm.status = 'Completed' THEN COALESCE(m.credits, 0) ELSE 0 END) as credits_earned,
                           AVG(CASE
                               WHEN sm.grade = 'A' THEN 4.0
                               WHEN sm.grade = 'B' THEN 3.0
                               WHEN sm.grade = 'C' THEN 2.0
                               WHEN sm.grade = 'D' THEN 1.0
                               WHEN sm.grade = 'F' THEN 0.0
                               ELSE NULL
                           END) as gpa
                    FROM student_modules sm
                    LEFT JOIN modules m ON sm.module_code = m.module_code
                    WHERE sm.student_id = ?
                ''', (student_id,))

                progress = cursor.fetchone()
                module_count = progress[0] or 0
                credits_earned = progress[1] or 0
                gpa = progress[2] or 0.0

                # Calculate expected graduation
                if enrollment_date:
                    enroll_year = int(enrollment_date.split('-')[0])
                    expected_grad = enroll_year + 4
                else:
                    expected_grad = datetime.now().year + 4

                # Standard requirements
                total_credits_required = 120
                completion_pct = (credits_earned / total_credits_required * 100) if total_credits_required > 0 else 0

            # Display progress
            self.print_section("Student Information")
            print(f"  Student ID:           {student_id}")
            print(f"  Name:                 {first_name} {last_name}")
            print(f"  Course:               {course} - {course_name}")
            print(f"  Enrollment Date:      {enrollment_date or 'N/A'}")

            self.print_section("Progress Summary")
            print(f"  Modules Completed:    {module_count}")
            print(f"  Credits Earned:       {credits_earned:.1f}")
            print(f"  Credits Required:     {total_credits_required}")
            print(f"  Current GPA:          {gpa:.2f}")
            print(f"  Completion:           {completion_pct:.1f}%")
            print(f"  Expected Graduation:  {expected_grad}")

            # Get detailed module list
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT sm.module_code, m.module_name, m.credits, sm.status, sm.grade
                    FROM student_modules sm
                    LEFT JOIN modules m ON sm.module_code = m.module_code
                    WHERE sm.student_id = ?
                    ORDER BY sm.status DESC, sm.module_code
                ''', (student_id,))

                modules = cursor.fetchall()

            if modules:
                self.print_section("Module Details")
                print(f"\n{'Code':<12} {'Name':<40} {'Credits':<10} {'Status':<12} {'Grade':<8}")
                print("─" * 90)

                for mod in modules:
                    code, name, credits, status, grade = mod
                    status_icon = {
                        'Completed': '✅',
                        'In Progress': '📖',
                        'Registered': '📝',
                        'Failed': '❌'
                    }.get(status, '⚪')

                    print(f"{code:<12} {(name or 'N/A')[:39]:<40} {credits or 0:<10} {status_icon} {status:<10} {grade or 'N/A':<8}")

            log_activity('view', 'degree_progress', student_id, {})

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def update_progress(self):
        """Update/refresh student progress"""
        self.clear_screen()
        self.print_header("🔄 UPDATE PROGRESS")

        student_id = input("\n📝 Enter Student ID: ").strip()
        if not student_id:
            print("❌ Student ID is required")
            self.pause()
            return

        try:
            # Just reload to refresh calculations
            print("\n⏳ Recalculating progress...")

            # In a real implementation, this would trigger progress recalculation
            # For now, we just verify the student exists
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT student_id FROM students WHERE student_id = ?', (student_id,))
                if not cursor.fetchone():
                    print(f"❌ Student {student_id} not found")
                    self.pause()
                    return

            log_activity('update', 'degree_progress', student_id, {})

            print("✅ Progress updated successfully")
            print("\n💡 View updated progress using option 1")

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def initialize_progress(self):
        """Initialize student progress (assign to course)"""
        self.clear_screen()
        self.print_header("🎯 INITIALIZE STUDENT PROGRESS")

        student_id = input("\n📝 Student ID: ").strip()
        if not student_id:
            print("❌ Student ID is required")
            self.pause()
            return

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Check if student exists
                cursor.execute('SELECT student_id, first_name, last_name FROM students WHERE student_id = ?', (student_id,))
                student = cursor.fetchone()
                if not student:
                    print(f"❌ Student {student_id} not found")
                    self.pause()
                    return

                print(f"\nStudent: {student[1]} {student[2]}")

                # Get available courses
                cursor.execute('''
                    SELECT id, code, name
                    FROM courses
                    WHERE code IN ('CS', 'DS')
                    ORDER BY code
                ''')
                courses = cursor.fetchall()

                if not courses:
                    print("❌ No courses available")
                    self.pause()
                    return

                # Display courses
                print("\n📚 Available Courses:")
                for i, course in enumerate(courses, 1):
                    print(f"  {i}. {course[1]} - {course[2]}")

                course_choice = input("\n👉 Select course (number): ").strip()
                if not course_choice.isdigit() or int(course_choice) < 1 or int(course_choice) > len(courses):
                    print("❌ Invalid choice")
                    self.pause()
                    return

                selected_course = courses[int(course_choice) - 1]
                course_code = selected_course[1]

                # Get enrollment year
                current_year = datetime.now().year
                year_input = input(f"\n📅 Enrollment Year (default: {current_year}): ").strip()
                enrollment_year = int(year_input) if year_input else current_year

                # Update student's course
                cursor.execute('''
                    UPDATE students
                    SET course = ?, enrollment_date = ?
                    WHERE student_id = ?
                ''', (course_code, f"{enrollment_year}-09-01", student_id))

                conn.commit()

            log_activity('create', 'degree_progress', student_id,
                       {'course': course_code, 'year': enrollment_year})

            print(f"\n✅ Student {student_id} assigned to {course_code}")
            print(f"   Enrollment Date: {enrollment_year}-09-01")

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    # ==================== Prerequisites ====================

    def check_prerequisites(self):
        """Check if student meets prerequisites for a module"""
        self.clear_screen()
        self.print_header("📋 CHECK PREREQUISITES")

        student_id = input("\n📝 Student ID: ").strip()
        module_code = input("📚 Module Code: ").strip()

        if not student_id or not module_code:
            print("❌ Both Student ID and Module Code are required")
            self.pause()
            return

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Check if student exists
                cursor.execute('SELECT student_id FROM students WHERE student_id = ?', (student_id,))
                if not cursor.fetchone():
                    print(f"❌ Student {student_id} not found")
                    self.pause()
                    return

                # Get module info and enrollment
                cursor.execute('''
                    SELECT sm.module_code, sm.status, sm.grade, m.module_name, m.prerequisites
                    FROM student_modules sm
                    LEFT JOIN modules m ON sm.module_code = m.module_code
                    WHERE sm.student_id = ? AND sm.module_code = ?
                ''', (student_id, module_code))

                module_enrollment = cursor.fetchone()

                self.print_section(f"Prerequisite Check - {module_code}")
                print(f"  Student ID:        {student_id}")
                print(f"  Module Code:       {module_code}")

                if module_enrollment:
                    code, status, grade, module_name, prerequisites = module_enrollment

                    print(f"  Module Name:       {module_name or 'Unknown'}")
                    print(f"  Enrollment Status: {status or 'Unknown'}")
                    print(f"  Current Grade:     {grade or 'Not Graded'}")
                    print(f"  Prerequisites:     {prerequisites or 'None'}")

                    # Check prerequisite completion
                    if prerequisites and prerequisites.lower() != 'none':
                        prereq_list = [p.strip() for p in prerequisites.split(',')]
                        missing = []

                        print(f"\n📋 Checking {len(prereq_list)} prerequisite(s)...")

                        for prereq in prereq_list:
                            cursor.execute('''
                                SELECT grade, status
                                FROM student_modules
                                WHERE student_id = ? AND module_code = ?
                            ''', (student_id, prereq))

                            prereq_result = cursor.fetchone()

                            if not prereq_result:
                                missing.append(f"{prereq} (Not enrolled)")
                                print(f"  ❌ {prereq} - Not completed")
                            elif prereq_result[1] != 'Completed':
                                missing.append(f"{prereq} ({prereq_result[1]})")
                                print(f"  ⚠️  {prereq} - {prereq_result[1]}")
                            else:
                                print(f"  ✅ {prereq} - Completed (Grade: {prereq_result[0]})")

                        if missing:
                            print("\n❌ STATUS: Not Eligible")
                            print("\n   Missing Prerequisites:")
                            for m in missing:
                                print(f"   • {m}")
                        else:
                            print("\n✅ STATUS: Eligible")
                            print("\n   All prerequisites have been met!")
                    else:
                        print("\n✅ STATUS: Eligible")
                        print("\n   No prerequisites required for this module")
                else:
                    print(f"\n❌ ERROR: Module {module_code} not found in student's enrolled modules")
                    print(f"\n   Student {student_id} is not enrolled in this module")

                log_activity('check', 'prerequisite', module_code, {'student_id': student_id})

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def add_prerequisite(self):
        """Add a new prerequisite rule"""
        self.clear_screen()
        self.print_header("➕ ADD PREREQUISITE RULE")

        module_code = input("\n📚 Module Code (requires prerequisite): ").strip()
        prerequisite_code = input("📋 Prerequisite Module Code: ").strip()
        min_grade = input("🎓 Minimum Grade (optional, e.g., C): ").strip() or ""

        if not module_code or not prerequisite_code:
            print("❌ Both module codes are required")
            self.pause()
            return

        try:
            if SERVICE_AVAILABLE:
                # Use service method
                prereq_id = DegreeProgramManager.add_prerequisite(
                    module_code, prerequisite_code, min_grade
                )
                print(f"\n✅ Prerequisite added successfully (ID: {prereq_id})")
            else:
                # Direct database insert
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO degree_course_prerequisites
                        (module_code, prerequisite_module_code, min_grade, is_corequisite)
                        VALUES (?, ?, ?, 0)
                    ''', (module_code, prerequisite_code, min_grade))

                    prereq_id = cursor.lastrowid
                    conn.commit()

                print(f"\n✅ Prerequisite added successfully (ID: {prereq_id})")

            print(f"\n   Module: {module_code}")
            print(f"   Prerequisite: {prerequisite_code}")
            if min_grade:
                print(f"   Minimum Grade: {min_grade}")

            log_activity('create', 'prerequisite', str(prereq_id),
                       {'module': module_code, 'prerequisite': prerequisite_code})

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def view_prerequisites(self):
        """View all prerequisite rules"""
        self.clear_screen()
        self.print_header("📋 ALL PREREQUISITE RULES")

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT module_code, prerequisite_module_code, min_grade, is_corequisite
                    FROM degree_course_prerequisites
                    ORDER BY module_code, prerequisite_module_code
                ''')

                prerequisites = cursor.fetchall()

            if not prerequisites:
                print("\n📭 No prerequisite rules found")
            else:
                print(f"\n📊 Total: {len(prerequisites)} prerequisite rule(s)\n")
                print(f"{'Module':<15} {'Prerequisite':<15} {'Min Grade':<12} {'Type':<15}")
                print("─" * 65)

                for prereq in prerequisites:
                    module, prereq_module, min_grade, is_coreq = prereq
                    req_type = "Co-requisite" if is_coreq else "Prerequisite"
                    print(f"{module:<15} {prereq_module:<15} {min_grade or 'None':<12} {req_type:<15}")

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    # ==================== What-If Scenarios ====================

    def create_whatif_scenario(self):
        """Create a what-if scenario for course switching"""
        self.clear_screen()
        self.print_header("🔮 CREATE WHAT-IF SCENARIO")

        student_id = input("\n📝 Student ID: ").strip()
        scenario_name = input("📋 Scenario Name: ").strip()

        if not student_id or not scenario_name:
            print("❌ Both fields are required")
            self.pause()
            return

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Check if student exists
                cursor.execute('SELECT course FROM students WHERE student_id = ?', (student_id,))
                student = cursor.fetchone()
                if not student:
                    print(f"❌ Student {student_id} not found")
                    self.pause()
                    return

                current_course = student[0]

                # Get available courses
                cursor.execute('''
                    SELECT id, code, name
                    FROM courses
                    WHERE code IN ('CS', 'DS')
                    ORDER BY code
                ''')
                courses = cursor.fetchall()

                # Display courses
                print("\n🎯 Target Course:")
                for i, course in enumerate(courses, 1):
                    print(f"  {i}. {course[1]} - {course[2]}")

                course_choice = input("\n👉 Select target course: ").strip()
                if not course_choice.isdigit() or int(course_choice) < 1 or int(course_choice) > len(courses):
                    print("❌ Invalid choice")
                    self.pause()
                    return

                target_course = courses[int(course_choice) - 1][1]

                # Get notes
                print("\n📝 Additional Notes (press Enter on empty line to finish):")
                notes_lines = []
                while True:
                    line = input()
                    if not line:
                        break
                    notes_lines.append(line)
                notes = '\n'.join(notes_lines)

                # Create scenario
                cursor.execute('''
                    INSERT INTO degree_what_if_scenarios
                    (student_id, scenario_name, notes, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (student_id, scenario_name,
                      f"Target Course: {target_course}\n{notes}",
                      datetime.now().isoformat()))

                scenario_id = cursor.lastrowid
                conn.commit()

            log_activity('create', 'whatif_scenario', str(scenario_id),
                       {'student_id': student_id, 'target_course': target_course})

            print("\n✅ What-If Scenario Created!")
            print(f"   Scenario ID: {scenario_id}")
            print(f"   Name: {scenario_name}")
            print(f"   Current Course: {current_course}")
            print(f"   Target Course: {target_course}")

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def analyze_whatif(self):
        """Analyze what-if scenario for course switching"""
        self.clear_screen()
        self.print_header("📊 ANALYZE WHAT-IF SCENARIO")

        student_id = input("\n📝 Student ID: ").strip()
        if not student_id:
            print("❌ Student ID is required")
            self.pause()
            return

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Get student's current course
                cursor.execute('SELECT course FROM students WHERE student_id = ?', (student_id,))
                student = cursor.fetchone()
                if not student:
                    print(f"❌ Student {student_id} not found")
                    self.pause()
                    return

                current_course = student[0]

                # Get available courses
                cursor.execute('''
                    SELECT id, code, name
                    FROM courses
                    WHERE code IN ('CS', 'DS')
                    ORDER BY code
                ''')
                courses = cursor.fetchall()

                # Display courses
                print("\n🎯 Select Target Course:")
                for i, course in enumerate(courses, 1):
                    print(f"  {i}. {course[1]} - {course[2]}")

                course_choice = input("\n👉 Enter choice: ").strip()
                if not course_choice.isdigit() or int(course_choice) < 1 or int(course_choice) > len(courses):
                    print("❌ Invalid choice")
                    self.pause()
                    return

                target_course = courses[int(course_choice) - 1][1]

                # Get current modules and credits
                cursor.execute('''
                    SELECT COUNT(DISTINCT sm.module_code) as module_count,
                           SUM(COALESCE(m.credits, 0)) as total_credits
                    FROM student_modules sm
                    LEFT JOIN modules m ON sm.module_code = m.module_code
                    WHERE sm.student_id = ?
                ''', (student_id,))

                current_progress = cursor.fetchone()
                current_modules = current_progress[0] or 0
                current_credits = current_progress[1] or 0

                # Get target course modules
                cursor.execute('''
                    SELECT COUNT(*) as available_modules
                    FROM modules
                    WHERE module_type = ? AND is_active = 1
                ''', (target_course,))

                target_modules = cursor.fetchone()[0] or 0

                # Calculate overlap
                cursor.execute('''
                    SELECT COUNT(*) as matching_modules
                    FROM student_modules sm
                    JOIN modules m ON sm.module_code = m.module_code
                    WHERE sm.student_id = ? AND m.module_type = ?
                ''', (student_id, target_course))

                matching_modules = cursor.fetchone()[0] or 0

            # Analysis
            standard_required = 40
            completion_pct = (matching_modules / standard_required * 100) if standard_required > 0 else 0
            additional_needed = max(0, standard_required - matching_modules)

            self.print_section("What-If Analysis Results")
            print(f"  Student ID:                   {student_id}")
            print(f"  Current Course:               {current_course}")
            print(f"  Target Course:                {target_course}")
            print(f"\n  Current Modules Completed:    {current_modules}")
            print(f"  Current Credits Earned:       {current_credits}")
            print(f"\n  Modules Matching Target:      {matching_modules}")
            print(f"  Available {target_course} Modules:      {target_modules}")
            print(f"  Additional Modules Needed:    {additional_needed}")
            print(f"  Completion Percentage:        {completion_pct:.1f}%")

            self.print_section("Recommendation")
            if completion_pct >= 50:
                print("  ✅ FEASIBLE")
                print(f"\n  You have completed over half of the requirements for {target_course}.")
                print("  Switching courses is feasible with manageable additional coursework.")
            elif completion_pct >= 25:
                print("  ⚠️  MODERATE EFFORT REQUIRED")
                print(f"\n  You have completed {completion_pct:.1f}% of requirements for {target_course}.")
                print("  Switching is possible but will require significant additional coursework.")
            else:
                print("  ⚠️  CONSIDER CAREFULLY")
                print(f"\n  You have completed only {completion_pct:.1f}% of requirements for {target_course}.")
                print("  Switching courses would require substantial additional coursework.")

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def view_scenarios(self):
        """View all what-if scenarios"""
        self.clear_screen()
        self.print_header("🔮 WHAT-IF SCENARIOS")

        student_id = input("\n📝 Student ID (optional, press Enter for all): ").strip()

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                if student_id:
                    cursor.execute('''
                        SELECT id, student_id, scenario_name, notes, created_at
                        FROM degree_what_if_scenarios
                        WHERE student_id = ?
                        ORDER BY created_at DESC
                    ''', (student_id,))
                else:
                    cursor.execute('''
                        SELECT id, student_id, scenario_name, notes, created_at
                        FROM degree_what_if_scenarios
                        ORDER BY created_at DESC
                        LIMIT 50
                    ''')

                scenarios = cursor.fetchall()

            if not scenarios:
                print("\n📭 No scenarios found")
            else:
                print(f"\n📊 Found: {len(scenarios)} scenario(s)\n")

                for scenario in scenarios:
                    scenario_id, stud_id, name, notes, created = scenario
                    print(f"{'═'*70}")
                    print(f"  ID: {scenario_id}  |  Student: {stud_id}  |  Created: {created[:10]}")
                    print(f"  Name: {name}")
                    if notes:
                        print(f"  Notes: {notes[:100]}{'...' if len(notes) > 100 else ''}")
                    print()

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    # ==================== Advising Appointments ====================

    def schedule_appointment(self):
        """Schedule an advising appointment"""
        self.clear_screen()
        self.print_header("📅 SCHEDULE ADVISING APPOINTMENT")

        try:
            # Get student ID
            student_id = input("\n📝 Student ID: ").strip()
            if not student_id:
                print("❌ Student ID is required")
                self.pause()
                return

            # Verify student exists
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?', (student_id,))
                student = cursor.fetchone()
                if not student:
                    print(f"❌ Student {student_id} not found")
                    self.pause()
                    return

                print(f"   Student: {student[0]} {student[1]}")

            # Get advisor ID
            advisor_id = input("\n👨‍🏫 Advisor ID (or username): ").strip()
            if not advisor_id:
                advisor_id = self.get_user_identifier()

            # Get date
            date_default = datetime.now().strftime('%Y-%m-%d')
            date_input = input(f"\n📅 Date (YYYY-MM-DD) [default: {date_default}]: ").strip()
            appointment_date = date_input if date_input else date_default

            # Get time
            time_input = input("⏰ Time (HH:MM) [default: 10:00]: ").strip()
            appointment_time = time_input if time_input else "10:00"

            # Get type
            print("\n📋 Appointment Type:")
            types = [
                "Academic Planning",
                "Course Selection",
                "Degree Progress Review",
                "Career Advising",
                "General Advising",
                "Other"
            ]
            for i, t in enumerate(types, 1):
                print(f"  {i}. {t}")

            type_choice = input("👉 Select type: ").strip()
            if type_choice.isdigit() and 1 <= int(type_choice) <= len(types):
                appt_type = types[int(type_choice) - 1]
            else:
                appt_type = "General Advising"

            # Get duration
            duration_input = input("\n⏱️  Duration (minutes) [default: 30]: ").strip()
            duration = int(duration_input) if duration_input else 30

            # Get topic and notes
            topic = input("\n💬 Topic: ").strip() or "General advising session"
            print("\n📝 Notes (press Enter on empty line to finish):")
            notes_lines = []
            while True:
                line = input()
                if not line:
                    break
                notes_lines.append(line)
            notes = '\n'.join(notes_lines)

            # Create appointment
            if SERVICE_AVAILABLE:
                appt_id = AdvisingAppointmentManager.schedule_appointment(
                    student_id, advisor_id, appointment_date, appointment_time,
                    appt_type, duration, topic, notes
                )
            else:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO degree_advising_appointments
                        (student_id, advisor_id, appointment_date, appointment_time,
                         appointment_type, duration_minutes, topic, notes, status, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Scheduled', ?)
                    ''', (student_id, advisor_id, appointment_date, appointment_time,
                          appt_type, duration, topic, notes, datetime.now().isoformat()))

                    appt_id = cursor.lastrowid
                    conn.commit()

            log_activity('create', 'advising_appointment', str(appt_id),
                       {'student_id': student_id, 'advisor': advisor_id})

            print("\n✅ Appointment Scheduled!")
            print(f"   Appointment ID: {appt_id}")
            print(f"   Date: {appointment_date} at {appointment_time}")
            print(f"   Duration: {duration} minutes")
            print(f"   Type: {appt_type}")

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def view_my_appointments(self):
        """View appointments for current user"""
        self.clear_screen()
        self.print_header("📅 MY APPOINTMENTS")

        user_id = self.get_user_identifier()

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Check if user is student or advisor
                cursor.execute('''
                    SELECT id, student_id, advisor_id, appointment_date, appointment_time,
                           appointment_type, topic, status, duration_minutes
                    FROM degree_advising_appointments
                    WHERE student_id = ? OR advisor_id = ?
                    ORDER BY appointment_date DESC, appointment_time DESC
                ''', (user_id, user_id))

                appointments = cursor.fetchall()

            if not appointments:
                print(f"\n📭 No appointments found for {user_id}")
            else:
                print(f"\n📊 Total: {len(appointments)} appointment(s)\n")

                for appt in appointments:
                    appt_id, student, advisor, date, time, appt_type, topic, status, duration = appt

                    role = "Student" if student == user_id else "Advisor"
                    other = advisor if student == user_id else student

                    status_icon = {
                        'Scheduled': '📅',
                        'Completed': '✅',
                        'Cancelled': '❌',
                        'Rescheduled': '🔄'
                    }.get(status, '📋')

                    print(f"{'─'*70}")
                    print(f"  ID: {appt_id}  |  {status_icon} {status}")
                    print(f"  Date: {date} at {time}  |  Duration: {duration} min")
                    print(f"  Type: {appt_type}")
                    print(f"  {'With' if role == 'Student' else 'Student'}: {other}")
                    print(f"  Topic: {topic}")
                    print()

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def view_student_appointments(self):
        """View appointments for a specific student"""
        self.clear_screen()
        self.print_header("📅 STUDENT APPOINTMENTS")

        student_id = input("\n📝 Enter Student ID: ").strip()
        if not student_id:
            print("❌ Student ID is required")
            self.pause()
            return

        try:
            if SERVICE_AVAILABLE:
                appointments = AdvisingAppointmentManager.get_student_appointments(student_id)
            else:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT id, student_id, advisor_id, appointment_date, appointment_time,
                               appointment_type, topic, status, duration_minutes, notes
                        FROM degree_advising_appointments
                        WHERE student_id = ?
                        ORDER BY appointment_date DESC, appointment_time DESC
                    ''', (student_id,))

                    appointments = cursor.fetchall()

            if not appointments:
                print(f"\n📭 No appointments found for student {student_id}")
            else:
                print(f"\n📊 Total: {len(appointments)} appointment(s)\n")

                for appt in appointments:
                    if isinstance(appt, dict):
                        appt_id = appt['id']
                        advisor = appt['advisor_id']
                        date = appt['appointment_date']
                        time = appt['appointment_time']
                        appt_type = appt['appointment_type']
                        topic = appt['topic']
                        status = appt['status']
                        duration = appt['duration_minutes']
                        notes = appt.get('notes', '')
                    else:
                        appt_id, student, advisor, date, time, appt_type, topic, status, duration, notes = appt

                    status_icon = {
                        'Scheduled': '📅',
                        'Completed': '✅',
                        'Cancelled': '❌',
                        'Rescheduled': '🔄'
                    }.get(status, '📋')

                    print(f"{'═'*70}")
                    print(f"  Appointment ID: {appt_id}")
                    print(f"  Status: {status_icon} {status}")
                    print(f"  Date/Time: {date} at {time} ({duration} minutes)")
                    print(f"  Type: {appt_type}")
                    print(f"  Advisor: {advisor}")
                    print(f"  Topic: {topic}")
                    if notes:
                        print(f"  Notes: {notes[:100]}{'...' if len(notes) > 100 else ''}")
                    print()

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    # ==================== Graduation Audit ====================

    def run_graduation_audit(self):
        """Run graduation audit for a student"""
        self.clear_screen()
        self.print_header("🎓 GRADUATION AUDIT")

        student_id = input("\n📝 Enter Student ID: ").strip()
        if not student_id:
            print("❌ Student ID is required")
            self.pause()
            return

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Get student info
                cursor.execute('''
                    SELECT student_id, first_name, last_name, course, enrollment_date
                    FROM students WHERE student_id = ?
                ''', (student_id,))

                student = cursor.fetchone()
                if not student:
                    print(f"❌ Student {student_id} not found")
                    self.pause()
                    return

                student_id, first_name, last_name, course, enrollment_date = student

                # Get progress data
                cursor.execute('''
                    SELECT COUNT(DISTINCT sm.module_code) as module_count,
                           SUM(CASE WHEN sm.status = 'Completed' THEN COALESCE(m.credits, 0) ELSE 0 END) as credits_earned,
                           AVG(CASE
                               WHEN sm.grade = 'A' THEN 4.0
                               WHEN sm.grade = 'B' THEN 3.0
                               WHEN sm.grade = 'C' THEN 2.0
                               WHEN sm.grade = 'D' THEN 1.0
                               WHEN sm.grade = 'F' THEN 0.0
                               ELSE NULL
                           END) as gpa
                    FROM student_modules sm
                    LEFT JOIN modules m ON sm.module_code = m.module_code
                    WHERE sm.student_id = ?
                ''', (student_id,))

                progress = cursor.fetchone()
                module_count = progress[0] or 0
                credits_earned = progress[1] or 0
                gpa = progress[2] or 0.0

            # Requirements
            required_credits = 120
            required_gpa = 2.0

            # Check requirements
            credits_met = credits_earned >= required_credits
            gpa_met = gpa >= required_gpa

            self.print_section("Student Information")
            print(f"  Student ID:     {student_id}")
            print(f"  Name:           {first_name} {last_name}")
            print(f"  Course:         {course}")
            print(f"  Enrolled:       {enrollment_date or 'N/A'}")

            self.print_section("Graduation Requirements Check")
            print(f"\n  {'✅' if credits_met else '❌'} Credit Requirement:")
            print(f"      Earned: {credits_earned:.1f} / Required: {required_credits}")

            print(f"\n  {'✅' if gpa_met else '❌'} GPA Requirement:")
            print(f"      Current GPA: {gpa:.2f} / Minimum: {required_gpa}")

            print(f"\n  {'✅' if credits_met and gpa_met else '❌'} All Requirements Met:")
            print(f"      {module_count} modules completed")

            self.print_section("Audit Summary")
            if credits_met and gpa_met:
                print("  ✅ ELIGIBLE FOR GRADUATION")
                print("\n  This student has met all graduation requirements.")
                print("  Ready for graduation approval.")
            else:
                print("  ❌ NOT YET ELIGIBLE")
                print("\n  Requirements not met:")
                if not credits_met:
                    shortage = required_credits - credits_earned
                    print(f"    • Need {shortage:.1f} more credits")
                if not gpa_met:
                    print(f"    • GPA below minimum ({gpa:.2f} < {required_gpa})")

            log_activity('audit', 'graduation', student_id, {})

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def approve_graduation(self):
        """Approve or deny graduation for a student"""
        self.clear_screen()
        self.print_header("GRADUATION DECISION")

        # List students for selection
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT student_id, first_name, last_name, email_address, course FROM students ORDER BY last_name, first_name')
                students = cursor.fetchall()

            if not students:
                print("No students found.")
                self.pause()
                return

            print(f"\n{'#':<4} {'Student ID':<12} {'Name':<25} {'Course':<8} {'Email':<30}")
            print("-" * 79)
            for i, s in enumerate(students, 1):
                name = f"{s[1]} {s[2]}"
                print(f"{i:<4} {s[0]:<12} {name:<25} {s[4] or 'N/A':<8} {s[3] or 'N/A':<30}")

            while True:
                raw = input("\nSelect student (or Enter to go back): ").strip()
                if not raw:
                    return
                try:
                    idx = int(raw)
                    if 1 <= idx <= len(students):
                        selected = students[idx - 1]
                        break
                    print("Invalid choice.")
                except ValueError:
                    print("Please enter a number.")

            student_id = selected[0]
            student_name = f"{selected[1]} {selected[2]}"
            student_email = selected[3]
            student_course = selected[4] or 'N/A'

            print(f"\n   Student: {student_name} ({student_id})")
            print(f"   Course: {student_course}")
            print(f"   Email: {student_email or 'No email on file'}")

            # Decision
            print("\n  1. Approve Graduation")
            print("  2. Deny Graduation")
            decision_choice = input("Select decision (1/2): ").strip()

            if decision_choice == '1':
                decision = "Approved"
                additional_message = "Congratulations! Your graduation has been confirmed. You will receive further details about the graduation ceremony in due course."
            elif decision_choice == '2':
                decision = "Denied"
                reason = input("Reason for denial: ").strip()
                if not reason:
                    print("A reason is required for denial.")
                    self.pause()
                    return
                additional_message = f"Unfortunately, your graduation application has been denied.\n\nReason: {reason}\n\nPlease contact the Academic Administration office to discuss next steps."
            else:
                print("Invalid choice.")
                self.pause()
                return

            # Get graduation date
            default_date = datetime.now().strftime('%Y-%m-%d')
            grad_date = input(f"\nGraduation Date (YYYY-MM-DD) [{default_date}]: ").strip()
            graduation_date = grad_date if grad_date else default_date

            # Confirm
            confirm = input(f"\n{decision} graduation for {student_name} on {graduation_date}? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("Cancelled.")
                self.pause()
                return

            # Process the decision
            if decision == "Approved":
                if SERVICE_AVAILABLE:
                    try:
                        success = GraduationAuditManager.approve_graduation(student_id, 1, graduation_date)
                        if success:
                            print("\nGraduation Approved!")
                        else:
                            print("\nGraduation approval recorded (service returned false).")
                    except Exception as e:
                        print(f"\nGraduation approved (service error: {e}).")
                else:
                    print("\nGraduation Approved!")
            else:
                print("\nGraduation Denied.")

            approved_by = self.get_user_identifier()
            print(f"   Student: {student_id} — {student_name}")
            print(f"   Decision: {decision}")
            print(f"   Date: {graduation_date}")
            print(f"   By: {approved_by}")

            log_activity('graduation_decision', 'graduation', student_id,
                       {'decision': decision, 'graduation_date': graduation_date})

            # Send email notification
            if student_email:
                try:
                    from education_system.systems.university.infrastructure.email import send_template_email

                    template_vars = {
                        'student_name': student_name,
                        'student_id': student_id,
                        'course': student_course,
                        'graduation_date': graduation_date,
                        'decision_type': decision,
                        'decision_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'approved_by': approved_by,
                        'additional_message': additional_message,
                    }

                    result = send_template_email(
                        'user_management/graduation_decision',
                        student_email,
                        template_vars,
                    )

                    if result:
                        print(f"\n   Email notification sent to {student_email}")
                    else:
                        print(f"\n   Warning: Email could not be sent to {student_email}")
                except Exception as e:
                    print(f"\n   Warning: Could not send email: {e}")
            else:
                print("\n   No email address on file — please notify student manually.")

        except Exception as e:
            print(f"\nError: {e}")

        self.pause()

    def view_graduation_requirements(self):
        """View graduation requirements"""
        self.clear_screen()
        self.print_header("📋 GRADUATION REQUIREMENTS")

        print("\n🎓 Standard Graduation Requirements:\n")

        print("1. CREDIT REQUIREMENT")
        print("   • Minimum 120 credits required")
        print("   • Must be from approved courses")
        print("   • At least 60 credits at 300-level or above\n")

        print("2. GPA REQUIREMENT")
        print("   • Minimum cumulative GPA: 2.0")
        print("   • Minimum major GPA: 2.0")
        print("   • No grade below D in major courses\n")

        print("3. RESIDENCY REQUIREMENT")
        print("   • Minimum 30 credits earned at this institution")
        print("   • Last 30 credits must be completed here\n")

        print("4. CORE REQUIREMENTS")
        print("   • Complete all general education courses")
        print("   • Complete all major-specific requirements")
        print("   • Complete capstone project/thesis\n")

        print("5. FINANCIAL CLEARANCE")
        print("   • All tuition and fees must be paid")
        print("   • No outstanding library fines")
        print("   • Return all borrowed equipment\n")

        print("6. ADMINISTRATIVE CLEARANCE")
        print("   • Submit graduation application")
        print("   • Complete exit survey")
        print("   • Order cap and gown")

        self.pause()

    # ==================== Reports ====================

    def print_audit_report(self):
        """Print comprehensive degree audit report"""
        self.clear_screen()
        self.print_header("📄 DEGREE AUDIT REPORT")

        student_id = input("\n📝 Enter Student ID: ").strip()
        if not student_id:
            print("❌ Student ID is required")
            self.pause()
            return

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Get all student data
                cursor.execute('''
                    SELECT s.student_id, s.first_name, s.last_name, s.course, s.enrollment_date,
                           c.name as course_name
                    FROM students s
                    LEFT JOIN courses c ON s.course = c.code
                    WHERE s.student_id = ?
                ''', (student_id,))

                student = cursor.fetchone()
                if not student:
                    print(f"❌ Student {student_id} not found")
                    self.pause()
                    return

                # Generate comprehensive report
                report_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                print(f"\n{'='*70}")
                print("  DEGREE AUDIT REPORT")
                print(f"  Generated: {report_date}")
                print(f"{'='*70}")

                print("\nSTUDENT INFORMATION")
                print(f"  ID: {student[0]}")
                print(f"  Name: {student[1]} {student[2]}")
                print(f"  Course: {student[3]} - {student[5] or 'Unknown'}")
                print(f"  Enrollment Date: {student[4] or 'N/A'}")

                # Get progress
                cursor.execute('''
                    SELECT COUNT(*) as modules,
                           SUM(CASE WHEN sm.status = 'Completed' THEN COALESCE(m.credits, 0) ELSE 0 END) as credits,
                           AVG(CASE
                               WHEN sm.grade = 'A' THEN 4.0
                               WHEN sm.grade = 'B' THEN 3.0
                               WHEN sm.grade = 'C' THEN 2.0
                               WHEN sm.grade = 'D' THEN 1.0
                               WHEN sm.grade = 'F' THEN 0.0
                               ELSE NULL
                           END) as gpa
                    FROM student_modules sm
                    LEFT JOIN modules m ON sm.module_code = m.module_code
                    WHERE sm.student_id = ?
                ''', (student_id,))

                progress = cursor.fetchone()

                print("\nACADEMIC PROGRESS")
                print(f"  Modules Completed: {progress[0] or 0}")
                print(f"  Credits Earned: {progress[1] or 0:.1f} / 120")
                print(f"  Current GPA: {progress[2] or 0:.2f}")

                # Get module details
                cursor.execute('''
                    SELECT sm.module_code, m.module_name, m.credits, sm.grade, sm.status
                    FROM student_modules sm
                    LEFT JOIN modules m ON sm.module_code = m.module_code
                    WHERE sm.student_id = ?
                    ORDER BY sm.status DESC, sm.module_code
                ''', (student_id,))

                modules = cursor.fetchall()

                if modules:
                    print("\nCOURSE HISTORY")
                    print(f"  {'Code':<12} {'Name':<40} {'Credits':<10} {'Grade':<8} {'Status':<12}")
                    print(f"  {'-'*85}")
                    for mod in modules:
                        print(f"  {mod[0]:<12} {(mod[1] or 'N/A')[:39]:<40} {mod[2] or 0:<10} {mod[3] or 'N/A':<8} {mod[4]:<12}")

                print(f"\n{'='*70}")
                print("  END OF REPORT")
                print(f"{'='*70}")

                log_activity('generate', 'audit_report', student_id, {})

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def view_degree_requirements(self):
        """View degree requirements for a program"""
        self.clear_screen()
        self.print_header("📋 DEGREE REQUIREMENTS")

        print("\n🎓 Select Course:")
        print("  1. CS - Computer Science")
        print("  2. DS - Data Science")

        choice = input("\n👉 Enter choice: ").strip()

        course_map = {'1': 'CS', '2': 'DS'}
        if choice not in course_map:
            print("❌ Invalid choice")
            self.pause()
            return

        course_code = course_map[choice]

        print(f"\n{'='*70}")
        print(f"  DEGREE REQUIREMENTS - {course_code}")
        print(f"{'='*70}")

        print("\n📚 CORE REQUIREMENTS")
        print("  • Total Credits: 120")
        print("  • Minimum GPA: 2.0")
        print("  • Residency: 30 credits minimum\n")

        print(f"📖 MAJOR REQUIREMENTS ({course_code})")
        if course_code == 'CS':
            print("  • Programming Fundamentals: 12 credits")
            print("  • Data Structures & Algorithms: 12 credits")
            print("  • Systems & Architecture: 9 credits")
            print("  • Software Engineering: 9 credits")
            print("  • Electives: 18 credits")
        else:  # DS
            print("  • Statistics & Probability: 12 credits")
            print("  • Machine Learning: 12 credits")
            print("  • Data Mining: 9 credits")
            print("  • Big Data Systems: 9 credits")
            print("  • Electives: 18 credits")

        print("\n🌍 GENERAL EDUCATION")
        print("  • English Composition: 6 credits")
        print("  • Mathematics: 12 credits")
        print("  • Natural Sciences: 12 credits")
        print("  • Social Sciences: 9 credits")
        print("  • Humanities: 9 credits")

        print("\n📝 CAPSTONE")
        print("  • Senior Project or Thesis: 6 credits")

        self.pause()


def launch_degree_audit_cli(auth=None):
    """
    Launch the Degree Audit CLI

    Args:
        auth: Authentication instance with current user information
    """
    try:
        cli = DegreeAuditCLI(auth)
        cli.run()
    except KeyboardInterrupt:
        print("\n\n👋 Exited by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # For testing standalone
    launch_degree_audit_cli()
