"""TA Management CLI menu."""

import logging
from education_system.post_18.university_system.modules.domain.academics.services.assignments.admin_tools.ta_service import TAService

logger = logging.getLogger(__name__)


def display_ta_management_menu(auth):
    """Display the TA management CLI menu."""
    if not auth or not auth.current_user:
        print("\n--- Please log in to access TA management.")
        input("Press Enter to continue...")
        return

    service = TAService()
    role = auth.current_user.get('role', '')
    user_id = auth.current_user.get('username', '')
    is_manager = role in ('admin', 'instructor')

    while True:
        print("\n" + "=" * 60)
        print("      TEACHING ASSISTANT MANAGEMENT")
        print("=" * 60)

        option_num = 1
        options = {}

        print(f"{option_num}. View TAs for a Module")
        options[str(option_num)] = 'view_module_tas'
        option_num += 1

        if is_manager:
            print(f"{option_num}. Assign TA to Module")
            options[str(option_num)] = 'assign'
            option_num += 1

            print(f"{option_num}. Remove TA")
            options[str(option_num)] = 'remove'
            option_num += 1

            print(f"{option_num}. Set TA Permissions")
            options[str(option_num)] = 'set_permissions'
            option_num += 1

            print(f"{option_num}. View TA Workload")
            options[str(option_num)] = 'view_workload'
            option_num += 1

            print(f"{option_num}. View All TAs")
            options[str(option_num)] = 'view_all'
            option_num += 1

        if role == 'student':
            print(f"{option_num}. View My TA Assignments")
            options[str(option_num)] = 'my_assignments'
            option_num += 1

        print(f"{option_num}. Return to Main Menu")
        options[str(option_num)] = 'return'

        print("=" * 60)
        choice = input("\nEnter your choice: ").strip()

        if choice not in options:
            print("Invalid choice. Please try again.")
            continue

        action = options[choice]

        if action == 'return':
            break
        elif action == 'view_module_tas':
            _view_module_tas(service)
        elif action == 'assign':
            _assign_ta(service, user_id)
        elif action == 'remove':
            _remove_ta(service)
        elif action == 'set_permissions':
            _set_ta_permissions(service, user_id)
        elif action == 'view_workload':
            _view_ta_workload(service)
        elif action == 'view_all':
            _view_all_tas(service)
        elif action == 'my_assignments':
            _view_my_assignments(service, user_id)


def _view_module_tas(service):
    """View all TAs assigned to a specific module."""
    print("\n--- View TAs for a Module ---")
    module_code = input("Enter module code: ").strip()
    if not module_code:
        print("Module code cannot be empty.")
        return

    try:
        tas = service.get_tas_for_module(module_code)
        if not tas:
            print(f"\nNo active TAs found for module '{module_code}'.")
            return

        print(f"\nActive TAs for module '{module_code}':")
        print("-" * 70)
        print(f"{'ID':<6} {'Student ID':<15} {'Role':<12} {'Hours/Week':<12} {'Start Date':<20}")
        print("-" * 70)
        for ta in tas:
            print(
                f"{ta.get('id', 'N/A'):<6} "
                f"{ta.get('student_id', 'N/A'):<15} "
                f"{ta.get('role_type', 'N/A'):<12} "
                f"{ta.get('hours_per_week', 'N/A'):<12} "
                f"{ta.get('start_date', 'N/A'):<20}"
            )
        print("-" * 70)
        print(f"Total: {len(tas)} TA(s)")
    except Exception as e:
        logger.error(f"Error viewing TAs for module: {e}")
        print(f"\nError retrieving TAs: {e}")

    input("\nPress Enter to continue...")


def _assign_ta(service, instructor_id):
    """Assign a student as a TA for a module."""
    print("\n--- Assign TA to Module ---")
    student_id = input("Enter student ID: ").strip()
    if not student_id:
        print("Student ID cannot be empty.")
        return

    module_code = input("Enter module code: ").strip()
    if not module_code:
        print("Module code cannot be empty.")
        return

    print("\nRole types: ta, lead_ta, grader")
    role_type = input("Enter role type [ta]: ").strip().lower() or 'ta'
    if role_type not in ('ta', 'lead_ta', 'grader'):
        print(f"Invalid role type '{role_type}'. Must be ta, lead_ta, or grader.")
        return

    hours_input = input("Enter hours per week [10]: ").strip()
    try:
        hours_per_week = float(hours_input) if hours_input else 10.0
        if hours_per_week <= 0:
            print("Hours per week must be a positive number.")
            return
    except ValueError:
        print("Invalid number for hours per week.")
        return

    print("\nAssignment Summary:")
    print(f"  Student ID:    {student_id}")
    print(f"  Module Code:   {module_code}")
    print(f"  Role Type:     {role_type}")
    print(f"  Hours/Week:    {hours_per_week}")
    print(f"  Instructor ID: {instructor_id}")

    confirm = input("\nConfirm assignment? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Assignment cancelled.")
        return

    try:
        ta_id = service.assign_ta(
            student_id=student_id,
            instructor_id=instructor_id,
            module_code=module_code,
            role_type=role_type,
            hours_per_week=hours_per_week,
        )
        print(f"\nTA assigned successfully. Assignment ID: {ta_id}")
    except ValueError as e:
        print(f"\nValidation error: {e}")
    except Exception as e:
        logger.error(f"Error assigning TA: {e}")
        if "UNIQUE constraint" in str(e):
            print(f"\nError: Student '{student_id}' is already a TA for module '{module_code}'.")
        else:
            print(f"\nError assigning TA: {e}")

    input("\nPress Enter to continue...")


def _remove_ta(service):
    """Remove (deactivate) a TA assignment."""
    print("\n--- Remove TA Assignment ---")
    ta_id_input = input("Enter TA assignment ID: ").strip()
    if not ta_id_input:
        print("TA assignment ID cannot be empty.")
        return

    try:
        ta_id = int(ta_id_input)
    except ValueError:
        print("Invalid TA assignment ID. Must be a number.")
        return

    # Show the TA details before confirming removal
    try:
        ta = service.get_ta(ta_id)
        if not ta:
            print(f"\nNo TA assignment found with ID {ta_id}.")
            input("\nPress Enter to continue...")
            return

        if ta.get('status') == 'inactive':
            print(f"\nTA assignment {ta_id} is already inactive.")
            input("\nPress Enter to continue...")
            return

        print("\nTA Assignment Details:")
        print(f"  ID:          {ta.get('id')}")
        print(f"  Student ID:  {ta.get('student_id')}")
        print(f"  Module:      {ta.get('module_code')}")
        print(f"  Role:        {ta.get('role_type')}")
        print(f"  Hours/Week:  {ta.get('hours_per_week')}")
        print(f"  Status:      {ta.get('status')}")
    except Exception as e:
        logger.error(f"Error retrieving TA details: {e}")
        print(f"\nError retrieving TA details: {e}")
        input("\nPress Enter to continue...")
        return

    confirm = input("\nAre you sure you want to remove this TA? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Removal cancelled.")
        input("\nPress Enter to continue...")
        return

    try:
        success = service.remove_ta(ta_id)
        if success:
            print(f"\nTA assignment {ta_id} has been deactivated successfully.")
        else:
            print(f"\nFailed to remove TA assignment {ta_id}. It may already be inactive.")
    except Exception as e:
        logger.error(f"Error removing TA: {e}")
        print(f"\nError removing TA: {e}")

    input("\nPress Enter to continue...")


def _set_ta_permissions(service, granted_by):
    """Set permissions for a TA on a specific module."""
    print("\n--- Set TA Permissions ---")
    ta_id_input = input("Enter TA assignment ID: ").strip()
    if not ta_id_input:
        print("TA assignment ID cannot be empty.")
        return

    try:
        ta_id = int(ta_id_input)
    except ValueError:
        print("Invalid TA assignment ID. Must be a number.")
        return

    # Verify TA exists
    try:
        ta = service.get_ta(ta_id)
        if not ta:
            print(f"\nNo TA assignment found with ID {ta_id}.")
            input("\nPress Enter to continue...")
            return
        if ta.get('status') != 'active':
            print(f"\nTA assignment {ta_id} is not active. Cannot set permissions.")
            input("\nPress Enter to continue...")
            return
    except Exception as e:
        logger.error(f"Error verifying TA: {e}")
        print(f"\nError verifying TA: {e}")
        input("\nPress Enter to continue...")
        return

    module_code = input(f"Enter module code [{ta.get('module_code', '')}]: ").strip()
    if not module_code:
        module_code = ta.get('module_code', '')
    if not module_code:
        print("Module code cannot be empty.")
        return

    permission_types = [
        'grade_assignments',
        'take_attendance',
        'upload_materials',
        'manage_discussions',
        'view_student_info',
    ]

    print(f"\nSelect permissions for TA {ta_id} (Student: {ta.get('student_id')}) "
          f"on module '{module_code}':")
    print("Toggle each permission by entering its number. Enter 'done' when finished.\n")

    selected = set()
    while True:
        for i, perm in enumerate(permission_types, 1):
            status = "[X]" if perm in selected else "[ ]"
            print(f"  {i}. {status} {perm}")
        print(f"  {len(permission_types) + 1}. Save and Apply")
        print(f"  {len(permission_types) + 2}. Cancel")

        toggle = input("\nToggle permission number (or save/cancel): ").strip()

        if toggle == str(len(permission_types) + 2):
            print("Permission update cancelled.")
            input("\nPress Enter to continue...")
            return

        if toggle == str(len(permission_types) + 1):
            break

        try:
            idx = int(toggle) - 1
            if 0 <= idx < len(permission_types):
                perm = permission_types[idx]
                if perm in selected:
                    selected.discard(perm)
                    print(f"  Removed: {perm}")
                else:
                    selected.add(perm)
                    print(f"  Added: {perm}")
            else:
                print("Invalid number. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    permissions_list = sorted(selected)
    if not permissions_list:
        print("\nNo permissions selected. Clear all permissions for this TA on this module?")
        confirm = input("Confirm? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Cancelled.")
            input("\nPress Enter to continue...")
            return

    try:
        success = service.set_ta_permissions(
            ta_id=ta_id,
            permission_types=permissions_list,
            module_code=module_code,
            granted_by=granted_by,
        )
        if success:
            print(f"\nPermissions updated successfully for TA {ta_id}.")
            if permissions_list:
                print("Granted permissions:")
                for perm in permissions_list:
                    print(f"  - {perm}")
            else:
                print("All permissions have been cleared.")
        else:
            print("\nFailed to update permissions.")
    except ValueError as e:
        print(f"\nValidation error: {e}")
    except Exception as e:
        logger.error(f"Error setting TA permissions: {e}")
        print(f"\nError setting permissions: {e}")

    input("\nPress Enter to continue...")


def _view_ta_workload(service):
    """View workload summary for a specific TA student."""
    print("\n--- View TA Workload ---")
    student_id = input("Enter student ID: ").strip()
    if not student_id:
        print("Student ID cannot be empty.")
        return

    try:
        workload = service.get_ta_workload(student_id)
        assignments = workload.get('assignments', [])
        total_hours = workload.get('total_hours', 0)
        count = workload.get('assignment_count', 0)

        if count == 0:
            print(f"\nNo active TA assignments found for student '{student_id}'.")
            input("\nPress Enter to continue...")
            return

        print(f"\nWorkload Summary for Student: {student_id}")
        print("=" * 60)
        print(f"  Total Active Assignments: {count}")
        print(f"  Total Hours per Week:     {total_hours}")
        print("=" * 60)
        print(f"\n{'ID':<6} {'Module':<15} {'Role':<12} {'Hours/Week':<12} {'Start Date':<20}")
        print("-" * 65)
        for a in assignments:
            print(
                f"{a.get('id', 'N/A'):<6} "
                f"{a.get('module_code', 'N/A'):<15} "
                f"{a.get('role_type', 'N/A'):<12} "
                f"{a.get('hours_per_week', 'N/A'):<12} "
                f"{a.get('start_date', 'N/A'):<20}"
            )
        print("-" * 65)

        if total_hours > 20:
            print("\n[WARNING] Student exceeds 20 hours/week across TA assignments.")
    except Exception as e:
        logger.error(f"Error viewing TA workload: {e}")
        print(f"\nError retrieving workload: {e}")

    input("\nPress Enter to continue...")


def _view_all_tas(service):
    """View all active TAs in the system."""
    print("\n--- All Active Teaching Assistants ---")

    try:
        tas = service.get_all_tas(status='active')
        if not tas:
            print("\nNo active TAs found in the system.")
            input("\nPress Enter to continue...")
            return

        print(f"\n{'ID':<6} {'Student ID':<15} {'Module':<15} {'Role':<12} "
              f"{'Hours/Week':<12} {'Instructor':<15}")
        print("-" * 75)
        for ta in tas:
            print(
                f"{ta.get('id', 'N/A'):<6} "
                f"{ta.get('student_id', 'N/A'):<15} "
                f"{ta.get('module_code', 'N/A'):<15} "
                f"{ta.get('role_type', 'N/A'):<12} "
                f"{ta.get('hours_per_week', 'N/A'):<12} "
                f"{ta.get('instructor_id', 'N/A'):<15}"
            )
        print("-" * 75)
        print(f"Total: {len(tas)} active TA(s)")
    except Exception as e:
        logger.error(f"Error viewing all TAs: {e}")
        print(f"\nError retrieving TAs: {e}")

    input("\nPress Enter to continue...")


def _view_my_assignments(service, student_id):
    """View TA assignments for the current student."""
    print("\n--- My TA Assignments ---")

    try:
        assignments = service.get_ta_assignments_for_student(student_id)
        if not assignments:
            print("\nYou have no TA assignments.")
            input("\nPress Enter to continue...")
            return

        active = [a for a in assignments if a.get('status') == 'active']
        inactive = [a for a in assignments if a.get('status') != 'active']

        if active:
            print(f"\nActive Assignments ({len(active)}):")
            print(f"{'ID':<6} {'Module':<15} {'Role':<12} {'Hours/Week':<12} {'Start Date':<20}")
            print("-" * 65)
            for a in active:
                print(
                    f"{a.get('id', 'N/A'):<6} "
                    f"{a.get('module_code', 'N/A'):<15} "
                    f"{a.get('role_type', 'N/A'):<12} "
                    f"{a.get('hours_per_week', 'N/A'):<12} "
                    f"{a.get('start_date', 'N/A'):<20}"
                )
            print("-" * 65)

        if inactive:
            print(f"\nPast Assignments ({len(inactive)}):")
            print(f"{'ID':<6} {'Module':<15} {'Role':<12} {'Hours/Week':<12} "
                  f"{'Start Date':<20} {'End Date':<20}")
            print("-" * 85)
            for a in inactive:
                print(
                    f"{a.get('id', 'N/A'):<6} "
                    f"{a.get('module_code', 'N/A'):<15} "
                    f"{a.get('role_type', 'N/A'):<12} "
                    f"{a.get('hours_per_week', 'N/A'):<12} "
                    f"{a.get('start_date', 'N/A'):<20} "
                    f"{a.get('end_date', 'N/A'):<20}"
                )
            print("-" * 85)

        # Show total active workload
        workload = service.get_ta_workload(student_id)
        total_hours = workload.get('total_hours', 0)
        print(f"\nTotal active hours per week: {total_hours}")
    except Exception as e:
        logger.error(f"Error viewing my assignments: {e}")
        print(f"\nError retrieving assignments: {e}")

    input("\nPress Enter to continue...")
