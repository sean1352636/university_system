"""Activity dashboard and summary CLI functions."""

import json
from datetime import datetime

from education_system.university_system.modules.shared.constants.paths import LOG_DIR


def display_activity_dashboard(log_manager, auth):
    """Display activity dashboard"""
    print("\n\U0001f4ca ACTIVITY DASHBOARD")
    print("="*50)

    # Quick stats for last 7 days
    summary = log_manager.analytics.generate_activity_summary(7)

    if "error" in summary:
        print(summary["error"])
        return

    print(f"Period: {summary['period']}")
    print(f"Total Activities: {summary['total_activities']:,}")
    print(f"Unique Users: {summary['unique_users']}")
    print(f"Success Rate: {summary['success_rate']:.1f}%")
    print(f"Failed Activities: {summary['failed_activities']}")
    print(f"Peak Activity Hour: {summary['peak_activity_hour']}:00")

    print("\n\U0001f525 Most Active Users:")
    for user, count in list(summary['most_active_users'].items())[:5]:
        print(f"  {user}: {count} activities")

    print("\n\U0001f4cb Activity by Action:")
    for action, count in list(summary['activity_by_action'].items())[:5]:
        print(f"  {action}: {count}")

    print("\n\U0001f527 Activity by Module:")
    for module, count in list(summary['activity_by_module'].items())[:5]:
        print(f"  {module}: {count}")

    input("\nPress Enter to continue...")


def generate_activity_summary_menu(log_manager, auth):
    """Generate activity summary menu"""
    print("\n\U0001f4ca GENERATE ACTIVITY SUMMARY")
    print("="*40)

    days = input("Enter number of days to analyze (default: 7): ")
    try:
        days = int(days) if days else 7
    except ValueError:
        days = 7

    print(f"\nGenerating summary for last {days} days...")
    summary = log_manager.analytics.generate_activity_summary(days)

    if "error" in summary:
        print(summary["error"])
        return

    # Display detailed summary
    print("\n" + "="*60)
    print(f"ACTIVITY SUMMARY - LAST {days} DAYS")
    print("="*60)
    print(f"Period: {summary['period']}")
    print(f"Total Activities: {summary['total_activities']:,}")
    print(f"Unique Users: {summary['unique_users']}")
    print(f"Success Rate: {summary['success_rate']:.2f}%")
    print(f"Failed Activities: {summary['failed_activities']}")
    print(f"Peak Activity Hour: {summary['peak_activity_hour']}:00")

    print(f"\n{'Top Users':<20} {'Activities':<10}")
    print("-" * 30)
    for user, count in list(summary['most_active_users'].items())[:10]:
        print(f"{user:<20} {count:<10}")

    print(f"\n{'Actions':<20} {'Count':<10}")
    print("-" * 30)
    for action, count in summary['activity_by_action'].items():
        print(f"{action:<20} {count:<10}")

    print(f"\n{'Modules':<20} {'Count':<10}")
    print("-" * 30)
    for module, count in summary['activity_by_module'].items():
        print(f"{module:<20} {count:<10}")

    # Option to export
    export = input("\nExport summary to file? (y/n): ")
    if export.lower() == 'y':
        filename = f"activity_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        reports_dir = LOG_DIR / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        filepath = str(reports_dir / filename)

        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"Summary exported to {filepath}")

    input("\nPress Enter to continue...")


def user_activity_report_menu(log_manager, auth):
    """User activity report menu"""
    print("\n\U0001f464 USER ACTIVITY REPORT")
    print("="*30)

    user_id = input("Enter user ID: ")
    if not user_id:
        print("User ID is required.")
        return

    days = input("Enter number of days to analyze (default: 30): ")
    try:
        days = int(days) if days else 30
    except ValueError:
        days = 30

    print(f"\nGenerating report for user {user_id} (last {days} days)...")

    report = log_manager.analytics.generate_user_activity_report(user_id, days)

    if "error" in report:
        print(report["error"])
        return

    # Display report
    print("\n" + "="*60)
    print(f"USER ACTIVITY REPORT: {report['username']} ({report['user_id']})")
    print("="*60)
    print(f"Period: {report['period']}")
    print(f"Total Activities: {report['total_activities']:,}")
    print(f"Success Rate: {report['success_rate']:.2f}%")

    print(f"\n{'Modules Used':<25} {'Count':<10}")
    print("-" * 35)
    for module, count in list(report['modules_used'].items())[:10]:
        print(f"{module:<25} {count:<10}")

    print(f"\n{'Actions Performed':<25} {'Count':<10}")
    print("-" * 35)
    for action, count in report['actions_performed'].items():
        print(f"{action:<25} {count:<10}")

    print(f"\n{'Most Active Hours':<15} {'Activities':<10}")
    print("-" * 25)
    sorted_hours = sorted(report['activity_hours'].items(), key=lambda x: x[1], reverse=True)
    for hour, count in sorted_hours[:5]:
        print(f"{hour:02d}:00{'':<9} {count:<10}")

    input("\nPress Enter to continue...")


def create_charts_menu(log_manager, auth):
    """Create activity charts menu"""
    print("\n\U0001f4c8 CREATE ACTIVITY CHARTS")
    print("="*30)

    days = input("Enter number of days to analyze (default: 7): ")
    try:
        days = int(days) if days else 7
    except ValueError:
        days = 7

    save_path = input("Enter save path (or press Enter for auto-path): ")
    if not save_path:
        charts_dir = LOG_DIR / "charts"
        charts_dir.mkdir(parents=True, exist_ok=True)
        save_path = str(charts_dir / f"activity_chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")

    print(f"\nGenerating activity charts for last {days} days...")

    try:
        result_path = log_manager.analytics.create_activity_chart("daily", days, save_path)
        if result_path:
            print(f"Charts saved to: {result_path}")
        else:
            print("Chart generation completed (displayed on screen)")
    except Exception as e:
        print(f"Error generating charts: {e}")

    input("\nPress Enter to continue...")
