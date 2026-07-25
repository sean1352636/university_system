"""
Export manager for CLI system.

Handles data export to various formats (CSV, Excel, PDF, TXT).
"""

from education_system.systems.university.interfaces.cli.shell.imports import (
    logging, sqlite3, csv, datetime, os, DB_PATH, logger, _t,
    log_export, pd, HAS_PANDAS, HAS_REPORTLAB, get_auth, paths
)
from education_system.systems.university.interfaces.cli.shell.database_manager import ValidationError
from education_system.systems.university.interfaces.cli.shell.student_operations import fetch_student_data

if HAS_REPORTLAB:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors

auth = None

def get_db_connection():
    """Get database connection"""
    return sqlite3.connect(DB_PATH)


def get_file_path(file_format, default_filename):
    """Helper function to get file path from user with error handling"""
    while True:
        location_choice = input(f"Where would you like to save the {file_format} file?\n1. Current directory\n2. Custom path\nEnter your choice (1-2): ")

        if location_choice == '1':
            # Use default exports directory
            default_dir = str(paths.EXPORTS_DIR)
            os.makedirs(default_dir, exist_ok=True)
            return os.path.join(default_dir, default_filename)
        elif location_choice == '2':
            # Custom directory
            while True:
                custom_path = input("Enter the full path (including filename): ")
                directory = os.path.dirname(custom_path)

                # Check if directory exists or can be created
                if not directory:  # If no directory specified, use current directory
                    return custom_path

                if not os.path.exists(directory):
                    try_create = input(f"Directory {directory} does not exist. Create it? (y/n): ")
                    if try_create.lower() == 'y':
                        try:
                            os.makedirs(directory, exist_ok=True)
                            return custom_path
                        except OSError as e:
                            print(f"Error creating directory: {e}")
                            continue
                    else:
                        continue
                return custom_path
        else:
            print("Invalid choice. Please enter 1 or 2.")


def export_to_csv():
    global auth

    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to export student records.")
        return

    if not (auth.check_permission('export_data') or auth.check_permission('export_module_data')):
        print("You don't have permission to export student records.")
        return

    try:
        # Fetch student data
        students = fetch_student_data(include_modules=False)

        if not students:
            print("No student records found to export.")
            return

        # Define the default filename
        default_filename = f"student_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        # Get file path from user
        file_path = get_file_path('CSV', default_filename)

        # Define CSV headers based on the student table structure
        headers = [
            'Student ID', 'Email Address', 'Title', 'First Name', 'Middle Name', 'Last Name',
            'Gender', 'Date of Birth', 'Age', 'Course', 'Registration Datetime'
        ]

        # Write to CSV file
        with open(file_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            for student in students:
                writer.writerow(student)

        print(f"Student records successfully exported to {file_path}")

    except (OSError, IOError) as e:
        logging.error(f"Error exporting to CSV: {e}")


def export_to_excel():
    global auth

    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to export student records.")
        return

    if not (auth.check_permission('export_data') or auth.check_permission('export_module_data')):
        print("You don't have permission to export student records.")
        return

    try:
        # Fetch student data
        students = fetch_student_data(include_modules=True)

        if not students:
            print("No student records found to export.")
            return

        # Define the default filename
        default_filename = f"student_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        # Get file path from user
        file_path = get_file_path('Excel', default_filename)

        # Create a pandas Excel writer
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            # Create student dataframe
            student_rows = []
            for student_data in students:
                student = student_data['student']
                student_rows.append({
                    'Student ID': student[0],
                    'Email Address': student[1],
                    'Title': student[2],
                    'First Name': student[3],
                    'Middle Name': student[4],
                    'Last Name': student[5],
                    'Gender': student[6],
                    'Date of Birth': student[7],
                    'Age': student[8],
                    'Course': student[9],
                    'Registration Datetime': student[10]
                })

            # Create student dataframe and write to Excel
            student_df = pd.DataFrame(student_rows)
            student_df.to_excel(writer, sheet_name='Students', index=False)

            # Create modules dataframe
            module_rows = []
            for student_data in students:
                student = student_data['student']
                modules = student_data['modules']

                for module in modules:
                    module_rows.append({
                        'Student ID': student[0],
                        'Student Name': f"{student[3]} {student[5]}",
                        'Module Type': module[0],
                        'Module Code': module[1],
                        'Module Name': module[2]
                    })

            # Create modules dataframe and write to Excel
            module_df = pd.DataFrame(module_rows)
            module_df.to_excel(writer, sheet_name='Modules', index=False)

        print(f"Student records successfully exported to {file_path}")

    except (ValueError, TypeError, ValidationError) as e:
        logging.error(f"Error exporting to Excel: {e}")


def export_to_pdf():
    global auth

    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to export student records.")
        return

    if not (auth.check_permission('export_data') or auth.check_permission('export_module_data')):
        print("You don't have permission to export student records.")
        return

    try:
        # Fetch student data
        students = fetch_student_data(include_modules=True)

        if not students:
            print("No student records found to export.")
            return

        # Define the default filename
        default_filename = f"student_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        # Get file path from user
        file_path = get_file_path('PDF', default_filename)

        # Create a PDF document
        doc = SimpleDocTemplate(file_path, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        # Add title
        title = Paragraph("Student Records", styles['Title'])
        elements.append(title)

        # Process each student
        for student_data in students:
            student = student_data['student']
            modules = student_data['modules']

            # Add student information
            elements.append(Paragraph(f"Student ID: {student[0]}", styles['Heading2']))

            # Student data table
            student_info = [
                ['Field', 'Value'],
                ['Email', student[1]],
                ['Name', f"{student[2]} {student[3]} {student[4]} {student[5]}"],
                ['Gender', student[6]],
                ['Date of Birth', student[7]],
                ['Age', str(student[8])],
                ['Course', student[9]],
                ['Registration Date', student[10]]
            ]

            student_table = Table(student_info, colWidths=[150, 350])
            student_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (1, 0), 12),
                ('BACKGROUND', (0, 1), (1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))

            elements.append(student_table)
            elements.append(Paragraph("Modules:", styles['Heading3']))

            # Module data table
            module_data = [['Type', 'Code', 'Name']]
            for module in modules:
                module_data.append([module[0], module[1], module[2]])

            module_table = Table(module_data, colWidths=[100, 100, 300])
            module_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (2, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (2, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (2, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (2, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (2, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))

            elements.append(module_table)
            elements.append(Paragraph(" ", styles['Normal']))  # Add some space

        # Build the PDF
        doc.build(elements)

        print(f"Student records successfully exported to {file_path}")

    except (ValueError, TypeError, ValidationError) as e:
        logging.error(f"Error exporting to PDF: {e}")


def export_to_txt():
    global auth

    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to export student records.")
        return

    if not (auth.check_permission('export_data') or auth.check_permission('export_module_data')):
        print("You don't have permission to export student records.")
        return

    try:
        # Fetch student data
        students = fetch_student_data(include_modules=True)

        if not students:
            print("No student records found to export.")
            return

        # Define the default filename
        default_filename = f"student_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        # Get file path from user
        file_path = get_file_path('TXT', default_filename)

        # Write to text file
        with open(file_path, 'w') as txtfile:
            txtfile.write("STUDENT RECORDS\n")
            txtfile.write("=" * 60 + "\n\n")

            for student_data in students:
                student = student_data['student']
                modules = student_data['modules']

                txtfile.write(f"Student ID: {student[0]}\n")
                txtfile.write(f"Email Address: {student[1]}\n")
                txtfile.write(f"Title: {student[2]}\n")
                txtfile.write(f"First Name: {student[3]}\n")
                txtfile.write(f"Middle Name: {student[4]}\n")
                txtfile.write(f"Last Name: {student[5]}\n")
                txtfile.write(f"Gender: {student[6]}\n")
                txtfile.write(f"Date of Birth: {student[7]}\n")
                txtfile.write(f"Age: {student[8]}\n")
                txtfile.write(f"Course: {student[9]}\n")
                txtfile.write(f"Registration Datetime: {student[10]}\n\n")

                txtfile.write("Modules:\n")
                txtfile.write("-" * 60 + "\n")
                txtfile.write(f"{'Type':<15} {'Code':<10} {'Name':<35}\n")
                txtfile.write("-" * 60 + "\n")

                for module in modules:
                    txtfile.write(f"{module[0]:<15} {module[1]:<10} {module[2]:<35}\n")

                txtfile.write("\n" + "=" * 60 + "\n\n")

        print(f"Student records successfully exported to {file_path}")

    except (OSError, IOError) as e:
        logging.error(f"Error exporting to TXT: {e}")


def export_to_json():
    global auth

    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to export student records.")
        return

    if not (auth.check_permission('export_data') or auth.check_permission('export_module_data')):
        print("You don't have permission to export student records.")
        return

    try:
        import json

        # Fetch student data
        students = fetch_student_data(include_modules=True)

        if not students:
            print("No student records found to export.")
            return

        # Define the default filename
        default_filename = f"student_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        # Get file path from user
        file_path = get_file_path('JSON', default_filename)

        # Build a list of JSON-serialisable student records
        records = []
        for student_data in students:
            student = student_data['student']
            modules = student_data['modules']
            records.append({
                'student_id': student[0],
                'email_address': student[1],
                'title': student[2],
                'first_name': student[3],
                'middle_name': student[4],
                'last_name': student[5],
                'gender': student[6],
                'date_of_birth': student[7],
                'age': student[8],
                'course': student[9],
                'registration_datetime': student[10],
                'modules': [
                    {'type': module[0], 'code': module[1], 'name': module[2]}
                    for module in modules
                ],
            })

        # Write to JSON file
        with open(file_path, 'w') as jsonfile:
            json.dump(records, jsonfile, indent=4, default=str)

        print(f"Student records successfully exported to {file_path}")

    except (OSError, IOError, ValueError, TypeError) as e:
        logging.error(f"Error exporting to JSON: {e}")


def _list_scheduled_reports(load_fn):
    """Print the currently persisted scheduled report definitions."""
    reports = load_fn()
    if not reports:
        print("No scheduled reports found.")
        return

    print(f"\n{len(reports)} scheduled report(s):")
    for i, report in enumerate(reports, 1):
        cfg = report.get('schedule_config', {})
        print(f"{i}. {report.get('template_name', 'Unnamed')} — "
              f"{cfg.get('frequency', 'n/a')} at {cfg.get('hour', 0):02d}:00 — "
              f"recipients: {len(report.get('recipients', []))} — "
              f"active: {report.get('is_active', True)}")


def _create_scheduled_report(load_fn, save_fn):
    """Prompt for a scheduled report definition and persist it."""
    template_name = input("Report/template name: ").strip()
    if not template_name:
        print("A name is required. Aborting.")
        return

    frequency = input("Frequency (daily/weekly/monthly) [daily]: ").strip().lower() or 'daily'
    if frequency not in ('daily', 'weekly', 'monthly'):
        print("Invalid frequency. Using 'daily'.")
        frequency = 'daily'

    hour_input = input("Hour of day 0-23 [8]: ").strip()
    try:
        hour = int(hour_input) if hour_input else 8
        if not 0 <= hour <= 23:
            raise ValueError
    except ValueError:
        print("Invalid hour. Using 8.")
        hour = 8

    recipients_raw = input("Recipient emails (comma-separated, optional): ").strip()
    recipients = [e.strip() for e in recipients_raw.split(',') if e.strip()]

    # Same schema the enhanced-reporting GUI persists (see
    # enhanced_reporting/mixins/dialogs_mixin.py).
    scheduled_report = {
        'template_name': template_name,
        'schedule_config': {
            'frequency': frequency,
            'hour': hour,
            'enabled': True,
            'conditions': {},
        },
        'recipients': recipients,
        'created_at': datetime.now().isoformat(),
        'last_run': None,
        'run_count': 0,
        'is_active': True,
    }

    reports = load_fn()
    reports.append(scheduled_report)
    save_fn(reports)
    print(f"Scheduled report '{template_name}' created ({frequency} at {hour:02d}:00).")


def display_scheduled_reports_menu():
    """Create/list scheduled reports from the CLI.

    Reuses the enhanced-reporting persistence helpers so definitions land in
    the same store the GUI uses (``data/reports/scheduled_reports.json``).
    """
    global auth

    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to manage scheduled reports.")
        return

    if not (auth.check_permission('export_data') or auth.check_permission('export_module_data')):
        print("You don't have permission to manage scheduled reports.")
        return

    try:
        from education_system.systems.university.interfaces.gui.shell.enhanced_reporting.standalone.system_ops import (
            load_scheduled_reports,
            save_scheduled_reports,
        )
    except Exception as e:  # noqa: BLE001 - backend optional
        print(f"Scheduled reports backend unavailable: {e}")
        return

    while True:
        print("\nScheduled Reports:")
        print("1. List scheduled reports")
        print("2. Create scheduled report")
        print("3. Return to Export Menu")

        choice = input("Enter your choice (1-3): ").strip()

        if choice == '1':
            _list_scheduled_reports(load_scheduled_reports)
        elif choice == '2':
            _create_scheduled_report(load_scheduled_reports, save_scheduled_reports)
        elif choice == '3':
            break
        else:
            print("Invalid choice. Please try again.")


def display_export_menu():
    """Display the export menu and handle user choices"""
    global auth

    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to access export functions.")
        return

    if not (auth.check_permission('export_data') or auth.check_permission('export_module_data')):
        print("You don't have permission to export data.")
        return

    while True:
        print("\nExport Menu:")
        print("1. Export to CSV")
        print("2. Export to Excel")
        print("3. Export to PDF")
        print("4. Export to TXT")
        print("5. Export to JSON")
        print("6. Scheduled Reports")
        print("7. Return to Main Menu")

        choice = input("Enter your choice (1-7): ")

        if choice == '1':
            export_to_csv()
        elif choice == '2':
            export_to_excel()
        elif choice == '3':
            export_to_pdf()
        elif choice == '4':
            export_to_txt()
        elif choice == '5':
            export_to_json()
        elif choice == '6':
            display_scheduled_reports_menu()
        elif choice == '7':
            print("Returning to main menu...")
            break
        else:
            print("Invalid choice. Please try again.")


def display_pdf_export_menu(auth):
    """Display the PDF Database Export menu."""
    print("\n" + "="*60)
    print("           PDF DATABASE EXPORT")
    print("="*60)
    print("Export all database data to a comprehensive PDF report")
    print("with charts, tables, and visualizations.")
    print("="*60)
    print("\n1. Full Export (Data + Charts)")
    print("2. Summary Export (Charts Only)")
    print("3. Data Export (Tables Only)")
    print("4. Preview Export Contents")
    print("5. Return to Main Menu")
    print("="*60)

    while True:
        try:
            choice = input("\nEnter your choice (1-5): ").strip()

            if choice == '1':
                _run_pdf_export(include_data=True, include_charts=True)
            elif choice == '2':
                _run_pdf_export(include_data=False, include_charts=True)
            elif choice == '3':
                _run_pdf_export(include_data=True, include_charts=False)
            elif choice == '4':
                _show_export_preview()
            elif choice == '5':
                print("Returning to main menu...")
                break
            else:
                print("Invalid choice. Please enter a number between 1 and 5.")

        except KeyboardInterrupt:
            print("\n\nExport cancelled.")
            break
        except (ValueError, TypeError, ValidationError) as e:
            print(f"Error: {e}")


def _run_pdf_export(include_data: bool = True, include_charts: bool = True):
    """Run the PDF export with progress display."""
    try:
        from education_system.systems.university.services.pdf_export import PDFExportManager

        print("\nInitializing PDF export...")
        manager = PDFExportManager()

        # Custom filename option
        custom_name = input("Enter custom filename (or press Enter for default): ").strip()
        output_filename = custom_name if custom_name else None

        # Max rows option
        max_rows_input = input("Max rows per table [50]: ").strip()
        max_rows = int(max_rows_input) if max_rows_input else 50

        def progress_callback(message, percent):
            bar_len = 30
            filled = int(bar_len * percent / 100)
            bar = "=" * filled + "-" * (bar_len - filled)
            print(f"\r[{bar}] {percent:3d}% - {message:<40}", end="", flush=True)

        print("\nStarting export...")
        output_path = manager.export_full_database(
            output_filename=output_filename,
            include_data=include_data,
            include_charts=include_charts,
            max_rows_per_table=max_rows,
            progress_callback=progress_callback,
        )

        print("\n\nExport completed successfully!")
        print(f"PDF saved to: {output_path}")
        input("\nPress Enter to continue...")

    except ImportError as e:
        print(f"\nError: PDF export module not available: {e}")
        print("Please ensure all dependencies are installed.")
        input("Press Enter to continue...")
    except (ValueError, TypeError, ValidationError) as e:
        print(f"\nExport failed: {e}")
        input("Press Enter to continue...")


def _show_export_preview():
    """Show a preview of what will be exported."""
    try:
        from education_system.systems.university.services.pdf_export import PDFExportManager

        print("\nLoading export preview...")
        manager = PDFExportManager()
        preview = manager.get_export_preview()

        stats = preview.get("statistics", {})
        print("\n" + "="*50)
        print("         EXPORT PREVIEW")
        print("="*50)
        print("\nDatabase Statistics:")
        print(f"  Total Tables: {stats.get('total_tables', 0)}")
        print(f"  Total Records: {stats.get('total_records', 0):,}")
        print(f"  Tables with Data: {stats.get('tables_with_data', 0)}")
        print(f"  Empty Tables: {stats.get('empty_tables', 0)}")
        print(f"\nEstimated Pages: ~{preview.get('estimated_pages', 0)}")

        print("\nData Categories:")
        for category, info in preview.get("categories", {}).items():
            table_count = info.get("table_count", 0)
            total_rows = sum(t.get("rows", 0) for t in info.get("tables", []))
            print(f"  {category}: {table_count} tables, {total_rows:,} records")

        print("\nTop Tables by Size:")
        largest = stats.get("largest_tables", [])[:10]
        for table_name, count in largest:
            display_name = table_name.replace("_", " ").title()[:30]
            print(f"  {display_name}: {count:,} records")

        print("="*50)
        input("\nPress Enter to continue...")

    except ImportError as e:
        print(f"\nError: PDF export module not available: {e}")
        input("Press Enter to continue...")
    except (ValueError, TypeError, ValidationError) as e:
        print(f"\nError loading preview: {e}")
        input("Press Enter to continue...")


__all__ = [
    'get_file_path',
    'export_to_csv',
    'export_to_excel',
    'export_to_pdf',
    'export_to_txt',
    'export_to_json',
    'display_export_menu',
    'display_scheduled_reports_menu',
    'display_pdf_export_menu',
    '_run_pdf_export',
    '_show_export_preview',
]
