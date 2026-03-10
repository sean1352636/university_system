"""
Exit Menu - Exit management and turnover analytics CLI.
"""

from datetime import datetime
from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager
from education_system.university_system.modules.domain.staff_hr.cli.validators import (
    validate_date, validate_required, validate_choice, validate_integer,
    validate_rating, get_date_input, get_choice_input, get_required_input,
    get_integer_input, get_rating_input, get_confirmation, ValidationError
)


def display_exit_menu(user_id: str, is_admin: bool = False) -> None:
    """Display exit management menu."""
    while True:
        print("\n" + "=" * 60)
        print("EXIT MANAGEMENT & TURNOVER ANALYTICS")
        print("=" * 60)

        print("\n--- My Exit Process ---")
        print("  1. View My Exit Checklist")
        print("  2. Complete Checklist Item")

        if is_admin:
            print("\n--- Exit Administration ---")
            print("  3. Initiate Exit Process")
            print("  4. Search Exit Records")
            print("  5. Manage Exit Checklist")
            print("  6. Schedule Exit Interview")
            print("  7. Conduct Exit Interview")

            print("\n--- Knowledge Transfer ---")
            print("  8. View Knowledge Transfer Items")
            print("  9. Create Knowledge Transfer")

            print("\n--- Analytics & Reports ---")
            print(" 10. Turnover Analytics")
            print(" 11. Exit Reasons Summary")
            print(" 12. Department Turnover Report")

            print("\n--- Templates ---")
            print(" 13. Manage Checklist Templates")

        print("\n  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _view_my_checklist(user_id)
        elif choice == '2':
            _complete_checklist_item(user_id)
        elif choice == '3' and is_admin:
            _initiate_exit()
        elif choice == '4' and is_admin:
            _search_exit_records()
        elif choice == '5' and is_admin:
            _manage_checklist()
        elif choice == '6' and is_admin:
            _schedule_interview()
        elif choice == '7' and is_admin:
            _conduct_interview()
        elif choice == '8' and is_admin:
            _view_knowledge_transfer()
        elif choice == '9' and is_admin:
            _create_knowledge_transfer()
        elif choice == '10' and is_admin:
            _turnover_analytics()
        elif choice == '11' and is_admin:
            _exit_reasons_summary()
        elif choice == '12' and is_admin:
            _department_turnover_report()
        elif choice == '13' and is_admin:
            _manage_templates()
        else:
            print("Invalid choice.")


def _view_my_checklist(user_id: str) -> None:
    """View user's exit checklist."""
    items = ExitManager.get_user_checklist(user_id)

    if not items:
        print("\nNo exit checklist found for you.")
        print("(This is only available during your exit process)")
        input("Press Enter to continue...")
        return

    completed = sum(1 for i in items if i.get('completed'))
    total = len(items)

    print(f"\n--- Exit Checklist ({completed}/{total} completed) ---")

    for item in items:
        status = "✓" if item.get('completed') else "○"
        required = "[Required]" if item.get('is_required') else ""

        print(f"\n{status} [{item.get('checklist_id')}] {item.get('task_name')} {required}")
        if item.get('description'):
            print(f"   {item.get('description')[:60]}")
        if item.get('assigned_to'):
            print(f"   Assigned to: {item.get('assigned_to')}")
        if item.get('due_date'):
            print(f"   Due: {item.get('due_date')}")
        if item.get('completed'):
            print(f"   Completed: {item.get('completed_date')} by {item.get('completed_by')}")

    input("\nPress Enter to continue...")


def _complete_checklist_item(user_id: str) -> None:
    """Complete a checklist item."""
    items = ExitManager.get_user_checklist(user_id)
    pending = [i for i in items if not i.get('completed')]

    if not pending:
        print("\nNo pending checklist items.")
        input("Press Enter to continue...")
        return

    print("\n--- Pending Items ---")
    for item in pending:
        print(f"  [{item.get('checklist_id')}] {item.get('task_name')}")

    item_id = input("\nEnter Item ID to complete: ").strip()

    try:
        item_id = int(item_id)
    except ValueError:
        print("Invalid ID.")
        return

    notes = input("Completion Notes (optional): ").strip()

    ExitManager.complete_checklist_item(item_id, user_id, notes)
    print("Item marked as completed.")

    input("\nPress Enter to continue...")


def _initiate_exit() -> None:
    """Initiate exit process for an employee."""
    print("\n--- Initiate Exit Process ---")

    try:
        user_id = get_required_input("Employee User ID: ", "Employee User ID")
    except ValidationError as e:
        print(f"Error: {e}")
        return

    print("\nExit Types:")
    print("  1. Resignation")
    print("  2. Retirement")
    print("  3. Termination")
    print("  4. End of Contract")
    print("  5. Redundancy")
    print("  6. Other")

    exit_type_map = {
        '1': 'resignation', '2': 'retirement', '3': 'termination',
        '4': 'end_of_contract', '5': 'redundancy', '6': 'other'
    }

    try:
        type_choice = get_choice_input(
            "\nExit Type (1-6): ",
            ['1', '2', '3', '4', '5', '6'], "Exit Type"
        )
        exit_type = exit_type_map.get(type_choice, 'other')

        last_working_day = get_date_input("Last Working Day (YYYY-MM-DD): ", "Last Working Day")
        reason = get_required_input("Reason for Leaving: ", "Reason")
        department = get_required_input("Department: ", "Department")
        manager_id = get_required_input("Manager User ID: ", "Manager User ID")
    except ValidationError as e:
        print(f"Error: {e}")
        input("Press Enter to continue...")
        return

    # Check for template
    templates = ExitManager.get_all_templates()
    template_id = None
    if templates:
        print("\nAvailable Checklist Templates:")
        for t in templates:
            print(f"  [{t['template_id']}] {t['name']} ({t.get('item_count', 0)} items)")
        template_choice = input("Use Template ID (Enter to skip): ").strip()
        if template_choice:
            try:
                template_id = int(template_choice)
            except ValueError:
                pass

    try:
        # Create exit record
        exit_id = ExitManager.initiate_exit(
            user_id=user_id,
            exit_type=exit_type,
            last_working_day=last_working_day,
            reason=reason,
            department=department,
            manager_id=manager_id
        )

        # Apply template if selected
        if template_id:
            ExitManager.apply_template(user_id, template_id)

        print(f"\nExit process initiated. Reference: EXIT-{exit_id}")
        print("Checklist items have been created.")

    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _search_exit_records() -> None:
    """Search exit records."""
    print("\n--- Search Exit Records ---")
    print("Search by:")
    print("  1. User ID")
    print("  2. Exit Type")
    print("  3. Department")
    print("  4. Date Range")
    print("  5. View All Active")
    print("  6. View All")

    search_choice = input("\nChoice: ").strip()

    records = []
    if search_choice == '1':
        user_id = input("User ID: ").strip()
        record = ExitManager.get_exit_record(user_id)
        records = [record] if record else []
    elif search_choice == '2':
        print("Types: resignation, retirement, termination, end_of_contract, redundancy")
        exit_type = input("Exit Type: ").strip()
        records = ExitManager.search_exits(exit_type=exit_type)
    elif search_choice == '3':
        department = input("Department: ").strip()
        records = ExitManager.search_exits(department=department)
    elif search_choice == '4':
        start_date = input("Start Date (YYYY-MM-DD): ").strip()
        end_date = input("End Date (YYYY-MM-DD): ").strip()
        records = ExitManager.search_exits(start_date=start_date, end_date=end_date)
    elif search_choice == '5':
        records = ExitManager.search_exits(status='in_progress')
    elif search_choice == '6':
        records = ExitManager.search_exits()
    else:
        print("Invalid choice.")
        return

    if not records:
        print("\nNo records found.")
    else:
        print(f"\n--- {len(records)} Exit Records ---")
        for r in records:
            status_icon = {
                'in_progress': '🔄', 'completed': '✓', 'cancelled': '✗'
            }.get(r.get('status', ''), '?')

            print(f"\n{status_icon} {r.get('user_id')}")
            print(f"   Type: {r.get('exit_type')} | Status: {r.get('status')}")
            print(f"   Last Day: {r.get('last_working_day')}")
            print(f"   Department: {r.get('department')}")
            if r.get('reason'):
                print(f"   Reason: {r.get('reason')[:50]}")

    input("\nPress Enter to continue...")


def _manage_checklist() -> None:
    """Manage exit checklist for an employee."""
    user_id = input("\nEmployee User ID: ").strip()

    items = ExitManager.get_user_checklist(user_id)

    if not items:
        print("\nNo checklist found. Create one?")
        if input("Create from template? (yes/no): ").strip().lower() == 'yes':
            templates = ExitManager.get_all_templates()
            for t in templates:
                print(f"  [{t['template_id']}] {t['name']}")
            template_id = input("Template ID: ").strip()
            ExitManager.apply_template(user_id, int(template_id))
            print("Checklist created from template.")
        input("Press Enter to continue...")
        return

    completed = sum(1 for i in items if i.get('completed'))
    print(f"\n--- Checklist for {user_id} ({completed}/{len(items)} complete) ---")

    for item in items:
        status = "✓" if item.get('completed') else "○"
        print(f"  {status} [{item.get('checklist_id')}] {item.get('task_name')}")

    print("\nOptions:")
    print("  1. Add Item")
    print("  2. Mark Item Complete")
    print("  3. Assign Item")
    print("  4. Remove Item")
    print("  0. Return")

    choice = input("\nChoice: ").strip()

    if choice == '1':
        task_name = input("Task Name: ").strip()
        description = input("Description: ").strip()
        category = input("Category (it, hr, finance, facilities, other): ").strip()
        assigned_to = input("Assign To (User ID, optional): ").strip() or None
        due_date = input("Due Date (YYYY-MM-DD, optional): ").strip() or None
        is_required = input("Required? (yes/no): ").strip().lower() == 'yes'

        ExitManager.add_checklist_item(
            user_id,
            task_name=task_name,
            description=description,
            category=category,
            assigned_to=assigned_to,
            due_date=due_date,
            is_required=is_required
        )
        print("Item added.")

    elif choice == '2':
        item_id = input("Item ID: ").strip()
        completed_by = input("Completed By (User ID): ").strip()
        ExitManager.complete_checklist_item(int(item_id), completed_by)
        print("Item completed.")

    elif choice == '3':
        item_id = input("Item ID: ").strip()
        assigned_to = input("Assign To (User ID): ").strip()
        ExitManager.assign_checklist_item(int(item_id), assigned_to)
        print("Item assigned.")

    elif choice == '4':
        item_id = input("Item ID: ").strip()
        confirm = input("Are you sure? (yes/no): ").strip().lower()
        if confirm == 'yes':
            ExitManager.remove_checklist_item(int(item_id))
            print("Item removed.")

    input("\nPress Enter to continue...")


def _schedule_interview() -> None:
    """Schedule an exit interview."""
    print("\n--- Schedule Exit Interview ---")

    try:
        user_id = get_required_input("Employee User ID: ", "Employee User ID")
        interviewer_id = get_required_input("Interviewer User ID: ", "Interviewer User ID")
        interview_date = get_date_input("Interview Date (YYYY-MM-DD): ", "Interview Date")
    except ValidationError as e:
        print(f"Error: {e}")
        input("Press Enter to continue...")
        return

    interview_time = input("Interview Time (HH:MM): ").strip()
    location = input("Location (or 'virtual'): ").strip() or 'virtual'

    try:
        interview_id = ExitManager.schedule_interview(
            user_id=user_id,
            interviewer_id=interviewer_id,
            interview_date=interview_date,
            interview_time=interview_time,
            location=location
        )
        print(f"\nInterview scheduled. ID: {interview_id}")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _conduct_interview() -> None:
    """Conduct/record an exit interview."""
    print("\n--- Conduct Exit Interview ---")

    # Find scheduled interviews
    pending = ExitManager.get_pending_interviews()

    if pending:
        print("\nScheduled Interviews:")
        for i in pending:
            print(f"  [{i.get('interview_id')}] {i.get('user_id')} - {i.get('interview_date')}")

    interview_id = input("\nInterview ID (or 'new' for walk-in): ").strip()

    if interview_id.lower() == 'new':
        user_id = input("Employee User ID: ").strip()
        interviewer_id = input("Your User ID: ").strip()
    else:
        interview = ExitManager.get_interview(int(interview_id))
        if not interview:
            print("Interview not found.")
            return
        user_id = interview.get('user_id')
        interviewer_id = interview.get('interviewer_id')

    print("\n--- Exit Interview Questions ---")

    print("\nPrimary Reason for Leaving:")
    print("  1. Better opportunity elsewhere")
    print("  2. Career advancement")
    print("  3. Compensation")
    print("  4. Work-life balance")
    print("  5. Management issues")
    print("  6. Company culture")
    print("  7. Relocation")
    print("  8. Personal reasons")
    print("  9. Retirement")
    print(" 10. Other")

    reason_map = {
        '1': 'better_opportunity', '2': 'career_advancement',
        '3': 'compensation', '4': 'work_life_balance',
        '5': 'management_issues', '6': 'company_culture',
        '7': 'relocation', '8': 'personal', '9': 'retirement', '10': 'other'
    }
    reason_choice = input("\nPrimary Reason: ").strip()
    reason_for_leaving = reason_map.get(reason_choice, 'other')

    print("\nRating Scale: 1 (Poor) to 5 (Excellent)")

    job_satisfaction = input("Job Satisfaction (1-5): ").strip()
    management_rating = input("Management/Supervisor Rating (1-5): ").strip()
    work_environment = input("Work Environment Rating (1-5): ").strip()
    growth_opportunities = input("Growth Opportunities Rating (1-5): ").strip()

    would_recommend = input("\nWould recommend as employer? (yes/no): ").strip().lower() == 'yes'
    would_return = input("Would consider returning? (yes/no): ").strip().lower() == 'yes'

    print("\nOpen Feedback:")
    feedback_positive = input("What did you like most about working here?\n").strip()
    feedback_negative = input("\nWhat could be improved?\n").strip()
    suggestions = input("\nAny suggestions for the organization?\n").strip()

    try:
        if interview_id.lower() == 'new':
            result_id = ExitManager.create_interview(
                user_id=user_id,
                interviewer_id=interviewer_id,
                interview_date=datetime.now().strftime('%Y-%m-%d'),
                reason_for_leaving=reason_for_leaving,
                job_satisfaction=int(job_satisfaction) if job_satisfaction else None,
                management_rating=int(management_rating) if management_rating else None,
                work_environment_rating=int(work_environment) if work_environment else None,
                growth_opportunities_rating=int(growth_opportunities) if growth_opportunities else None,
                would_recommend=would_recommend,
                would_return=would_return,
                feedback_positive=feedback_positive,
                feedback_negative=feedback_negative,
                suggestions=suggestions
            )
        else:
            result_id = ExitManager.complete_interview(
                int(interview_id),
                reason_for_leaving=reason_for_leaving,
                job_satisfaction=int(job_satisfaction) if job_satisfaction else None,
                management_rating=int(management_rating) if management_rating else None,
                work_environment_rating=int(work_environment) if work_environment else None,
                growth_opportunities_rating=int(growth_opportunities) if growth_opportunities else None,
                would_recommend=would_recommend,
                would_return=would_return,
                feedback_positive=feedback_positive,
                feedback_negative=feedback_negative,
                suggestions=suggestions
            )

        print(f"\nExit interview recorded. ID: {result_id}")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _view_knowledge_transfer() -> None:
    """View knowledge transfer items."""
    print("\n--- Knowledge Transfer Items ---")

    user_id = input("Departing Employee User ID (or Enter for all): ").strip() or None

    items = ExitManager.get_knowledge_transfers(user_id)

    if not items:
        print("\nNo knowledge transfer items found.")
    else:
        print(f"\n{len(items)} Knowledge Transfer Items:")
        for item in items:
            status_icon = "✓" if item.get('status') == 'completed' else "○"
            print(f"\n{status_icon} [{item.get('transfer_id')}] {item.get('topic')}")
            print(f"   From: {item.get('from_user_id')} → To: {item.get('to_user_id')}")
            print(f"   Priority: {item.get('priority')} | Status: {item.get('status')}")
            if item.get('due_date'):
                print(f"   Due: {item.get('due_date')}")

    input("\nPress Enter to continue...")


def _create_knowledge_transfer() -> None:
    """Create a knowledge transfer item."""
    print("\n--- Create Knowledge Transfer ---")

    priorities = ['low', 'medium', 'high', 'critical']

    try:
        from_user_id = get_required_input("Departing Employee User ID: ", "Departing Employee")
        to_user_id = get_required_input("Receiving Employee User ID: ", "Receiving Employee")
        topic = get_required_input("Topic/Area of Knowledge: ", "Topic")
        description = get_required_input("Description: ", "Description")
        priority = get_choice_input(
            f"\nPriority ({', '.join(priorities)}): ",
            priorities, "Priority", allow_empty=True
        ) or 'medium'
        due_date = get_date_input(
            "Due Date (YYYY-MM-DD, optional): ", "Due Date", allow_empty=True
        )
    except ValidationError as e:
        print(f"Error: {e}")
        input("Press Enter to continue...")
        return

    documentation_path = input("Documentation Path (optional): ").strip() or None

    try:
        transfer_id = ExitManager.create_knowledge_transfer(
            departing_user_id=from_user_id,
            receiving_user_id=to_user_id,
            topic=topic,
            description=description,
            priority=priority,
            scheduled_date=due_date
        )
        print(f"\nKnowledge transfer created. ID: {transfer_id}")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _turnover_analytics() -> None:
    """View turnover analytics."""
    print("\n--- Turnover Analytics ---")

    year = input("Year (Enter for current): ").strip()
    if not year:
        year = datetime.now().year

    analytics = ExitManager.get_turnover_analytics(int(year))

    print(f"\n=== Turnover Report for {year} ===")
    print(f"\nTotal Exits: {analytics.get('total_exits', 0)}")
    print(f"Voluntary Exits: {analytics.get('voluntary_exits', 0)}")
    print(f"Involuntary Exits: {analytics.get('involuntary_exits', 0)}")
    print(f"Overall Turnover Rate: {analytics.get('turnover_rate', 0):.1f}%")

    print("\n--- Monthly Breakdown ---")
    for month, count in analytics.get('monthly_exits', {}).items():
        print(f"  {month}: {count} exits")

    print("\n--- By Department ---")
    for dept, data in analytics.get('by_department', {}).items():
        print(f"  {dept}: {data.get('exits', 0)} exits ({data.get('rate', 0):.1f}% rate)")

    print("\n--- By Exit Type ---")
    for exit_type, count in analytics.get('by_type', {}).items():
        print(f"  {exit_type}: {count}")

    print("\n--- Average Tenure ---")
    print(f"  All Exits: {analytics.get('avg_tenure_months', 0):.1f} months")
    print(f"  Voluntary: {analytics.get('avg_tenure_voluntary', 0):.1f} months")

    input("\nPress Enter to continue...")


def _exit_reasons_summary() -> None:
    """View exit reasons summary."""
    print("\n--- Exit Reasons Summary ---")

    period = input("Period (e.g., '2024', '2024-Q1', or Enter for all): ").strip() or None

    summary = ExitManager.get_exit_reasons_summary(period)

    print(f"\n=== Exit Reasons Analysis ===")
    print(f"Total Responses: {summary.get('total_interviews', 0)}")

    print("\n--- Primary Reasons ---")
    for reason, count in summary.get('reasons', {}).items():
        pct = (count / summary.get('total_interviews', 1)) * 100
        bar = "█" * int(pct / 5)
        print(f"  {reason:25} {count:3} ({pct:5.1f}%) {bar}")

    print("\n--- Average Ratings ---")
    ratings = summary.get('avg_ratings', {})
    print(f"  Job Satisfaction:      {ratings.get('job_satisfaction', 'N/A'):.1f}/5")
    print(f"  Management:            {ratings.get('management', 'N/A'):.1f}/5")
    print(f"  Work Environment:      {ratings.get('work_environment', 'N/A'):.1f}/5")
    print(f"  Growth Opportunities:  {ratings.get('growth', 'N/A'):.1f}/5")

    print("\n--- Would Recommend ---")
    recommend = summary.get('would_recommend', {})
    print(f"  Yes: {recommend.get('yes', 0)} | No: {recommend.get('no', 0)}")

    print("\n--- Would Return ---")
    return_stat = summary.get('would_return', {})
    print(f"  Yes: {return_stat.get('yes', 0)} | No: {return_stat.get('no', 0)}")

    input("\nPress Enter to continue...")


def _department_turnover_report() -> None:
    """View department turnover report."""
    department = input("\nDepartment (or Enter for all): ").strip() or None

    report = ExitManager.get_department_turnover_report(department)

    print("\n=== Department Turnover Report ===")

    for dept_name, data in report.items():
        print(f"\n--- {dept_name} ---")
        print(f"  Current Headcount: {data.get('headcount', 'N/A')}")
        print(f"  Exits (12 months): {data.get('exits_12m', 0)}")
        print(f"  Turnover Rate: {data.get('turnover_rate', 0):.1f}%")
        print(f"  Avg Tenure: {data.get('avg_tenure', 0):.1f} months")

        if data.get('top_reasons'):
            print("  Top Exit Reasons:")
            for reason in data['top_reasons'][:3]:
                print(f"    - {reason}")

    input("\nPress Enter to continue...")


def _manage_templates() -> None:
    """Manage exit checklist templates."""
    while True:
        print("\n--- Checklist Templates ---")

        templates = ExitManager.get_all_templates()

        if templates:
            print("\nExisting Templates:")
            for t in templates:
                status = "Active" if t.get('is_active') else "Inactive"
                print(f"  [{t['template_id']}] {t['name']} ({status})")
                print(f"      {t.get('description', '')[:50]}")
                print(f"      Items: {t.get('item_count', 0)}")

        print("\nOptions:")
        print("  1. Create Template")
        print("  2. View/Edit Template Items")
        print("  3. Toggle Template Active")
        print("  4. Delete Template")
        print("  0. Return")

        choice = input("\nChoice: ").strip()

        if choice == '0':
            break

        elif choice == '1':
            name = input("Template Name: ").strip()
            description = input("Description: ").strip()
            exit_type = input("For Exit Type (or 'all'): ").strip() or 'all'

            try:
                template_id = ExitManager.create_template(
                    name=name,
                    description=description,
                    exit_type=exit_type
                )
                print(f"Template created. ID: {template_id}")

                # Add items
                print("\nAdd items to template (Enter blank to finish):")
                order = 1
                while True:
                    task_name = input(f"  Item {order} name: ").strip()
                    if not task_name:
                        break

                    category = input("    Category (it, hr, finance, facilities): ").strip() or 'other'
                    is_required = input("    Required? (yes/no): ").strip().lower() == 'yes'

                    ExitManager.add_template_item(
                        template_id,
                        task_name=task_name,
                        category=category,
                        is_required=is_required,
                        order=order
                    )
                    order += 1
                    print("    Item added.")

            except Exception as e:
                print(f"Error: {e}")

        elif choice == '2':
            template_id = input("Template ID: ").strip()
            items = ExitManager.get_template_items(int(template_id))

            if not items:
                print("No items in this template.")
            else:
                print(f"\nTemplate Items ({len(items)}):")
                for item in items:
                    req = "[Required]" if item.get('is_required') else ""
                    print(f"  {item.get('order')}. {item.get('task_name')} ({item.get('category')}) {req}")

            add_more = input("\nAdd more items? (yes/no): ").strip().lower()
            if add_more == 'yes':
                task_name = input("Task Name: ").strip()
                category = input("Category: ").strip()
                is_required = input("Required? (yes/no): ").strip().lower() == 'yes'

                ExitManager.add_template_item(
                    int(template_id),
                    task_name=task_name,
                    category=category,
                    is_required=is_required
                )
                print("Item added.")

        elif choice == '3':
            template_id = input("Template ID: ").strip()
            for t in templates:
                if t['template_id'] == int(template_id):
                    new_status = not t.get('is_active', True)
                    ExitManager.update_template(int(template_id), is_active=new_status)
                    print(f"Template {'activated' if new_status else 'deactivated'}.")
                    break

        elif choice == '4':
            template_id = input("Template ID to delete: ").strip()
            confirm = input("Are you sure? This cannot be undone. (yes/no): ").strip().lower()
            if confirm == 'yes':
                ExitManager.delete_template(int(template_id))
                print("Template deleted.")

    input("Press Enter to continue...")
