import logging
from datetime import datetime, timedelta

from education_system.university_system.modules.domain.campus.housing.services.accommodation._common import (
    sqlite3, DB_PATH, TEMPLATES_TABLE, get_auth, get_current_user,
    backup_before_operation, get_text,
)
from education_system.university_system.modules.domain.campus.housing.services.accommodation.db import init_accommodation_db
from education_system.university_system.modules.domain.campus.housing.services.accommodation.validation import (
    get_accommodation_types, validate_student_id, check_conflict,
)
from education_system.university_system.modules.domain.campus.housing.services.accommodation.audit import log_action
from education_system.university_system.modules.domain.campus.housing.services.accommodation.notifications import notify_student
from education_system.university_system.modules.domain.campus.housing.services.accommodation.crud import view_accommodation_by_id


def save_template():
    """Save current inputs as a reusable template with improved validation."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_save_template", "You must be logged in to save templates."))
        return

    if not auth.check_permission('manage_accommodations'):
        print(get_text("housing.accommodation.auth.no_permission_save_template", "You don't have permission to save templates."))
        return

    init_accommodation_db()
    try:
        # Get template name with validation
        while True:
            name = input(get_text("housing.accommodation.input.template_name", "Template name: ")).strip()
            if not name:
                print(get_text("housing.accommodation.error.template_name_required", "Error: Template name is required."))
                continue

            # Check if template already exists
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM [" + TEMPLATES_TABLE + "] WHERE name = ?", (name,))
                if cursor.fetchone():
                    overwrite = input(get_text("housing.accommodation.input.template_overwrite", "Template '{name}' already exists. Overwrite? (y/n): ").format(name=name))
                    if overwrite.lower() != 'y':
                        continue
            break

        # Get accommodation type
        available_types = get_accommodation_types()
        print("\n" + get_text("housing.accommodation.label.available_types", "Available accommodation types:"))
        for i, type_name in enumerate(available_types):
            print(f"{i+1}. {type_name}")

        while True:
            type_choice = input("\n" + get_text("housing.accommodation.input.select_type", "Select type (number or enter custom): ")).strip()
            if type_choice.isdigit() and 1 <= int(type_choice) <= len(available_types):
                typ = available_types[int(type_choice)-1]
                break
            elif type_choice:
                typ = type_choice
                break
            else:
                print(get_text("housing.accommodation.error.type_required", "Error: Accommodation type is required."))

        desc = input(get_text("housing.accommodation.input.description_optional", "Description [optional]: ")).strip() or None

        # Get offset days with validation
        while True:
            offset_str = input(get_text("housing.accommodation.input.start_offset_days", "Start offset days from today: ")).strip()
            try:
                offset = int(offset_str)
                if offset < 0:
                    print(get_text("housing.accommodation.error.offset_non_negative", "Error: Offset must be a non-negative number."))
                    continue
                break
            except ValueError:
                print(get_text("housing.accommodation.error.valid_number", "Error: Please enter a valid number."))

        # Get duration days with validation
        while True:
            duration_str = input(get_text("housing.accommodation.input.duration_days", "Duration days: ")).strip()
            try:
                duration = int(duration_str)
                if duration <= 0:
                    print(get_text("housing.accommodation.error.duration_positive", "Error: Duration must be a positive number."))
                    continue
                break
            except ValueError:
                print(get_text("housing.accommodation.error.valid_number", "Error: Please enter a valid number."))

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        user = get_current_user()

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO [" + TEMPLATES_TABLE + "]"
                " (name, accommodation_type, description, start_offset_days, duration_days, created_by, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (name, typ, desc, offset, duration, user, now, now))
            conn.commit()

        print(get_text("housing.accommodation.success.template_saved", "Template '{name}' saved successfully.").format(name=name))
        log_action('save_template', None, f"Saved template: {name} for {typ}")

    except Exception as e:
        logging.error(f"Error saving template: {e}")
        print(get_text("housing.accommodation.error.saving_template", "Error saving template: {error}").format(error=e))


def apply_template():
    """Apply a saved template to a student with improved validation and error handling."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_apply_template", "You must be logged in to apply templates."))
        return

    if not auth.check_permission('manage_accommodations'):
        print(get_text("housing.accommodation.auth.no_permission_apply_template", "You don't have permission to apply templates."))
        return

    # Backup before making changes
    backup_before_operation('accommodation_apply_template')

    init_accommodation_db()
    try:
        # List available templates
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, accommodation_type FROM [" + TEMPLATES_TABLE + "] ORDER BY name")
            templates = cursor.fetchall()

        if not templates:
            print(get_text("housing.accommodation.error.no_templates", "No templates available. Please create a template first."))
            return

        print("\n" + get_text("housing.accommodation.label.available_templates", "Available templates:"))
        for i, (name, atype) in enumerate(templates):
            print(f"{i+1}. {name} ({atype})")

        # Get template selection
        while True:
            choice = input("\n" + get_text("housing.accommodation.input.select_template", "Select template (number or name): ")).strip()
            if choice.isdigit() and 1 <= int(choice) <= len(templates):
                name = templates[int(choice)-1][0]
                break
            else:
                # Check if they entered the name directly
                name = choice
                cursor.execute("SELECT COUNT(*) FROM [" + TEMPLATES_TABLE + "] WHERE name = ?", (name,))
                if cursor.fetchone()[0] > 0:
                    break
                print(get_text("housing.accommodation.error.invalid_template_selection", "Error: Invalid template selection."))

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

        # Get the template details
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT accommodation_type, description, start_offset_days, duration_days"
                " FROM [" + TEMPLATES_TABLE + "] WHERE name = ?",
                (name,))

            template = cursor.fetchone()
            if not template:
                print(get_text("housing.accommodation.error.template_not_found", "Error: Template '{name}' not found.").format(name=name))
                return

            typ, desc, offset, duration = template

            # Calculate dates
            sd_date = datetime.now() + timedelta(days=offset)
            ed_date = sd_date + timedelta(days=duration)
            sd = sd_date.strftime('%Y-%m-%d')
            ed = ed_date.strftime('%Y-%m-%d')

            # Check for conflicts
            if check_conflict(student_id, typ, sd, ed):
                print(get_text("housing.accommodation.warning.overlap_existing", "Warning: This accommodation overlaps an existing record."))
                cont = input(get_text("housing.accommodation.input.continue_anyway", "Continue anyway? (y/n): "))
                if cont.lower() != 'y':
                    return

            # Insert accommodation
            now_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            status = 'active'  # Default status
            notes = f"Applied from template: {name}"

            cursor.execute('''
                INSERT INTO accommodations
                (student_id, accommodation_type, description, start_date, end_date, status, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, typ, desc, sd, ed, status, notes, now_ts, now_ts))

            aid = cursor.lastrowid
            conn.commit()

        print(get_text("housing.accommodation.success.template_applied", "Template '{name}' applied successfully to student {student_id}.").format(name=name, student_id=student_id))
        log_action('apply_template', aid, f"Applied template {name} to student {student_id}")
        notify_student(student_id, 'Accommodation Template Applied',
                      f"Template '{name}' for {typ} has been applied to your account.")

        # Display the added accommodation details
        view_accommodation_by_id(aid)

    except Exception as e:
        logging.error(f"Error applying template: {e}")
        print(get_text("housing.accommodation.error.applying_template", "Error applying template: {error}").format(error=e))
