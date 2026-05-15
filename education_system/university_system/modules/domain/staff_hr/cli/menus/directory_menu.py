"""
Directory Menu - Staff directory search CLI.
"""

from education_system.university_system.modules.domain.staff_comms.staff_hr.services import EmployeeManager


def display_directory_menu() -> None:
    """Display staff directory menu."""
    while True:
        print("\n" + "=" * 60)
        print("STAFF DIRECTORY")
        print("=" * 60)

        print("\n  1. Search by Name")
        print("  2. Search by Department")
        print("  3. Search by Job Title")
        print("  4. View All Staff")
        print("  5. View Organization Chart")
        print("  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _search_by_name()
        elif choice == '2':
            _search_by_department()
        elif choice == '3':
            _search_by_title()
        elif choice == '4':
            _view_all_staff()
        elif choice == '5':
            _view_org_chart()
        else:
            print("Invalid choice.")


def _search_by_name() -> None:
    """Search staff by name."""
    name = input("\nEnter name to search: ").strip()
    if not name:
        print("Search cancelled.")
        return

    results = EmployeeManager.search_employees(name=name)
    _display_results(results)


def _search_by_department() -> None:
    """Search staff by department."""
    dept = input("\nEnter department: ").strip()
    if not dept:
        print("Search cancelled.")
        return

    results = EmployeeManager.search_employees(department=dept)
    _display_results(results)


def _search_by_title() -> None:
    """Search staff by job title."""
    title = input("\nEnter job title: ").strip()
    if not title:
        print("Search cancelled.")
        return

    results = EmployeeManager.search_employees(job_title=title)
    _display_results(results)


def _view_all_staff() -> None:
    """View all staff members."""
    results = EmployeeManager.get_all_employees()
    _display_results(results)


def _view_org_chart() -> None:
    """View organization chart."""
    print("\n--- Organization Chart ---")
    try:
        org_data = EmployeeManager.get_organization_structure()
        if org_data:
            for dept, employees in org_data.items():
                print(f"\n{dept}:")
                for emp in employees:
                    print(f"  - {emp.get('name', 'N/A')} ({emp.get('job_title', 'N/A')})")
        else:
            print("No organization data available.")
    except Exception as e:
        print(f"Error loading organization chart: {e}")

    input("\nPress Enter to continue...")


def _display_results(results: list) -> None:
    """Display search results."""
    if not results:
        print("\nNo results found.")
        input("Press Enter to continue...")
        return

    print(f"\n--- Found {len(results)} staff member(s) ---")
    for i, emp in enumerate(results, 1):
        print(f"\n{i}. {emp.get('name', 'N/A')}")
        print(f"   Department: {emp.get('department', 'N/A')}")
        print(f"   Job Title: {emp.get('job_title', 'N/A')}")
        print(f"   Email: {emp.get('email', 'N/A')}")
        print(f"   Office: {emp.get('office_location', 'N/A')}")

    input("\nPress Enter to continue...")
