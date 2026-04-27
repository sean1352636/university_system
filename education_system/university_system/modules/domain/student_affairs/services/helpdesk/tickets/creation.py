from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.infrastructure.email.email_manager import (
    send_ticket_notification,
    send_sla_alert,
)
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
    FROM helpdesk_ticket_templates
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
    SELECT * FROM helpdesk_ticket_templates WHERE template_id = ?
    ''', (template_id,))
    template = cursor.fetchone()

    if not template:
        print("Template not found.")
        conn.close()
        return

    print(f"\nUsing template: {template[1]}")
    print(f"Description: {template[2]}")

    # Parse form fields if available
    form_fields = {}
    if template[9]:  # form_fields column
        try:
            form_data = json.loads(template[9])
            if 'fields' in form_data:
                print("\nPlease fill in the following information:")
                for field in form_data['fields']:
                    value = get_form_field_value(field)
                    form_fields[field['name']] = value
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse template form data JSON: {e}")

    # Generate subject and message from template
    subject = template[4] or ''  # subject_template
    message = template[5] or ''  # message_template

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
    category = template[3]  # category
    priority = template[6] or 'medium'  # default_priority
    impact = template[7] or 'low'  # default_impact
    urgency = template[8] or 'low'  # default_urgency

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
    conn = get_connection()
    cursor = conn.cursor()

    # Determine SLA and department assignment
    cursor.execute('''
    SELECT sla_id, first_response_hours, resolution_hours
    FROM sla_policies
    WHERE priority = ? AND impact = ? AND urgency = ? AND is_active = 1
    ORDER BY sla_id LIMIT 1
    ''', (priority, impact, urgency))

    sla_result = cursor.fetchone()
    due_date = None
    if sla_result:
        resolution_hours = sla_result[2]
        due_date = (datetime.now() + timedelta(hours=resolution_hours)).strftime('%Y-%m-%d %H:%M:%S')

    # Auto-assign to department based on category
    assigned_to = None
    department = None

    category_dept_map = {
        "Technical Support": "IT Support",
        "Academic Inquiry": "Academic Affairs",
        "Financial Services": "Financial Services",
        "Account Access": "IT Support"
    }

    if category in category_dept_map:
        department = category_dept_map[category]

        # Find available staff in the department
        cursor.execute('''
        SELECT u.id FROM users u
        JOIN departments d ON u.department = d.name
        WHERE d.name = ? AND u.role IN ('staff', 'admin') AND u.is_active = 1
        ORDER BY u.last_login_at DESC LIMIT 1
        ''', (department,))

        dept_staff = cursor.fetchone()
        if dept_staff:
            assigned_to = dept_staff[0]

    # Get current time
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Insert ticket into database
    try:
        cursor.execute('''
        INSERT INTO support_tickets
        (user_id, assigned_to, subject, message, category, subcategory, status, priority,
         impact, urgency, source, due_date, department, created_at, updated_at, last_activity_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (auth.current_user['id'], assigned_to, subject, message, category, subcategory,
              'open', priority, impact, urgency, 'web', due_date, department, now, now, now))

        conn.commit()
        ticket_id = cursor.lastrowid

        # Log ticket creation
        from education_system.university_system.modules.domain.student_affairs.services.helpdesk.workflows import log_ticket_action, run_ticket_workflows
        log_ticket_action(ticket_id, auth.current_user['id'], 'created', {}, {
            'subject': subject, 'category': category, 'priority': priority,
            'impact': impact, 'urgency': urgency
        })

        # Handle file attachments
        from education_system.university_system.modules.domain.student_affairs.services.helpdesk.tickets.attachments import handle_file_attachments, suggest_knowledge_base_articles
        handle_file_attachments(ticket_id, None, auth.current_user['id'])

        print(f"\nTicket #{ticket_id} created successfully!")
        print(f"Priority: {priority.upper()}, Impact: {impact.upper()}, Urgency: {urgency.upper()}")
        if due_date:
            print(f"Due date: {due_date}")
        if assigned_to:
            cursor.execute("SELECT username FROM users WHERE id = ?", (assigned_to,))
            assignee = cursor.fetchone()
            if assignee:
                print(f"Assigned to: {assignee[0]}")

        # Run automated workflows
        run_ticket_workflows(ticket_id, 'ticket_created')

        # Send notifications
        try:
            # Notify assigned staff member
            if assigned_to:
                send_ticket_notification(ticket_id, subject, auth.current_user['username'], [(assignee[0],)])

            # Notify department managers
            if department:
                cursor.execute('''
                SELECT u.username FROM users u
                JOIN departments d ON u.id = d.manager_id
                WHERE d.name = ?
                ''', (department,))
                managers = cursor.fetchall()
                if managers:
                    send_ticket_notification(ticket_id, subject, auth.current_user['username'], managers)
        except Exception as e:
            print(f"Note: Could not send email notification: {e}")

        # Suggest knowledge base articles
        suggest_knowledge_base_articles(ticket_id, subject + " " + message)

        # Check for immediate SLA breach (rare but possible)
        if due_date:
            try:
                due_datetime = datetime.strptime(due_date, '%Y-%m-%d %H:%M:%S')
                if datetime.now() > due_datetime:
                    send_sla_alert(ticket_id, alert_type='overdue')
                    print("\u26a0\ufe0f  SLA alert sent - ticket is already overdue")
            except (ValueError, Exception) as e:
                # Skip SLA check if date parsing fails
                logger.debug(f"SLA check failed during ticket creation: {e}")

    except sqlite3.Error as e:
        print(f"Error creating support ticket: {e}")
    finally:
        conn.close()
