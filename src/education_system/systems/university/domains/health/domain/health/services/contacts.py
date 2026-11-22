from __future__ import annotations

from datetime import datetime

from education_system.systems.university.domains.health.domain.health.services.audit import log_audit_event
from education_system.systems.university.infrastructure.database.data_backup import backup_before_operation
from education_system.systems.university.domains.health.infrastructure.health.storage import get_connection
from education_system.systems.university.infrastructure.i18n import get_text as _t

# Who may see or change whose contacts (application/health/access): the
# health team for any student, a student only for their own.
from education_system.systems.university.domains.health.application.health import (  # noqa: E402
    access as _access,
)


def _who(auth):
    return _access.from_user(getattr(auth, 'current_user', None))


def _is_clinician(auth):
    who = _who(auth)
    return bool(who and who.is_clinician)


def _own_or_refuse(auth, student_id):
    """True when this person may change ``student_id``'s contacts; prints
    the refusal (and writes nothing) otherwise."""
    if _is_clinician(auth):
        return True
    own = get_user_student_id(auth)
    if own and str(student_id) == str(own):
        return True
    print(_t("health_misc.contacts.contact_not_found"))
    return False


def _audit_view(auth, student_id):
    """Record the look; False (and nothing shown) when it can't be recorded."""
    try:
        _access.record_view(_who(auth), "emergency_contacts", student_id=student_id)
        return True
    except PermissionError as exc:
        print(exc)
        return False

def get_user_student_id(auth):
    """The signed-in student's student number, or None for anyone who is not
    a student. Taken from the session (``current_user['student_id']``); the
    old lookup matched ``users.id`` against the session id, which belongs to
    a different id space and could return another person's student number."""
    if not auth or not auth.current_user:
        return None
    who = _who(auth)
    if who is None or not who.is_student:
        return None
    if who.student_id:
        return str(who.student_id)
    # Older sessions without student_id: a student signs in with their
    # student number.
    conn = get_connection()
    try:
        row = conn.execute("SELECT student_id FROM students WHERE student_id = ?",
                           (who.username,)).fetchone()
    finally:
        conn.close()
    return str(row[0]) if row else None

def update_emergency_contact(auth):
    if not (auth.check_permission('manage_health_records') or auth.check_permission('view_own_health_record')):
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
    # A contact id is guessable: only the student's own, or the health team.
    if not _own_or_refuse(auth, student_id):
        conn.close()
        return

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
    if not (auth.check_permission('manage_health_records') or auth.check_permission('view_own_health_record')):
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
    if not _own_or_refuse(auth, student_id):
        conn.close()
        return

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
    if not (auth.check_permission('manage_health_records') or auth.check_permission('view_own_health_record')):
        print(_t("health_misc.contacts.no_permission_manage"))
        return

    conn = get_connection()
    cursor = conn.cursor()

    if _is_clinician(auth):
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

    if not _audit_view(auth, student_id):
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
                WHERE id = ? AND student_id = ?
                ''', (new_priority, contact_id, student_id))

                conn.commit()
                print(_t("health_misc.contacts.priority_updated"))
            else:
                print(_t("health_misc.contacts.invalid_priority"))
        except ValueError:
            print(_t("health_misc.contacts.invalid_input"))

    elif choice == '2':
        # Set medical decision maker
        contact_id = input(_t("health_misc.contacts.enter_contact_id_medical_dm"))

        # Only one of this student's own contacts can be chosen.
        cursor.execute('SELECT 1 FROM emergency_contacts WHERE id = ? AND student_id = ?',
                       (contact_id, student_id))
        if cursor.fetchone() is None:
            print(_t("health_misc.contacts.contact_not_found"))
            conn.close()
            return

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
        WHERE id = ? AND student_id = ?
        ''', (contact_id, student_id))

        conn.commit()
        print(_t("health_misc.contacts.medical_dm_updated"))

    conn.close()

def manage_emergency_contacts(auth):
    if not auth or not auth.current_user:
        print(_t("health_misc.contacts.must_be_logged_in"))
        return
    # The health team, or a student for their own contacts.
    if not (_is_clinician(auth) or get_user_student_id(auth)):
        print(_t("health_misc.contacts.no_permission_manage"))
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
    if not (auth.check_permission('manage_health_records') or auth.check_permission('view_own_health_record')):
        print(_t("health_misc.contacts.no_permission_add"))
        return

    backup_before_operation('add_emergency_contact')

    conn = get_connection()
    cursor = conn.cursor()

    if _is_clinician(auth):
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

    if _is_clinician(auth):
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

    if not _audit_view(auth, student_id):
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


# --------------------------------------------------------------------------
# Non-interactive API: the health portal GUI screen and the health portal
# CLI use these (the menu functions above prompt). One layout —
# contact_name / relationship / phone_primary / phone_secondary / email /
# address / priority_order / medical_decision_maker / is_primary — keyed on
# the student number (students.student_id). The CLI's older layout
# (name / phone, keyed on users.id) was folded in by migration 9c1e3a5d7f0b.

CONTACT_FIELDS = ("contact_name", "relationship", "phone_primary", "phone_secondary", "email",
                  "address", "medical_decision_maker", "is_primary")


def _ensure_contact_columns(conn):
    """``emergency_contacts`` with every column — declared in
    ``infrastructure/health/health_schema`` (applied once per database)."""
    from education_system.systems.university.domains.health.infrastructure.health import (
        health_schema,
    )
    health_schema.apply_to_connection(conn)


def _may_change(who, student_id):
    if who is None:
        raise PermissionError("Sign in to change emergency contacts")
    if who.is_clinician:
        return
    if who.is_student and who.student_id and str(who.student_id) == str(student_id):
        return
    raise PermissionError("Emergency contacts can be changed by the health team and the "
                          "student themselves")


def _student_exists(conn, student_id):
    return conn.execute("SELECT 1 FROM students WHERE student_id = ?",
                        (str(student_id),)).fetchone() is not None


def list_contacts(who, student_id):
    """``student_id``'s contacts (primary first, then priority), after the
    access check and the audit entry (fail closed)."""
    _access.require_view(who, student_id)
    _access.record_view(who, "emergency_contacts", student_id=student_id)
    conn = get_connection()
    try:
        _ensure_contact_columns(conn)
        cur = conn.execute('''
            SELECT id, student_id, contact_name, relationship, phone_primary, phone_secondary,
                   email, address, priority_order, medical_decision_maker, is_primary, created_at
            FROM emergency_contacts WHERE student_id = ?
            ORDER BY COALESCE(is_primary, 0) DESC, COALESCE(priority_order, 999), id''',
                           (str(student_id),))
        names = [d[0] for d in cur.description]
        return [dict(zip(names, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def save_contact(who, student_id, data, contact_id=None):
    """Add (``contact_id`` None) or change one contact; returns its id.
    Name, relationship and a primary phone are required. Setting
    ``is_primary`` clears it on the student's other contacts."""
    _may_change(who, student_id)
    values = {k: (str(data.get(k)).strip() if data.get(k) is not None else None)
              for k in CONTACT_FIELDS}
    for flag in ("is_primary", "medical_decision_maker"):
        values[flag] = 1 if str(data.get(flag) or "").lower() in ("1", "true", "yes", "y") \
            or data.get(flag) is True else 0
    for required in ("contact_name", "relationship", "phone_primary"):
        if not values[required]:
            raise ValueError(f"{required.replace('_', ' ').capitalize()} is required")
    conn = get_connection()
    try:
        _ensure_contact_columns(conn)
        if not _student_exists(conn, student_id):
            raise ValueError(f"No student {student_id}")
        if contact_id is not None:
            owner = conn.execute("SELECT student_id FROM emergency_contacts WHERE id = ?",
                                 (contact_id,)).fetchone()
            if not owner or str(owner[0]) != str(student_id):
                raise PermissionError("That contact is not one of this student's")
        if values["is_primary"]:
            conn.execute("UPDATE emergency_contacts SET is_primary = 0 WHERE student_id = ? "
                         "AND id IS NOT ?", (str(student_id), contact_id))
        if contact_id is None:
            priority = conn.execute("SELECT COALESCE(MAX(priority_order), 0) + 1 FROM "
                                    "emergency_contacts WHERE student_id = ?",
                                    (str(student_id),)).fetchone()[0]
            cur = conn.execute(f'''
                INSERT INTO emergency_contacts (student_id, {", ".join(CONTACT_FIELDS)},
                    priority_order, created_at)
                VALUES (?, {", ".join("?" * len(CONTACT_FIELDS))}, ?, ?)''',  # nosec B608
                               (str(student_id), *(values[k] for k in CONTACT_FIELDS), priority,
                                datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            contact_id = cur.lastrowid
            action = 'add_emergency_contact'
        else:
            conn.execute(f'''UPDATE emergency_contacts SET
                {", ".join(f"{k} = ?" for k in CONTACT_FIELDS)} WHERE id = ?''',  # nosec B608
                         (*(values[k] for k in CONTACT_FIELDS), contact_id))
            action = 'update_emergency_contact'
        log_audit_event(who.username, action, 'emergency_contact', contact_id,
                        details={'student_id': str(student_id)}, conn=conn)
        conn.commit()
        return contact_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_contact(who, student_id, contact_id):
    _may_change(who, student_id)
    conn = get_connection()
    try:
        removed = conn.execute("DELETE FROM emergency_contacts WHERE id = ? AND student_id = ?",
                               (contact_id, str(student_id))).rowcount
        if not removed:
            raise PermissionError("That contact is not one of this student's")
        log_audit_event(who.username, 'delete_emergency_contact', 'emergency_contact',
                        contact_id, details={'student_id': str(student_id)}, conn=conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def set_primary(who, student_id, contact_id):
    _may_change(who, student_id)
    conn = get_connection()
    try:
        _ensure_contact_columns(conn)
        if not conn.execute("SELECT 1 FROM emergency_contacts WHERE id = ? AND student_id = ?",
                            (contact_id, str(student_id))).fetchone():
            raise PermissionError("That contact is not one of this student's")
        conn.execute("UPDATE emergency_contacts SET is_primary = CASE WHEN id = ? THEN 1 "
                     "ELSE 0 END WHERE student_id = ?", (contact_id, str(student_id)))
        log_audit_event(who.username, 'set_primary_emergency_contact', 'emergency_contact',
                        contact_id, details={'student_id': str(student_id)}, conn=conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
