from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime


def manage_organizations(auth):
    """Manage organizations"""
    print("\nOrganization Management")
    print("======================")
    print("1. View organizations")
    print("2. Create new organization")
    print("3. Edit organization")
    print("4. Return to system management")

    choice = input("\nEnter your choice: ").strip()

    if choice == '1':
        view_organizations()
    elif choice == '2':
        create_organization(auth)
    elif choice == '3':
        edit_organization(auth)

def view_organizations():
    """View existing organizations"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT org_id, name, domain, contact_email, is_active
    FROM organizations
    ORDER BY name
    ''')

    organizations = cursor.fetchall()

    if organizations:
        print("\nOrganizations:")
        print("=" * 80)
        print(f"{'ID':<5} {'Name':<25} {'Domain':<20} {'Contact Email':<25} {'Active':<6}")
        print("=" * 80)

        for org in organizations:
            active = "Yes" if org[4] else "No"
            domain = org[2] or ''
            email = org[3] or ''
            print(f"{org[0]:<5} {org[1][:23]:<25} {domain[:18]:<20} "
                  f"{email[:23]:<25} {active:<6}")

        print("=" * 80)
    else:
        print("No organizations found.")

    conn.close()

def create_organization(auth):
    """Create a new organization"""
    print("\nCreate New Organization")
    print("======================")

    name = input("Organization name: ").strip()
    if not name:
        print("Name is required.")
        return

    domain = input("Domain (optional): ").strip()
    contact_email = input("Contact email: ").strip()
    phone = input("Phone (optional): ").strip()
    address = input("Address (optional): ").strip()

    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        cursor.execute('''
        INSERT INTO organizations (name, domain, contact_email, phone, address, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, domain, contact_email, phone, address, now))

        conn.commit()
        org_id = cursor.lastrowid

        print(f"\nOrganization #{org_id} created successfully!")

    except sqlite3.Error as e:
        print(f"Error creating organization: {e}")
    finally:
        conn.close()

def edit_organization(auth):
    """Edit an existing organization"""
    view_organizations()

    org_id = input("\nEnter organization ID to edit: ").strip()

    try:
        org_id = int(org_id)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT * FROM organizations WHERE org_id = ?
        ''', (org_id,))

        org = cursor.fetchone()
        if not org:
            print("Organization not found.")
            conn.close()
            return

        print(f"\nEditing Organization: {org[1]}")

        new_name = input(f"New name (current: {org[1]}): ").strip()
        new_email = input(f"New contact email (current: {org[3]}): ").strip()

        updates = []
        params = []

        if new_name:
            updates.append("name = ?")
            params.append(new_name)

        if new_email:
            updates.append("contact_email = ?")
            params.append(new_email)

        if updates:
            params.append(org_id)
            cursor.execute(
                'UPDATE organizations SET ' + ", ".join(updates) + ' WHERE org_id = ?',
                params)

            conn.commit()
            print("Organization updated successfully!")
        else:
            print("No changes made.")

        conn.close()

    except (ValueError, sqlite3.Error) as e:
        print(f"Error editing organization: {e}")
