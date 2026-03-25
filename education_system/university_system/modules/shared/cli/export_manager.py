"""
Export manager for CLI system.

Handles data export to various formats (CSV, Excel, PDF, TXT).
"""

from education_system.university_system.modules.shared.cli.imports import (
    logging, sqlite3, csv, datetime, os, DB_PATH, logger, _t,
    log_export, pd, HAS_PANDAS, HAS_REPORTLAB, get_auth, paths
)
from education_system.university_system.modules.shared.cli.student_operations import fetch_student_data

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
        print("5. Return to Main Menu")
        
        choice = input("Enter your choice (1-5): ")
        
        if choice == '1':
            export_to_csv()
        elif choice == '2':
            export_to_excel()
        elif choice == '3':
            export_to_pdf()
        elif choice == '4':
            export_to_txt()
        elif choice == '5':
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
        from education_system.university_system.modules.shared.services.pdf_export import PDFExportManager

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

        print(f"\n\nExport completed successfully!")
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
        from education_system.university_system.modules.shared.services.pdf_export import PDFExportManager

        print("\nLoading export preview...")
        manager = PDFExportManager()
        preview = manager.get_export_preview()

        stats = preview.get("statistics", {})
        print("\n" + "="*50)
        print("         EXPORT PREVIEW")
        print("="*50)
        print(f"\nDatabase Statistics:")
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
    'display_export_menu',
    'display_pdf_export_menu',
    '_run_pdf_export',
    '_show_export_preview',
]
