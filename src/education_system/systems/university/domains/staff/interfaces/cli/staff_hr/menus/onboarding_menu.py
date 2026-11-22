"""
Onboarding Menu - Employee onboarding management CLI.

Everyone sees their own onboarding tasks; running onboardings and templates
is HR's (OnboardingManager checks the actor too).
"""

from education_system.systems.university.domains.staff.domain.staff_hr import access
from education_system.systems.university.domains.staff.domain.staff_hr.services import OnboardingManager
from education_system.systems.university.domains.staff.interfaces.cli.staff_hr.menus.profile_menu import (
    _run,
    session_actor,
)


def display_onboarding_menu(user_id: str = None) -> None:
    """Display onboarding management menu."""
    actor = session_actor(user_id)
    is_hr = access.can(actor, 'hr')
    while True:
        print("\n" + "=" * 60)
        print("ONBOARDING MANAGEMENT")
        print("=" * 60)

        if is_hr:
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
        print(" 10. My Onboarding Tasks")
        print("  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice in ('1', '2', '3', '4', '5', '6', '7') and not is_hr:
            print("Only HR can do that.")
        elif choice == '1':
            _run(lambda: _view_active_onboardings(actor))
        elif choice == '2':
            _run(lambda: _start_onboarding(actor))
        elif choice == '3':
            _run(lambda: _update_progress(actor))
        elif choice == '4':
            _run(lambda: _complete_onboarding(actor))
        elif choice == '5':
            _run(lambda: _view_templates(actor))
        elif choice == '6':
            _run(lambda: _create_template(actor))
        elif choice == '7':
            _run(lambda: _edit_template(actor))
        elif choice == '8':
            _run(lambda: _view_checklist(actor))
        elif choice == '9':
            _run(lambda: _mark_item_complete(actor))
        elif choice == '10':
            _run(lambda: _my_tasks(actor))
        else:
            print("Invalid choice.")


def _view_active_onboardings(actor) -> None:
    """View active onboardings."""
    print("\n--- Active Onboardings ---")
    onboardings = OnboardingManager.list_assignments(actor, status='in_progress')
    if onboardings:
        for o in onboardings:
            total = o.get('total_tasks') or 0
            progress = round(100 * (o.get('done_tasks') or 0) / total) if total else 0
            print(f"\nID: {o['assignment_id']}")
            print(f"  Employee: {access.display_name(o['user_id'])} ({o['user_id']})")
            print(f"  Template: {o['template_name']} ({o['template_type']})")
            print(f"  Start Date: {o.get('start_date') or 'N/A'}")
            print(f"  Target: {o.get('target_completion_date') or 'N/A'}")
            print(f"  Progress: {progress}% ({o.get('done_tasks') or 0}/{total})")
    else:
        print("No active onboardings.")

    input("\nPress Enter to continue...")


def _start_onboarding(actor) -> None:
    """Start a new onboarding process."""
    print("\n--- Start New Onboarding ---")
    employee_id = input("Employee (username or ID): ").strip()
    if not employee_id:
        print("Cancelled.")
        return

    start_date = input("Start Date (YYYY-MM-DD, Enter for today): ").strip()
    templates = OnboardingManager.get_templates()
    for t in templates:
        print(f"  {t['template_id']}. {t['name']} ({t['template_type']})")
    template_id = input("Template ID (Enter for the first onboarding template): ").strip()
    if not template_id:
        default = next((t for t in templates if t['template_type'] == 'onboarding'), None)
        if not default:
            print("No active onboarding template.")
            return
        template_id = default['template_id']

    onboarding_id = OnboardingManager.assign_template(
        employee_id, int(template_id), None,
        start_date=start_date or None, actor=actor)
    print(f"\nOnboarding started. ID: {onboarding_id}")
    input("Press Enter to continue...")


def _update_progress(actor) -> None:
    """Update onboarding progress."""
    onboarding_id = input("\nEnter onboarding ID: ").strip()
    if not onboarding_id:
        print("Cancelled.")
        return

    onboarding = OnboardingManager.get_assignment(int(onboarding_id), actor=actor)
    if not onboarding:
        print("Onboarding not found.")
        return

    total = onboarding.get('total_tasks') or 0
    print(f"\nCurrent Progress: {onboarding.get('done_tasks') or 0}/{total} tasks")
    print(f"Target: {onboarding.get('target_completion_date') or 'N/A'}")
    notes = input("Progress Notes: ").strip()
    target = input("New Target Date (YYYY-MM-DD, Enter to keep): ").strip()

    OnboardingManager.update_assignment(int(onboarding_id), actor, notes=notes or None,
                                        target_date=target or None)
    print("Progress updated.")
    input("Press Enter to continue...")


def _complete_onboarding(actor) -> None:
    """Mark onboarding as complete."""
    onboarding_id = input("\nEnter onboarding ID to complete: ").strip()
    if not onboarding_id:
        print("Cancelled.")
        return

    OnboardingManager.complete_assignment(int(onboarding_id), actor)
    print("Onboarding marked as complete.")
    input("Press Enter to continue...")


def _view_templates(actor) -> None:
    """View onboarding templates."""
    print("\n--- Onboarding Templates ---")
    templates = OnboardingManager.list_templates(actor)
    if templates:
        for t in templates:
            print(f"\nID: {t['template_id']}")
            print(f"  Name: {t.get('name', 'N/A')} ({t.get('template_type')})")
            print(f"  Department: {t.get('department') or 'All'}")
            print(f"  Items: {t.get('task_count', 0)}")
            print(f"  Active: {'Yes' if t.get('is_active') else 'No'}")
    else:
        print("No templates found.")

    input("\nPress Enter to continue...")


def _create_template(actor) -> None:
    """Create a new onboarding template."""
    print("\n--- Create Onboarding Template ---")
    name = input("Template Name: ").strip()
    if not name:
        print("Cancelled.")
        return

    kind = input("Type (onboarding/offboarding, Enter for onboarding): ").strip().lower() or 'onboarding'
    if kind not in ('onboarding', 'offboarding'):
        print("Type must be onboarding or offboarding.")
        return
    department = input("Department (Enter for all): ").strip()
    description = input("Description: ").strip()

    template_id = OnboardingManager.create_template(
        name, actor=actor,
        template_type=kind,
        department=department or None,
        description=description,
    )
    print(f"\nTemplate created. ID: {template_id}")
    input("Press Enter to continue...")


def _edit_template(actor) -> None:
    """Edit an onboarding template."""
    template_id = input("\nEnter template ID to edit: ").strip()
    if not template_id:
        print("Cancelled.")
        return

    template = OnboardingManager.get_template(int(template_id))
    if not template:
        print("Template not found.")
        return

    print(f"\nCurrent Name: {template.get('name')}")
    new_name = input("New Name (Enter to keep): ").strip()

    print(f"Current Description: {template.get('description')}")
    new_desc = input("New Description (Enter to keep): ").strip()

    active = input(f"Active? (y/n, Enter to keep '{'y' if template.get('is_active') else 'n'}'): ").strip().lower()

    changes = {}
    if new_name:
        changes['name'] = new_name
    if new_desc:
        changes['description'] = new_desc
    if active in ('y', 'n'):
        changes['is_active'] = 1 if active == 'y' else 0
    if not changes:
        print("Nothing changed.")
        return
    OnboardingManager.update_template(int(template_id), actor=actor, **changes)
    print("Template updated.")
    input("Press Enter to continue...")


def _view_checklist(actor) -> None:
    """View checklist items for an onboarding."""
    onboarding_id = input("\nEnter onboarding ID: ").strip()
    if not onboarding_id:
        print("Cancelled.")
        return

    print("\n--- Checklist Items ---")
    items = OnboardingManager.get_assignment_tasks(int(onboarding_id), actor)
    if items:
        for item in items:
            status = "[X]" if item.get('status') == 'completed' else "[ ]"
            owner = item.get('assigned_to') or item.get('assigned_to_role') or 'employee'
            print(f"{status} {item['progress_id']}: {item.get('title', 'N/A')}  ({owner})")
            if item.get('due_date'):
                print(f"    Due: {item.get('due_date')}")
    else:
        print("No checklist items found.")

    input("\nPress Enter to continue...")


def _mark_item_complete(actor) -> None:
    """Mark a checklist item as complete."""
    item_id = input("\nEnter checklist item ID: ").strip()
    if not item_id:
        print("Cancelled.")
        return

    notes = input("Notes (optional): ").strip()
    result = OnboardingManager.complete_task_for(actor, int(item_id), notes or None)
    if result is None:
        print("Item not found.")
    else:
        print("Item marked as complete.")
        if result['contract_missing']:
            print("All tasks are done, but no signed contract is on file in Document Manager; "
                  "the onboarding stays open until it is uploaded.")
        elif result['assignment_completed']:
            print("That was the last required task: the onboarding is complete.")
    input("Press Enter to continue...")


def _my_tasks(actor) -> None:
    """The signed-in person's open onboarding tasks."""
    print("\n--- My Onboarding Tasks ---")
    tasks = [t for t in OnboardingManager.get_my_tasks(actor) if t['status'] != 'completed']
    if not tasks:
        print("No open tasks.")
    for t in tasks:
        mark = '*' if t['can_complete'] else ' '
        print(f"{mark} {t['progress_id']}: {t['title']}  [{t['template_name']} - {t['staff_user']}]"
              f"  due {t.get('due_date') or '-'}")
    if tasks:
        print("\n(* = you can mark it complete with option 9)")
    input("\nPress Enter to continue...")
