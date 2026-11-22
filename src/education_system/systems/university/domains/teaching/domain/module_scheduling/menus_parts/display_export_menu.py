"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def display_export_menu(scheduler):
    """Display export options menu"""
    print("\nExport Options:")
    print("===============")
    print("1. Export All Schedules to CSV")
    print("2. Export Room Utilization Report")
    print("3. Export Instructor Workload Report")
    print("4. Export to iCal Format")
    print("5. Generate PDF Reports")

    choice = input("\nEnter your choice (1-5): ")

    if choice == '1':
        filename = scheduler.export_all_schedules_to_csv()
        print(f"All schedules exported to: {filename}")
    elif choice == '2':
        format_choice = input("Choose format (csv/pdf/display): ").lower()
        scheduler.generate_room_utilization_report(format_choice)
    elif choice == '3':
        format_choice = input("Choose format (csv/pdf/display): ").lower()
        scheduler.generate_instructor_workload_report(format_choice)
    elif choice == '4':
        display_ical_export_menu(scheduler)
    elif choice == '5':
        display_pdf_reports_menu(scheduler)
    else:
        print("Invalid choice.")
