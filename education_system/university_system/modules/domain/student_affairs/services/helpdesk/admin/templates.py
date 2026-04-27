from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime


def manage_ticket_templates(auth):
    """Manage ticket templates"""
    print("\nTicket Template Management")
    print("=========================")
    print("1. View templates")
    print("2. Create new template")
    print("3. Edit template")
    print("4. Activate/Deactivate template")
    print("5. Return to system management")

    choice = input("\nEnter your choice: ").strip()

    if choice == '1':
        view_ticket_templates()
    elif choice == '2':
        create_ticket_template(auth)
    elif choice == '3':
        edit_ticket_template(auth)
    elif choice == '4':
        toggle_ticket_template(auth)

def view_ticket_templates():
    """View existing ticket templates"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT template_id, name, category, default_priority, is_active
    FROM helpdesk_ticket_templates
    ORDER BY category, name
    ''')

    templates = cursor.fetchall()

    if templates:
        print("\nTicket Templates:")
        print("=" * 80)
        print(f"{'ID':<5} {'Name':<25} {'Category':<20} {'Priority':<10} {'Active':<6}")
        print("=" * 80)

        for template in templates:
            active = "Yes" if template[4] else "No"
            print(f"{template[0]:<5} {template[1][:23]:<25} {template[2][:18]:<20} "
                  f"{template[3]:<10} {active:<6}")

        print("=" * 80)
    else:
        print("No templates found.")

    conn.close()

def create_ticket_template(auth):
    """Create a new ticket template"""
    print("\nCreate New Ticket Template")
    print("==========================")

    name = input("Template name: ").strip()
    if not name:
        print("Name is required.")
        return

    description = input("Description: ").strip()
    category = input("Category: ").strip()

    subject_template = input("Subject template (use [FIELD_NAME] for placeholders): ").strip()

    print("\nEnter message template (type 'done' on a new line when finished):")
    message_template = ""
    while True:
        line = input()
        if line.lower() == 'done':
            break
        message_template += line + "\n"

    from education_system.university_system.modules.domain.student_affairs.services.helpdesk.tickets.creation import get_priority_selection, get_impact_selection, get_urgency_selection
    priority = get_priority_selection()
    impact = get_impact_selection()
    urgency = get_urgency_selection()

    # Save template
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        cursor.execute('''
        INSERT INTO helpdesk_ticket_templates
        (name, description, category, subject_template, message_template,
         default_priority, default_impact, default_urgency, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, description, category, subject_template, message_template,
              priority, impact, urgency, auth.current_user['id'], now))

        conn.commit()
        template_id = cursor.lastrowid

        print(f"\nTemplate #{template_id} created successfully!")

    except sqlite3.Error as e:
        print(f"Error creating template: {e}")
    finally:
        conn.close()

def edit_ticket_template(auth):
    """Edit an existing ticket template"""
    view_ticket_templates()

    template_id = input("\nEnter template ID to edit: ").strip()

    try:
        template_id = int(template_id)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT * FROM helpdesk_ticket_templates WHERE template_id = ?
        ''', (template_id,))

        template = cursor.fetchone()
        if not template:
            print("Template not found.")
            conn.close()
            return

        print(f"\nEditing Template: {template[1]}")

        new_name = input(f"New name (current: {template[1]}): ").strip()
        new_description = input(f"New description (current: {template[2]}): ").strip()

        updates = []
        params = []

        if new_name:
            updates.append("name = ?")
            params.append(new_name)

        if new_description:
            updates.append("description = ?")
            params.append(new_description)

        if updates:
            params.append(template_id)
            cursor.execute(
                'UPDATE helpdesk_ticket_templates SET ' + ", ".join(updates) + ' WHERE template_id = ?',
                params)

            conn.commit()
            print("Template updated successfully!")
        else:
            print("No changes made.")

        conn.close()

    except (ValueError, sqlite3.Error) as e:
        print(f"Error editing template: {e}")

def toggle_ticket_template(auth):
    """Activate or deactivate a ticket template"""
    view_ticket_templates()

    template_id = input("\nEnter template ID to toggle: ").strip()

    try:
        template_id = int(template_id)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT name, is_active FROM helpdesk_ticket_templates WHERE template_id = ?
        ''', (template_id,))

        result = cursor.fetchone()
        if not result:
            print("Template not found.")
            conn.close()
            return

        name, is_active = result
        new_status = not is_active

        cursor.execute('''
        UPDATE helpdesk_ticket_templates SET is_active = ? WHERE template_id = ?
        ''', (new_status, template_id))

        conn.commit()
        conn.close()

        status_text = "activated" if new_status else "deactivated"
        print(f"Template '{name}' has been {status_text}.")

    except (ValueError, sqlite3.Error) as e:
        print(f"Error toggling template: {e}")
