"""
Onboarding Menu - Employee onboarding management CLI.
"""

from education_system.university_system.modules.domain.staff_hr.services import OnboardingManager


def display_onboarding_menu(user_id: str = None) -> None:
    """Display onboarding management menu."""
    while True:
        print("\n" + "=" * 60)
        print("ONBOARDING MANAGEMENT")
        print("=" * 60)

        print("\n--- Active Onboardings ---")
        print("  1. View Active Onboardings")
        print("  2. Start New Onboarding")
        print("  3. Update Onboarding Progress")
        print("  4. Complete Onboarding")

        print("\n--- Templates ---")
        print("  5. View Onboarding Templates")
        print("  6. Create Template")
        print("  7. Edit Template")

        print("\n--- Checklists ---")
        print("  8. View Checklist Items")
        print("  9. Mark Item Complete")
        print("  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _view_active_onboardings()
        elif choice == '2':
            _start_onboarding(user_id)
        elif choice == '3':
            _update_progress()
        elif choice == '4':
            _complete_onboarding()
        elif choice == '5':
            _view_templates()
        elif choice == '6':
            _create_template(user_id)
        elif choice == '7':
            _edit_template()
        elif choice == '8':
            _view_checklist()
        elif choice == '9':
            _mark_item_complete()
        else:
            print("Invalid choice.")


def _view_active_onboardings() -> None:
    """View active onboardings."""
    print("\n--- Active Onboardings ---")
    try:
        onboardings = OnboardingManager.get_active_onboardings()
        if onboardings:
            for o in onboardings:
                print(f"\nID: {o.get('id')}")
                print(f"  Employee: {o.get('employee_name', 'N/A')}")
                print(f"  Start Date: {o.get('start_date', 'N/A')}")
                print(f"  Progress: {o.get('progress', 0)}%")
                print(f"  Status: {o.get('status', 'N/A')}")
        else:
            print("No active onboardings.")
    except Exception as e:
        print(f"Error loading onboardings: {e}")

    input("\nPress Enter to continue...")


def _start_onboarding(user_id: str) -> None:
    """Start a new onboarding process."""
    print("\n--- Start New Onboarding ---")
    try:
        employee_id = input("Employee ID: ").strip()
        if not employee_id:
            print("Cancelled.")
            return

        start_date = input("Start Date (YYYY-MM-DD): ").strip()
        template_id = input("Template ID (Enter for default): ").strip()

        onboarding_id = OnboardingManager.start_onboarding(
            employee_id=employee_id,
            start_date=start_date,
            template_id=template_id or None,
            created_by=user_id
        )
        print(f"\nOnboarding started. ID: {onboarding_id}")
    except Exception as e:
        print(f"Error starting onboarding: {e}")

    input("Press Enter to continue...")


def _update_progress() -> None:
    """Update onboarding progress."""
    onboarding_id = input("\nEnter onboarding ID: ").strip()
    if not onboarding_id:
        print("Cancelled.")
        return

    try:
        onboarding = OnboardingManager.get_onboarding(onboarding_id)
        if not onboarding:
            print("Onboarding not found.")
            return

        print(f"\nCurrent Progress: {onboarding.get('progress', 0)}%")
        notes = input("Progress Notes: ").strip()

        OnboardingManager.update_progress(onboarding_id, notes=notes)
        print("Progress updated.")
    except Exception as e:
        print(f"Error updating progress: {e}")

    input("Press Enter to continue...")


def _complete_onboarding() -> None:
    """Mark onboarding as complete."""
    onboarding_id = input("\nEnter onboarding ID to complete: ").strip()
    if not onboarding_id:
        print("Cancelled.")
        return

    try:
        OnboardingManager.complete_onboarding(onboarding_id)
        print("Onboarding marked as complete.")
    except Exception as e:
        print(f"Error completing onboarding: {e}")

    input("Press Enter to continue...")


def _view_templates() -> None:
    """View onboarding templates."""
    print("\n--- Onboarding Templates ---")
    try:
        templates = OnboardingManager.get_templates()
        if templates:
            for t in templates:
                print(f"\nID: {t.get('id')}")
                print(f"  Name: {t.get('name', 'N/A')}")
                print(f"  Department: {t.get('department', 'All')}")
                print(f"  Items: {t.get('item_count', 0)}")
        else:
            print("No templates found.")
    except Exception as e:
        print(f"Error loading templates: {e}")

    input("\nPress Enter to continue...")


def _create_template(user_id: str) -> None:
    """Create a new onboarding template."""
    print("\n--- Create Onboarding Template ---")
    try:
        name = input("Template Name: ").strip()
        if not name:
            print("Cancelled.")
            return

        department = input("Department (Enter for all): ").strip()
        description = input("Description: ").strip()

        template_id = OnboardingManager.create_template(
            name=name,
            department=department or None,
            description=description,
            created_by=user_id
        )
        print(f"\nTemplate created. ID: {template_id}")
    except Exception as e:
        print(f"Error creating template: {e}")

    input("Press Enter to continue...")


def _edit_template() -> None:
    """Edit an onboarding template."""
    template_id = input("\nEnter template ID to edit: ").strip()
    if not template_id:
        print("Cancelled.")
        return

    try:
        template = OnboardingManager.get_template(template_id)
        if not template:
            print("Template not found.")
            return

        print(f"\nCurrent Name: {template.get('name')}")
        new_name = input("New Name (Enter to keep): ").strip()

        print(f"Current Description: {template.get('description')}")
        new_desc = input("New Description (Enter to keep): ").strip()

        OnboardingManager.update_template(
            template_id,
            name=new_name or None,
            description=new_desc or None
        )
        print("Template updated.")
    except Exception as e:
        print(f"Error updating template: {e}")

    input("Press Enter to continue...")


def _view_checklist() -> None:
    """View checklist items for an onboarding."""
    onboarding_id = input("\nEnter onboarding ID: ").strip()
    if not onboarding_id:
        print("Cancelled.")
        return

    print("\n--- Checklist Items ---")
    try:
        items = OnboardingManager.get_checklist_items(onboarding_id)
        if items:
            for item in items:
                status = "[X]" if item.get('completed') else "[ ]"
                print(f"{status} {item.get('id')}: {item.get('description', 'N/A')}")
                if item.get('due_date'):
                    print(f"    Due: {item.get('due_date')}")
        else:
            print("No checklist items found.")
    except Exception as e:
        print(f"Error loading checklist: {e}")

    input("\nPress Enter to continue...")


def _mark_item_complete() -> None:
    """Mark a checklist item as complete."""
    item_id = input("\nEnter checklist item ID: ").strip()
    if not item_id:
        print("Cancelled.")
        return

    try:
        OnboardingManager.complete_checklist_item(item_id)
        print("Item marked as complete.")
    except Exception as e:
        print(f"Error completing item: {e}")

    input("Press Enter to continue...")
