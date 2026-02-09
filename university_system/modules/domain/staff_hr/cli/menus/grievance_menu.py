"""
Grievance Menu - Grievance and disciplinary management CLI.
"""

from datetime import datetime
from university_system.modules.domain.staff_hr.services.managers.grievance_manager import GrievanceManager
from university_system.modules.domain.staff_hr.cli.validators import (
    validate_date, validate_required, validate_choice, validate_integer,
    get_date_input, get_choice_input, get_required_input, get_integer_input,
    get_confirmation, ValidationError
)


def display_grievance_menu(user_id: str, is_admin: bool = False) -> None:
    """Display grievance and disciplinary menu."""
    while True:
        print("\n" + "=" * 60)
        print("GRIEVANCE & DISCIPLINARY MANAGEMENT")
        print("=" * 60)

        print("\n--- My Grievances ---")
        print("  1. File a Grievance")
        print("  2. View My Grievances")
        print("  3. View Grievance Status")

        if is_admin:
            print("\n--- Grievance Administration ---")
            print("  4. View All Grievances")
            print("  5. Manage Grievance")
            print("  6. Schedule Meeting")

            print("\n--- Disciplinary Records ---")
            print("  7. Search Disciplinary Records")
            print("  8. Create Disciplinary Record")
            print("  9. Manage Disciplinary Action")
            print(" 10. View Appeals")

            print("\n--- Reports ---")
            print(" 11. Grievance Statistics")
            print(" 12. Disciplinary Statistics")

        print("\n  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _file_grievance(user_id)
        elif choice == '2':
            _view_my_grievances(user_id)
        elif choice == '3':
            _view_grievance_status(user_id)
        elif choice == '4' and is_admin:
            _view_all_grievances()
        elif choice == '5' and is_admin:
            _manage_grievance()
        elif choice == '6' and is_admin:
            _schedule_meeting()
        elif choice == '7' and is_admin:
            _search_disciplinary_records()
        elif choice == '8' and is_admin:
            _create_disciplinary_record()
        elif choice == '9' and is_admin:
            _manage_disciplinary_action()
        elif choice == '10' and is_admin:
            _view_appeals()
        elif choice == '11' and is_admin:
            _grievance_statistics()
        elif choice == '12' and is_admin:
            _disciplinary_statistics()
        else:
            print("Invalid choice.")


def _file_grievance(user_id: str) -> None:
    """File a new grievance."""
    print("\n--- File a Grievance ---")

    # Show categories
    categories = GrievanceManager.get_all_categories()
    if categories:
        print("\nGrievance Categories:")
        for i, cat in enumerate(categories, 1):
            print(f"  {i}. {cat['name']}")
            if cat.get('description'):
                print(f"      {cat['description'][:60]}")

    print("\n  Or enter a custom category")

    cat_input = input("\nSelect category (number) or enter custom: ").strip()

    if not cat_input:
        print("Category is required.")
        input("Press Enter to continue...")
        return

    try:
        cat_idx = int(cat_input)
        if 1 <= cat_idx <= len(categories):
            category = categories[cat_idx - 1]['name']
        else:
            category = cat_input
    except ValueError:
        category = cat_input

    print("\nFiling Options:")
    print("  1. Standard Filing (your identity will be recorded)")
    print("  2. Anonymous Filing (your identity will be protected)")

    filing_type = get_choice_input(
        "\nChoice: ", ['1', '2'], "Filing Option", allow_empty=True
    ) or '1'
    is_anonymous = filing_type == '2'

    respondent_id = input("Respondent ID (person complaint is against, optional): ").strip() or None

    try:
        description = get_required_input(
            "\nDescribe your grievance in detail:\n", "Description"
        )
    except ValidationError as e:
        print(f"Error: {e}")
        input("Press Enter to continue...")
        return

    try:
        grievance_id = GrievanceManager.create_grievance(
            complainant_id=user_id,
            category=category,
            description=description,
            respondent_id=respondent_id,
            is_anonymous=is_anonymous
        )

        print(f"\nGrievance filed successfully.")
        print(f"Reference Number: GRV-{grievance_id}")
        if is_anonymous:
            print("Note: Your identity will be kept confidential.")
        print("\nYou will be notified of any updates.")

    except Exception as e:
        print(f"\nError filing grievance: {e}")

    input("\nPress Enter to continue...")


def _view_my_grievances(user_id: str) -> None:
    """View user's grievances."""
    grievances = GrievanceManager.get_user_grievances(user_id)

    if not grievances:
        print("\nNo grievances found.")
    else:
        print(f"\n--- My Grievances ({len(grievances)}) ---")
        for g in grievances:
            status_icon = {
                'open': '📂', 'investigating': '🔍', 'resolved': '✓',
                'closed': '○', 'escalated': '⚠'
            }.get(g.get('status', ''), '?')

            print(f"\n{status_icon} GRV-{g.get('grievance_id')}")
            print(f"   Category: {g.get('category')}")
            print(f"   Status: {g.get('status')} | Filed: {g.get('filed_date')}")
            print(f"   Description: {g.get('description', '')[:60]}...")

            if g.get('resolution'):
                print(f"   Resolution: {g.get('resolution')[:60]}...")

    input("\nPress Enter to continue...")


def _view_grievance_status(user_id: str) -> None:
    """View detailed status of a grievance."""
    grievance_id = input("\nEnter Grievance ID (number only): ").strip()

    try:
        grievance_id = int(grievance_id)
    except ValueError:
        print("Invalid ID.")
        return

    grievance = GrievanceManager.get_grievance(grievance_id)

    if not grievance:
        print("Grievance not found.")
        input("Press Enter to continue...")
        return

    # Verify ownership
    if grievance.get('complainant_id') != user_id:
        print("You can only view your own grievances.")
        input("Press Enter to continue...")
        return

    print(f"\n{'=' * 50}")
    print(f"GRIEVANCE GRV-{grievance_id}")
    print(f"{'=' * 50}")
    print(f"Category: {grievance.get('category')}")
    print(f"Status: {grievance.get('status')}")
    print(f"Priority: {grievance.get('priority', 'normal')}")
    print(f"Filed: {grievance.get('filed_date')}")

    if grievance.get('assigned_to'):
        print(f"Assigned To: {grievance.get('assigned_to')}")

    print(f"\nDescription:\n{grievance.get('description')}")

    if grievance.get('resolution'):
        print(f"\nResolution:\n{grievance.get('resolution')}")
        print(f"Resolution Date: {grievance.get('resolution_date')}")

    # Show actions
    actions = GrievanceManager.get_grievance_actions(grievance_id)
    if actions:
        print(f"\n--- Action History ({len(actions)}) ---")
        for a in actions:
            print(f"\n  {a.get('action_date')} - {a.get('action_type')}")
            print(f"  {a.get('details', '')[:60]}")

    input("\nPress Enter to continue...")


def _view_all_grievances() -> None:
    """View all grievances (admin)."""
    print("\n--- All Grievances ---")
    print("Filter by status:")
    print("  1. Open")
    print("  2. Investigating")
    print("  3. Resolved")
    print("  4. All Active")
    print("  5. All")

    filter_choice = input("\nChoice (default: All Active): ").strip()

    status_map = {
        '1': 'open', '2': 'investigating', '3': 'resolved', '5': None
    }

    if filter_choice in status_map:
        status = status_map[filter_choice]
        grievances = GrievanceManager.search_grievances(status=status)
    else:
        grievances = GrievanceManager.search_grievances(status='active')

    if not grievances:
        print("\nNo grievances found.")
    else:
        print(f"\n--- {len(grievances)} Grievances ---")
        for g in grievances:
            anon = "[ANON]" if g.get('is_anonymous') else ""
            priority = f"[{g.get('priority', 'normal').upper()}]" if g.get('priority') != 'normal' else ""

            print(f"\n#{g.get('grievance_id')} {priority} {anon}")
            print(f"   Category: {g.get('category')} | Status: {g.get('status')}")
            print(f"   Filed: {g.get('filed_date')}")
            if not g.get('is_anonymous'):
                print(f"   Complainant: {g.get('complainant_id')}")
            if g.get('assigned_to'):
                print(f"   Assigned: {g.get('assigned_to')}")

    input("\nPress Enter to continue...")


def _manage_grievance() -> None:
    """Manage a grievance."""
    grievance_id = input("\nEnter Grievance ID: ").strip()

    try:
        grievance_id = int(grievance_id)
    except ValueError:
        print("Invalid ID.")
        return

    grievance = GrievanceManager.get_grievance(grievance_id)
    if not grievance:
        print("Grievance not found.")
        input("Press Enter to continue...")
        return

    print(f"\n--- Grievance #{grievance_id} ---")
    print(f"Category: {grievance.get('category')}")
    print(f"Status: {grievance.get('status')}")
    print(f"Description: {grievance.get('description')[:100]}...")

    print("\nActions:")
    print("  1. Assign Handler")
    print("  2. Update Status")
    print("  3. Set Priority")
    print("  4. Add Action/Note")
    print("  5. Resolve Grievance")
    print("  6. Escalate")
    print("  0. Cancel")

    action = input("\nChoice: ").strip()

    if action == '1':
        handler_id = input("Handler User ID: ").strip()
        GrievanceManager.update_grievance(grievance_id, assigned_to=handler_id)
        GrievanceManager.create_action(
            grievance_id, 'assigned',
            details=f"Assigned to {handler_id}"
        )
        print("Handler assigned.")

    elif action == '2':
        print("Statuses: open, investigating, pending_response, resolved, closed")
        new_status = input("New Status: ").strip()
        GrievanceManager.update_grievance(grievance_id, status=new_status)
        GrievanceManager.create_action(
            grievance_id, 'status_change',
            details=f"Status changed to {new_status}"
        )
        print("Status updated.")

    elif action == '3':
        print("Priorities: low, normal, high, urgent")
        priority = input("Priority: ").strip()
        GrievanceManager.update_grievance(grievance_id, priority=priority)
        print("Priority updated.")

    elif action == '4':
        action_type = input("Action Type (note, investigation, communication): ").strip() or 'note'
        details = input("Details: ").strip()
        taken_by = input("Your User ID: ").strip()
        GrievanceManager.create_action(
            grievance_id, action_type,
            details=details, taken_by=taken_by
        )
        print("Action recorded.")

    elif action == '5':
        resolution = input("Resolution Details: ").strip()
        if resolution:
            GrievanceManager.resolve_grievance(grievance_id, resolution)
            print("Grievance resolved.")

    elif action == '6':
        reason = input("Escalation Reason: ").strip()
        escalated_by = input("Your User ID: ").strip()
        GrievanceManager.escalate_grievance(grievance_id, reason, escalated_by)
        print("Grievance escalated.")

    input("\nPress Enter to continue...")


def _schedule_meeting() -> None:
    """Schedule a grievance meeting."""
    grievance_id = input("\nGrievance ID: ").strip()

    try:
        grievance_id = int(grievance_id)
    except ValueError:
        print("Invalid ID.")
        return

    print("\nMeeting Types: hearing, mediation, follow_up, review")
    meeting_type = input("Meeting Type: ").strip() or 'hearing'
    scheduled_date = input("Date (YYYY-MM-DD): ").strip()
    scheduled_time = input("Time (HH:MM): ").strip()
    location = input("Location: ").strip()
    attendees = input("Attendees (comma-separated user IDs): ").strip()
    notes = input("Meeting Notes/Agenda: ").strip()

    try:
        meeting_id = GrievanceManager.create_meeting(
            grievance_id,
            meeting_type=meeting_type,
            scheduled_date=scheduled_date,
            scheduled_time=scheduled_time,
            location=location,
            attendees=attendees,
            notes=notes
        )
        print(f"\nMeeting scheduled. ID: {meeting_id}")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _search_disciplinary_records() -> None:
    """Search disciplinary records."""
    print("\n--- Search Disciplinary Records ---")
    print("Search by:")
    print("  1. User ID")
    print("  2. Offense Type")
    print("  3. Severity")
    print("  4. Date Range")
    print("  5. View All")

    search_choice = input("\nChoice: ").strip()

    records = []
    if search_choice == '1':
        user_id = input("User ID: ").strip()
        records = GrievanceManager.get_user_disciplinary_records(user_id)
    elif search_choice == '2':
        print("Types: misconduct, performance, attendance, policy_violation, harassment, other")
        offense_type = input("Offense Type: ").strip()
        records = GrievanceManager.search_disciplinary_records(offense_type=offense_type)
    elif search_choice == '3':
        print("Severity: minor, moderate, major, severe")
        severity = input("Severity: ").strip()
        records = GrievanceManager.search_disciplinary_records(severity=severity)
    elif search_choice == '4':
        start_date = input("Start Date (YYYY-MM-DD): ").strip()
        end_date = input("End Date (YYYY-MM-DD): ").strip()
        records = GrievanceManager.search_disciplinary_records(
            start_date=start_date, end_date=end_date
        )
    elif search_choice == '5':
        records = GrievanceManager.search_disciplinary_records()
    else:
        print("Invalid choice.")
        return

    if not records:
        print("\nNo records found.")
    else:
        print(f"\n--- {len(records)} Disciplinary Records ---")
        for r in records:
            severity_icon = {
                'minor': '⚪', 'moderate': '🟡', 'major': '🟠', 'severe': '🔴'
            }.get(r.get('severity', ''), '?')

            print(f"\n{severity_icon} Record #{r.get('record_id')} - {r.get('user_id')}")
            print(f"   Offense: {r.get('offense_type')} | Severity: {r.get('severity')}")
            print(f"   Date: {r.get('date_occurred')}")
            print(f"   Description: {r.get('description', '')[:60]}")

    input("\nPress Enter to continue...")


def _create_disciplinary_record() -> None:
    """Create a new disciplinary record."""
    print("\n--- Create Disciplinary Record ---")

    offense_types = ['misconduct', 'performance', 'attendance', 'policy_violation', 'harassment', 'other']
    severities = ['minor', 'moderate', 'major', 'severe']

    try:
        user_id = get_required_input("Employee User ID: ", "Employee User ID")
        offense_type = get_choice_input(
            f"\nOffense Type ({', '.join(offense_types)}): ",
            offense_types, "Offense Type"
        )
        severity = get_choice_input(
            f"\nSeverity ({', '.join(severities)}): ",
            severities, "Severity"
        )
        description = get_required_input("Description of offense: ", "Description")
        date_occurred = get_date_input("Date Occurred (YYYY-MM-DD): ", "Date Occurred")
        reported_by = get_required_input("Reported By (User ID): ", "Reported By")
    except ValidationError as e:
        print(f"Error: {e}")
        input("Press Enter to continue...")
        return

    witnesses = input("Witnesses (comma-separated, optional): ").strip() or None
    evidence_path = input("Evidence File Path (optional): ").strip() or None

    try:
        record_id = GrievanceManager.create_disciplinary_record(
            user_id=user_id,
            offense_type=offense_type,
            severity=severity,
            description=description,
            date_occurred=date_occurred,
            reported_by=reported_by,
            witnesses=witnesses,
            evidence_path=evidence_path
        )
        print(f"\nDisciplinary record created. ID: {record_id}")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _manage_disciplinary_action() -> None:
    """Manage disciplinary actions."""
    record_id = input("\nDisciplinary Record ID: ").strip()

    try:
        record_id = int(record_id)
    except ValueError:
        print("Invalid ID.")
        return

    record = GrievanceManager.get_disciplinary_record(record_id)
    if not record:
        print("Record not found.")
        input("Press Enter to continue...")
        return

    print(f"\n--- Record #{record_id} ---")
    print(f"Employee: {record.get('user_id')}")
    print(f"Offense: {record.get('offense_type')} ({record.get('severity')})")
    print(f"Status: {record.get('status', 'pending')}")

    # Show existing actions
    actions = GrievanceManager.get_disciplinary_actions(record_id)
    if actions:
        print(f"\nExisting Actions ({len(actions)}):")
        for a in actions:
            print(f"  - {a.get('action_type')}: Effective {a.get('effective_date')}")

    print("\nOptions:")
    print("  1. Add Disciplinary Action")
    print("  2. Update Record Status")
    print("  0. Cancel")

    choice = input("\nChoice: ").strip()

    if choice == '1':
        print("\nAction Types: verbal_warning, written_warning, final_warning, ")
        print("              suspension, demotion, termination, training_required")
        action_type = input("Action Type: ").strip()
        effective_date = input("Effective Date (YYYY-MM-DD): ").strip()
        duration = input("Duration (e.g., '3 days', 'permanent', optional): ").strip() or None
        imposed_by = input("Imposed By (User ID): ").strip()
        notes = input("Notes: ").strip()

        # Calculate appeal deadline (usually 10 business days)
        appeal_deadline = input("Appeal Deadline (YYYY-MM-DD, optional): ").strip() or None

        try:
            action_id = GrievanceManager.create_disciplinary_action(
                record_id,
                action_type=action_type,
                effective_date=effective_date,
                duration=duration,
                imposed_by=imposed_by,
                notes=notes,
                appeal_deadline=appeal_deadline
            )
            print(f"\nAction created. ID: {action_id}")
        except Exception as e:
            print(f"\nError: {e}")

    elif choice == '2':
        print("\nStatuses: pending, under_review, action_taken, closed, appealed")
        new_status = input("New Status: ").strip()
        GrievanceManager.update_disciplinary_record(record_id, status=new_status)
        print("Status updated.")

    input("\nPress Enter to continue...")


def _view_appeals() -> None:
    """View disciplinary appeals."""
    appeals = GrievanceManager.get_pending_appeals()

    if not appeals:
        print("\nNo pending appeals.")
    else:
        print(f"\n--- {len(appeals)} Pending Appeals ---")
        for a in appeals:
            print(f"\n  Appeal #{a.get('appeal_id')}")
            print(f"    Action: {a.get('action_type')} for {a.get('user_id')}")
            print(f"    Filed: {a.get('filed_date')}")
            print(f"    Reason: {a.get('appeal_reason', '')[:60]}")

            print("\n    [R]eview, [S]kip?")
            choice = input("    Choice: ").strip().upper()

            if choice == 'R':
                print("\n    Outcomes: upheld, modified, overturned")
                outcome = input("    Decision: ").strip()
                notes = input("    Decision Notes: ").strip()
                decided_by = input("    Your User ID: ").strip()

                GrievanceManager.resolve_appeal(
                    a['appeal_id'],
                    outcome=outcome,
                    decision_notes=notes,
                    decided_by=decided_by
                )
                print("    Appeal resolved.")

    input("\nPress Enter to continue...")


def _grievance_statistics() -> None:
    """View grievance statistics."""
    stats = GrievanceManager.get_grievance_statistics()

    print("\n--- Grievance Statistics ---")
    print(f"Total Open: {stats.get('total_open', 0)}")
    print(f"Total Investigating: {stats.get('total_investigating', 0)}")
    print(f"Resolved This Month: {stats.get('resolved_this_month', 0)}")
    print(f"Average Resolution Time: {stats.get('avg_resolution_days', 'N/A')} days")

    print("\nBy Category:")
    for cat, count in stats.get('by_category', {}).items():
        print(f"  {cat}: {count}")

    print("\nBy Priority:")
    for priority, count in stats.get('by_priority', {}).items():
        print(f"  {priority}: {count}")

    input("\nPress Enter to continue...")


def _disciplinary_statistics() -> None:
    """View disciplinary statistics."""
    stats = GrievanceManager.get_disciplinary_statistics()

    print("\n--- Disciplinary Statistics ---")
    print(f"Total Active Records: {stats.get('total_active', 0)}")
    print(f"Actions This Month: {stats.get('actions_this_month', 0)}")
    print(f"Pending Appeals: {stats.get('pending_appeals', 0)}")

    print("\nBy Offense Type:")
    for offense, count in stats.get('by_offense_type', {}).items():
        print(f"  {offense}: {count}")

    print("\nBy Severity:")
    for severity, count in stats.get('by_severity', {}).items():
        print(f"  {severity}: {count}")

    print("\nBy Action Type:")
    for action, count in stats.get('by_action_type', {}).items():
        print(f"  {action}: {count}")

    input("\nPress Enter to continue...")
