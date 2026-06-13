"""
Reports Menu - Staff HR reports and analytics CLI.
"""

from education_system.university_system.modules.domain.operations.staff_hr.services import (
    EmployeeManager,
    LeaveManager,
    TimeManager,
    TrainingManager,
    PerformanceManager,
)


def display_reports_menu(user_id: str = None) -> None:
    """Display reports and analytics menu."""
    while True:
        print("\n" + "=" * 60)
        print("REPORTS & ANALYTICS")
        print("=" * 60)

        print("\n--- Staff Reports ---")
        print("  1. Staff Summary")
        print("  2. Department Breakdown")
        print("  3. Headcount Report")

        print("\n--- Leave Reports ---")
        print("  4. Leave Balance Summary")
        print("  5. Leave Usage Report")
        print("  6. Absence Trends")

        print("\n--- Time & Attendance ---")
        print("  7. Attendance Summary")
        print("  8. Overtime Report")

        print("\n--- Training & Development ---")
        print("  9. Training Completion Report")
        print("  10. Certification Status")

        print("\n--- Performance ---")
        print("  11. Appraisal Summary")
        print("  12. Goal Progress Report")

        print("\n  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _staff_summary()
        elif choice == '2':
            _department_breakdown()
        elif choice == '3':
            _headcount_report()
        elif choice == '4':
            _leave_balance_summary()
        elif choice == '5':
            _leave_usage_report()
        elif choice == '6':
            _absence_trends()
        elif choice == '7':
            _attendance_summary()
        elif choice == '8':
            _overtime_report()
        elif choice == '9':
            _training_completion()
        elif choice == '10':
            _certification_status()
        elif choice == '11':
            _appraisal_summary()
        elif choice == '12':
            _goal_progress()
        else:
            print("Invalid choice.")


def _staff_summary() -> None:
    """Display staff summary report."""
    print("\n--- Staff Summary Report ---")
    try:
        stats = EmployeeManager.get_statistics()
        if stats:
            print(f"Total Employees: {stats.get('total_employees', 0)}")
            print(f"Full-Time: {stats.get('full_time', 0)}")
            print(f"Part-Time: {stats.get('part_time', 0)}")
            print(f"Contract: {stats.get('contract', 0)}")
            print(f"Active: {stats.get('active', 0)}")
            print(f"On Leave: {stats.get('on_leave', 0)}")
        else:
            print("No statistics available.")
    except Exception as e:
        print(f"Error loading report: {e}")

    input("\nPress Enter to continue...")


def _department_breakdown() -> None:
    """Display department breakdown."""
    print("\n--- Department Breakdown ---")
    try:
        breakdown = EmployeeManager.get_department_breakdown()
        if breakdown:
            for dept, count in breakdown.items():
                print(f"  {dept}: {count}")
        else:
            print("No data available.")
    except Exception as e:
        print(f"Error loading report: {e}")

    input("\nPress Enter to continue...")


def _headcount_report() -> None:
    """Display headcount report."""
    print("\n--- Headcount Report ---")
    try:
        report = EmployeeManager.get_headcount_report()
        if report:
            print(f"Current Headcount: {report.get('current', 0)}")
            print(f"New Hires (This Month): {report.get('new_hires_month', 0)}")
            print(f"New Hires (This Year): {report.get('new_hires_year', 0)}")
            print(f"Departures (This Month): {report.get('departures_month', 0)}")
            print(f"Departures (This Year): {report.get('departures_year', 0)}")
            print(f"Turnover Rate: {report.get('turnover_rate', 0):.1f}%")
        else:
            print("No data available.")
    except Exception as e:
        print(f"Error loading report: {e}")

    input("\nPress Enter to continue...")


def _leave_balance_summary() -> None:
    """Display leave balance summary."""
    print("\n--- Leave Balance Summary ---")
    try:
        summary = LeaveManager.get_balance_summary()
        if summary:
            for leave_type, data in summary.items():
                print(f"\n{leave_type}:")
                print(f"  Total Allocated: {data.get('total_allocated', 0)}")
                print(f"  Total Used: {data.get('total_used', 0)}")
                print(f"  Total Remaining: {data.get('total_remaining', 0)}")
        else:
            print("No data available.")
    except Exception as e:
        print(f"Error loading report: {e}")

    input("\nPress Enter to continue...")


def _leave_usage_report() -> None:
    """Display leave usage report."""
    print("\n--- Leave Usage Report ---")
    period = input("Period (YYYY-MM or Enter for current month): ").strip()

    try:
        report = LeaveManager.get_usage_report(period or None)
        if report:
            print(f"\nPeriod: {report.get('period', 'N/A')}")
            print(f"Total Leave Days Taken: {report.get('total_days', 0)}")
            print(f"Employees on Leave: {report.get('employees_count', 0)}")
            print("\nBy Type:")
            for leave_type, days in report.get('by_type', {}).items():
                print(f"  {leave_type}: {days} days")
        else:
            print("No data available.")
    except Exception as e:
        print(f"Error loading report: {e}")

    input("\nPress Enter to continue...")


def _absence_trends() -> None:
    """Display absence trends."""
    print("\n--- Absence Trends ---")
    try:
        trends = LeaveManager.get_absence_trends()
        if trends:
            print("Monthly Absence Days (Last 6 months):")
            for month, days in trends.get('monthly', {}).items():
                print(f"  {month}: {days} days")
            print(f"\nAverage Monthly Absences: {trends.get('average', 0):.1f} days")
        else:
            print("No data available.")
    except Exception as e:
        print(f"Error loading report: {e}")

    input("\nPress Enter to continue...")


def _attendance_summary() -> None:
    """Display attendance summary."""
    print("\n--- Attendance Summary ---")
    try:
        summary = TimeManager.get_attendance_summary()
        if summary:
            print(f"Reporting Period: {summary.get('period', 'N/A')}")
            print(f"Total Work Days: {summary.get('work_days', 0)}")
            print(f"Average Attendance Rate: {summary.get('attendance_rate', 0):.1f}%")
            print(f"Late Arrivals: {summary.get('late_arrivals', 0)}")
            print(f"Early Departures: {summary.get('early_departures', 0)}")
        else:
            print("No data available.")
    except Exception as e:
        print(f"Error loading report: {e}")

    input("\nPress Enter to continue...")


def _overtime_report() -> None:
    """Display overtime report."""
    print("\n--- Overtime Report ---")
    try:
        report = TimeManager.get_overtime_report()
        if report:
            print(f"Reporting Period: {report.get('period', 'N/A')}")
            print(f"Total Overtime Hours: {report.get('total_hours', 0):.1f}")
            print(f"Employees with Overtime: {report.get('employee_count', 0)}")
            print(f"Average Overtime per Employee: {report.get('average_hours', 0):.1f} hrs")
            print("\nTop Departments:")
            for dept, hours in report.get('by_department', {}).items():
                print(f"  {dept}: {hours:.1f} hrs")
        else:
            print("No data available.")
    except Exception as e:
        print(f"Error loading report: {e}")

    input("\nPress Enter to continue...")


def _training_completion() -> None:
    """Display training completion report."""
    print("\n--- Training Completion Report ---")
    try:
        report = TrainingManager.get_completion_report()
        if report:
            print(f"Total Training Programs: {report.get('total_programs', 0)}")
            print(f"Completed This Year: {report.get('completed_year', 0)}")
            print(f"In Progress: {report.get('in_progress', 0)}")
            print(f"Overall Completion Rate: {report.get('completion_rate', 0):.1f}%")
            print("\nMandatory Training:")
            print(f"  Required: {report.get('mandatory_required', 0)}")
            print(f"  Completed: {report.get('mandatory_completed', 0)}")
        else:
            print("No data available.")
    except Exception as e:
        print(f"Error loading report: {e}")

    input("\nPress Enter to continue...")


def _certification_status() -> None:
    """Display certification status report."""
    print("\n--- Certification Status ---")
    try:
        status = TrainingManager.get_certification_status()
        if status:
            print(f"Total Certifications Tracked: {status.get('total', 0)}")
            print(f"Valid: {status.get('valid', 0)}")
            print(f"Expiring Soon (30 days): {status.get('expiring_soon', 0)}")
            print(f"Expired: {status.get('expired', 0)}")
        else:
            print("No data available.")
    except Exception as e:
        print(f"Error loading report: {e}")

    input("\nPress Enter to continue...")


def _appraisal_summary() -> None:
    """Display appraisal summary."""
    print("\n--- Appraisal Summary ---")
    try:
        summary = PerformanceManager.get_appraisal_summary()
        if summary:
            print(f"Appraisal Period: {summary.get('period', 'N/A')}")
            print(f"Total Appraisals: {summary.get('total', 0)}")
            print(f"Completed: {summary.get('completed', 0)}")
            print(f"Pending: {summary.get('pending', 0)}")
            print(f"Completion Rate: {summary.get('completion_rate', 0):.1f}%")
            print("\nRating Distribution:")
            for rating, count in summary.get('ratings', {}).items():
                print(f"  {rating}: {count}")
        else:
            print("No data available.")
    except Exception as e:
        print(f"Error loading report: {e}")

    input("\nPress Enter to continue...")


def _goal_progress() -> None:
    """Display goal progress report."""
    print("\n--- Goal Progress Report ---")
    try:
        report = PerformanceManager.get_goal_progress_report()
        if report:
            print(f"Total Goals Set: {report.get('total_goals', 0)}")
            print(f"Completed: {report.get('completed', 0)}")
            print(f"On Track: {report.get('on_track', 0)}")
            print(f"At Risk: {report.get('at_risk', 0)}")
            print(f"Overdue: {report.get('overdue', 0)}")
            print(f"Overall Progress: {report.get('overall_progress', 0):.1f}%")
        else:
            print("No data available.")
    except Exception as e:
        print(f"Error loading report: {e}")

    input("\nPress Enter to continue...")
