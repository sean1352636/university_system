from education_system.university_system.modules.shared.utils.document_manager._common import (
    os, csv, datetime, timedelta, sqlite3,
    get_connection, _t,
)
from education_system.university_system.core import paths as _paths

_EXPORT_DIR = str(_paths.EXPORTS_DIR / "documents")
os.makedirs(_EXPORT_DIR, exist_ok=True)


class ImportExportMixin:
    def bulk_import_documents(self):
        """Bulk import documents from CSV/Excel"""
        print("\n📥 BULK IMPORT DOCUMENTS")
        print("1. Import from CSV")
        print("2. Import from Excel")
        print("3. Download Import Template")
        print("4. Return to Main Menu")

        choice = input("\nChoose option (1-4): ").strip()

        if choice == '1':
            self.import_from_csv()
        elif choice == '2':
            self.import_from_excel()
        elif choice == '3':
            self.download_import_template()

    def import_from_csv(self):
        """Import documents from CSV file"""
        try:
            file_path = input("Enter CSV file path: ").strip()

            if not os.path.exists(file_path):
                print(_t("shared.utils.document_manager.file_not_found", default="File not found."))
                return

            with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)

                success_count = 0
                error_count = 0

                for row in reader:
                    student_id = row.get('student_id', '').strip()
                    document_type = row.get('document_type', '').strip()
                    doc_file_path = row.get('file_path', '').strip()

                    if student_id and document_type and doc_file_path:
                        result = self.validate_and_import_document(student_id, document_type, doc_file_path)
                        if result:
                            success_count += 1
                        else:
                            error_count += 1
                    else:
                        error_count += 1

                print(f"\n✅ Import complete:")
                print(f"   Successful: {success_count}")
                print(f"   Errors: {error_count}")

        except Exception as e:
            print(f"Import error: {e}")

    def validate_and_import_document(self, student_id, document_type, file_path):
        """Validate and import a single document"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Verify student exists
            cursor.execute('SELECT student_id FROM students WHERE student_id = ?', (student_id,))
            if not cursor.fetchone():
                print(f"  ✗ Student not found: {student_id}")
                conn.close()
                return False

            # Get document type ID
            cursor.execute('SELECT type_id FROM document_types WHERE type_name = ? AND is_active = 1', (document_type,))
            type_result = cursor.fetchone()

            if not type_result:
                print(f"  ✗ Invalid document type: {document_type}")
                conn.close()
                return False

            type_id = type_result[0]

            # Verify file exists
            if not os.path.exists(file_path):
                print(f"  ✗ File not found: {file_path}")
                conn.close()
                return False

            # Insert document
            original_filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            upload_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            INSERT INTO documents
            (source_type, owner_id, type_id, file_path, original_filename, upload_date,
             verification_status, version_number, uploaded_by, file_size, workflow_status)
            VALUES ('student', ?, ?, ?, ?, ?, 'Pending', 1, 'bulk_import', ?, 'submitted')
            ''', (student_id, type_id, file_path, original_filename, upload_date, file_size))

            conn.commit()
            conn.close()

            print(f"  ✓ Imported: {original_filename} for {student_id}")
            return True

        except sqlite3.Error as e:
            print(f"  ✗ Database error: {e}")
            return False

    def import_from_excel(self):
        """Import documents from Excel spreadsheet"""
        try:
            print("\n📥 IMPORT FROM EXCEL")

            file_path = input("Enter Excel file path: ").strip()

            if not os.path.exists(file_path):
                print(_t("shared.utils.document_manager.file_not_found", default="File not found."))
                return

            print("\nNote: This feature requires openpyxl library.")
            print("For now, please convert your Excel file to CSV and use the CSV import option.")

            # Placeholder for future Excel import implementation
            # Would need: import openpyxl

        except Exception as e:
            print(f"Import error: {e}")

    def download_import_template(self):
        """Download a template file for bulk import"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = os.path.join(_EXPORT_DIR, f"import_template_{timestamp}.csv")

            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['student_id', 'document_type', 'file_path', 'expiry_date',
                               'tags', 'priority', 'notes'])
                writer.writerow(['STU001', 'Birth Certificate', '/path/to/file.pdf',
                               '2025-12-31', 'verified,urgent', '5', 'Sample entry'])

            print(f"✅ Template downloaded: {filename}")
            print("\nTemplate Instructions:")
            print("- student_id: Student ID from your system")
            print("- document_type: Exact name of document type")
            print("- file_path: Full path to the document file")
            print("- expiry_date: Format YYYY-MM-DD (optional)")
            print("- tags: Comma-separated tags (optional)")
            print("- priority: Number 0-5 (optional)")
            print("- notes: Any additional notes (optional)")

        except Exception as e:
            print(f"Error creating template: {e}")

    def export_data_menu(self):
        """Data export menu"""
        print("\n📤 DATA EXPORT")
        print("1. Export All Students")
        print("2. Export All Documents")
        print("3. Export Compliance Data")
        print("4. Export Activity Log")
        print("5. Export Custom Dataset")
        print("6. Return to Main Menu")

        choice = input("\nChoose option (1-6): ").strip()

        if choice == '1':
            self.export_all_students()
        elif choice == '2':
            self.export_all_documents()
        elif choice == '3':
            self.export_compliance_data()
        elif choice == '4':
            self.export_activity_log()
        elif choice == '5':
            self.export_custom_dataset()

    def export_all_students(self):
        """Export all student data"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT student_id, first_name, last_name, email, course, year,
                   enrollment_date, status
            FROM students
            ORDER BY last_name, first_name
            ''')

            students = cursor.fetchall()

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = os.path.join(_EXPORT_DIR, f"students_export_{timestamp}.csv")

            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow(['Student ID', 'First Name', 'Last Name', 'Email',
                               'Course', 'Year', 'Enrollment Date', 'Status'])

                # Write data
                writer.writerows(students)

            print(f"✅ Students exported to: {filename}")
            print(f"Total records: {len(students)}")

            conn.close()

        except Exception as e:
            print(f"Export error: {e}")

    def export_all_documents(self):
        """Export all document records to CSV"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT sd.document_id, sd.owner_id as student_id, s.first_name, s.last_name,
                   dt.type_name, sd.original_filename, sd.upload_date,
                   sd.expiry_date, sd.verification_status, sd.version_number,
                   sd.tags, sd.workflow_status
            FROM documents sd
            JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
            LEFT JOIN students s ON sd.owner_id = s.student_id
            WHERE sd.is_current_version = 1
            ORDER BY sd.upload_date DESC
            ''')

            documents = cursor.fetchall()

            if not documents:
                print(_t("shared.utils.document_manager.no_documents_to_export", default="No documents to export."))
                conn.close()
                return

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = os.path.join(_EXPORT_DIR, f"all_documents_{timestamp}.csv")

            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Document ID', 'Student ID', 'First Name', 'Last Name',
                               'Document Type', 'Filename', 'Upload Date', 'Expiry Date',
                               'Status', 'Version', 'Tags', 'Workflow Status'])
                writer.writerows(documents)

            print(f"✅ Exported {len(documents)} documents to {filename}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def export_search_results(self, results=None):
        """Export search results to CSV"""
        if results is None:
            print("\n📤 EXPORT SEARCH RESULTS")
            print("First, perform a search...")
            results = self.execute_advanced_search({})

        if not results:
            print(_t("shared.utils.document_manager.no_results_to_export", default="No results to export."))
            return

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = os.path.join(_EXPORT_DIR, f"search_results_{timestamp}.csv")

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Document ID', 'Student ID', 'Student Name', 'Document Type',
                           'Filename', 'Upload Date', 'Status'])
            writer.writerows(results)

        print(f"✅ Exported {len(results)} results to {filename}")

    def export_activity_log(self):
        """Export activity log/audit trail to CSV"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            days = input("Export log for how many days? (default 30): ").strip()
            days = int(days) if days else 30

            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            cursor.execute('''
            SELECT log_id, user_id, action, table_name, record_id,
                   old_values, new_values, timestamp
            FROM audit_log
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
            ''', (cutoff_date,))

            logs = cursor.fetchall()

            if not logs:
                print(_t("shared.utils.document_manager.no_activity_logs_found", default="No activity logs found."))
                conn.close()
                return

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = os.path.join(_EXPORT_DIR, f"activity_log_{timestamp}.csv")

            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Log ID', 'User', 'Action', 'Table', 'Record ID',
                               'Old Values', 'New Values', 'Timestamp'])
                writer.writerows(logs)

            print(f"✅ Exported {len(logs)} log entries to {filename}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def export_compliance_data(self):
        """Export compliance data for auditing"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n📋 EXPORT COMPLIANCE DATA")

            cursor.execute('''
            SELECT s.student_id, s.first_name, s.last_name, s.course,
                   dt.type_name, dt.is_required,
                   CASE WHEN sd.document_id IS NOT NULL THEN 'Submitted' ELSE 'Missing' END as status,
                   sd.verification_status, sd.upload_date, sd.expiry_date
            FROM students s
            CROSS JOIN document_types dt
            LEFT JOIN documents sd ON s.student_id = sd.owner_id
                AND sd.source_type = 'student'
                AND dt.type_id = CAST(sd.document_type AS INTEGER) AND sd.is_current_version = 1
            WHERE dt.is_active = 1
            ORDER BY s.student_id, dt.category, dt.sort_order
            ''')

            compliance_data = cursor.fetchall()

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = os.path.join(_EXPORT_DIR, f"compliance_data_{timestamp}.csv")

            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Student ID', 'First Name', 'Last Name', 'Program',
                               'Document Type', 'Required', 'Status', 'Verification Status',
                               'Upload Date', 'Expiry Date'])
                writer.writerows(compliance_data)

            print(f"✅ Exported compliance data to {filename}")
            print(f"Total records: {len(compliance_data)}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def export_custom_dataset(self):
        """Export custom dataset with selected fields"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n📊 EXPORT CUSTOM DATASET")
            print("Select fields to export:")
            print("1. Student Information")
            print("2. Document Details")
            print("3. Verification Status")
            print("4. Workflow Information")
            print("5. Dates and Expiry")
            print("6. All Fields")

            choice = input("\nChoose option (1-6): ").strip()

            if choice == '6':
                query = '''
                SELECT sd.document_id, sd.owner_id as student_id, s.first_name, s.last_name,
                       s.course, dt.type_name, sd.original_filename, sd.upload_date,
                       sd.expiry_date, sd.verification_status, sd.verification_date,
                       sd.verification_notes, sd.version_number, sd.uploaded_by,
                       sd.tags, sd.workflow_status, sd.priority
                FROM documents sd
                JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
                LEFT JOIN students s ON sd.owner_id = s.student_id
                WHERE sd.is_current_version = 1
                '''
                headers = ['Document ID', 'Student ID', 'First Name', 'Last Name', 'Program',
                          'Document Type', 'Filename', 'Upload Date', 'Expiry Date',
                          'Verification Status', 'Verification Date', 'Verification Notes',
                          'Version', 'Uploaded By', 'Tags', 'Workflow Status', 'Priority']
            else:
                print("Custom field selection not fully implemented. Using default export.")
                query = '''
                SELECT sd.document_id, sd.owner_id as student_id, dt.type_name, sd.original_filename,
                       sd.upload_date, sd.verification_status
                FROM documents sd
                JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
                WHERE sd.is_current_version = 1
                '''
                headers = ['Document ID', 'Student ID', 'Document Type', 'Filename',
                          'Upload Date', 'Status']

            cursor.execute(query)
            data = cursor.fetchall()

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = os.path.join(_EXPORT_DIR, f"custom_export_{timestamp}.csv")

            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(data)

            print(f"✅ Exported {len(data)} records to {filename}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")
