from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime
import json


def manage_workflows(auth):
    """Manage automated workflows"""
    print("\nWorkflow Management")
    print("==================")
    print("1. View workflows")
    print("2. Create new workflow")
    print("3. Edit workflow")
    print("4. Activate/Deactivate workflow")
    print("5. Return to system management")

    choice = input("\nEnter your choice: ").strip()

    if choice == '1':
        view_workflows()
    elif choice == '2':
        create_workflow(auth)
    elif choice == '3':
        edit_workflow(auth)
    elif choice == '4':
        toggle_workflow(auth)

def view_workflows():
    """View existing workflows"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT workflow_id, name, trigger_type, is_active, created_at
    FROM ticket_workflows
    ORDER BY is_active DESC, name
    ''')

    workflows = cursor.fetchall()

    if workflows:
        print("\nWorkflows:")
        print("=" * 80)
        print(f"{'ID':<5} {'Name':<30} {'Trigger':<15} {'Active':<8} {'Created':<20}")
        print("=" * 80)

        for workflow in workflows:
            active = "Yes" if workflow[3] else "No"
            print(f"{workflow[0]:<5} {workflow[1][:28]:<30} {workflow[2]:<15} "
                  f"{active:<8} {workflow[4]:<20}")

        print("=" * 80)
    else:
        print("No workflows found.")

    conn.close()

def create_workflow(auth):
    """Create a new workflow"""
    print("\nCreate New Workflow")
    print("==================")

    name = input("Workflow name: ").strip()
    if not name:
        print("Name is required.")
        return

    description = input("Description: ").strip()

    print("\nTrigger types:")
    print("1. ticket_created")
    print("2. status_changed")
    print("3. reply_added")
    print("4. time_based")

    trigger_map = {
        '1': 'ticket_created',
        '2': 'status_changed',
        '3': 'reply_added',
        '4': 'time_based'
    }

    trigger_choice = input("Select trigger type (1-4): ").strip()
    if trigger_choice not in trigger_map:
        print("Invalid trigger type.")
        return

    trigger_type = trigger_map[trigger_choice]

    # Simple conditions and actions for demo
    conditions = {}
    actions = {}

    if trigger_type == 'ticket_created':
        category = input("Category condition (or press Enter to skip): ").strip()
        if category:
            conditions['category'] = category

    print("\nActions:")
    assign_dept = input("Auto-assign to department (or press Enter to skip): ").strip()
    if assign_dept:
        actions['assign_to_department'] = assign_dept

    set_priority = input("Set priority (low/medium/high, or press Enter to skip): ").strip()
    if set_priority in ['low', 'medium', 'high']:
        actions['set_priority'] = set_priority

    # Save workflow
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        cursor.execute('''
        INSERT INTO ticket_workflows
        (name, description, trigger_type, trigger_conditions, actions, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, description, trigger_type, json.dumps(conditions),
              json.dumps(actions), auth.current_user['id'], now))

        conn.commit()
        workflow_id = cursor.lastrowid

        print(f"\nWorkflow #{workflow_id} created successfully!")

    except sqlite3.Error as e:
        print(f"Error creating workflow: {e}")
    finally:
        conn.close()

def edit_workflow(auth):
    """Edit an existing workflow"""
    view_workflows()

    workflow_id = input("\nEnter workflow ID to edit: ").strip()

    try:
        workflow_id = int(workflow_id)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT * FROM ticket_workflows WHERE workflow_id = ?
        ''', (workflow_id,))

        workflow = cursor.fetchone()
        if not workflow:
            print("Workflow not found.")
            conn.close()
            return

        print(f"\nEditing Workflow: {workflow[1]}")

        new_name = input(f"New name (current: {workflow[1]}): ").strip()
        new_description = input(f"New description (current: {workflow[2]}): ").strip()

        updates = []
        params = []

        if new_name:
            updates.append("name = ?")
            params.append(new_name)

        if new_description:
            updates.append("description = ?")
            params.append(new_description)

        if updates:
            params.append(workflow_id)
            cursor.execute(
                'UPDATE ticket_workflows SET ' + ", ".join(updates) + ' WHERE workflow_id = ?',
                params)

            conn.commit()
            print("Workflow updated successfully!")
        else:
            print("No changes made.")

        conn.close()

    except (ValueError, sqlite3.Error) as e:
        print(f"Error editing workflow: {e}")

def toggle_workflow(auth):
    """Activate or deactivate a workflow"""
    view_workflows()

    workflow_id = input("\nEnter workflow ID to toggle: ").strip()

    try:
        workflow_id = int(workflow_id)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT name, is_active FROM ticket_workflows WHERE workflow_id = ?
        ''', (workflow_id,))

        result = cursor.fetchone()
        if not result:
            print("Workflow not found.")
            conn.close()
            return

        name, is_active = result
        new_status = not is_active

        cursor.execute('''
        UPDATE ticket_workflows SET is_active = ? WHERE workflow_id = ?
        ''', (new_status, workflow_id))

        conn.commit()
        conn.close()

        status_text = "activated" if new_status else "deactivated"
        print(f"Workflow '{name}' has been {status_text}.")

    except (ValueError, sqlite3.Error) as e:
        print(f"Error toggling workflow: {e}")
