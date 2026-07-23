from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime


def manage_departments(auth):
    """Manage departments"""
    print("\nDepartment Management")
    print("====================")
    print("1. View departments")
    print("2. Create new department")
    print("3. Edit department")
    print("4. Activate/Deactivate department")
    print("5. Return to system management")

    choice = input("\nEnter your choice: ").strip()

    if choice == '1':
        view_departments()
    elif choice == '2':
        create_department(auth)
    elif choice == '3':
        edit_department(auth)
    elif choice == '4':
        toggle_department(auth)

def view_departments():
    """View existing departments"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT d.dept_id, d.name, d.email, u.username as manager, d.is_active
    FROM departments d
    LEFT JOIN users u ON d.manager_id = u.id
    ORDER BY d.name
    ''')

    departments = cursor.fetchall()

    if departments:
        print("\nDepartments:")
        print("=" * 80)
        print(f"{'ID':<5} {'Name':<20} {'Email':<25} {'Manager':<15} {'Active':<6}")
        print("=" * 80)

        for dept in departments:
            manager = dept[3] or 'None'
            active = "Yes" if dept[4] else "No"
            print(f"{dept[0]:<5} {dept[1][:18]:<20} {dept[2][:23]:<25} "
                  f"{manager[:13]:<15} {active:<6}")

        print("=" * 80)
    else:
        print("No departments found.")

    conn.close()

def create_department(auth):
    """Create a new department"""
    print("\nCreate New Department")
    print("====================")

    name = input("Department name: ").strip()
    if not name:
        print("Name is required.")
        return

    description = input("Description: ").strip()
    email = input("Department email: ").strip()

    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        cursor.execute('''
        INSERT INTO departments (name, description, email, created_at)
        VALUES (?, ?, ?, ?)
        ''', (name, description, email, now))

        conn.commit()
        dept_id = cursor.lastrowid

        print(f"\nDepartment #{dept_id} created successfully!")

    except sqlite3.Error as e:
        print(f"Error creating department: {e}")
    finally:
        conn.close()

def edit_department(auth):
    """Edit an existing department"""
    view_departments()

    dept_id = input("\nEnter department ID to edit: ").strip()

    try:
        dept_id = int(dept_id)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT * FROM departments WHERE dept_id = ?
        ''', (dept_id,))

        dept = cursor.fetchone()
        if not dept:
            print("Department not found.")
            conn.close()
            return

        print(f"\nEditing Department: {dept[1]}")

        new_name = input(f"New name (current: {dept[1]}): ").strip()
        new_email = input(f"New email (current: {dept[3]}): ").strip()

        updates = []
        params = []

        if new_name:
            updates.append("name = ?")
            params.append(new_name)

        if new_email:
            updates.append("email = ?")
            params.append(new_email)

        if updates:
            params.append(dept_id)
            cursor.execute(
                'UPDATE departments SET ' + ", ".join(updates) + ' WHERE dept_id = ?',
                params)

            conn.commit()
            print("Department updated successfully!")
        else:
            print("No changes made.")

        conn.close()

    except (ValueError, sqlite3.Error) as e:
        print(f"Error editing department: {e}")

def toggle_department(auth):
    """Activate or deactivate a department"""
    view_departments()

    dept_id = input("\nEnter department ID to toggle: ").strip()

    try:
        dept_id = int(dept_id)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT name, is_active FROM departments WHERE dept_id = ?
        ''', (dept_id,))

        result = cursor.fetchone()
        if not result:
            print("Department not found.")
            conn.close()
            return

        name, is_active = result
        new_status = not is_active

        cursor.execute('''
        UPDATE departments SET is_active = ? WHERE dept_id = ?
        ''', (new_status, dept_id))

        conn.commit()
        conn.close()

        status_text = "activated" if new_status else "deactivated"
        print(f"Department '{name}' has been {status_text}.")

    except (ValueError, sqlite3.Error) as e:
        print(f"Error toggling department: {e}")
