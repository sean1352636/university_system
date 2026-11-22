from education_system.systems.university.infrastructure.database.db import get_connection
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)


def create_ticket_enhanced(auth):
    if not auth or not auth.current_user:
        print("You must be logged in to create a support ticket.")
        return

    if not auth.check_permission('create_ticket'):
        print("You don't have permission to create support tickets.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\nCreate New Support Ticket")
    print("=========================")

    # Show available templates
    cursor.execute('''
    SELECT template_id, name, description, category
    FROM ticket_templates
    WHERE is_active = 1
    ORDER BY category, name
    ''')
    templates = cursor.fetchall()

    if templates:
        print("\nAvailable templates:")
        print("0. Create custom ticket")
        for i, template in enumerate(templates, 1):
            print(f"{i}. {template[1]} ({template[3]})")

        template_choice = input("\nSelect template (0 for custom): ").strip()

        try:
            if template_choice != '0':
                template_idx = int(template_choice) - 1
                if 0 <= template_idx < len(templates):
                    return create_ticket_from_template(auth, templates[template_idx][0])
        except ValueError as e:
            logger.debug(f"Invalid template choice input: {e}")

    # Custom ticket creation
    return create_custom_ticket(auth)

def create_ticket_from_template(auth, template_id):
    conn = get_connection()
    cursor = conn.cursor()

    # Get template details
    cursor.execute('''
    SELECT * FROM ticket_templates WHERE template_id = ?
    ''', (template_id,))
    template = cursor.fetchone()

    if not template:
        print("Template not found.")
        conn.close()
        return

    print(f"\nUsing template: {template['name']}")
    print(f"Description: {template['description']}")

    # Parse form fields if available
    form_fields = {}
    if template['form_fields']:
        try:
            form_data = json.loads(template['form_fields'])
            if 'fields' in form_data:
                print("\nPlease fill in the following information:")
                for field in form_data['fields']:
                    value = get_form_field_value(field)
                    form_fields[field['name']] = value
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse template form data JSON: {e}")

    # Generate subject and message from template
    subject = template['subject_template'] or ''
    message = template['message_template'] or ''

    # Replace placeholders with form field values
    for field_name, field_value in form_fields.items():
        placeholder = f'[{field_name.upper()}]'
        subject = subject.replace(placeholder, str(field_value))
        message = message.replace(placeholder, str(field_value))

    # Allow user to edit subject and message
    print(f"\nSubject: {subject}")
    new_subject = input("Edit subject (or press Enter to keep): ").strip()
    if new_subject:
        subject = new_subject

    print(f"\nMessage:\n{message}")
    print("\nEdit message (type 'done' on a new line when finished, or 'keep' to use template):")

    edit_choice = input().strip().lower()
    if edit_choice != 'keep':
        if edit_choice != 'done':
            message = edit_choice + "\n"

        while True:
            line = input()
            if line.lower() == 'done':
                break
            message += line + "\n"

    # Use template defaults
    category = template['category']
    priority = template['priority'] or 'medium'
    impact = template['default_impact'] or 'low'
    urgency = template['default_urgency'] or 'low'

    # Create the ticket
    return create_ticket_with_details(auth, subject, message, category, priority, impact, urgency)

def get_form_field_value(field):
    field_name = field.get('name', '')
    field_type = field.get('type', 'text')
    required = field.get('required', False)
    options = field.get('options', [])

    while True:
        if field_type == 'select' and options:
            print(f"\n{field_name.replace('_', ' ').title()}:")
            for i, option in enumerate(options, 1):
                print(f"{i}. {option}")

            choice = input("Select option: ").strip()
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    return options[idx]
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Please enter a number.")
        else:
            prompt = f"{field_name.replace('_', ' ').title()}: "
            if field_type == 'textarea':
                print(f"\n{field_name.replace('_', ' ').title()} (type 'done' when finished):")
                value = ""
                while True:
                    line = input()
                    if line.lower() == 'done':
                        break
                    value += line + "\n"
                return value.strip()
            else:
                value = input(prompt).strip()

            if value or not required:
                return value
            else:
                print("This field is required.")

def create_custom_ticket(auth):
    # Get ticket information from user
    subject = ""
    while not subject:
        subject = input("Subject: ").strip()
        if not subject:
            print("Error: Subject cannot be empty.")

    # Enhanced categories with subcategories
    print("\nCategories:")
    categories = {
        "1": {"name": "Technical Support", "subcategories": ["Login Issues", "Performance Problems", "Software Bugs", "Hardware Problems"]},
        "2": {"name": "Academic Inquiry", "subcategories": ["Course Information", "Grading Questions", "Academic Records", "Transcript Requests"]},
        "3": {"name": "Financial Services", "subcategories": ["Payment Plans", "Refunds", "Financial Aid", "Billing Inquiries"]},
        "4": {"name": "Account Access", "subcategories": ["Password Reset", "Account Locked", "Permission Issues", "Profile Updates"]},
        "5": {"name": "Other", "subcategories": ["General Inquiry", "Feedback", "Complaint", "Suggestion"]}
    }

    for key, cat in categories.items():
        print(f"{key}. {cat['name']}")

    category_choice = ""
    while category_choice not in categories:
        category_choice = input("Select category (1-5): ").strip()
        if category_choice not in categories:
            print("Error: Invalid category selection.")

    category = categories[category_choice]["name"]

    # Select subcategory
    subcategories = categories[category_choice]["subcategories"]
    print(f"\nSubcategories for {category}:")
    for i, subcat in enumerate(subcategories, 1):
        print(f"{i}. {subcat}")

    subcat_choice = ""
    while True:
        try:
            subcat_choice = int(input("Select subcategory: ").strip())
            if 1 <= subcat_choice <= len(subcategories):
                subcategory = subcategories[subcat_choice - 1]
                break
            else:
                print("Error: Invalid subcategory selection.")
        except ValueError:
            print("Error: Please enter a number.")

    # Get ticket message
    message = ""
    print("\nPlease describe your issue (type 'done' on a new line when finished):")
    while True:
        line = input()
        if line.lower() == 'done':
            break
        message += line + "\n"

    if not message.strip():
        print("Error: Message cannot be empty.")
        return

    # Set priority, impact, and urgency
    priority = get_priority_selection()
    impact = get_impact_selection()
    urgency = get_urgency_selection()

    return create_ticket_with_details(auth, subject, message, category, priority, impact, urgency, subcategory)

def get_priority_selection():
    print("\nPriority:")
    print("1. Low - General inquiries, minor issues")
    print("2. Medium - Standard requests, moderate impact")
    print("3. High - Urgent issues, significant impact")

    priority_map = {"1": "low", "2": "medium", "3": "high"}

    while True:
        choice = input("Select priority (1-3): ").strip()
        if choice in priority_map:
            return priority_map[choice]
        print("Error: Invalid priority selection.")

def get_impact_selection():
    print("\nImpact (how many people are affected):")
    print("1. Low - Individual user")
    print("2. Medium - Department or group")
    print("3. High - Institution-wide")

    impact_map = {"1": "low", "2": "medium", "3": "high"}

    while True:
        choice = input("Select impact (1-3): ").strip()
        if choice in impact_map:
            return impact_map[choice]
        print("Error: Invalid impact selection.")

def get_urgency_selection():
    print("\nUrgency (how quickly this needs to be resolved):")
    print("1. Low - Can wait days/weeks")
    print("2. Medium - Should be resolved within 1-2 days")
    print("3. High - Needs immediate attention")

    urgency_map = {"1": "low", "2": "medium", "3": "high"}

    while True:
        choice = input("Select urgency (1-3): ").strip()
        if choice in urgency_map:
            return urgency_map[choice]
        print("Error: Invalid urgency selection.")

def create_ticket_with_details(auth, subject, message, category, priority, impact, urgency, subcategory=None):
    """CLI: raise the ticket through ``tickets.service`` (routing, tier,
    crisis detection, SLA, assignment and the "ticket received" notices all
    happen there); show the crisis contacts at once when the words call for
    them; then attachments, workflows and self-help suggestions."""
    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.service import (
        submit_helpdesk_ticket,
    )
    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.cli_support import (
        local_user_id, print_crisis, sla_label, tier_badge,
    )
    from education_system.systems.university.domains.student_support.domain.student_support import (
        service,
    )
    try:
        result = submit_helpdesk_ticket(
            auth, subject=subject, description=message, category=category, priority=priority,
            impact=impact, urgency=urgency, subcategory=subcategory, channel='cli')
    except (PermissionError, ValueError) as e:
        print(f"Error creating support ticket: {e}")
        return None
    ticket_id = result['ticket_id']
    print_crisis(result.get('crisis'))

    local_id = local_user_id(auth)
    from education_system.systems.university.domains.student_support.domain.helpdesk.workflows import log_ticket_action, run_ticket_workflows
    if local_id is not None:
        # ticket_audit_log keys on the local users.id
        log_ticket_action(ticket_id, local_id, 'created', {}, {
            'category': category, 'priority': priority, 'impact': impact, 'urgency': urgency
        })

    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.attachments import handle_file_attachments, suggest_knowledge_base_articles
    handle_file_attachments(ticket_id, None, local_id, auth=auth)

    print(f"\nTicket #{ticket_id} created successfully!")
    try:
        ticket = service.get_ticket(auth, ticket_id)
    except (PermissionError, ValueError):
        ticket = None
    if ticket:
        badge = tier_badge(ticket)
        if badge:
            print(f"Confidentiality: {badge} - only the team that handles it can read it.")
        print(f"Priority: {str(ticket.get('priority') or priority).upper()}, "
              f"Impact: {impact.upper()}, Urgency: {urgency.upper()}")
        print(f"SLA: {sla_label(ticket)}")
        if ticket.get('assigned_to'):
            print(f"Assigned to: {ticket['assigned_to']}")

    run_ticket_workflows(ticket_id, 'ticket_created')

    # Self-help from both knowledge bases (not for a crisis: the contacts
    # above are what matters).
    if not result.get('crisis'):
        suggest_knowledge_base_articles(ticket_id, subject + " " + message)
    return ticket_id
