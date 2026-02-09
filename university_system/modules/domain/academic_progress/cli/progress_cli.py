"""
Academic Progress Dashboard CLI Interface

Provides command-line interface for degree tracking, GPA simulation, and early warnings.
"""

from datetime import datetime
from typing import Optional
import sys

from university_system.modules.domain.academic_progress.services.progress_service import ProgressService
from university_system.infrastructure.shared_context import get_auth


class AcademicProgressCLI:
    """Command-line interface for Academic Progress Dashboard."""

    def __init__(self):
        """Initialize the Academic Progress CLI."""
        self.service = ProgressService()
        self.auth = get_auth()

    def main_menu(self):
        """Display main progress dashboard menu."""
        while True:
            self._clear_screen()
            print("\n" + "=" * 70)
            print("  ACADEMIC PROGRESS DASHBOARD".center(70))
            print("=" * 70)

            if not self.auth.is_logged_in():
                print("\n\nPlease log in to access academic progress features.")
                input("\nPress Enter to return...")
                return

            student_id = self.auth.get_current_user()['user_id']

            # Show quick status summary
            self._display_quick_status(student_id)

            print("\n" + "=" * 70)
            print("\nDEGREE PROGRESS:")
            print("  1. View Degree Progress & Requirements")
            print("  2. Track Degree Milestones")
            print("  3. View Degree Progress Visualization")
            print("  4. Graduation Forecast & Timeline")

            print("\nGPA TOOLS:")
            print("  5. Calculate What-If GPA Scenario")
            print("  6. Calculate Target GPA Requirements")
            print("  7. View GPA Simulation History")

            print("\nEARLY WARNING SYSTEM:")
            print("  8. Check Active Warnings")
            print("  9. Run Complete Warning Scan")
            print("  10. Acknowledge Warning")
            print("  11. Resolve Warning")

            print("\nANALYTICS & REPORTS:")
            print("  12. View Progress Analytics")
            print("  13. View Progress History")
            print("  14. Create Progress Snapshot")
            print("  15. Comprehensive Progress Report")

            print("\n  0. Back to Main Menu")
            print("=" * 70)

            choice = input("\nSelect an option: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self.view_degree_progress()
            elif choice == '2':
                self.track_milestones()
            elif choice == '3':
                self.view_progress_visualization()
            elif choice == '4':
                self.view_graduation_forecast()
            elif choice == '5':
                self.calculate_what_if_gpa()
            elif choice == '6':
                self.calculate_target_gpa()
            elif choice == '7':
                self.view_simulation_history()
            elif choice == '8':
                self.view_active_warnings()
            elif choice == '9':
                self.run_warning_scan()
            elif choice == '10':
                self.acknowledge_warning()
            elif choice == '11':
                self.resolve_warning()
            elif choice == '12':
                self.view_progress_analytics()
            elif choice == '13':
                self.view_progress_history()
            elif choice == '14':
                self.create_snapshot()
            elif choice == '15':
                self.comprehensive_report()
            else:
                print("\nInvalid option. Please try again.")
                input("\nPress Enter to continue...")

    def _clear_screen(self):
        """Clear the screen."""
        print("\033[2J\033[H", end="")

    def _display_quick_status(self, student_id: str):
        """Display quick status summary."""
        try:
            # Get active warnings count
            warnings = self.service.get_active_warnings(student_id)
            warning_count = len(warnings)

            # Get current GPA
            gpa_stats = self.service._calculate_current_gpa(student_id)

            print("\n" + "-" * 70)
            print(f"  Quick Status: GPA {gpa_stats['current_gpa']:.2f} | "
                  f"Credits: {gpa_stats['total_credits']} | "
                  f"Active Warnings: {warning_count}")
            print("-" * 70)

            if warning_count > 0:
                print(f"\n  ⚠ You have {warning_count} active warning(s). Check option 8 for details.")
        except Exception:
            pass  # Gracefully handle if data not available

    # ========== Degree Progress ==========

    def view_degree_progress(self):
        """View comprehensive degree progress."""
        print("\n" + "=" * 70)
        print("  DEGREE PROGRESS & REQUIREMENTS".center(70))
        print("=" * 70)

        student_id = self.auth.get_current_user()['user_id']
        program_code = input("\nEnter program code (e.g., CSCI, BIOL): ").strip().upper()

        if not program_code:
            print("\nProgram code is required.")
            input("\nPress Enter to continue...")
            return

        try:
            progress = self.service.calculate_degree_progress(student_id, program_code)

            print(f"\n{'=' * 70}")
            print(f"  DEGREE PROGRESS - {progress['program_code']}".center(70))
            print(f"{'=' * 70}")

            print(f"\nOVERALL COMPLETION: {progress['overall_completion']:.1f}%")
            self._display_progress_bar(progress['overall_completion'])

            print(f"\nCREDITS SUMMARY:")
            print(f"  Total Required:    {progress['total_credits_required']}")
            print(f"  Completed:         {progress['total_credits_completed']}")
            print(f"  In Progress:       {progress['total_credits_in_progress']}")
            print(f"  Remaining:         {progress['total_credits_remaining']}")

            print(f"\n{'=' * 70}")
            print("  PROGRESS BY CATEGORY".center(70))
            print(f"{'=' * 70}")

            for category, data in progress['by_category'].items():
                print(f"\n{category}:")
                print(f"  Required: {data['required']} | Completed: {data['completed']} | "
                      f"In Progress: {data['in_progress']} | Remaining: {data['remaining']}")
                print(f"  Completion: {data['completion_percentage']:.1f}%")
                self._display_progress_bar(data['completion_percentage'], width=40)

            print(f"\nLast Updated: {progress['last_updated']}")

        except Exception as e:
            print(f"\nError calculating degree progress: {str(e)}")

        input("\nPress Enter to continue...")

    def track_milestones(self):
        """Track degree milestones."""
        print("\n" + "=" * 70)
        print("  DEGREE MILESTONES".center(70))
        print("=" * 70)

        student_id = self.auth.get_current_user()['user_id']
        program_code = input("\nEnter program code (e.g., CSCI, BIOL): ").strip().upper()

        if not program_code:
            print("\nProgram code is required.")
            input("\nPress Enter to continue...")
            return

        try:
            milestone_data = self.service.track_milestones(student_id, program_code)

            print(f"\n{'=' * 70}")
            print(f"  MILESTONE TRACKING - {program_code}".center(70))
            print(f"{'=' * 70}")

            stats = milestone_data['student_stats']
            print(f"\nYour Current Stats:")
            print(f"  Total Credits: {stats['total_credits']}")
            print(f"  Current GPA:   {stats['gpa']:.2f}")

            print(f"\n{'=' * 70}")
            print("  MILESTONES".center(70))
            print(f"{'=' * 70}")

            achieved_count = 0
            for milestone_info in milestone_data['milestones']:
                milestone = milestone_info['milestone']
                achieved = milestone_info['achieved']

                status = "✓ ACHIEVED" if achieved else "○ Not Achieved"
                if achieved:
                    achieved_count += 1

                print(f"\n{status} - {milestone['milestone_name']}")
                print(f"  Type: {milestone['milestone_type']}")
                print(f"  Requirements: {milestone['required_credits']} credits, "
                      f"{milestone['required_gpa']:.1f} GPA")
                print(f"  Typical Semester: {milestone['typical_semester']}")

                if milestone['description']:
                    print(f"  Description: {milestone['description']}")

            print(f"\n{'=' * 70}")
            print(f"  Milestones Achieved: {achieved_count}/{len(milestone_data['milestones'])}")

        except Exception as e:
            print(f"\nError tracking milestones: {str(e)}")

        input("\nPress Enter to continue...")

    def view_progress_visualization(self):
        """View degree progress visualization data."""
        print("\n" + "=" * 70)
        print("  DEGREE PROGRESS VISUALIZATION".center(70))
        print("=" * 70)

        student_id = self.auth.get_current_user()['user_id']
        program_code = input("\nEnter program code (e.g., CSCI, BIOL): ").strip().upper()

        if not program_code:
            print("\nProgram code is required.")
            input("\nPress Enter to continue...")
            return

        try:
            viz_data = self.service.get_degree_visualization_data(student_id, program_code)

            print(f"\n{'=' * 70}")
            print(f"  VISUAL PROGRESS - {program_code}".center(70))
            print(f"{'=' * 70}")

            print(f"\nOVERALL PROGRESS: {viz_data['overall_progress']:.1f}%")
            self._display_progress_bar(viz_data['overall_progress'])

            print(f"\n{'=' * 70}")
            print("  CATEGORY BREAKDOWN".center(70))
            print(f"{'=' * 70}")

            for category in viz_data['categories']:
                print(f"\n{category['name']}:")
                print(f"  Completed:   {category['completed']} credits")
                print(f"  In Progress: {category['in_progress']} credits")
                print(f"  Remaining:   {category['remaining']} credits")
                print(f"  Progress:    {category['percentage']:.1f}%")
                self._display_progress_bar(category['percentage'], width=40)

            summary = viz_data['summary']
            print(f"\n{'=' * 70}")
            print("  SUMMARY".center(70))
            print(f"{'=' * 70}")
            print(f"  Total Required:    {summary['total_required']} credits")
            print(f"  Total Completed:   {summary['total_completed']} credits")
            print(f"  Total In Progress: {summary['total_in_progress']} credits")
            print(f"  Total Remaining:   {summary['total_remaining']} credits")

        except Exception as e:
            print(f"\nError generating visualization: {str(e)}")

        input("\nPress Enter to continue...")

    def view_graduation_forecast(self):
        """View graduation forecast."""
        print("\n" + "=" * 70)
        print("  GRADUATION FORECAST".center(70))
        print("=" * 70)

        student_id = self.auth.get_current_user()['user_id']
        program_code = input("\nEnter program code (e.g., CSCI, BIOL): ").strip().upper()

        if not program_code:
            print("\nProgram code is required.")
            input("\nPress Enter to continue...")
            return

        try:
            forecast = self.service.forecast_graduation(student_id, program_code)

            print(f"\n{'=' * 70}")
            print(f"  GRADUATION FORECAST - {program_code}".center(70))
            print(f"{'=' * 70}")

            # Timeline
            on_track_status = "✓ ON TRACK" if forecast['on_track'] else "⚠ DELAYED"
            print(f"\nStatus: {on_track_status}")
            print(f"Estimated Graduation: {forecast['estimated_semester']}")
            print(f"  ({forecast['estimated_graduation_date']})")

            print(f"\nREMAINING REQUIREMENTS:")
            print(f"  Credits Remaining:      {forecast['remaining_credits']}")
            print(f"  Semesters Needed:       {forecast['semesters_needed']}")
            print(f"  Avg Credits/Semester:   {forecast['avg_credits_per_semester']:.1f}")
            print(f"  Confidence Level:       {forecast['confidence_level']*100:.0f}%")

            if forecast['delay_reasons']:
                print(f"\n⚠ POTENTIAL DELAY FACTORS:")
                for reason in forecast['delay_reasons']:
                    print(f"  • {reason}")

            if forecast['acceleration_options']:
                print(f"\n💡 ACCELERATION OPTIONS:")
                for option in forecast['acceleration_options']:
                    print(f"\n  {option['option']}")
                    print(f"    Impact: {option['impact']}")
                    print(f"    Credits: {option['credits']}")

        except Exception as e:
            print(f"\nError forecasting graduation: {str(e)}")

        input("\nPress Enter to continue...")

    # ========== GPA Tools ==========

    def calculate_what_if_gpa(self):
        """Calculate what-if GPA scenario."""
        print("\n" + "=" * 70)
        print("  WHAT-IF GPA CALCULATOR".center(70))
        print("=" * 70)

        student_id = self.auth.get_current_user()['user_id']

        simulation_name = input("\nSimulation name: ").strip()
        if not simulation_name:
            print("\nSimulation name is required.")
            input("\nPress Enter to continue...")
            return

        print("\nEnter hypothetical courses (type 'done' when finished):")
        print("Grade options: A+, A, A-, B+, B, B-, C+, C, C-, D+, D, F")

        simulated_courses = []
        course_num = 1

        while True:
            print(f"\n--- Course {course_num} ---")
            course_id = input("Course ID (or 'done' to finish): ").strip()

            if course_id.lower() == 'done':
                break

            if not course_id:
                continue

            try:
                credits = int(input("Credits: "))
                expected_grade = input("Expected grade: ").strip().upper()

                simulated_courses.append({
                    'course_id': course_id,
                    'credits': credits,
                    'expected_grade': expected_grade
                })

                course_num += 1
            except ValueError:
                print("\nInvalid input. Please try again.")

        if not simulated_courses:
            print("\nNo courses entered.")
            input("\nPress Enter to continue...")
            return

        try:
            result = self.service.calculate_what_if_gpa(student_id, simulation_name, simulated_courses)

            print(f"\n{'=' * 70}")
            print(f"  WHAT-IF GPA RESULTS - {simulation_name}".center(70))
            print(f"{'=' * 70}")

            print(f"\nCURRENT GPA:     {result['current_gpa']:.3f}")
            print(f"PROJECTED GPA:   {result['projected_gpa']:.3f}")
            print(f"GPA CHANGE:      {result['gpa_change']:+.3f}")

            print(f"\nCREDITS:")
            print(f"  Simulated:  {result['credits_simulated']}")
            print(f"  Total After: {result['total_credits_after']}")

            print(f"\n📊 IMPACT ANALYSIS:")
            print(f"  {result['impact_analysis']}")

            print(f"\nSIMULATED COURSES:")
            for course in result['simulated_courses']:
                print(f"  • {course['course_id']}: {course['expected_grade']} ({course['credits']} credits)")

            print(f"\nSimulation ID: {result['simulation_id']}")

        except Exception as e:
            print(f"\nError calculating what-if GPA: {str(e)}")

        input("\nPress Enter to continue...")

    def calculate_target_gpa(self):
        """Calculate target GPA requirements."""
        print("\n" + "=" * 70)
        print("  TARGET GPA CALCULATOR".center(70))
        print("=" * 70)

        student_id = self.auth.get_current_user()['user_id']

        try:
            target_gpa = float(input("\nTarget GPA (0.0-4.0): "))
            if not 0.0 <= target_gpa <= 4.0:
                raise ValueError
        except ValueError:
            print("\nInvalid GPA. Please enter a value between 0.0 and 4.0.")
            input("\nPress Enter to continue...")
            return

        try:
            credits_to_take = int(input("Credits planning to take: "))
            if credits_to_take <= 0:
                raise ValueError
        except ValueError:
            print("\nInvalid credits. Please enter a positive number.")
            input("\nPress Enter to continue...")
            return

        try:
            result = self.service.calculate_target_gpa_requirements(
                student_id, target_gpa, credits_to_take
            )

            print(f"\n{'=' * 70}")
            print("  TARGET GPA ANALYSIS".center(70))
            print(f"{'=' * 70}")

            print(f"\nCURRENT GPA:          {result['current_gpa']:.3f}")
            print(f"TARGET GPA:           {result['target_gpa']:.3f}")
            print(f"CURRENT CREDITS:      {result['current_credits']}")
            print(f"CREDITS TO TAKE:      {result['credits_to_take']}")

            print(f"\n{'=' * 70}")
            print("  REQUIREMENTS".center(70))
            print(f"{'=' * 70}")

            print(f"\nRequired Average Grade: {result['required_average_grade']:.2f}")
            print(f"Required Grade Letter:  {result['required_grade_letter']}")

            print(f"\n📊 FEASIBILITY:")
            if result['achievable']:
                print(f"  ✓ {result['feasibility']}")
            else:
                print(f"  ✗ {result['feasibility']}")

                # Suggest alternative
                print(f"\n💡 SUGGESTION:")
                print(f"  Consider taking more credits or adjusting your target GPA.")

        except Exception as e:
            print(f"\nError calculating target GPA: {str(e)}")

        input("\nPress Enter to continue...")

    def view_simulation_history(self):
        """View GPA simulation history."""
        print("\n" + "=" * 70)
        print("  GPA SIMULATION HISTORY".center(70))
        print("=" * 70)

        student_id = self.auth.get_current_user()['user_id']

        try:
            simulations = self.service.get_simulation_history(student_id)

            if not simulations:
                print("\nNo simulation history found.")
                input("\nPress Enter to continue...")
                return

            print(f"\nTotal Simulations: {len(simulations)}")

            for i, sim in enumerate(simulations, 1):
                print(f"\n{'-' * 70}")
                print(f"[{i}] {sim['simulation_name']}")
                print(f"    Date: {sim['created_at']}")
                print(f"    Current GPA: {sim['current_gpa']:.3f}")
                print(f"    Projected GPA: {sim['projected_gpa']:.3f}")
                print(f"    Change: {(sim['projected_gpa'] - sim['current_gpa']):+.3f}")
                print(f"    Credits Simulated: {sim['credits_simulated']}")

        except Exception as e:
            print(f"\nError retrieving simulation history: {str(e)}")

        input("\nPress Enter to continue...")

    # ========== Early Warning System ==========

    def view_active_warnings(self):
        """View active warnings."""
        print("\n" + "=" * 70)
        print("  ACTIVE ACADEMIC WARNINGS".center(70))
        print("=" * 70)

        student_id = self.auth.get_current_user()['user_id']

        try:
            warnings = self.service.get_active_warnings(student_id)

            if not warnings:
                print("\n✓ No active warnings! You're doing great!")
                input("\nPress Enter to continue...")
                return

            print(f"\nTotal Active Warnings: {len(warnings)}")

            for warning in warnings:
                severity_symbol = {
                    'High': '🔴',
                    'Medium': '🟡',
                    'Low': '🟢'
                }.get(warning['severity'], '⚪')

                print(f"\n{'-' * 70}")
                print(f"{severity_symbol} WARNING ID: {warning['warning_id']} - "
                      f"{warning['warning_type']} [{warning['severity']}]")
                print(f"\n{warning['warning_message']}")

                if warning['trigger_metric']:
                    print(f"\nTrigger: {warning['trigger_metric']} = {warning['trigger_value']}")

                if warning['recommendations_json']:
                    import json
                    recommendations = json.loads(warning['recommendations_json'])
                    if recommendations:
                        print(f"\n💡 RECOMMENDATIONS:")
                        for rec in recommendations:
                            print(f"  • {rec}")

                ack_status = "✓ Acknowledged" if warning['acknowledged'] else "○ Not Acknowledged"
                print(f"\nStatus: {ack_status}")
                print(f"Created: {warning['created_at']}")

        except Exception as e:
            print(f"\nError retrieving warnings: {str(e)}")

        input("\nPress Enter to continue...")

    def run_warning_scan(self):
        """Run complete warning scan."""
        print("\n" + "=" * 70)
        print("  RUNNING WARNING SCAN".center(70))
        print("=" * 70)

        student_id = self.auth.get_current_user()['user_id']

        print("\nScanning academic records for warning indicators...")
        print("Checking: GPA, attendance, assignments, grades...")

        try:
            warnings = self.service.check_early_warnings(student_id)

            print(f"\n{'=' * 70}")
            print("  SCAN RESULTS".center(70))
            print(f"{'=' * 70}")

            if not warnings:
                print("\n✓ SCAN COMPLETE: No warnings detected!")
                print("  Your academic performance looks good. Keep it up!")
            else:
                print(f"\n⚠ SCAN COMPLETE: {len(warnings)} warning(s) detected")

                for i, warning in enumerate(warnings, 1):
                    severity_symbol = {
                        'High': '🔴',
                        'Medium': '🟡',
                        'Low': '🟢'
                    }.get(warning['severity'], '⚪')

                    print(f"\n{'-' * 70}")
                    print(f"{severity_symbol} [{i}] {warning['type']} - {warning['severity']} Severity")
                    print(f"\n{warning['message']}")

                    if warning.get('recommendations'):
                        print(f"\n💡 RECOMMENDATIONS:")
                        for rec in warning['recommendations']:
                            print(f"  • {rec}")

                print(f"\n{'=' * 70}")
                print("  These warnings have been saved to your record.")
                print("  View option 8 to manage them.")

        except Exception as e:
            print(f"\nError running warning scan: {str(e)}")

        input("\nPress Enter to continue...")

    def acknowledge_warning(self):
        """Acknowledge a warning."""
        print("\n" + "=" * 70)
        print("  ACKNOWLEDGE WARNING".center(70))
        print("=" * 70)

        try:
            warning_id = int(input("\nEnter warning ID to acknowledge: "))
        except ValueError:
            print("\nInvalid warning ID.")
            input("\nPress Enter to continue...")
            return

        try:
            success = self.service.acknowledge_warning(warning_id)

            if success:
                print(f"\n✓ Warning {warning_id} has been acknowledged.")
            else:
                print(f"\n✗ Failed to acknowledge warning {warning_id}.")

        except Exception as e:
            print(f"\nError acknowledging warning: {str(e)}")

        input("\nPress Enter to continue...")

    def resolve_warning(self):
        """Resolve a warning."""
        print("\n" + "=" * 70)
        print("  RESOLVE WARNING".center(70))
        print("=" * 70)

        try:
            warning_id = int(input("\nEnter warning ID to resolve: "))
        except ValueError:
            print("\nInvalid warning ID.")
            input("\nPress Enter to continue...")
            return

        notes = input("Resolution notes (optional): ").strip() or None

        try:
            success = self.service.resolve_warning(warning_id, notes)

            if success:
                print(f"\n✓ Warning {warning_id} has been resolved!")
            else:
                print(f"\n✗ Failed to resolve warning {warning_id}.")

        except Exception as e:
            print(f"\nError resolving warning: {str(e)}")

        input("\nPress Enter to continue...")

    # ========== Analytics & Reports ==========

    def view_progress_analytics(self):
        """View progress analytics."""
        print("\n" + "=" * 70)
        print("  PROGRESS ANALYTICS".center(70))
        print("=" * 70)

        student_id = self.auth.get_current_user()['user_id']

        try:
            analytics = self.service.get_progress_analytics(student_id)

            print(f"\n{'=' * 70}")
            print("  CURRENT STATS".center(70))
            print(f"{'=' * 70}")

            stats = analytics['current_stats']
            print(f"\nCurrent GPA:      {stats['current_gpa']:.3f}")
            print(f"Total Credits:    {stats['total_credits']}")
            print(f"Total Points:     {stats['total_points']:.2f}")

            if analytics['gpa_trend']:
                print(f"\n{'=' * 70}")
                print("  GPA TREND (Last 8 Semesters)".center(70))
                print(f"{'=' * 70}")

                for entry in analytics['gpa_trend']:
                    print(f"  {entry['semester']}: {entry['semester_gpa']:.2f}")

            if analytics['warning_stats']:
                print(f"\n{'=' * 70}")
                print("  WARNING STATISTICS".center(70))
                print(f"{'=' * 70}")

                w_stats = analytics['warning_stats']
                print(f"\nTotal Warnings:         {w_stats.get('total_warnings', 0)}")
                print(f"Resolved Warnings:      {w_stats.get('resolved_count', 0)}")
                print(f"High Severity Warnings: {w_stats.get('high_severity_count', 0)}")

            print(f"\nLast Updated: {analytics['last_updated']}")

        except Exception as e:
            print(f"\nError retrieving analytics: {str(e)}")

        input("\nPress Enter to continue...")

    def view_progress_history(self):
        """View progress history."""
        print("\n" + "=" * 70)
        print("  PROGRESS HISTORY".center(70))
        print("=" * 70)

        student_id = self.auth.get_current_user()['user_id']

        try:
            history = self.service.get_progress_history(student_id)

            if not history:
                print("\nNo progress history found.")
                input("\nPress Enter to continue...")
                return

            print(f"\nTotal Snapshots: {len(history)}")

            for snapshot in history:
                print(f"\n{'-' * 70}")
                print(f"Semester: {snapshot['semester']}")
                print(f"  Overall GPA:     {snapshot['overall_gpa']:.2f}")
                print(f"  Semester GPA:    {snapshot['semester_gpa']:.2f}")
                print(f"  Total Credits:   {snapshot['total_credits']}")
                print(f"  Class Standing:  {snapshot['class_standing']}")
                print(f"  Academic Status: {snapshot['academic_status']}")
                print(f"  Active Warnings: {snapshot['warnings_count']}")
                print(f"  Date: {snapshot['snapshot_date']}")

        except Exception as e:
            print(f"\nError retrieving progress history: {str(e)}")

        input("\nPress Enter to continue...")

    def create_snapshot(self):
        """Create a progress snapshot."""
        print("\n" + "=" * 70)
        print("  CREATE PROGRESS SNAPSHOT".center(70))
        print("=" * 70)

        student_id = self.auth.get_current_user()['user_id']
        semester = input("\nEnter semester (e.g., Fall 2025): ").strip()

        if not semester:
            print("\nSemester is required.")
            input("\nPress Enter to continue...")
            return

        try:
            snapshot_id = self.service.create_progress_snapshot(student_id, semester)

            print(f"\n✓ Progress snapshot created successfully!")
            print(f"  Snapshot ID: {snapshot_id}")
            print(f"  Semester: {semester}")

        except Exception as e:
            print(f"\nError creating snapshot: {str(e)}")

        input("\nPress Enter to continue...")

    def comprehensive_report(self):
        """Generate comprehensive progress report."""
        print("\n" + "=" * 70)
        print("  COMPREHENSIVE PROGRESS REPORT".center(70))
        print("=" * 70)

        student_id = self.auth.get_current_user()['user_id']
        program_code = input("\nEnter program code (e.g., CSCI, BIOL): ").strip().upper()

        if not program_code:
            print("\nProgram code is required.")
            input("\nPress Enter to continue...")
            return

        print("\nGenerating comprehensive report...")

        try:
            # Get all data
            progress = self.service.calculate_degree_progress(student_id, program_code)
            milestones = self.service.track_milestones(student_id, program_code)
            forecast = self.service.forecast_graduation(student_id, program_code)
            warnings = self.service.get_active_warnings(student_id)
            analytics = self.service.get_progress_analytics(student_id)

            # Print comprehensive report
            print(f"\n{'=' * 70}")
            print(f"  COMPREHENSIVE PROGRESS REPORT".center(70))
            print(f"  Student ID: {student_id} | Program: {program_code}".center(70))
            print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}".center(70))
            print(f"{'=' * 70}")

            # Section 1: Degree Progress
            print(f"\n{'─' * 70}")
            print("1. DEGREE PROGRESS")
            print(f"{'─' * 70}")
            print(f"Overall Completion: {progress['overall_completion']:.1f}%")
            self._display_progress_bar(progress['overall_completion'])
            print(f"Credits: {progress['total_credits_completed']}/{progress['total_credits_required']} "
                  f"(Remaining: {progress['total_credits_remaining']})")

            # Section 2: Academic Standing
            print(f"\n{'─' * 70}")
            print("2. ACADEMIC STANDING")
            print(f"{'─' * 70}")
            stats = analytics['current_stats']
            print(f"Current GPA: {stats['current_gpa']:.3f}")
            print(f"Total Credits: {stats['total_credits']}")
            standing = self.service._determine_class_standing(stats['total_credits'])
            print(f"Class Standing: {standing}")

            # Section 3: Milestones
            print(f"\n{'─' * 70}")
            print("3. MILESTONE PROGRESS")
            print(f"{'─' * 70}")
            achieved = sum(1 for m in milestones['milestones'] if m['achieved'])
            total_milestones = len(milestones['milestones'])
            print(f"Milestones Achieved: {achieved}/{total_milestones}")

            # Section 4: Graduation Forecast
            print(f"\n{'─' * 70}")
            print("4. GRADUATION FORECAST")
            print(f"{'─' * 70}")
            status = "On Track ✓" if forecast['on_track'] else "Delayed ⚠"
            print(f"Status: {status}")
            print(f"Estimated Graduation: {forecast['estimated_semester']}")
            print(f"Semesters Remaining: {forecast['semesters_needed']}")

            # Section 5: Warnings
            print(f"\n{'─' * 70}")
            print("5. ACTIVE WARNINGS")
            print(f"{'─' * 70}")
            if warnings:
                print(f"Total Active Warnings: {len(warnings)}")
                high_severity = sum(1 for w in warnings if w['severity'] == 'High')
                if high_severity > 0:
                    print(f"⚠ High Severity Warnings: {high_severity}")
            else:
                print("No active warnings ✓")

            # Section 6: Recommendations
            print(f"\n{'─' * 70}")
            print("6. RECOMMENDATIONS")
            print(f"{'─' * 70}")

            if warnings:
                print("• Address active academic warnings")
            if not forecast['on_track']:
                print("• Consider acceleration options to get back on track")
            if stats['current_gpa'] < 3.0:
                print("• Focus on improving GPA through tutoring and study support")
            if forecast['on_track'] and not warnings:
                print("• Continue current academic trajectory")
                print("• Consider challenging yourself with advanced courses")

            print(f"\n{'=' * 70}")
            print("  END OF REPORT".center(70))
            print(f"{'=' * 70}")

        except Exception as e:
            print(f"\nError generating comprehensive report: {str(e)}")

        input("\nPress Enter to continue...")

    # ========== Helper Methods ==========

    def _display_progress_bar(self, percentage: float, width: int = 50):
        """Display a text-based progress bar."""
        filled = int(width * percentage / 100)
        bar = '█' * filled + '░' * (width - filled)
        print(f"  [{bar}] {percentage:.1f}%")

    def run(self):
        """Run the CLI interface."""
        self.main_menu()


# Entry point for direct execution
if __name__ == "__main__":
    cli = AcademicProgressCLI()
    cli.run()
