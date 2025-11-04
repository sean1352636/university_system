from __future__ import annotations

from datetime import datetime

from university_system.modules.core.services.health_misc.audit import log_audit_event
from university_system.infrastructure.database.data_backup import backup_before_operation
from university_system.infrastructure.database.db import get_connection

def get_user_student_id(auth):
    """Get the current user's student ID"""
    if not auth or not auth.current_user:
        return None

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT student_id FROM users WHERE id = ?
    ''', (auth.current_user['id'],))

    result = cursor.fetchone()
    conn.close()

    if result:
        return result[0]
    return None

def update_emergency_contact(auth):
    if not (auth.check_permission('manage_health_records') or auth.check_permission('update_insurance_info')):
        print("You don't have permission to update emergency contacts.")
        return

    backup_before_operation('update_emergency_contact')

    conn = get_connection()
    cursor = conn.cursor()

    contact_id = input("Enter emergency contact ID to update: ")

    cursor.execute('''
    SELECT ec.id, s.student_id, s.first_name, s.last_name, ec.contact_name,
           ec.relationship, ec.phone_primary, ec.phone_secondary, ec.email,
           ec.address, ec.priority_order, ec.medical_decision_maker
    FROM emergency_contacts ec
    JOIN students s ON ec.student_id = s.student_id
    WHERE ec.id = ?
    ''', (contact_id,))

    contact = cursor.fetchone()

    if not contact:
        print("Error: Emergency contact not found.")
        conn.close()
        return

    ec_id, student_id, first_name, last_name, contact_name, relationship, phone1, phone2, email, address, priority, medical_dm = contact

    print(f"\nCurrent Contact Details:")
    print(f"Student: {first_name} {last_name} (ID: {student_id})")
    print(f"Contact: {contact_name}")
    print(f"Relationship: {relationship}")
    print(f"Primary Phone: {phone1}")
    print(f"Secondary Phone: {phone2}")
    print(f"Email: {email}")
    print(f"Address: {address}")
    print(f"Priority: {priority}")
    print(f"Medical Decision Maker: {'Yes' if medical_dm else 'No'}")

    print("\nEnter new values (press Enter to keep current):")

    new_contact_name = input(f"Contact name [{contact_name}]: ").strip()
    if not new_contact_name:
        new_contact_name = contact_name

    new_relationship = input(f"Relationship [{relationship}]: ").strip()
    if not new_relationship:
        new_relationship = relationship

    new_phone1 = input(f"Primary phone [{phone1}]: ").strip()
    if not new_phone1:
        new_phone1 = phone1

    new_phone2 = input(f"Secondary phone [{phone2}]: ").strip()
    if not new_phone2:
        new_phone2 = phone2

    new_email = input(f"Email [{email}]: ").strip()
    if not new_email:
        new_email = email

    new_address = input(f"Address [{address}]: ").strip()
    if not new_address:
        new_address = address

    medical_dm_input = input(f"Medical decision maker ({'Yes' if medical_dm else 'No'}) [y/n]: ").strip().lower()
    if medical_dm_input == 'y':
        new_medical_dm = 1
    elif medical_dm_input == 'n':
        new_medical_dm = 0
    else:
        new_medical_dm = medical_dm

    cursor.execute('''
    UPDATE emergency_contacts 
    SET contact_name = ?, relationship = ?, phone_primary = ?, phone_secondary = ?,
        email = ?, address = ?, medical_decision_maker = ?
    WHERE id = ?
    ''', (new_contact_name, new_relationship, new_phone1, new_phone2, new_email,
          new_address, new_medical_dm, contact_id))

    conn.commit()
    log_audit_event(auth.current_user['id'], 'update_emergency_contact', 'emergency_contact', contact_id)
    print("\nEmergency contact updated successfully!")
    conn.close()

def delete_emergency_contact(auth):
    if not (auth.check_permission('manage_health_records') or auth.check_permission('update_insurance_info')):
        print("You don't have permission to delete emergency contacts.")
        return

    backup_before_operation('delete_emergency_contact')

    conn = get_connection()
    cursor = conn.cursor()

    contact_id = input("Enter emergency contact ID to delete: ")

    cursor.execute('''
    SELECT ec.id, s.student_id, s.first_name, s.last_name, ec.contact_name,
           ec.relationship, ec.priority_order
    FROM emergency_contacts ec
    JOIN students s ON ec.student_id = s.student_id
    WHERE ec.id = ?
    ''', (contact_id,))

    contact = cursor.fetchone()

    if not contact:
        print("Error: Emergency contact not found.")
        conn.close()
        return

    ec_id, student_id, first_name, last_name, contact_name, relationship, priority = contact

    print(f"\nContact to delete:")
    print(f"Student: {first_name} {last_name} (ID: {student_id})")
    print(f"Contact: {contact_name}")
    print(f"Relationship: {relationship}")
    print(f"Priority: {priority}")

    confirm = input("\nAre you sure you want to delete this emergency contact? (yes/no): ").lower()
    if confirm != 'yes':
        print("Deletion cancelled.")
        conn.close()
        return

    cursor.execute('DELETE FROM emergency_contacts WHERE id = ?', (contact_id,))

    # Reorder remaining contacts
    cursor.execute('''
    UPDATE emergency_contacts 
    SET priority_order = priority_order - 1
    WHERE student_id = ? AND priority_order > ?
    ''', (student_id, priority))

    conn.commit()
    log_audit_event(auth.current_user['id'], 'delete_emergency_contact', 'emergency_contact', contact_id)
    print("\nEmergency contact deleted successfully!")
    conn.close()

def manage_contact_hierarchy(auth):
    if not (auth.check_permission('manage_health_records') or auth.check_permission('update_insurance_info')):
        print("You don't have permission to manage contact hierarchy.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    if auth.current_user['role'] in ['admin', 'health_provider']:
        student_id = input("Enter student ID: ")

        cursor.execute("SELECT first_name, last_name FROM students WHERE student_id = ?", (student_id,))
        student = cursor.fetchone()
        if not student:
            print("Error: Student ID not found.")
            conn.close()
            return

        print(f"Managing contacts for: {student[0]} {student[1]}")
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print("Error: No student ID associated with your account.")
            conn.close()
            return

    # Get current contacts
    cursor.execute('''
    SELECT id, contact_name, relationship, phone_primary, priority_order,
           medical_decision_maker
    FROM emergency_contacts
    WHERE student_id = ?
    ORDER BY priority_order
    ''', (student_id,))

    contacts = cursor.fetchall()

    if not contacts:
        print("No emergency contacts found.")
        conn.close()
        return

    print(f"\n===== Emergency Contact Hierarchy =====")
    for contact in contacts:
        contact_id, name, relationship, phone, priority, medical_dm = contact
        print(f"{priority}. {name} ({relationship}) - {phone}")
        if medical_dm:
            print("   🏥 Medical Decision Maker")

    print("\nOptions:")
    print("1. Change contact priority")
    print("2. Set medical decision maker")
    print("3. Return to menu")

    choice = input("\nSelect option (1-3): ")

    if choice == '1':
        # Change priority
        contact_id = input("Enter contact ID to reorder: ")
        new_priority = input("Enter new priority (1-{}): ".format(len(contacts)))

        try:
            new_priority = int(new_priority)
            if 1 <= new_priority <= len(contacts):
                # Complex reordering logic would go here
                cursor.execute('''
                UPDATE emergency_contacts 
                SET priority_order = ?
                WHERE id = ?
                ''', (new_priority, contact_id))

                conn.commit()
                print("Contact priority updated!")
            else:
                print("Invalid priority number.")
        except ValueError:
            print("Invalid input.")

    elif choice == '2':
        # Set medical decision maker
        contact_id = input("Enter contact ID to set as medical decision maker: ")

        # Clear existing medical decision maker
        cursor.execute('''
        UPDATE emergency_contacts 
        SET medical_decision_maker = 0
        WHERE student_id = ?
        ''', (student_id,))

        # Set new medical decision maker
        cursor.execute('''
        UPDATE emergency_contacts 
        SET medical_decision_maker = 1
        WHERE id = ?
        ''', (contact_id,))

        conn.commit()
        print("Medical decision maker updated!")

    conn.close()

def manage_emergency_contacts(auth):
    if not auth or not auth.current_user:
        print("You must be logged in to manage emergency contacts.")
        return

    while True:
        print("\n===== Emergency Contact Management =====")
        print("1. Add Emergency Contact")
        print("2. View Emergency Contacts")
        print("3. Update Emergency Contact")
        print("4. Delete Emergency Contact")
        print("5. Emergency Contact Hierarchy")
        print("6. Return to Main Menu")

        choice = input("\nEnter your choice (1-6): ")

        if choice == '1':
            add_emergency_contact(auth)
        elif choice == '2':
            view_emergency_contacts(auth)
        elif choice == '3':
            update_emergency_contact(auth)
        elif choice == '4':
            delete_emergency_contact(auth)
        elif choice == '5':
            manage_contact_hierarchy(auth)
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")

def add_emergency_contact(auth):
    if not (auth.check_permission('manage_health_records') or auth.check_permission('update_insurance_info')):
        print("You don't have permission to add emergency contacts.")
        return

    backup_before_operation('add_emergency_contact')

    conn = get_connection()
    cursor = conn.cursor()

    if auth.current_user['role'] in ['admin', 'health_provider']:
        student_id = input("Enter student ID: ")

        cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
        if cursor.fetchone()[0] == 0:
            print("Error: Student ID not found.")
            conn.close()
            return
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print("Error: No student ID associated with your account.")
            conn.close()
            return

    contact_name = input("Contact name: ")
    relationship = input("Relationship: ")
    phone_primary = input("Primary phone: ")
    phone_secondary = input("Secondary phone (optional): ")
    email = input("Email: ")
    address = input("Address: ")

    # Get priority order
    cursor.execute('''
    SELECT COALESCE(MAX(priority_order), 0) + 1 
    FROM emergency_contacts 
    WHERE student_id = ?
    ''', (student_id,))

    priority_order = cursor.fetchone()[0]

    medical_decision_maker = input("Medical decision maker? (y/n): ").lower() == 'y'

    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
    INSERT INTO emergency_contacts 
    (student_id, contact_name, relationship, phone_primary, phone_secondary, 
     email, address, priority_order, medical_decision_maker, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (student_id, contact_name, relationship, phone_primary, phone_secondary,
          email, address, priority_order, 1 if medical_decision_maker else 0, created_at))

    conn.commit()
    log_audit_event(auth.current_user['id'], 'add_emergency_contact', 'emergency_contact', cursor.lastrowid)
    print("\nEmergency contact added successfully!")
    conn.close()

def view_emergency_contacts(auth):
    if not (auth.check_permission('view_any_health_record') or auth.check_permission('view_own_health_record')):
        print("You don't have permission to view emergency contacts.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    if auth.check_permission('view_any_health_record'):
        student_id = input("Enter student ID: ")

        cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
        if cursor.fetchone()[0] == 0:
            print("Error: Student ID not found.")
            conn.close()
            return
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print("Error: No student ID associated with your account.")
            conn.close()
            return

    cursor.execute('''
    SELECT id, contact_name, relationship, phone_primary, phone_secondary,
           email, address, priority_order, medical_decision_maker
    FROM emergency_contacts
    WHERE student_id = ?
    ORDER BY priority_order
    ''', (student_id,))

    contacts = cursor.fetchall()

    if not contacts:
        print("No emergency contacts found.")
        conn.close()
        return

    print("\n===== Emergency Contacts =====")
    for contact in contacts:
        contact_id, name, relationship, phone1, phone2, email, address, priority, medical_dm = contact

        print(f"\nPriority: {priority}")
        print(f"Name: {name}")
        print(f"Relationship: {relationship}")
        print(f"Primary Phone: {phone1}")
        if phone2:
            print(f"Secondary Phone: {phone2}")
        print(f"Email: {email}")
        print(f"Address: {address}")
        print(f"Medical Decision Maker: {'Yes' if medical_dm else 'No'}")

        if medical_dm:
            print("🏥 MEDICAL DECISION MAKER")

        print("-" * 30)

    conn.close()
