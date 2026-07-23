import logging
from datetime import datetime, timedelta

from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation._common import (
    sqlite3, DB_PATH, get_auth, backup_before_operation, get_text,
)
from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.db import init_accommodation_db
from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.validation import (
    validate_date, check_conflict, get_accommodation_types, validate_student_id,
)
from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.audit import log_action
from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.notifications import notify_student
from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.documents import upload_accommodation_document


def add_accommodation():
    """Register a student to an accommodation, with conflict detection and better validation."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_add", "You must be logged in to add accommodations."))
        return

    if not auth.check_permission('manage_accommodations'):
        print(get_text("housing.accommodation.auth.no_permission_add", "You don't have permission to add accommodations."))
        return

    # Backup before making changes
    backup_before_operation('accommodation_add')

    init_accommodation_db()
    try:
        # Get student ID with validation
        while True:
            student_id = input(get_text("housing.accommodation.input.enter_student_id", "Enter student ID: ")).strip()
            if not student_id:
                print(get_text("housing.accommodation.error.student_id_required", "Error: Student ID is required."))
                continue

            if not validate_student_id(student_id):
                print(get_text("housing.accommodation.error.student_not_found", "Error: Student ID not found in the system."))
                retry = input(get_text("housing.accommodation.input.try_again", "Would you like to try again? (y/n): "))
                if retry.lower() != 'y':
                    return
                continue
            break

        # Get accommodation type with autocomplete
        available_types = get_accommodation_types()
        print("\n" + get_text("housing.accommodation.label.available_types", "Available accommodation types:"))
        for i, type_name in enumerate(available_types):
            print(f"{i+1}. {type_name}")

        while True:
            type_choice = input("\n" + get_text("housing.accommodation.input.select_type", "Select type (number or enter custom): ")).strip()
            if type_choice.isdigit() and 1 <= int(type_choice) <= len(available_types):
                accommodation_type = available_types[int(type_choice)-1]
                break
            elif type_choice:
                accommodation_type = type_choice
                break
            else:
                print(get_text("housing.accommodation.error.type_required", "Error: Accommodation type is required."))

        # Get description
        description = input(get_text("housing.accommodation.input.enter_description", "Enter description [optional]: ")).strip() or None

        # Get dates with validation
        while True:
            start_date = input(get_text("housing.accommodation.input.enter_start_date", "Enter start date (YYYY-MM-DD) [optional]: ")).strip() or None
            if start_date:
                valid, error = validate_date(start_date)
                if not valid:
                    print(get_text("housing.accommodation.error.generic", "Error: {error}").format(error=error))
                    continue
            break

        while True:
            end_date = input(get_text("housing.accommodation.input.enter_end_date", "Enter end date (YYYY-MM-DD) [optional]: ")).strip() or None
            if end_date:
                valid, error = validate_date(end_date)
                if not valid:
                    print(get_text("housing.accommodation.error.generic", "Error: {error}").format(error=error))
                    continue

                # Check that end date is after start date
                if start_date and end_date:
                    start = datetime.fromisoformat(start_date)
                    end = datetime.fromisoformat(end_date)
                    if end <= start:
                        print(get_text("housing.accommodation.error.end_date_after_start", "Error: End date must be after start date."))
                        continue
            break

        # Check for conflicts
        if check_conflict(student_id, accommodation_type, start_date, end_date):
            print(get_text("housing.accommodation.warning.overlap_existing", "Warning: This accommodation overlaps an existing record."))
            cont = input(get_text("housing.accommodation.input.continue_anyway", "Continue anyway? (y/n): "))
            if cont.lower() != 'y':
                return

        # Additional fields
        notes = input(get_text("housing.accommodation.input.additional_notes", "Additional notes [optional]: ")).strip() or None
        status = 'pending' if 'requires_approval' else 'active'

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO accommodations
                (student_id, accommodation_type, description, start_date, end_date, status, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, accommodation_type, description, start_date, end_date, status, notes, now, now))
            aid = cursor.lastrowid
            conn.commit()

        print(get_text("housing.accommodation.success.added", "Accommodation added successfully."))

        # Document upload option
        doc_upload = input(get_text("housing.accommodation.input.upload_documentation", "Would you like to upload supporting documentation? (y/n): "))
        if doc_upload.lower() == 'y':
            upload_accommodation_document(aid)

        log_action('add', aid, f"Added {accommodation_type} for student {student_id}")
        notify_student(student_id, 'Accommodation Registered',
                      f"You have been registered for {accommodation_type}.")

        # Display the added accommodation details
        view_accommodation_by_id(aid)

    except Exception as e:
        logging.error(f"Error adding accommodation: {e}")
        print(get_text("housing.accommodation.error.adding", "Error adding accommodation: {error}").format(error=e))
        print(get_text("housing.accommodation.error.try_again_or_contact", "Please try again or contact technical support."))


def view_accommodation_by_id(accommodation_id):
    """View a specific accommodation by ID."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get accommodation details
            cursor.execute('''
                SELECT a.*, s.first_name, s.last_name, s.email_address
                FROM accommodations a
                LEFT JOIN students s ON a.student_id = s.student_id
                WHERE a.id = ?
            ''', (accommodation_id,))

            accommodation = cursor.fetchone()
            if not accommodation:
                print(get_text("housing.accommodation.error.not_found_id", "No accommodation found with ID {id}").format(id=accommodation_id))
                return

            # Get documents
            cursor.execute('''
                SELECT document_id as id, reference_id as accommodation_id,
                       document_name, file_path as document_path,
                       uploaded_by, upload_date as uploaded_at
                FROM documents
                WHERE source_type = 'accommodation' AND reference_id = ?
                  AND reference_type = 'accommodation'
            ''', (str(accommodation_id),))

            documents = cursor.fetchall()

            # Display accommodation details
            print("\n" + "="*60)
            print(get_text("housing.accommodation.view.id", "Accommodation ID: {id}").format(id=accommodation['id']))
            print(get_text("housing.accommodation.view.student", "Student: {student_id} - {first_name} {last_name}").format(
                student_id=accommodation['student_id'],
                first_name=accommodation['first_name'],
                last_name=accommodation['last_name']))
            print(get_text("housing.accommodation.view.type", "Type: {type}").format(type=accommodation['accommodation_type']))
            print(get_text("housing.accommodation.view.description", "Description: {description}").format(
                description=accommodation['description'] or get_text("housing.accommodation.label.na", "N/A")))
            print(get_text("housing.accommodation.view.start_date", "Start Date: {date}").format(
                date=accommodation['start_date'] or get_text("housing.accommodation.label.not_specified", "Not specified")))
            print(get_text("housing.accommodation.view.end_date", "End Date: {date}").format(
                date=accommodation['end_date'] or get_text("housing.accommodation.label.not_specified", "Not specified")))
            print(get_text("housing.accommodation.view.status", "Status: {status}").format(status=accommodation['status']))
            print(get_text("housing.accommodation.view.notes", "Notes: {notes}").format(
                notes=accommodation['notes'] or get_text("housing.accommodation.label.na", "N/A")))
            print(get_text("housing.accommodation.view.created", "Created: {date}").format(date=accommodation['created_at']))
            print(get_text("housing.accommodation.view.updated", "Last Updated: {date}").format(date=accommodation['updated_at']))

            if documents:
                print("\n" + get_text("housing.accommodation.view.attached_documents", "Attached Documents:"))
                for doc in documents:
                    print(f" - {doc['document_name']} ({get_text('housing.accommodation.view.uploaded', 'Uploaded')}: {doc['uploaded_at']})")

            print("="*60)

    except Exception as e:
        logging.error(f"Error viewing accommodation {accommodation_id}: {e}")
        print(get_text("housing.accommodation.error.viewing", "Error viewing accommodation: {error}").format(error=e))


def update_accommodation():
    """Update an existing accommodation record."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_update", "You must be logged in to update accommodations."))
        return

    if not auth.check_permission('manage_accommodations'):
        print(get_text("housing.accommodation.auth.no_permission_update", "You don't have permission to update accommodations."))
        return

    # Backup before making changes
    backup_before_operation('accommodation_update')

    init_accommodation_db()
    try:
        # Get accommodation ID
        while True:
            id_str = input(get_text("housing.accommodation.input.enter_id_to_update", "Enter accommodation ID to update: ")).strip()
            if not id_str:
                print(get_text("housing.accommodation.error.accommodation_id_required", "Error: Accommodation ID is required."))
                continue

            try:
                accommodation_id = int(id_str)
                break
            except ValueError:
                print(get_text("housing.accommodation.error.valid_id_number", "Error: Please enter a valid ID number."))

        # Check if accommodation exists
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM accommodations WHERE id = ?', (accommodation_id,))
            accommodation = cursor.fetchone()

        if not accommodation:
            print(get_text("housing.accommodation.error.not_found_id", "No accommodation found with ID {id}").format(id=accommodation_id))
            return

        # Display current accommodation
        print("\n" + get_text("housing.accommodation.label.current_details", "Current accommodation details:"))
        view_accommodation_by_id(accommodation_id)

        # Get field to update
        print("\n" + get_text("housing.accommodation.menu.which_field_update", "Which field would you like to update?"))
        print("1. " + get_text("housing.accommodation.menu.accommodation_type", "Accommodation Type"))
        print("2. " + get_text("housing.accommodation.menu.description", "Description"))
        print("3. " + get_text("housing.accommodation.menu.start_date", "Start Date"))
        print("4. " + get_text("housing.accommodation.menu.end_date", "End Date"))
        print("5. " + get_text("housing.accommodation.menu.status", "Status"))
        print("6. " + get_text("housing.accommodation.menu.notes", "Notes"))
        print("7. " + get_text("housing.accommodation.menu.cancel", "Cancel"))

        choice = input(get_text("housing.accommodation.input.enter_choice", "Enter your choice (1-7): ")).strip()

        if choice == '7':
            print(get_text("housing.accommodation.message.update_cancelled", "Update cancelled."))
            return

        # Initialize values with current data
        student_id = accommodation['student_id']
        accommodation_type = accommodation['accommodation_type']
        description = accommodation['description']
        start_date = accommodation['start_date']
        end_date = accommodation['end_date']
        status = accommodation['status']
        notes = accommodation['notes']

        # Update selected field
        if choice == '1':
            available_types = get_accommodation_types()
            print("\n" + get_text("housing.accommodation.label.available_types", "Available accommodation types:"))
            for i, type_name in enumerate(available_types):
                print(f"{i+1}. {type_name}")

            while True:
                type_choice = input("\n" + get_text("housing.accommodation.input.select_new_type", "Select new type (number or enter custom): ")).strip()
                if type_choice.isdigit() and 1 <= int(type_choice) <= len(available_types):
                    accommodation_type = available_types[int(type_choice)-1]
                    break
                elif type_choice:
                    accommodation_type = type_choice
                    break
                else:
                    print(get_text("housing.accommodation.error.type_required", "Error: Accommodation type is required."))

        elif choice == '2':
            description = input(get_text("housing.accommodation.input.enter_new_description", "Enter new description [leave blank to clear]: ")).strip() or None

        elif choice == '3':
            while True:
                start_date = input(get_text("housing.accommodation.input.enter_new_start_date", "Enter new start date (YYYY-MM-DD) [leave blank to clear]: ")).strip() or None
                if start_date:
                    valid, error = validate_date(start_date)
                    if not valid:
                        print(get_text("housing.accommodation.error.generic", "Error: {error}").format(error=error))
                        continue
                break

        elif choice == '4':
            while True:
                end_date = input(get_text("housing.accommodation.input.enter_new_end_date", "Enter new end date (YYYY-MM-DD) [leave blank to clear]: ")).strip() or None
                if end_date:
                    valid, error = validate_date(end_date)
                    if not valid:
                        print(get_text("housing.accommodation.error.generic", "Error: {error}").format(error=error))
                        continue

                    # Check that end date is after start date if start date exists
                    if start_date and end_date:
                        try:
                            start = datetime.fromisoformat(start_date)
                            end = datetime.fromisoformat(end_date)
                            if end <= start:
                                print(get_text("housing.accommodation.error.end_date_after_start", "Error: End date must be after start date."))
                                continue
                        except ValueError:
                            print(get_text("housing.accommodation.validation.invalid_date_format", "Invalid date format. Please use YYYY-MM-DD format."))
                            continue
                break

        elif choice == '5':
            print("\n" + get_text("housing.accommodation.label.available_statuses", "Available statuses:"))
            print("1. " + get_text("housing.accommodation.status.active", "active"))
            print("2. " + get_text("housing.accommodation.status.pending", "pending"))
            print("3. " + get_text("housing.accommodation.status.suspended", "suspended"))
            print("4. " + get_text("housing.accommodation.status.expired", "expired"))

            while True:
                status_choice = input(get_text("housing.accommodation.input.select_new_status", "Select new status (1-4): ")).strip()
                if status_choice == '1':
                    status = 'active'
                    break
                elif status_choice == '2':
                    status = 'pending'
                    break
                elif status_choice == '3':
                    status = 'suspended'
                    break
                elif status_choice == '4':
                    status = 'expired'
                    break
                else:
                    print(get_text("housing.accommodation.error.invalid_selection", "Error: Invalid selection."))

        elif choice == '6':
            notes = input(get_text("housing.accommodation.input.enter_new_notes", "Enter new notes [leave blank to clear]: ")).strip() or None

        else:
            print(get_text("housing.accommodation.error.invalid_choice_cancelled", "Invalid choice. Update cancelled."))
            return

        # Check for conflicts if dates or type changed
        if start_date != accommodation['start_date'] or end_date != accommodation['end_date'] or accommodation_type != accommodation['accommodation_type']:
            if check_conflict(student_id, accommodation_type, start_date, end_date, excluded_id=accommodation_id):
                print(get_text("housing.accommodation.warning.update_conflict", "Warning: This update creates a conflict with an existing accommodation."))
                cont = input(get_text("housing.accommodation.input.continue_anyway", "Continue anyway? (y/n): "))
                if cont.lower() != 'y':
                    return

        # Update the accommodation record
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE accommodations SET
                    accommodation_type = ?,
                    description = ?,
                    start_date = ?,
                    end_date = ?,
                    status = ?,
                    notes = ?,
                    updated_at = ?
                    WHERE id = ?
                ''', (accommodation_type, description, start_date, end_date, status, notes, now, accommodation_id))
                conn.commit()

            print(get_text("housing.accommodation.success.updated", "Accommodation updated successfully."))
            log_action('update', accommodation_id, f"Updated accommodation for student {student_id}")

            # Notify student
            notify_student(student_id, 'Accommodation Updated',
                          f"Your {accommodation_type} accommodation has been updated.")

            # Display updated record
            view_accommodation_by_id(accommodation_id)

        except Exception as update_e:
            logging.error(f"Error updating accommodation {accommodation_id}: {update_e}")
            print(get_text("housing.accommodation.error.updating", "Error updating accommodation: {error}").format(error=update_e))

    except Exception as e:
        logging.error(f"Error in update_accommodation: {e}")
        print(get_text("housing.accommodation.error.updating", "Error updating accommodation: {error}").format(error=e))


def remove_accommodation():
    """Remove an accommodation record with validation and confirmation."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_remove", "You must be logged in to remove accommodations."))
        return

    if not auth.check_permission('manage_accommodations'):
        print(get_text("housing.accommodation.auth.no_permission_remove", "You don't have permission to remove accommodations."))
        return

    # Backup before making changes
    backup_before_operation('accommodation_remove')

    init_accommodation_db()
    try:
        # Get accommodation ID
        while True:
            id_str = input(get_text("housing.accommodation.input.enter_id_to_remove", "Enter accommodation ID to remove: ")).strip()
            if not id_str:
                print(get_text("housing.accommodation.error.accommodation_id_required", "Error: Accommodation ID is required."))
                continue

            try:
                accommodation_id = int(id_str)
                break
            except ValueError:
                print(get_text("housing.accommodation.error.valid_id_number", "Error: Please enter a valid ID number."))

        # Check if accommodation exists and get student info
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT student_id, accommodation_type FROM accommodations WHERE id = ?', (accommodation_id,))
            accommodation = cursor.fetchone()

        if not accommodation:
            print(get_text("housing.accommodation.error.not_found_id", "No accommodation found with ID {id}").format(id=accommodation_id))
            return

        # Display accommodation for confirmation
        view_accommodation_by_id(accommodation_id)

        # Confirm removal
        confirm = input("\n" + get_text("housing.accommodation.input.confirm_remove", "Are you sure you want to remove this accommodation? (y/n): ")).strip().lower()
        if confirm != 'y':
            print(get_text("housing.accommodation.message.removal_cancelled", "Removal cancelled."))
            return

        # Ask for removal reason
        reason = input(get_text("housing.accommodation.input.removal_reason", "Please enter a reason for removal [optional]: ")).strip() or get_text("housing.accommodation.label.not_specified", "Not specified")

        # Soft delete or hard delete option
        delete_type = input(get_text("housing.accommodation.input.delete_or_expire", "Permanently delete or mark as expired? (1=delete/2=expire): ")).strip()

        if delete_type == '2':
            # Soft delete - mark as expired
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE accommodations SET
                    status = 'expired',
                    notes = CASE WHEN notes IS NULL THEN ? ELSE notes || ' | ' || ? END,
                    updated_at = ?
                    WHERE id = ?
                ''', (f"Expired: {reason}", f"Expired: {reason}", now, accommodation_id))
                conn.commit()

            print(get_text("housing.accommodation.success.marked_expired", "Accommodation marked as expired."))

        else:
            # Hard delete - remove from database
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()

                # First remove any associated documents
                cursor.execute(
                    "DELETE FROM documents WHERE source_type = 'accommodation'"
                    " AND reference_id = ? AND reference_type = 'accommodation'",
                    (str(accommodation_id),))

                # Then remove the accommodation record
                cursor.execute('DELETE FROM accommodations WHERE id = ?', (accommodation_id,))
                conn.commit()

            print(get_text("housing.accommodation.success.permanently_deleted", "Accommodation permanently deleted."))

        # Log the action
        student_id = accommodation['student_id']
        accommodation_type = accommodation['accommodation_type']
        log_action('remove', accommodation_id, f"Removed {accommodation_type} for student {student_id}. Reason: {reason}")

        # Notify student
        notify_student(student_id, 'Accommodation Removed',
                      f"Your {accommodation_type} accommodation has been removed. Reason: {reason}")

    except Exception as e:
        logging.error(f"Error removing accommodation: {e}")
        print(get_text("housing.accommodation.error.removing", "Error removing accommodation: {error}").format(error=e))


def view_students_by_accommodation():
    """View all students with a specific accommodation type."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_view_reports", "You must be logged in to view accommodation reports."))
        return

    if not auth.check_permission('view_accommodations'):
        print(get_text("housing.accommodation.auth.no_permission_view_reports", "You don't have permission to view accommodation reports."))
        return

    init_accommodation_db()
    try:
        # Get available accommodation types
        available_types = get_accommodation_types()
        print("\n" + get_text("housing.accommodation.label.available_types", "Available accommodation types:"))
        for i, type_name in enumerate(available_types):
            print(f"{i+1}. {type_name}")

        # Get accommodation type selection
        while True:
            type_choice = input("\n" + get_text("housing.accommodation.input.select_type_to_view", "Select type to view (number or enter name): ")).strip()
            if type_choice.isdigit() and 1 <= int(type_choice) <= len(available_types):
                accommodation_type = available_types[int(type_choice)-1]
                break
            elif type_choice:
                accommodation_type = type_choice
                break
            else:
                print(get_text("housing.accommodation.error.select_type", "Error: Please select an accommodation type."))

        # Get optional status filter
        print("\n" + get_text("housing.accommodation.label.filter_by_status", "Filter by status (leave blank for all):"))
        print("1. " + get_text("housing.accommodation.status.active", "active"))
        print("2. " + get_text("housing.accommodation.status.pending", "pending"))
        print("3. " + get_text("housing.accommodation.status.suspended", "suspended"))
        print("4. " + get_text("housing.accommodation.status.expired", "expired"))

        status_filter = None
        status_choice = input(get_text("housing.accommodation.input.select_status_filter", "Select status filter (1-4 or blank): ")).strip()
        if status_choice == '1':
            status_filter = 'active'
        elif status_choice == '2':
            status_filter = 'pending'
        elif status_choice == '3':
            status_filter = 'suspended'
        elif status_choice == '4':
            status_filter = 'expired'

        # Query database
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = '''
                SELECT a.*, s.first_name, s.last_name, s.email_address
                FROM accommodations a
                JOIN students s ON a.student_id = s.student_id
                WHERE a.accommodation_type = ?
            '''
            params = [accommodation_type]

            if status_filter:
                query += " AND a.status = ?"
                params.append(status_filter)

            query += " ORDER BY a.start_date DESC"

            cursor.execute(query, params)
            accommodations = cursor.fetchall()

        # Display results
        if not accommodations:
            print(get_text("housing.accommodation.message.no_students_found_type", "No students found with {type} accommodation.").format(type=accommodation_type))
            return

        status_text = get_text("housing.accommodation.label.with_status", " with status '{status}'").format(status=status_filter) if status_filter else ""
        print("\n" + get_text("housing.accommodation.message.students_with_type", "Students with {type} accommodation{status}:").format(type=accommodation_type, status=status_text))
        print("=" * 80)
        print(f"{get_text('housing.accommodation.table.id', 'ID'):<5} {get_text('housing.accommodation.table.student_id', 'Student ID'):<10} {get_text('housing.accommodation.table.name', 'Name'):<25} {get_text('housing.accommodation.table.start_date', 'Start Date'):<12} {get_text('housing.accommodation.table.end_date', 'End Date'):<12} {get_text('housing.accommodation.table.status', 'Status'):<10}")
        print("-" * 80)

        for acc in accommodations:
            name = f"{acc['first_name']} {acc['last_name']}"
            start_date = acc['start_date'] or get_text("housing.accommodation.label.na", "N/A")
            end_date = acc['end_date'] or get_text("housing.accommodation.label.na", "N/A")
            print(f"{acc['id']:<5} {acc['student_id']:<10} {name:<25} {start_date:<12} {end_date:<12} {acc['status']:<10}")

        print("=" * 80)
        print(get_text("housing.accommodation.message.total_records", "Total: {count} record(s)").format(count=len(accommodations)))

        # Offer detailed view option
        detail_view = input("\n" + get_text("housing.accommodation.input.enter_id_for_details", "Enter accommodation ID to view details (or press Enter to return): ")).strip()
        if detail_view.isdigit():
            view_accommodation_by_id(int(detail_view))

    except Exception as e:
        logging.error(f"Error viewing students by accommodation: {e}")
        print(get_text("housing.accommodation.error.viewing_students_by_type", "Error viewing students by accommodation: {error}").format(error=e))


def view_accommodations():
    """Rich search and filters, integrating student profiles."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_view", "You must be logged in to view accommodations."))
        return

    if not auth.check_permission('view_accommodations'):
        print(get_text("housing.accommodation.auth.no_permission_view", "You don't have permission to view accommodations."))
        return

    init_accommodation_db()
    try:
        print(get_text("housing.accommodation.filter.options", "Filter options:"))
        print("1) " + get_text("housing.accommodation.filter.all", "All accommodations"))
        print("2) " + get_text("housing.accommodation.filter.by_student", "By student"))
        print("3) " + get_text("housing.accommodation.filter.by_type", "By accommodation type"))
        print("4) " + get_text("housing.accommodation.filter.active", "Active accommodations"))
        print("5) " + get_text("housing.accommodation.filter.expired", "Expired accommodations"))
        print("6) " + get_text("housing.accommodation.filter.date_range", "Date range"))
        print("7) " + get_text("housing.accommodation.filter.keyword_search", "Keyword search in description"))
        print("8) " + get_text("housing.accommodation.filter.by_status", "By status (active/pending/suspended/expired)"))
        print("9) " + get_text("housing.accommodation.filter.recently_added", "Recently added"))
        print("10) " + get_text("housing.accommodation.filter.recently_updated", "Recently updated"))

        choice = input("\n" + get_text("housing.accommodation.input.choose_filter", "Choose filter (1-10): ")).strip()

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            base_query = '''
                SELECT a.id, a.student_id, a.accommodation_type, a.description,
                       a.start_date, a.end_date, a.status, a.created_at, a.updated_at,
                       s.first_name, s.last_name, s.email_address
                FROM accommodations a
                LEFT JOIN students s ON a.student_id = s.student_id
            '''

            where_clauses = []
            params = []

            if choice == '2':
                student_id = input(get_text("housing.accommodation.input.enter_student_id", "Enter student ID: ")).strip()
                where_clauses.append('a.student_id = ?')
                params.append(student_id)

            elif choice == '3':
                available_types = get_accommodation_types()
                print("\n" + get_text("housing.accommodation.label.available_types", "Available accommodation types:"))
                for i, type_name in enumerate(available_types):
                    print(f"{i+1}. {type_name}")

                type_choice = input("\n" + get_text("housing.accommodation.input.select_type", "Select type (number or enter custom): ")).strip()
                if type_choice.isdigit() and 1 <= int(type_choice) <= len(available_types):
                    accommodation_type = available_types[int(type_choice)-1]
                else:
                    accommodation_type = type_choice

                where_clauses.append('a.accommodation_type = ?')
                params.append(accommodation_type)

            elif choice == '4':
                today = datetime.now().strftime('%Y-%m-%d')
                where_clauses.append("(a.end_date >= ? OR a.end_date IS NULL) AND a.status = 'active'")
                params.append(today)

            elif choice == '5':
                today = datetime.now().strftime('%Y-%m-%d')
                where_clauses.append("(a.end_date < ? OR a.status = 'expired')")
                params.append(today)

            elif choice == '6':
                start_date = input(get_text("housing.accommodation.input.start_date_gte", "Start date >= (YYYY-MM-DD): ")).strip()
                end_date = input(get_text("housing.accommodation.input.end_date_lte", "End date <= (YYYY-MM-DD): ")).strip()
                valid_start, error_start = validate_date(start_date)
                valid_end, error_end = validate_date(end_date)

                if not valid_start:
                    print(get_text("housing.accommodation.error.with_start_date", "Error with start date: {error}").format(error=error_start))
                    return
                if not valid_end:
                    print(get_text("housing.accommodation.error.with_end_date", "Error with end date: {error}").format(error=error_end))
                    return

                where_clauses.append('a.start_date >= ? AND a.end_date <= ?')
                params.extend([start_date, end_date])

            elif choice == '7':
                keyword = input(get_text("housing.accommodation.input.enter_keyword", "Enter keyword: ")).strip()
                where_clauses.append('(a.description LIKE ? OR a.notes LIKE ?)')
                params.extend([f'%{keyword}%', f'%{keyword}%'])

            elif choice == '8':
                print("\n" + get_text("housing.accommodation.label.select_status", "Select status:"))
                print("1. " + get_text("housing.accommodation.status.active", "active"))
                print("2. " + get_text("housing.accommodation.status.pending", "pending"))
                print("3. " + get_text("housing.accommodation.status.suspended", "suspended"))
                print("4. " + get_text("housing.accommodation.status.expired", "expired"))

                status_choice = input(get_text("housing.accommodation.input.enter_choice_1_4", "Enter choice (1-4): ")).strip()
                if status_choice == '1':
                    status = 'active'
                elif status_choice == '2':
                    status = 'pending'
                elif status_choice == '3':
                    status = 'suspended'
                elif status_choice == '4':
                    status = 'expired'
                else:
                    print(get_text("housing.accommodation.error.invalid_status_choice", "Invalid status choice."))
                    return

                where_clauses.append('a.status = ?')
                params.append(status)

            elif choice == '9':
                days = input(get_text("housing.accommodation.input.show_added_last_days", "Show accommodations added in the last X days (default 30): ")).strip()
                if not days:
                    days = 30
                try:
                    days = int(days)
                    if days <= 0:
                        raise ValueError
                except ValueError:
                    print(get_text("housing.accommodation.error.positive_number", "Error: Please enter a positive number."))
                    return

                date_limit = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
                where_clauses.append('a.created_at >= ?')
                params.append(date_limit)

            elif choice == '10':
                days = input(get_text("housing.accommodation.input.show_updated_last_days", "Show accommodations updated in the last X days (default 30): ")).strip()
                if not days:
                    days = 30
                try:
                    days = int(days)
                    if days <= 0:
                        raise ValueError
                except ValueError:
                    print(get_text("housing.accommodation.error.positive_number", "Error: Please enter a positive number."))
                    return

                date_limit = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
                where_clauses.append('a.updated_at >= ?')
                params.append(date_limit)

            # Construct and execute the query
            query = base_query
            if where_clauses:
                query += ' WHERE ' + ' AND '.join(where_clauses)

            # Add sort options
            print("\n" + get_text("housing.accommodation.label.sort_by", "Sort by:"))
            print("1. " + get_text("housing.accommodation.sort.start_date_newest", "Start date (newest first)"))
            print("2. " + get_text("housing.accommodation.sort.end_date_soonest", "End date (soonest first)"))
            print("3. " + get_text("housing.accommodation.sort.student_id", "Student ID"))
            print("4. " + get_text("housing.accommodation.sort.accommodation_type", "Accommodation type"))

            sort_choice = input(get_text("housing.accommodation.input.select_sort", "Select sort option (1-4): ")).strip()
            if sort_choice == '1':
                query += ' ORDER BY a.start_date DESC'
            elif sort_choice == '2':
                query += ' ORDER BY a.end_date ASC'
            elif sort_choice == '3':
                query += ' ORDER BY a.student_id'
            elif sort_choice == '4':
                query += ' ORDER BY a.accommodation_type'
            else:
                query += ' ORDER BY a.id DESC'  # Default sort

            cursor.execute(query, params)
            rows = cursor.fetchall()

        if not rows:
            print(get_text("housing.accommodation.message.no_records_matching", "No records found matching your criteria."))
            return

        # Display results
        print("\n" + get_text("housing.accommodation.message.found_records", "Found {count} record(s):").format(count=len(rows)))
        print("=" * 100)
        print(f"{get_text('housing.accommodation.table.id', 'ID'):<5} {get_text('housing.accommodation.table.student', 'Student'):<10} {get_text('housing.accommodation.table.type', 'Type'):<20} {get_text('housing.accommodation.table.start_date', 'Start Date'):<12} {get_text('housing.accommodation.table.end_date', 'End Date'):<12} {get_text('housing.accommodation.table.status', 'Status'):<10} {get_text('housing.accommodation.table.name', 'Name'):<25}")
        print("-" * 100)

        for row in rows:
            student_name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or get_text("housing.accommodation.label.na", "N/A")
            start_date = row['start_date'] or get_text("housing.accommodation.label.na", "N/A")
            end_date = row['end_date'] or get_text("housing.accommodation.label.na", "N/A")

            print(f"{row['id']:<5} {row['student_id']:<10} {row['accommodation_type'][:20]:<20} "
                  f"{start_date:<12} {end_date:<12} {row['status']:<10} {student_name[:25]:<25}")

        print("=" * 100)

        # Offer detailed view option
        while True:
            detail_view = input("\n" + get_text("housing.accommodation.input.enter_id_for_details", "Enter accommodation ID to view details (or press Enter to return): ")).strip()
            if not detail_view:
                break

            try:
                acc_id = int(detail_view)
                view_accommodation_by_id(acc_id)
            except ValueError:
                print(get_text("housing.accommodation.error.valid_id_number", "Error: Please enter a valid ID number."))

    except Exception as e:
        logging.error(f"Error in view_accommodations: {e}")
        print(get_text("housing.accommodation.error.viewing_accommodations", "Error viewing accommodations: {error}").format(error=e))
