import csv
import os
import json
import logging
from datetime import datetime

from education_system.university_system.modules.domain.housing.services.accommodation._common import (
    sqlite3, DB_PATH, ACCOMMODATION_LOG_PATH, pd, canvas,
    get_auth, backup_before_operation, get_text,
)

# Conditional reportlab imports
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
except ImportError:
    pass

from education_system.university_system.modules.domain.housing.services.accommodation.db import init_accommodation_db
from education_system.university_system.modules.domain.housing.services.accommodation.validation import (
    validate_date, check_conflict, validate_student_id,
)
from education_system.university_system.modules.domain.housing.services.accommodation.audit import log_action


def bulk_import_from_csv(filepath):
    """Bulk register students from a CSV file with enhanced validation and error handling."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_bulk_import", "You must be logged in to perform bulk imports."))
        return

    if not auth.check_permission('manage_accommodations') or not auth.check_permission('batch_operations'):
        print(get_text("housing.accommodation.auth.no_permission_bulk_import", "You don't have permission to perform bulk imports."))
        return

    # Backup before making changes
    backup_before_operation('accommodation_bulk_import')

    init_accommodation_db()
    if not os.path.exists(filepath):
        print(get_text("housing.accommodation.error.file_not_found", "Error: File not found."))
        return

    print(get_text("housing.accommodation.bulk.beginning_import", "Beginning bulk import from {filepath}").format(filepath=filepath))
    success_count = 0
    error_count = 0
    conflict_count = 0

    try:
        # Track imported records for logging
        import_log = []

        with open(filepath, newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            required_fields = ['student_id', 'accommodation_type']

            # Validate CSV headers
            headers = reader.fieldnames
            if not all(field in headers for field in required_fields):
                print(get_text("housing.accommodation.error.csv_missing_columns", "Error: CSV must contain columns: {columns}").format(columns=', '.join(required_fields)))
                return

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            for row_num, row in enumerate(reader, start=2):  # Start at 2 to account for header row
                try:
                    # Extract and validate required fields
                    student_id = row.get('student_id', '').strip()
                    typ = row.get('accommodation_type', '').strip()

                    if not student_id or not typ:
                        error_count += 1
                        import_log.append(f"Row {row_num}: Missing required fields")
                        continue

                    # Validate student exists
                    if not validate_student_id(student_id):
                        error_count += 1
                        import_log.append(f"Row {row_num}: Student ID {student_id} not found")
                        continue

                    # Extract optional fields
                    desc = row.get('description', '').strip() or None
                    sd = row.get('start_date', '').strip() or None
                    ed = row.get('end_date', '').strip() or None
                    notes = row.get('notes', '').strip() or None
                    status = row.get('status', '').strip() or 'active'

                    # Validate dates
                    if sd:
                        valid, error = validate_date(sd)
                        if not valid:
                            error_count += 1
                            import_log.append(f"Row {row_num}: Invalid start date - {error}")
                            continue

                    if ed:
                        valid, error = validate_date(ed)
                        if not valid:
                            error_count += 1
                            import_log.append(f"Row {row_num}: Invalid end date - {error}")
                            continue

                    # Check date range
                    if sd and ed:
                        try:
                            start = datetime.fromisoformat(sd)
                            end = datetime.fromisoformat(ed)
                            if end <= start:
                                error_count += 1
                                import_log.append(f"Row {row_num}: End date must be after start date")
                                continue
                        except ValueError:
                            error_count += 1
                            import_log.append(f"Row {row_num}: Date format error")
                            continue

                    # Check for conflicts
                    if check_conflict(student_id, typ, sd, ed):
                        conflict_count += 1
                        import_log.append(f"Row {row_num}: Conflict for student {student_id}, type {typ}")
                        # Continue with import if configured to do so
                        # In a real system, you might want to make this configurable

                    # Insert into database
                    with sqlite3.connect(DB_PATH) as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO accommodations
                            (student_id, accommodation_type, description, start_date, end_date, status, notes, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (student_id, typ, desc, sd, ed, status, notes, now, now))
                        aid = cursor.lastrowid
                        conn.commit()

                        log_action('bulk_add', aid, f"Bulk import: {typ} for {student_id}")
                        success_count += 1
                        import_log.append(f"Row {row_num}: Successfully added {typ} for {student_id}")

                except sqlite3.Error as db_e:
                    error_count += 1
                    import_log.append(f"Row {row_num}: Database error - {db_e}")
                    logging.error(f"Bulk import DB error for row {row_num}: {db_e}")
                    continue
                except Exception as row_e:
                    error_count += 1
                    import_log.append(f"Row {row_num}: Unexpected error - {row_e}")
                    logging.error(f"Bulk import error for row {row_num}: {row_e}")
                    continue

        # Write import log to file
        log_filename = f"accommodation_import_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        log_path = os.path.join(ACCOMMODATION_LOG_PATH, log_filename)
        try:
            with open(log_path, 'w') as log_file:
                log_file.write(f"Import from {filepath} at {now}\n")
                log_file.write(f"Summary: {success_count} succeeded, {error_count} failed, {conflict_count} conflicts\n\n")
                log_file.write("Details:\n")
                for entry in import_log:
                    log_file.write(f"{entry}\n")
            print(get_text("housing.accommodation.bulk.log_saved", "Import log saved to {path}").format(path=log_path))
        except Exception as log_e:
            logging.error(f"Error writing import log: {log_e}")
            print(get_text("housing.accommodation.warning.could_not_save_log", "Warning: Could not save import log: {error}").format(error=log_e))

        print(get_text("housing.accommodation.bulk.complete", "Bulk import complete. {count} records imported successfully.").format(count=success_count))
        if error_count > 0:
            print(get_text("housing.accommodation.bulk.errors", "{count} records had errors and were not imported.").format(count=error_count))
        if conflict_count > 0:
            print(get_text("housing.accommodation.bulk.conflicts", "{count} records had conflicts but were imported anyway.").format(count=conflict_count))

    except Exception as e:
        logging.error(f"Bulk import error: {e}")
        print(get_text("housing.accommodation.error.bulk_import", "Error during bulk import: {error}").format(error=e))
        print(get_text("housing.accommodation.warning.partial_complete", "Operation may be partially complete. Check logs for details."))


def export_accommodations():
    """Export accommodation data to various formats."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_export", "You must be logged in to export accommodations."))
        return

    if not auth.check_permission('export_data'):
        print(get_text("housing.accommodation.auth.no_permission_export", "You don't have permission to export accommodations."))
        return

    init_accommodation_db()
    try:
        # Get export format
        print(get_text("housing.accommodation.export.choose_format", "Choose export format:"))
        print("1. CSV")
        print("2. Excel")
        print("3. PDF")
        print("4. JSON")
        print("5. " + get_text("housing.accommodation.menu.cancel", "Cancel"))

        format_choice = input(get_text("housing.accommodation.input.enter_choice_1_5", "Enter choice (1-5): ")).strip()
        if format_choice == '5':
            print(get_text("housing.accommodation.message.export_cancelled", "Export cancelled."))
            return

        # Get export filters
        print("\n" + get_text("housing.accommodation.export.filters", "Export filters (leave blank for all records):"))
        student_id = input(get_text("housing.accommodation.input.student_id_optional", "Student ID (optional): ")).strip() or None
        acc_type = input(get_text("housing.accommodation.input.type_optional", "Accommodation type (optional): ")).strip() or None
        status = input(get_text("housing.accommodation.input.status_optional", "Status (active/pending/suspended/expired) (optional): ")).strip() or None

        # Build query based on filters
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = '''
                SELECT a.*, s.first_name, s.last_name, s.email_address
                FROM accommodations a
                LEFT JOIN students s ON a.student_id = s.student_id
            '''

            where_clauses = []
            params = []

            if student_id:
                where_clauses.append('a.student_id = ?')
                params.append(student_id)

            if acc_type:
                where_clauses.append('a.accommodation_type = ?')
                params.append(acc_type)

            if status:
                where_clauses.append('a.status = ?')
                params.append(status)

            if where_clauses:
                query += ' WHERE ' + ' AND '.join(where_clauses)

            query += ' ORDER BY a.id'

            cursor.execute(query, params)
            rows = cursor.fetchall()

        if not rows:
            print(get_text("housing.accommodation.message.no_records_matching", "No records found matching your criteria."))
            return

        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename_base = f"accommodation_export_{timestamp}"

        # Export based on selected format
        if format_choice == '1':  # CSV
            filename = filename_base + ".csv"
            export_to_csv(rows, filename)
        elif format_choice == '2':  # Excel
            if not pd:
                print(get_text("housing.accommodation.error.pandas_not_installed", "Error: pandas module not installed. Cannot export to Excel."))
                return
            filename = filename_base + ".xlsx"
            export_to_excel(rows, filename)
        elif format_choice == '3':  # PDF
            if not canvas:
                print(get_text("housing.accommodation.error.reportlab_not_installed", "Error: reportlab module not installed. Cannot export to PDF."))
                return
            filename = filename_base + ".pdf"
            export_to_pdf(rows, filename)
        elif format_choice == '4':  # JSON
            filename = filename_base + ".json"
            export_to_json(rows, filename)
        else:
            print(get_text("housing.accommodation.error.invalid_format_choice", "Invalid format choice."))
            return

    except Exception as e:
        logging.error(f"Error exporting accommodations: {e}")
        print(get_text("housing.accommodation.error.exporting", "Error exporting accommodations: {error}").format(error=e))


def export_to_csv(rows, filename):
    """Export accommodation data to CSV file."""
    try:
        # Get save location
        path = input(get_text("housing.accommodation.input.enter_save_path", "Enter save path (or press Enter for current directory): ")).strip()
        if path:
            full_path = os.path.join(path, filename)
        else:
            full_path = filename

        # Ensure directory exists
        directory = os.path.dirname(full_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        # Extract data and write to CSV
        with open(full_path, 'w', newline='') as csvfile:
            headers = [
                'ID', 'Student ID', 'Student Name', 'Email', 'Accommodation Type',
                'Description', 'Start Date', 'End Date', 'Status', 'Notes',
                'Created At', 'Updated At'
            ]

            writer = csv.writer(csvfile)
            writer.writerow(headers)

            for row in rows:
                student_name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or 'N/A'
                writer.writerow([
                    row['id'],
                    row['student_id'],
                    student_name,
                    row['email_address'] or 'N/A',
                    row['accommodation_type'],
                    row['description'] or '',
                    row['start_date'] or '',
                    row['end_date'] or '',
                    row['status'],
                    row['notes'] or '',
                    row['created_at'],
                    row['updated_at']
                ])

        print(get_text("housing.accommodation.success.data_exported", "Data exported to {path}").format(path=full_path))
    except Exception as e:
        logging.error(f"Error exporting to CSV: {e}")
        print(get_text("housing.accommodation.error.exporting_csv", "Error exporting to CSV: {error}").format(error=e))


def export_to_excel(rows, filename):
    """Export accommodation data to Excel file."""
    try:
        # Check for pandas
        if not pd:
            print(get_text("housing.accommodation.error.pandas_not_installed", "Error: pandas module not installed. Cannot export to Excel."))
            return

        # Get save location
        path = input(get_text("housing.accommodation.input.enter_save_path", "Enter save path (or press Enter for current directory): ")).strip()
        if path:
            full_path = os.path.join(path, filename)
        else:
            full_path = filename

        # Ensure directory exists
        directory = os.path.dirname(full_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        # Convert data to DataFrame
        data = []
        for row in rows:
            student_name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or 'N/A'
            data.append({
                'ID': row['id'],
                'Student ID': row['student_id'],
                'Student Name': student_name,
                'Email': row['email_address'] or 'N/A',
                'Accommodation Type': row['accommodation_type'],
                'Description': row['description'] or '',
                'Start Date': row['start_date'] or '',
                'End Date': row['end_date'] or '',
                'Status': row['status'],
                'Notes': row['notes'] or '',
                'Created At': row['created_at'],
                'Updated At': row['updated_at']
            })

        df = pd.DataFrame(data)

        # Write to Excel
        with pd.ExcelWriter(full_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Accommodations', index=False)

        print(get_text("housing.accommodation.success.data_exported", "Data exported to {path}").format(path=full_path))
    except Exception as e:
        logging.error(f"Error exporting to Excel: {e}")
        print(get_text("housing.accommodation.error.exporting_excel", "Error exporting to Excel: {error}").format(error=e))


def export_to_pdf(rows, filename):
    """Export accommodation data to PDF file."""
    try:
        # Check for reportlab
        if not canvas:
            print(get_text("housing.accommodation.error.reportlab_not_installed", "Error: reportlab module not installed. Cannot export to PDF."))
            return

        # Get save location
        path = input(get_text("housing.accommodation.input.enter_save_path", "Enter save path (or press Enter for current directory): ")).strip()
        if path:
            full_path = os.path.join(path, filename)
        else:
            full_path = filename

        # Ensure directory exists
        directory = os.path.dirname(full_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        # Create PDF document
        doc = SimpleDocTemplate(full_path, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        # Add title
        title = Paragraph("Accommodation Records", styles['Title'])
        elements.append(title)

        # Add timestamp
        timestamp = Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal'])
        elements.append(timestamp)
        elements.append(Paragraph("<br/>", styles['Normal']))

        # Add summary
        elements.append(Paragraph(f"Total Records: {len(rows)}", styles['Heading2']))
        elements.append(Paragraph("<br/>", styles['Normal']))

        # Add table data
        table_data = [['ID', 'Student', 'Accommodation Type', 'Dates', 'Status']]

        for row in rows:
            student_name = f"{row['student_id']} - {row['first_name'] or ''} {row['last_name'] or ''}".strip()
            dates = f"Start: {row['start_date'] or 'N/A'}\nEnd: {row['end_date'] or 'N/A'}"

            table_data.append([
                str(row['id']),
                student_name,
                row['accommodation_type'],
                dates,
                row['status']
            ])

        # Create table
        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        elements.append(table)
        elements.append(Paragraph("<br/><br/>", styles['Normal']))

        # Add detailed records
        elements.append(Paragraph("Detailed Records", styles['Heading2']))

        for row in rows:
            student_name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or 'N/A'

            elements.append(Paragraph(f"<br/><b>Record ID: {row['id']}</b>", styles['Normal']))
            elements.append(Paragraph(f"Student: {row['student_id']} - {student_name}", styles['Normal']))
            elements.append(Paragraph(f"Type: {row['accommodation_type']}", styles['Normal']))
            elements.append(Paragraph(f"Description: {row['description'] or 'N/A'}", styles['Normal']))
            elements.append(Paragraph(f"Start Date: {row['start_date'] or 'N/A'}", styles['Normal']))
            elements.append(Paragraph(f"End Date: {row['end_date'] or 'N/A'}", styles['Normal']))
            elements.append(Paragraph(f"Status: {row['status']}", styles['Normal']))

            if row['notes']:
                elements.append(Paragraph(f"Notes: {row['notes']}", styles['Normal']))

            elements.append(Paragraph(f"Created: {row['created_at']}", styles['Normal']))
            elements.append(Paragraph(f"Updated: {row['updated_at']}", styles['Normal']))
            elements.append(Paragraph("<br/>", styles['Normal']))

        # Build the PDF
        doc.build(elements)
        print(get_text("housing.accommodation.success.data_exported", "Data exported to {path}").format(path=full_path))

    except Exception as e:
        logging.error(f"Error exporting to PDF: {e}")
        print(get_text("housing.accommodation.error.exporting_pdf", "Error exporting to PDF: {error}").format(error=e))


def export_to_json(rows, filename):
    """Export accommodation data to JSON file."""
    try:
        # Get save location
        path = input(get_text("housing.accommodation.input.enter_save_path", "Enter save path (or press Enter for current directory): ")).strip()
        if path:
            full_path = os.path.join(path, filename)
        else:
            full_path = filename

        # Ensure directory exists
        directory = os.path.dirname(full_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        # Convert to list of dictionaries
        data = []
        for row in rows:
            data.append({
                'id': row['id'],
                'student_id': row['student_id'],
                'student_name': f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or None,
                'email': row['email_address'],
                'accommodation_type': row['accommodation_type'],
                'description': row['description'],
                'start_date': row['start_date'],
                'end_date': row['end_date'],
                'status': row['status'],
                'notes': row['notes'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            })

        # Write to JSON file
        with open(full_path, 'w') as json_file:
            json.dump(data, json_file, indent=2)

        print(get_text("housing.accommodation.success.data_exported", "Data exported to {path}").format(path=full_path))
    except Exception as e:
        logging.error(f"Error exporting to JSON: {e}")
        print(get_text("housing.accommodation.error.exporting_json", "Error exporting to JSON: {error}").format(error=e))


def import_from_json():
    """Import accommodations from a JSON file."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_import", "You must be logged in to import accommodations."))
        return

    if not auth.check_permission('manage_accommodations') or not auth.check_permission('batch_operations'):
        print(get_text("housing.accommodation.auth.no_permission_import", "You don't have permission to import accommodations."))
        return

    # Backup before making changes
    backup_before_operation('accommodation_import')

    init_accommodation_db()
    try:
        # Get file path
        file_path = input(get_text("housing.accommodation.input.enter_json_path", "Enter path to JSON file: ")).strip()
        if not os.path.exists(file_path):
            print(get_text("housing.accommodation.error.file_not_found", "Error: File not found."))
            return

        # Read and parse JSON file
        with open(file_path, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                print(get_text("housing.accommodation.error.invalid_json_format", "Error: Invalid JSON format - {error}").format(error=e))
                return

        if not isinstance(data, list):
            print(get_text("housing.accommodation.error.json_must_be_list", "Error: JSON file must contain a list of accommodation records."))
            return

        # Process records
        success_count = 0
        error_count = 0

        for i, record in enumerate(data):
            try:
                # Validate required fields
                student_id = record.get('student_id')
                acc_type = record.get('accommodation_type')

                if not student_id or not acc_type:
                    error_count += 1
                    print(f"Error: Record {i+1} - Missing required fields")
                    continue

                # Check if student exists
                if not validate_student_id(student_id):
                    error_count += 1
                    print(f"Error: Record {i+1} - Student ID {student_id} not found")
                    continue

                # Extract other fields
                description = record.get('description')
                start_date = record.get('start_date')
                end_date = record.get('end_date')
                status = record.get('status', 'active')
                notes = record.get('notes')

                # Validate dates
                if start_date:
                    valid, error = validate_date(start_date)
                    if not valid:
                        error_count += 1
                        print(f"Error: Record {i+1} - Invalid start date - {error}")
                        continue

                if end_date:
                    valid, error = validate_date(end_date)
                    if not valid:
                        error_count += 1
                        print(f"Error: Record {i+1} - Invalid end date - {error}")
                        continue

                # Check for conflicts
                if check_conflict(student_id, acc_type, start_date, end_date):
                    print(f"Warning: Record {i+1} - Conflict for student {student_id}, type {acc_type}")

                # Insert record
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                with sqlite3.connect(DB_PATH) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO accommodations
                        (student_id, accommodation_type, description, start_date, end_date, status, notes, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (student_id, acc_type, description, start_date, end_date, status, notes, now, now))

                    aid = cursor.lastrowid
                    conn.commit()

                    log_action('import', aid, f"Imported from JSON: {acc_type} for {student_id}")
                    success_count += 1

            except Exception as rec_e:
                error_count += 1
                logging.error(f"Error importing record {i+1}: {rec_e}")
                print(f"Error: Record {i+1} - {rec_e}")

        print("\n" + get_text("housing.accommodation.json.import_complete", "Import complete: {success} records imported successfully, {errors} errors.").format(success=success_count, errors=error_count))

    except Exception as e:
        logging.error(f"Error importing from JSON: {e}")
        print(get_text("housing.accommodation.error.importing_json", "Error importing from JSON: {error}").format(error=e))
