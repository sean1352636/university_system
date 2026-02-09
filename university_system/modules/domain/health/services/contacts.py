from __future__ import annotations

from datetime import datetime

from university_system.modules.domain.health.services.audit import log_audit_event
from university_system.infrastructure.database.data_backup import backup_before_operation
from university_system.infrastructure.database.db import get_connection
from university_system.modules.shared.utils.i18n import get_text as _t

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
        print(_t("health_misc.contacts.no_permission_update"))
        return

    backup_before_operation('update_emergency_contact')

    conn = get_connection()
    cursor = conn.cursor()

    contact_id = input(_t("health_misc.contacts.enter_contact_id_update"))

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
        print(_t("health_misc.contacts.contact_not_found"))
        conn.close()
        return

    ec_id, student_id, first_name, last_name, contact_name, relationship, phone1, phone2, email, address, priority, medical_dm = contact

    print(f"\n{_t('health_misc.contacts.current_details')}:")
    print(f"{_t('health_misc.contacts.student')}: {first_name} {last_name} ({_t('common.id')}: {student_id})")
    print(f"{_t('health_misc.contacts.contact')}: {contact_name}")
    print(f"{_t('health_misc.contacts.relationship')}: {relationship}")
    print(f"{_t('health_misc.contacts.primary_phone')}: {phone1}")
    print(f"{_t('health_misc.contacts.secondary_phone')}: {phone2}")
    print(f"{_t('health_misc.contacts.email')}: {email}")
    print(f"{_t('health_misc.contacts.address')}: {address}")
    print(f"{_t('health_misc.contacts.priority')}: {priority}")
    print(f"{_t('health_misc.contacts.medical_decision_maker')}: {_t('common.yes') if medical_dm else _t('common.no')}")

    print(f"\n{_t('health_misc.contacts.enter_new_values')}:")

    new_contact_name = input(f"{_t('health_misc.contacts.contact_name')} [{contact_name}]: ").strip()
    if not new_contact_name:
        new_contact_name = contact_name

    new_relationship = input(f"{_t('health_misc.contacts.relationship')} [{relationship}]: ").strip()
    if not new_relationship:
        new_relationship = relationship

    new_phone1 = input(f"{_t('health_misc.contacts.primary_phone')} [{phone1}]: ").strip()
    if not new_phone1:
        new_phone1 = phone1

    new_phone2 = input(f"{_t('health_misc.contacts.secondary_phone')} [{phone2}]: ").strip()
    if not new_phone2:
        new_phone2 = phone2

    new_email = input(f"{_t('health_misc.contacts.email')} [{email}]: ").strip()
    if not new_email:
        new_email = email

    new_address = input(f"{_t('health_misc.contacts.address')} [{address}]: ").strip()
    if not new_address:
        new_address = address

    medical_dm_input = input(f"{_t('health_misc.contacts.medical_decision_maker')} ({_t('common.yes') if medical_dm else _t('common.no')}) [y/n]: ").strip().lower()
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
    print(f"\n{_t('health_misc.contacts.contact_updated')}")
    conn.close()

def delete_emergency_contact(auth):
    if not (auth.check_permission('manage_health_records') or auth.check_permission('update_insurance_info')):
        print(_t("health_misc.contacts.no_permission_delete"))
        return

    backup_before_operation('delete_emergency_contact')

    conn = get_connection()
    cursor = conn.cursor()

    contact_id = input(_t("health_misc.contacts.enter_contact_id_delete"))

    cursor.execute('''
    SELECT ec.id, s.student_id, s.first_name, s.last_name, ec.contact_name,
           ec.relationship, ec.priority_order
    FROM emergency_contacts ec
    JOIN students s ON ec.student_id = s.student_id
    WHERE ec.id = ?
    ''', (contact_id,))

    contact = cursor.fetchone()

    if not contact:
        print(_t("health_misc.contacts.contact_not_found"))
        conn.close()
        return

    ec_id, student_id, first_name, last_name, contact_name, relationship, priority = contact

    print(f"\n{_t('health_misc.contacts.contact_to_delete')}:")
    print(f"{_t('health_misc.contacts.student')}: {first_name} {last_name} ({_t('common.id')}: {student_id})")
    print(f"{_t('health_misc.contacts.contact')}: {contact_name}")
    print(f"{_t('health_misc.contacts.relationship')}: {relationship}")
    print(f"{_t('health_misc.contacts.priority')}: {priority}")

    confirm = input(f"\n{_t('health_misc.contacts.confirm_delete')} (yes/no): ").lower()
    if confirm != 'yes':
        print(_t("health_misc.contacts.deletion_cancelled"))
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
    print(f"\n{_t('health_misc.contacts.contact_deleted')}")
    conn.close()

def manage_contact_hierarchy(auth):
    if not (auth.check_permission('manage_health_records') or auth.check_permission('update_insurance_info')):
        print(_t("health_misc.contacts.no_permission_manage"))
        return

    conn = get_connection()
    cursor = conn.cursor()

    if auth.current_user['role'] in ['admin', 'health_provider']:
        student_id = input(_t("health_misc.contacts.enter_student_id"))

        cursor.execute("SELECT first_name, last_name FROM students WHERE student_id = ?", (student_id,))
        student = cursor.fetchone()
        if not student:
            print(_t("health_misc.contacts.student_not_found"))
            conn.close()
            return

        print(_t("health_misc.contacts.managing_contacts_for", name=f"{student[0]} {student[1]}"))
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print(_t("health_misc.contacts.no_student_id_associated"))
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
        print(_t("health_misc.contacts.no_contacts_found"))
        conn.close()
        return

    print(f"\n===== {_t('health_misc.contacts.hierarchy_title')} =====")
    for contact in contacts:
        contact_id, name, relationship, phone, priority, medical_dm = contact
        print(f"{priority}. {name} ({relationship}) - {phone}")
        if medical_dm:
            print(f"   {_t('health_misc.contacts.medical_decision_maker_indicator')}")

    print(f"\n{_t('health_misc.contacts.options')}:")
    print(f"1. {_t('health_misc.contacts.change_priority')}")
    print(f"2. {_t('health_misc.contacts.set_medical_dm')}")
    print(f"3. {_t('health_misc.contacts.return_to_menu')}")

    choice = input(f"\n{_t('health_misc.contacts.select_option')} (1-3): ")

    if choice == '1':
        # Change priority
        contact_id = input(_t("health_misc.contacts.enter_contact_id_reorder"))
        new_priority = input(_t("health_misc.contacts.enter_new_priority", max=len(contacts)))

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
                print(_t("health_misc.contacts.priority_updated"))
            else:
                print(_t("health_misc.contacts.invalid_priority"))
        except ValueError:
            print(_t("health_misc.contacts.invalid_input"))

    elif choice == '2':
        # Set medical decision maker
        contact_id = input(_t("health_misc.contacts.enter_contact_id_medical_dm"))

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
        print(_t("health_misc.contacts.medical_dm_updated"))

    conn.close()

def manage_emergency_contacts(auth):
    if not auth or not auth.current_user:
        print(_t("health_misc.contacts.must_be_logged_in"))
        return

    while True:
        print(f"\n===== {_t('health_misc.contacts.menu_title')} =====")
        print(f"1. {_t('health_misc.contacts.menu_add')}")
        print(f"2. {_t('health_misc.contacts.menu_view')}")
        print(f"3. {_t('health_misc.contacts.menu_update')}")
        print(f"4. {_t('health_misc.contacts.menu_delete')}")
        print(f"5. {_t('health_misc.contacts.menu_hierarchy')}")
        print(f"6. {_t('health_misc.contacts.menu_return')}")

        choice = input(f"\n{_t('health_misc.contacts.enter_choice')} (1-6): ")

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
            print(_t("health_misc.contacts.invalid_choice"))

def add_emergency_contact(auth):
    if not (auth.check_permission('manage_health_records') or auth.check_permission('update_insurance_info')):
        print(_t("health_misc.contacts.no_permission_add"))
        return

    backup_before_operation('add_emergency_contact')

    conn = get_connection()
    cursor = conn.cursor()

    if auth.current_user['role'] in ['admin', 'health_provider']:
        student_id = input(_t("health_misc.contacts.enter_student_id"))

        cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
        if cursor.fetchone()[0] == 0:
            print(_t("health_misc.contacts.student_not_found"))
            conn.close()
            return
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print(_t("health_misc.contacts.no_student_id_associated"))
            conn.close()
            return

    contact_name = input(f"{_t('health_misc.contacts.contact_name')}: ")
    relationship = input(f"{_t('health_misc.contacts.relationship')}: ")
    phone_primary = input(f"{_t('health_misc.contacts.primary_phone')}: ")
    phone_secondary = input(f"{_t('health_misc.contacts.secondary_phone')} ({_t('common.optional')}): ")
    email = input(f"{_t('health_misc.contacts.email')}: ")
    address = input(f"{_t('health_misc.contacts.address')}: ")

    # Get priority order
    cursor.execute('''
    SELECT COALESCE(MAX(priority_order), 0) + 1
    FROM emergency_contacts
    WHERE student_id = ?
    ''', (student_id,))

    priority_order = cursor.fetchone()[0]

    medical_decision_maker = input(f"{_t('health_misc.contacts.medical_decision_maker')}? (y/n): ").lower() == 'y'

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
    print(f"\n{_t('health_misc.contacts.contact_added')}")
    conn.close()

def view_emergency_contacts(auth):
    if not (auth.check_permission('view_any_health_record') or auth.check_permission('view_own_health_record')):
        print(_t("health_misc.contacts.no_permission_view"))
        return

    conn = get_connection()
    cursor = conn.cursor()

    if auth.check_permission('view_any_health_record'):
        student_id = input(_t("health_misc.contacts.enter_student_id"))

        cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
        if cursor.fetchone()[0] == 0:
            print(_t("health_misc.contacts.student_not_found"))
            conn.close()
            return
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print(_t("health_misc.contacts.no_student_id_associated"))
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
        print(_t("health_misc.contacts.no_contacts_found"))
        conn.close()
        return

    print(f"\n===== {_t('health_misc.contacts.contacts_title')} =====")
    for contact in contacts:
        contact_id, name, relationship, phone1, phone2, email, address, priority, medical_dm = contact

        print(f"\n{_t('health_misc.contacts.priority')}: {priority}")
        print(f"{_t('health_misc.contacts.name')}: {name}")
        print(f"{_t('health_misc.contacts.relationship')}: {relationship}")
        print(f"{_t('health_misc.contacts.primary_phone')}: {phone1}")
        if phone2:
            print(f"{_t('health_misc.contacts.secondary_phone')}: {phone2}")
        print(f"{_t('health_misc.contacts.email')}: {email}")
        print(f"{_t('health_misc.contacts.address')}: {address}")
        print(f"{_t('health_misc.contacts.medical_decision_maker')}: {_t('common.yes') if medical_dm else _t('common.no')}")

        if medical_dm:
            print(_t("health_misc.contacts.medical_decision_maker_indicator"))

        print("-" * 30)

    conn.close()
