# import_export.py
# Import/export functionality mixin for AccommodationGUI.

from education_system.post_18.university_system.modules.domain.health.gui.medical_accommodation._common import (
    tk, ttk, messagebox, filedialog,
    datetime, json, csv, threading, sqlite3,
    CLI_AVAILABLE, get_connection, logger,
)

if CLI_AVAILABLE:
    from education_system.post_18.university_system.modules.domain.health.gui.medical_accommodation._common import bulk_import_from_csv, validate_student_id

from education_system.post_18.university_system.modules.domain.health.gui.medical_accommodation.dialogs.export_filter import ExportFilterDialog
from education_system.post_18.university_system.modules.domain.health.gui.medical_accommodation.dialogs.import_result import ImportResultDialog


class ImportExportMixin:
    """Import and export methods for AccommodationGUI."""

    # --- Import Methods ---

    def import_csv(self):
        """Import accommodations from CSV file"""
        if not CLI_AVAILABLE:
            messagebox.showerror("Error", "CLI module not available")
            return

        file_path = filedialog.askopenfilename(
            title="Select CSV file",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if file_path:
            try:
                # Use the original bulk import function
                self.status_var.set("Importing from CSV...")
                self.root.update()

                # Run import in thread to prevent GUI freezing
                thread = threading.Thread(target=self.run_csv_import, args=(file_path,))
                thread.start()

            except Exception as e:
                messagebox.showerror("Error", f"Import failed: {str(e)}")
                self.status_var.set("Import failed")

    def run_csv_import(self, file_path):
        """Run CSV import in background thread"""
        try:
            # Redirect output to capture results
            import io
            import contextlib

            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                bulk_import_from_csv(file_path)

            result = output.getvalue()

            # Show result in main thread
            self.root.after(0, lambda: self.show_import_result(result))

        except Exception as e:
            self.root.after(0, lambda _e=e: messagebox.showerror("Import Error", str(_e)))
        finally:
            self.root.after(0, lambda: self.status_var.set("Ready"))
            self.root.after(0, self.refresh_data)

    def show_import_result(self, result):
        """Show import result"""
        ImportResultDialog(self.root, "CSV Import Results", result)

    def import_json(self):
        """Import accommodations from JSON file"""
        if not CLI_AVAILABLE:
            messagebox.showerror("Error", "CLI module not available")
            return

        file_path = filedialog.askopenfilename(
            title="Select JSON file",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )

        if file_path:
            try:
                self.status_var.set("Importing from JSON...")
                self.root.update()

                thread = threading.Thread(target=self.run_json_import, args=(file_path,))
                thread.start()

            except Exception as e:
                messagebox.showerror("Error", f"Import failed: {str(e)}")
                self.status_var.set("Import failed")

    def run_json_import(self, file_path):
        """Run JSON import in background thread"""
        try:
            success_count = 0
            error_count = 0
            error_details = []

            # Read and validate JSON file
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except json.JSONDecodeError as e:
                self.root.after(0, lambda _e=e: messagebox.showerror("JSON Error", f"Invalid JSON format: {_e}"))
                return
            except Exception as e:
                self.root.after(0, lambda _e=e: messagebox.showerror("File Error", f"Could not read file: {_e}"))
                return

            # Handle both list of records and single record
            if isinstance(data, dict):
                if 'accommodations' in data:
                    records = data['accommodations']
                else:
                    records = [data]
            elif isinstance(data, list):
                records = data
            else:
                self.root.after(0, lambda: messagebox.showerror("Data Error", "JSON must contain a list of records or a single record"))
                return

            # Process each record
            for i, record in enumerate(records):
                try:
                    # Validate required fields
                    student_id = record.get('student_id', '').strip()
                    acc_type = record.get('accommodation_type', '').strip()

                    if not student_id:
                        error_details.append(f"Record {i+1}: Missing student_id")
                        error_count += 1
                        continue

                    if not acc_type:
                        error_details.append(f"Record {i+1}: Missing accommodation_type")
                        error_count += 1
                        continue

                    # Validate student_id format if function exists
                    try:
                        if not validate_student_id(student_id):
                            error_details.append(f"Record {i+1}: Invalid student_id format")
                            error_count += 1
                            continue
                    except NameError as e:
                        logger.debug(f"validate_student_id function not available: {e}")

                    # Validate dates if provided
                    start_date = record.get('start_date')
                    end_date = record.get('end_date')

                    if start_date:
                        try:
                            datetime.strptime(start_date, '%Y-%m-%d')
                        except ValueError:
                            error_details.append(f"Record {i+1}: Invalid start_date format (use YYYY-MM-DD)")
                            error_count += 1
                            continue

                    if end_date:
                        try:
                            datetime.strptime(end_date, '%Y-%m-%d')
                        except ValueError:
                            error_details.append(f"Record {i+1}: Invalid end_date format (use YYYY-MM-DD)")
                            error_count += 1
                            continue

                    # Insert record into database
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    with get_connection() as conn:
                        cursor = conn.cursor()

                        # Check if accommodation already exists for this student
                        cursor.execute('''
                            SELECT id FROM accommodations
                            WHERE student_id = ? AND accommodation_type = ? AND status != 'cancelled'
                        ''', (student_id, acc_type))

                        if cursor.fetchone():
                            error_details.append(f"Record {i+1}: Active accommodation already exists for student {student_id}")
                            error_count += 1
                            continue

                        # Insert new accommodation
                        cursor.execute('''
                            INSERT INTO accommodations
                            (student_id, accommodation_type, description, start_date, end_date,
                             status, notes, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            student_id,
                            acc_type,
                            record.get('description', ''),
                            start_date,
                            end_date,
                            record.get('status', 'pending'),
                            record.get('notes', ''),
                            now, now
                        ))
                        conn.commit()
                        success_count += 1

                except Exception as e:
                    error_details.append(f"Record {i+1}: {str(e)}")
                    error_count += 1

            # Prepare result message
            result_message = "JSON Import Results:\n"
            result_message += f"- Successfully imported: {success_count} records\n"
            result_message += f"- Errors encountered: {error_count} records\n\n"

            if error_details:
                result_message += "Error Details:\n"
                for detail in error_details[:10]:
                    result_message += f"\u2022 {detail}\n"
                if len(error_details) > 10:
                    result_message += f"\u2022 ... and {len(error_details) - 10} more errors\n"

            self.root.after(0, lambda: self.show_import_result(result_message))

        except Exception as e:
            self.root.after(0, lambda _e=e: messagebox.showerror("Import Error", f"Unexpected error: {str(_e)}"))
        finally:
            self.root.after(0, lambda: self.status_var.set("Ready"))
            self.root.after(0, self.refresh_data)

    # --- Export Methods ---

    def export_data(self, format_type):
        """Export accommodations data"""
        if not CLI_AVAILABLE:
            messagebox.showerror("Error", "CLI module not available")
            return

        # Get export filters
        filter_dialog = ExportFilterDialog(self.root)
        if not filter_dialog.result:
            return

        filters = filter_dialog.result

        # Choose save location
        if format_type == 'csv':
            file_path = filedialog.asksaveasfilename(
                title="Export to CSV",
                filetypes=[("CSV files", "*.csv")],
                defaultextension=".csv"
            )
        elif format_type == 'excel':
            file_path = filedialog.asksaveasfilename(
                title="Export to Excel",
                filetypes=[("Excel files", "*.xlsx")],
                defaultextension=".xlsx"
            )
        elif format_type == 'pdf':
            file_path = filedialog.asksaveasfilename(
                title="Export to PDF",
                filetypes=[("PDF files", "*.pdf")],
                defaultextension=".pdf"
            )
        elif format_type == 'json':
            file_path = filedialog.asksaveasfilename(
                title="Export to JSON",
                filetypes=[("JSON files", "*.json")],
                defaultextension=".json"
            )
        else:
            messagebox.showerror("Error", f"Unsupported export format: {format_type}")
            return

        if not file_path:
            return

        try:
            # Get data with filters
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                query = '''
                    SELECT a.*, s.first_name, s.last_name, s.email_address
                    FROM accommodations a
                    LEFT JOIN students s ON a.student_id = s.student_id
                '''

                where_clauses = []
                params = []

                if filters['student_id']:
                    where_clauses.append('a.student_id = ?')
                    params.append(filters['student_id'])

                if filters['accommodation_type']:
                    where_clauses.append('a.accommodation_type = ?')
                    params.append(filters['accommodation_type'])

                if filters['status']:
                    where_clauses.append('a.status = ?')
                    params.append(filters['status'])

                if where_clauses:
                    query += ' WHERE ' + ' AND '.join(where_clauses)

                query += ' ORDER BY a.id DESC'

                cursor.execute(query, params)
                rows = cursor.fetchall()

            # Export based on format
            if format_type == 'csv':
                self.export_to_csv_file(rows, file_path)
            elif format_type == 'excel':
                self.export_to_excel_file(rows, file_path)
            elif format_type == 'pdf':
                self.export_to_pdf_file(rows, file_path)
            elif format_type == 'json':
                self.export_to_json_file(rows, file_path)

            messagebox.showinfo("Success", f"Data exported to {file_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {str(e)}")

    def export_csv(self):
        """Export accommodations to CSV"""
        self.export_data('csv')

    def export_excel(self):
        """Export accommodations to Excel"""
        self.export_data('excel')

    def export_pdf(self):
        """Export accommodations to PDF"""
        self.export_data('pdf')

    def export_json(self):
        """Export accommodations to JSON"""
        self.export_data('json')

    # --- Export File Writers ---

    def export_to_csv_file(self, rows, file_path):
        """Export data to CSV file"""
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
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

    def export_to_excel_file(self, rows, file_path):
        """Export data to Excel file"""
        try:
            import pandas as pd

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
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Accommodations', index=False)

        except ImportError:
            messagebox.showerror("Error", "pandas module not installed. Cannot export to Excel.")
            raise

    def export_to_pdf_file(self, rows, file_path):
        """Export data to PDF file"""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib import colors

            doc = SimpleDocTemplate(file_path, pagesize=letter)
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
            doc.build(elements)

        except ImportError:
            messagebox.showerror("Error", "reportlab module not installed. Cannot export to PDF.")
            raise

    def export_to_json_file(self, rows, file_path):
        """Export data to JSON file"""
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

        with open(file_path, 'w', encoding='utf-8') as json_file:
            json.dump(data, json_file, indent=2)
