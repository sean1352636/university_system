"""
Course Planning Assistant CLI Interface

Provides command-line interface for multi-semester course planning,
prerequisite tracking, schedule conflict detection, and course recommendations.
"""

import json
import os
import sys
from typing import Optional

from education_system.university_system.modules.domain.course_planning.services.planning_service import PlanningService
from education_system.university_system.infrastructure.database.db import get_connection


class PlanningCLI:
    """Command-line interface for the Course Planning Assistant."""

    def __init__(self):
        """Initialize the Planning CLI."""
        self.service = PlanningService()

    def _clear_screen(self):
        """Clear terminal screen."""
        os.system('cls' if os.name == 'nt' else 'clear')

    def main_menu(self):
        """Display main course planning menu."""
        while True:
            self._clear_screen()
            print("\n" + "=" * 70)
            print("  COURSE PLANNING ASSISTANT".center(70))
            print("=" * 70)

            print("\nSEMESTER PLANS:")
            print("  1. Create Semester Plan")
            print("  2. View My Semester Plans")
            print("  3. View Plan Details")
            print("  4. Add Course to Plan")
            print("  5. Auto-Generate Plan")

            print("\nPREREQUISITES:")
            print("  6. Check Prerequisite Eligibility")
            print("  7. View Prerequisite Tree")
            print("  8. Visualize Prerequisite Chain")
            print("  9. View All Prerequisites for a Course")

            print("\nSCHEDULE CONFLICTS:")
            print("  10. Detect Plan Conflicts")
            print("  11. View Plan Conflicts")
            print("  12. Resolve a Conflict")

            print("\nCOURSE RECOMMENDATIONS:")
            print("  13. Get Course Recommendations")
            print("  14. View Saved Recommendations")

            print("\nSEQUENCES & ANALYTICS:")
            print("  15. Create Course Sequence")
            print("  16. View Recommended Sequences")
            print("  17. View Planning Analytics")

            print("\n  0. Back to Main Menu")
            print("=" * 70)

            choice = input("\nSelect an option: ").strip()

            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self.create_semester_plan()
                elif choice == '2':
                    self.view_student_plans()
                elif choice == '3':
                    self.view_plan_details()
                elif choice == '4':
                    self.add_course_to_plan()
                elif choice == '5':
                    self.auto_generate_plan()
                elif choice == '6':
                    self.check_prerequisite_eligibility()
                elif choice == '7':
                    self.view_prerequisite_tree()
                elif choice == '8':
                    self.visualize_prerequisite_chain()
                elif choice == '9':
                    self.view_all_prerequisites()
                elif choice == '10':
                    self.detect_plan_conflicts()
                elif choice == '11':
                    self.view_plan_conflicts()
                elif choice == '12':
                    self.resolve_conflict()
                elif choice == '13':
                    self.get_course_recommendations()
                elif choice == '14':
                    self.view_saved_recommendations()
                elif choice == '15':
                    self.create_course_sequence()
                elif choice == '16':
                    self.view_recommended_sequences()
                elif choice == '17':
                    self.view_planning_analytics()
                else:
                    print("\nInvalid option. Please try again.")
                    input("\nPress Enter to continue...")
            except Exception as e:
                print(f"\nError: {e}")
                input("\nPress Enter to continue...")

    # ========== Semester Plans ==========

    def create_semester_plan(self):
        """Create a new multi-semester course plan."""
        print("\n" + "-" * 70)
        print("  CREATE SEMESTER PLAN".center(70))
        print("-" * 70)

        student_id = input("\nStudent ID: ").strip()
        if not student_id:
            print("Student ID is required.")
            input("\nPress Enter to continue...")
            return

        plan_name = input("Plan Name: ").strip()
        if not plan_name:
            print("Plan name is required.")
            input("\nPress Enter to continue...")
            return

        program_code = input("Program Code (optional, press Enter to skip): ").strip() or None
        start_semester = input("Start Semester (e.g., Fall 2026) [Fall 2026]: ").strip() or "Fall 2026"

        total_semesters_str = input("Total Semesters [8]: ").strip()
        total_semesters = int(total_semesters_str) if total_semesters_str else 8

        credits_str = input("Credits Per Semester [15]: ").strip()
        credits_per_semester = int(credits_str) if credits_str else 15

        include_summer_str = input("Include Summer Sessions? (y/n) [n]: ").strip().lower()
        include_summer = include_summer_str == 'y'

        try:
            plan_id = self.service.create_semester_plan(
                student_id=student_id,
                plan_name=plan_name,
                program_code=program_code,
                start_semester=start_semester,
                total_semesters=total_semesters,
                credits_per_semester=credits_per_semester,
                include_summer=include_summer
            )
            print(f"\nSemester plan created successfully! Plan ID: {plan_id}")
        except Exception as e:
            print(f"\nError creating plan: {e}")

        input("\nPress Enter to continue...")

    def view_student_plans(self):
        """View all semester plans for a student."""
        print("\n" + "-" * 70)
        print("  MY SEMESTER PLANS".center(70))
        print("-" * 70)

        student_id = input("\nStudent ID: ").strip()
        if not student_id:
            print("Student ID is required.")
            input("\nPress Enter to continue...")
            return

        try:
            plans = self.service.get_student_plans(student_id)

            if not plans:
                print("\nNo semester plans found.")
            else:
                print(f"\nFound {len(plans)} plan(s):\n")
                print(f"  {'ID':<6} {'Name':<30} {'Program':<12} {'Start':<14} {'Status':<10}")
                print("  " + "-" * 72)

                for plan in plans:
                    print(f"  {plan['plan_id']:<6} "
                          f"{plan['plan_name'][:28]:<30} "
                          f"{(plan['program_code'] or 'N/A'):<12} "
                          f"{plan['start_semester']:<14} "
                          f"{plan['status']:<10}")
        except Exception as e:
            print(f"\nError retrieving plans: {e}")

        input("\nPress Enter to continue...")

    def view_plan_details(self):
        """View detailed information about a specific plan."""
        print("\n" + "-" * 70)
        print("  PLAN DETAILS".center(70))
        print("-" * 70)

        plan_id_str = input("\nPlan ID: ").strip()
        if not plan_id_str:
            print("Plan ID is required.")
            input("\nPress Enter to continue...")
            return

        try:
            plan_id = int(plan_id_str)
            plan_data = self.service.get_semester_plan(plan_id)

            if not plan_data:
                print("\nPlan not found.")
            else:
                plan = plan_data['plan']
                semesters = plan_data['semesters']

                print(f"\n  Plan: {plan['plan_name']}")
                print(f"  Student: {plan['student_id']}")
                print(f"  Program: {plan.get('program_code', 'N/A')}")
                print(f"  Start: {plan['start_semester']}")
                print(f"  Status: {plan['status']}")
                print(f"  Target Credits/Semester: {plan['credits_per_semester']}")
                print(f"  Total Courses: {plan_data['total_courses']}")

                if semesters:
                    for sem_num in sorted(semesters.keys()):
                        courses = semesters[sem_num]
                        total_credits = sum(c.get('credits', 0) for c in courses)
                        sem_name = courses[0].get('semester_name', f'Semester {sem_num}') if courses else f'Semester {sem_num}'

                        print(f"\n  --- {sem_name} (Semester {sem_num}) --- [{total_credits} credits]")
                        print(f"    {'Course ID':<14} {'Course Name':<30} {'Credits':<8} {'Locked':<8}")
                        print("    " + "-" * 60)

                        for course in courses:
                            locked = "Yes" if course.get('is_locked') else "No"
                            print(f"    {course['course_id']:<14} "
                                  f"{(course.get('course_name', 'N/A'))[:28]:<30} "
                                  f"{course.get('credits', 'N/A'):<8} "
                                  f"{locked:<8}")
                else:
                    print("\n  No courses added to this plan yet.")
        except ValueError:
            print("\nInvalid Plan ID. Please enter a number.")
        except Exception as e:
            print(f"\nError retrieving plan details: {e}")

        input("\nPress Enter to continue...")

    def add_course_to_plan(self):
        """Add a course to a semester plan."""
        print("\n" + "-" * 70)
        print("  ADD COURSE TO PLAN".center(70))
        print("-" * 70)

        try:
            plan_id = int(input("\nPlan ID: ").strip())
            course_id = input("Course ID: ").strip()
            if not course_id:
                print("Course ID is required.")
                input("\nPress Enter to continue...")
                return

            semester_number = int(input("Semester Number: ").strip())
            semester_name = input("Semester Name (e.g., Fall 2026): ").strip()
            if not semester_name:
                print("Semester name is required.")
                input("\nPress Enter to continue...")
                return

            locked_str = input("Lock course in this semester? (y/n) [n]: ").strip().lower()
            is_locked = locked_str == 'y'

            priority_str = input("Priority (0-10) [0]: ").strip()
            priority = int(priority_str) if priority_str else 0

            notes = input("Notes (optional): ").strip() or None

            planned_id = self.service.add_course_to_plan(
                plan_id=plan_id,
                course_id=course_id,
                semester_number=semester_number,
                semester_name=semester_name,
                is_locked=is_locked,
                priority=priority,
                notes=notes
            )
            print(f"\nCourse added successfully! Planned Course ID: {planned_id}")
        except ValueError as e:
            print(f"\nInvalid input: {e}")
        except Exception as e:
            print(f"\nError adding course: {e}")

        input("\nPress Enter to continue...")

    def auto_generate_plan(self):
        """Auto-generate a semester plan based on degree requirements."""
        print("\n" + "-" * 70)
        print("  AUTO-GENERATE SEMESTER PLAN".center(70))
        print("-" * 70)

        student_id = input("\nStudent ID: ").strip()
        if not student_id:
            print("Student ID is required.")
            input("\nPress Enter to continue...")
            return

        program_code = input("Program Code: ").strip()
        if not program_code:
            print("Program code is required.")
            input("\nPress Enter to continue...")
            return

        start_semester = input("Start Semester (e.g., Fall 2026) [Fall 2026]: ").strip() or "Fall 2026"

        try:
            print("\nGenerating plan... This may take a moment.")
            plan_id = self.service.generate_auto_plan(
                student_id=student_id,
                program_code=program_code,
                start_semester=start_semester
            )
            print(f"\nAuto-generated plan created! Plan ID: {plan_id}")
            print("Use 'View Plan Details' to review the generated schedule.")
        except Exception as e:
            print(f"\nError generating plan: {e}")

        input("\nPress Enter to continue...")

    # ========== Prerequisites ==========

    def check_prerequisite_eligibility(self):
        """Check if a student meets prerequisites for a course."""
        print("\n" + "-" * 70)
        print("  CHECK PREREQUISITE ELIGIBILITY".center(70))
        print("-" * 70)

        student_id = input("\nStudent ID: ").strip()
        if not student_id:
            print("Student ID is required.")
            input("\nPress Enter to continue...")
            return

        course_id = input("Course ID: ").strip()
        if not course_id:
            print("Course ID is required.")
            input("\nPress Enter to continue...")
            return

        try:
            result = self.service.check_prerequisite_eligibility(student_id, course_id)

            print(f"\n  Course: {result['course_id']}")
            print(f"  Eligible: {'Yes' if result['eligible'] else 'No'}")
            print(f"  Total Prerequisites: {result['total_prerequisites']}")

            if result['met_prerequisites']:
                print("\n  Met Prerequisites:")
                for prereq in result['met_prerequisites']:
                    print(f"    - {prereq['course_id']} "
                          f"(Grade: {prereq['grade']}, Required: {prereq['required_grade']})")

            if result['missing_prerequisites']:
                print("\n  Missing Prerequisites:")
                for prereq in result['missing_prerequisites']:
                    print(f"    - {prereq['course_id']} "
                          f"({prereq['reason']}, Status: {prereq['status']})")
        except Exception as e:
            print(f"\nError checking eligibility: {e}")

        input("\nPress Enter to continue...")

    def view_prerequisite_tree(self):
        """View the prerequisite tree for a course."""
        print("\n" + "-" * 70)
        print("  PREREQUISITE TREE".center(70))
        print("-" * 70)

        course_id = input("\nCourse ID: ").strip()
        if not course_id:
            print("Course ID is required.")
            input("\nPress Enter to continue...")
            return

        depth_str = input("Max Depth [10]: ").strip()
        depth = int(depth_str) if depth_str else 10

        try:
            tree = self.service.build_prerequisite_tree(course_id, depth)
            print(f"\n  Prerequisite Tree for {course_id}:")
            print()
            self._print_tree(tree, indent=2)
        except Exception as e:
            print(f"\nError building prerequisite tree: {e}")

        input("\nPress Enter to continue...")

    def _print_tree(self, node, indent=0):
        """Recursively print a prerequisite tree."""
        prefix = " " * indent
        prereq_count = node.get('prerequisite_count', 0)
        label = node['course_id']
        if prereq_count > 0:
            label += f" ({prereq_count} prerequisite(s))"
        print(f"{prefix}{label}")

        for prereq in node.get('prerequisites', []):
            self._print_tree(prereq, indent + 4)

    def visualize_prerequisite_chain(self):
        """Visualize the prerequisite chain for a course as levels."""
        print("\n" + "-" * 70)
        print("  PREREQUISITE CHAIN VISUALIZATION".center(70))
        print("-" * 70)

        course_id = input("\nCourse ID: ").strip()
        if not course_id:
            print("Course ID is required.")
            input("\nPress Enter to continue...")
            return

        try:
            levels = self.service.visualize_prerequisite_chain(course_id)

            if not levels:
                print("\nNo prerequisite chain found.")
            else:
                print(f"\n  Prerequisite Chain for {course_id}:")
                print(f"  (Foundation -> Advanced)\n")

                for i, level in enumerate(levels):
                    level_label = "Foundation" if i == 0 else (
                        "Target" if i == len(levels) - 1 else f"Level {i}"
                    )
                    courses_str = ", ".join(level)
                    print(f"  [{level_label}] {courses_str}")

                    if i < len(levels) - 1:
                        print(f"  {'':>10} |")
                        print(f"  {'':>10} v")
        except Exception as e:
            print(f"\nError visualizing chain: {e}")

        input("\nPress Enter to continue...")

    def view_all_prerequisites(self):
        """View all direct and indirect prerequisites for a course."""
        print("\n" + "-" * 70)
        print("  ALL PREREQUISITES".center(70))
        print("-" * 70)

        course_id = input("\nCourse ID: ").strip()
        if not course_id:
            print("Course ID is required.")
            input("\nPress Enter to continue...")
            return

        try:
            prereqs = self.service.get_all_prerequisites(course_id)

            if not prereqs:
                print(f"\nNo prerequisites found for {course_id}.")
            else:
                print(f"\nAll prerequisites for {course_id} ({len(prereqs)} total):\n")
                for i, prereq_id in enumerate(sorted(prereqs), 1):
                    print(f"  {i}. {prereq_id}")
        except Exception as e:
            print(f"\nError retrieving prerequisites: {e}")

        input("\nPress Enter to continue...")

    # ========== Schedule Conflicts ==========

    def detect_plan_conflicts(self):
        """Detect scheduling conflicts in a semester plan."""
        print("\n" + "-" * 70)
        print("  DETECT PLAN CONFLICTS".center(70))
        print("-" * 70)

        plan_id_str = input("\nPlan ID: ").strip()
        if not plan_id_str:
            print("Plan ID is required.")
            input("\nPress Enter to continue...")
            return

        try:
            plan_id = int(plan_id_str)
            print("\nAnalyzing plan for conflicts...")
            conflicts = self.service.detect_plan_schedule_conflicts(plan_id)

            if not conflicts:
                print("\nNo conflicts detected! Your plan looks good.")
            else:
                print(f"\nFound {len(conflicts)} conflict(s):\n")
                self._display_conflicts(conflicts)
        except ValueError:
            print("\nInvalid Plan ID. Please enter a number.")
        except Exception as e:
            print(f"\nError detecting conflicts: {e}")

        input("\nPress Enter to continue...")

    def view_plan_conflicts(self):
        """View all unresolved conflicts for a plan."""
        print("\n" + "-" * 70)
        print("  PLAN CONFLICTS".center(70))
        print("-" * 70)

        plan_id_str = input("\nPlan ID: ").strip()
        if not plan_id_str:
            print("Plan ID is required.")
            input("\nPress Enter to continue...")
            return

        try:
            plan_id = int(plan_id_str)
            conflicts = self.service.get_plan_conflicts(plan_id)

            if not conflicts:
                print("\nNo unresolved conflicts for this plan.")
            else:
                print(f"\nUnresolved conflicts ({len(conflicts)}):\n")
                for conflict in conflicts:
                    print(f"  Conflict ID: {conflict['conflict_id']}")
                    print(f"  Type: {conflict['conflict_type']}")
                    print(f"  Severity: {conflict['severity']}")
                    print(f"  Description: {conflict['description']}")
                    if conflict.get('affected_courses_json'):
                        affected = json.loads(conflict['affected_courses_json'])
                        print(f"  Affected Courses: {', '.join(affected)}")
                    if conflict.get('resolution_suggestions_json'):
                        suggestions = json.loads(conflict['resolution_suggestions_json'])
                        if suggestions:
                            print("  Suggestions:")
                            for s in suggestions:
                                print(f"    - {s}")
                    print()
        except ValueError:
            print("\nInvalid Plan ID. Please enter a number.")
        except Exception as e:
            print(f"\nError retrieving conflicts: {e}")

        input("\nPress Enter to continue...")

    def resolve_conflict(self):
        """Mark a conflict as resolved."""
        print("\n" + "-" * 70)
        print("  RESOLVE CONFLICT".center(70))
        print("-" * 70)

        conflict_id_str = input("\nConflict ID: ").strip()
        if not conflict_id_str:
            print("Conflict ID is required.")
            input("\nPress Enter to continue...")
            return

        try:
            conflict_id = int(conflict_id_str)
            success = self.service.resolve_conflict(conflict_id)

            if success:
                print(f"\nConflict {conflict_id} marked as resolved.")
            else:
                print(f"\nFailed to resolve conflict {conflict_id}.")
        except ValueError:
            print("\nInvalid Conflict ID. Please enter a number.")
        except Exception as e:
            print(f"\nError resolving conflict: {e}")

        input("\nPress Enter to continue...")

    def _display_conflicts(self, conflicts):
        """Display a list of conflicts in a formatted way."""
        for i, conflict in enumerate(conflicts, 1):
            severity_marker = "!!!" if conflict['severity'] == 'High' else "! " if conflict['severity'] == 'Medium' else "  "
            print(f"  {severity_marker} [{i}] {conflict['type']} (Severity: {conflict['severity']})")
            print(f"      {conflict['description']}")

            if conflict.get('affected_courses'):
                print(f"      Affected: {', '.join(conflict['affected_courses'])}")

            if conflict.get('suggestions'):
                print("      Suggestions:")
                for suggestion in conflict['suggestions']:
                    print(f"        - {suggestion}")
            print()

    # ========== Course Recommendations ==========

    def get_course_recommendations(self):
        """Get course recommendations for a student."""
        print("\n" + "-" * 70)
        print("  COURSE RECOMMENDATIONS".center(70))
        print("-" * 70)

        student_id = input("\nStudent ID: ").strip()
        if not student_id:
            print("Student ID is required.")
            input("\nPress Enter to continue...")
            return

        semester = input("Target Semester (e.g., Fall 2026): ").strip()
        if not semester:
            print("Target semester is required.")
            input("\nPress Enter to continue...")
            return

        max_str = input("Max Recommendations [10]: ").strip()
        max_recommendations = int(max_str) if max_str else 10

        try:
            print("\nGenerating recommendations...")
            recommendations = self.service.recommend_courses(
                student_id=student_id,
                semester=semester,
                max_recommendations=max_recommendations
            )

            if not recommendations:
                print("\nNo recommendations available. This may mean all eligible courses are completed.")
            else:
                print(f"\nTop {len(recommendations)} Recommended Courses for {semester}:\n")
                print(f"  {'#':<4} {'Course ID':<14} {'Course Name':<28} {'Credits':<8} {'Score':<7}")
                print("  " + "-" * 61)

                for i, rec in enumerate(recommendations, 1):
                    print(f"  {i:<4} {rec['course_id']:<14} "
                          f"{rec['course_name'][:26]:<28} "
                          f"{rec['credits']:<8} "
                          f"{rec['relevance_score']:<7}")
                    print(f"       Reason: {rec['reason']}")
        except Exception as e:
            print(f"\nError generating recommendations: {e}")

        input("\nPress Enter to continue...")

    def view_saved_recommendations(self):
        """View previously saved course recommendations."""
        print("\n" + "-" * 70)
        print("  SAVED RECOMMENDATIONS".center(70))
        print("-" * 70)

        student_id = input("\nStudent ID: ").strip()
        if not student_id:
            print("Student ID is required.")
            input("\nPress Enter to continue...")
            return

        try:
            recommendations = self.service.get_student_recommendations(student_id)

            if not recommendations:
                print("\nNo saved recommendations found.")
            else:
                print(f"\nSaved Recommendations ({len(recommendations)}):\n")
                print(f"  {'Course ID':<14} {'Course Name':<28} {'Credits':<8} {'Score':<7} {'Semester':<14}")
                print("  " + "-" * 71)

                for rec in recommendations:
                    print(f"  {rec['course_id']:<14} "
                          f"{(rec.get('course_name', 'N/A'))[:26]:<28} "
                          f"{rec.get('credits', 'N/A'):<8} "
                          f"{rec['relevance_score']:<7} "
                          f"{rec.get('semester_recommended', 'N/A'):<14}")
        except Exception as e:
            print(f"\nError retrieving recommendations: {e}")

        input("\nPress Enter to continue...")

    # ========== Course Sequences & Analytics ==========

    def create_course_sequence(self):
        """Create a predefined course sequence."""
        print("\n" + "-" * 70)
        print("  CREATE COURSE SEQUENCE".center(70))
        print("-" * 70)

        sequence_name = input("\nSequence Name: ").strip()
        if not sequence_name:
            print("Sequence name is required.")
            input("\nPress Enter to continue...")
            return

        program_code = input("Program Code: ").strip()
        if not program_code:
            print("Program code is required.")
            input("\nPress Enter to continue...")
            return

        sequence_type = input("Sequence Type (Linear/Flexible/Branching) [Linear]: ").strip() or "Linear"
        if sequence_type not in ("Linear", "Flexible", "Branching"):
            print("Invalid sequence type. Must be Linear, Flexible, or Branching.")
            input("\nPress Enter to continue...")
            return

        print("\nEnter course IDs in order, one per line. Enter a blank line when finished:")
        courses = []
        while True:
            course_id = input("  Course ID: ").strip()
            if not course_id:
                break
            courses.append(course_id)

        if not courses:
            print("\nAt least one course is required.")
            input("\nPress Enter to continue...")
            return

        try:
            sequence_id = self.service.create_course_sequence(
                sequence_name=sequence_name,
                program_code=program_code,
                courses=courses,
                sequence_type=sequence_type
            )
            print(f"\nCourse sequence created! Sequence ID: {sequence_id}")
            print(f"Courses in sequence: {len(courses)}")
        except Exception as e:
            print(f"\nError creating sequence: {e}")

        input("\nPress Enter to continue...")

    def view_recommended_sequences(self):
        """View recommended course sequences for a program."""
        print("\n" + "-" * 70)
        print("  RECOMMENDED COURSE SEQUENCES".center(70))
        print("-" * 70)

        program_code = input("\nProgram Code: ").strip()
        if not program_code:
            print("Program code is required.")
            input("\nPress Enter to continue...")
            return

        try:
            sequences = self.service.get_recommended_sequences(program_code)

            if not sequences:
                print(f"\nNo course sequences found for program '{program_code}'.")
            else:
                print(f"\nSequences for {program_code} ({len(sequences)}):\n")

                for seq in sequences:
                    print(f"  Sequence ID: {seq['sequence_id']}")
                    print(f"  Name: {seq['sequence_name']}")
                    print(f"  Type: {seq.get('sequence_type', 'Linear')}")

                    courses = json.loads(seq['courses_json']) if seq.get('courses_json') else []
                    if courses:
                        print(f"  Courses ({len(courses)}): {' -> '.join(courses)}")
                    print()
        except Exception as e:
            print(f"\nError retrieving sequences: {e}")

        input("\nPress Enter to continue...")

    def view_planning_analytics(self):
        """View comprehensive planning analytics for a student."""
        print("\n" + "-" * 70)
        print("  PLANNING ANALYTICS".center(70))
        print("-" * 70)

        student_id = input("\nStudent ID: ").strip()
        if not student_id:
            print("Student ID is required.")
            input("\nPress Enter to continue...")
            return

        try:
            analytics = self.service.get_planning_analytics(student_id)

            print(f"\n  Planning Analytics for Student: {student_id}\n")

            # Plan statistics
            plans = analytics.get('plans', {})
            print("  PLAN STATISTICS:")
            print(f"    Total Plans: {plans.get('total_plans', 0)}")
            print(f"    Active Plans: {plans.get('active_plans', 0)}")

            # Conflict statistics
            conflicts = analytics.get('conflicts', {})
            print("\n  CONFLICT STATISTICS:")
            print(f"    Total Conflicts: {conflicts.get('total_conflicts', 0)}")
            print(f"    Resolved: {conflicts.get('resolved_conflicts', 0)}")
            print(f"    High Severity: {conflicts.get('high_severity_conflicts', 0)}")

            unresolved = (conflicts.get('total_conflicts', 0) or 0) - (conflicts.get('resolved_conflicts', 0) or 0)
            print(f"    Unresolved: {unresolved}")

            # Recommendation statistics
            recs = analytics.get('recommendations', {})
            print("\n  RECOMMENDATION STATISTICS:")
            print(f"    Total Recommendations: {recs.get('total_recommendations', 0)}")
            avg_score = recs.get('avg_relevance_score')
            if avg_score is not None:
                print(f"    Average Relevance Score: {avg_score:.2f}")
            else:
                print(f"    Average Relevance Score: N/A")
        except Exception as e:
            print(f"\nError retrieving analytics: {e}")

        input("\nPress Enter to continue...")


def main():
    """Entry point for the Course Planning CLI."""
    cli = PlanningCLI()
    cli.main_menu()


if __name__ == "__main__":
    main()
