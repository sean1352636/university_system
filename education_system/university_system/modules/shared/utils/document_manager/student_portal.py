from ._common import (
    os, hashlib, datetime, sqlite3,
    get_connection, _t,
)


class StudentPortalMixin:
    def view_my_documents(self):
        """Student view of their own documents"""
        print(_t("shared.utils.document_manager.my_documents_header", default="\n📄 MY DOCUMENTS"))

        student_id = input(_t("shared.utils.document_manager.prompt_enter_student_id", default="Enter your student ID: ")).strip()

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT sd.document_id, dt.type_name, sd.original_filename,
                   sd.upload_date, sd.expiry_date, sd.verification_status,
                   sd.version_number, sd.workflow_status
            FROM student_documents sd
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.student_id = ? AND sd.is_current_version = 1
            ORDER BY sd.upload_date DESC
            ''', (student_id,))

            documents = cursor.fetchall()

            if not documents:
                print(_t("shared.utils.document_manager.no_documents_found", default="No documents found."))
                conn.close()
                return

            print(f"\n{'='*80}")
            print(f"{'ID':<5} {'Type':<25} {'Filename':<25} {'Status':<12} {'Version':<8} {'Upload Date'}")
            print(f"{'='*80}")

            for doc in documents:
                doc_id, type_name, filename, upload_date, expiry_date, status, version, workflow = doc
                upload_display = upload_date[:10] if upload_date else 'N/A'
                print(f"{doc_id:<5} {type_name:<25} {filename:<25} {status:<12} {version:<8} {upload_display}")

                if expiry_date:
                    expiry_dt = datetime.strptime(expiry_date, '%Y-%m-%d')
                    days_until_expiry = (expiry_dt - datetime.now()).days

                    if days_until_expiry < 0:
                        print(f"      ⚠️ EXPIRED ({expiry_date})")
                    elif days_until_expiry < 30:
                        print(f"      ⚠️ Expires in {days_until_expiry} days ({expiry_date})")

            print(f"\nTotal Documents: {len(documents)}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def student_upload_document(self):
        """Allow student to upload their own documents"""
        print(_t("shared.utils.document_manager.student_upload_header", default="\n📤 UPLOAD MY DOCUMENT"))

        student_id = input(_t("shared.utils.document_manager.prompt_enter_student_id", default="Enter your student ID: ")).strip()

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Verify student exists
            cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?', (student_id,))
            student = cursor.fetchone()

            if not student:
                print(_t("shared.utils.document_manager.student_not_found", default="Student not found."))
                conn.close()
                return

            print(f"\nWelcome, {student[0]} {student[1]}!")

            # Show available document types
            type_info = self.select_document_type(cursor)
            if not type_info:
                conn.close()
                return

            type_id, type_name, has_expiry, max_size, allowed_formats = type_info

            # Get file details
            file_info = self.get_file_upload_details(allowed_formats, max_size)
            if not file_info:
                conn.close()
                return

            file_path, original_filename, file_size, file_hash = file_info

            # Get expiry date if needed
            expiry_date = None
            if has_expiry:
                expiry_date = self.get_expiry_date()

            # Insert document
            upload_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            INSERT INTO student_documents
            (student_id, type_id, file_path, original_filename, upload_date, expiry_date,
             verification_status, version_number, uploaded_by, file_size, file_hash, workflow_status)
            VALUES (?, ?, ?, ?, ?, ?, 'Pending', 1, ?, ?, ?, 'submitted')
            ''', (student_id, type_id, file_path, original_filename, upload_date,
                  expiry_date, student_id, file_size, file_hash))

            document_id = cursor.lastrowid

            # Create workflow steps
            self.create_workflow_steps(cursor, document_id, type_id)

            conn.commit()
            conn.close()

            print(_t("shared.utils.document_manager.document_uploaded_success", default="\nDocument uploaded successfully!"))
            print(_t("shared.utils.document_manager.document_id", default="Document ID: {doc_id}", doc_id=document_id))
            print(_t("shared.utils.document_manager.status_pending_verification", default="Status: Pending Verification"))

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def student_dashboard(self):
        """Student dashboard with progress overview"""
        print(_t("shared.utils.document_manager.student_dashboard_header", default="\n📊 MY DASHBOARD"))

        student_id = input(_t("shared.utils.document_manager.prompt_enter_student_id", default="Enter your student ID: ")).strip()

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get student info
            cursor.execute('''
            SELECT first_name, last_name, course, year
            FROM students WHERE student_id = ?
            ''', (student_id,))

            student = cursor.fetchone()
            if not student:
                print(_t("shared.utils.document_manager.student_not_found", default="Student not found."))
                conn.close()
                return

            first_name, last_name, course, year = student

            print(f"\nWelcome, {first_name} {last_name}!")
            print(f"Course: {course}, Year: {year}")
            print("=" * 60)

            # Document statistics
            cursor.execute('''
            SELECT verification_status, COUNT(*) as count
            FROM student_documents
            WHERE student_id = ? AND is_current_version = 1
            GROUP BY verification_status
            ''', (student_id,))

            status_counts = dict(cursor.fetchall())

            total_docs = sum(status_counts.values())
            verified = status_counts.get('Verified', 0)
            pending = status_counts.get('Pending', 0)
            rejected = status_counts.get('Rejected', 0)

            print(f"\n📄 My Documents: {total_docs}")
            print(f"   ✅ Verified: {verified}")
            print(f"   ⏳ Pending: {pending}")
            print(f"   ❌ Rejected: {rejected}")

            # Required documents progress
            cursor.execute('''
            SELECT COUNT(DISTINCT dt.type_id) as total_required,
                   COUNT(DISTINCT CASE WHEN sd.document_id IS NOT NULL THEN dt.type_id END) as submitted
            FROM document_types dt
            LEFT JOIN student_documents sd ON dt.type_id = sd.type_id
                AND sd.student_id = ? AND sd.is_current_version = 1
            WHERE dt.is_required = 1 AND dt.is_active = 1
            ''', (student_id,))

            req_total, req_submitted = cursor.fetchone()

            if req_total > 0:
                progress = (req_submitted / req_total) * 100
                print(f"\n📋 Required Documents: {req_submitted}/{req_total} ({progress:.0f}%)")

                # Progress bar
                bar_length = 20
                filled = int(bar_length * req_submitted / req_total)
                bar = '█' * filled + '░' * (bar_length - filled)
                print(f"   [{bar}]")

            # Expiring documents
            cursor.execute('''
            SELECT COUNT(*)
            FROM student_documents
            WHERE student_id = ?
            AND expiry_date IS NOT NULL
            AND expiry_date <= date('now', '+30 days')
            AND is_current_version = 1
            ''', (student_id,))

            expiring = cursor.fetchone()[0]
            if expiring > 0:
                print(f"\n⚠️ {expiring} document(s) expiring within 30 days")

            # Unread notifications
            cursor.execute('''
            SELECT COUNT(*)
            FROM notifications
            WHERE recipient_id = ? AND is_read = 0
            ''', (student_id,))

            unread = cursor.fetchone()[0]
            if unread > 0:
                print(f"\n🔔 {unread} unread notification(s)")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def check_my_requirements(self):
        """Student check their document requirements"""
        print(_t("shared.utils.document_manager.my_requirements_header", default="\n📋 MY DOCUMENT REQUIREMENTS"))

        student_id = input(_t("shared.utils.document_manager.prompt_enter_student_id", default="Enter your student ID: ")).strip()

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get student info
            cursor.execute('SELECT first_name, last_name, course, year FROM students WHERE student_id = ?', (student_id,))
            student = cursor.fetchone()

            if not student:
                print(_t("shared.utils.document_manager.student_not_found", default="Student not found."))
                conn.close()
                return

            first_name, last_name, course, year = student

            print(f"\nRequirements for: {first_name} {last_name}")
            print(f"Course: {course}, Year: {year}")
            print("=" * 60)

            # Get all required documents
            cursor.execute('''
            SELECT dt.type_name, dt.description, dt.has_expiry,
                   CASE WHEN sd.document_id IS NOT NULL THEN 'Submitted' ELSE 'Missing' END as status,
                   sd.verification_status
            FROM document_types dt
            LEFT JOIN student_documents sd ON dt.type_id = sd.type_id
                AND sd.student_id = ? AND sd.is_current_version = 1
            WHERE dt.is_required = 1
            ORDER BY dt.sort_order
            ''', (student_id,))

            requirements = cursor.fetchall()

            if requirements:
                print(f"{'Document Type':<25} {'Status':<12} {'Verification':<15} {'Description'}")
                print("-" * 80)

                for req in requirements:
                    doc_type, description, has_expiry, status, verification = req

                    if status == 'Missing':
                        status_display = "❌ Missing"
                        verification_display = "N/A"
                    else:
                        status_display = "✅ Submitted"
                        verification_display = verification or "Pending"

                    desc_short = description[:30] + "..." if len(description) > 30 else description

                    print(f"{doc_type:<25} {status_display:<12} {verification_display:<15} {desc_short}")

            # Show submission progress
            submitted_count = sum(1 for req in requirements if req[3] == 'Submitted')
            total_count = len(requirements)
            progress = (submitted_count / total_count) * 100 if total_count > 0 else 0

            print(f"\n📊 Progress: {submitted_count}/{total_count} ({progress:.1f}%)")

            if submitted_count == total_count:
                print("🎉 Congratulations! All required documents submitted.")
            else:
                missing_count = total_count - submitted_count
                print(f"⚠️  You still need to submit {missing_count} required documents.")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def my_document_status(self):
        """Show detailed status of student's documents"""
        print(_t("shared.utils.document_manager.my_doc_status_header", default="\n📊 MY DOCUMENT STATUS"))

        student_id = input(_t("shared.utils.document_manager.prompt_enter_student_id", default="Enter your student ID: ")).strip()

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get detailed document status
            cursor.execute('''
            SELECT dt.type_name, sd.upload_date, sd.verification_status,
                   sd.verification_date, sd.expiry_date, sd.verification_notes,
                   sd.version_number
            FROM student_documents sd
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.student_id = ? AND sd.is_current_version = 1
            ORDER BY sd.upload_date DESC
            ''', (student_id,))

            documents = cursor.fetchall()

            if not documents:
                print("No documents found for this student ID.")
                conn.close()
                return

            print(f"\n📄 DOCUMENT STATUS DETAILS")
            print("=" * 100)

            for doc in documents:
                doc_type, upload_date, status, verify_date, expiry_date, notes, version = doc

                print(f"\n📋 {doc_type} (Version {version})")
                print(f"   Upload Date: {upload_date[:10] if upload_date else 'N/A'}")
                print(f"   Status: {status}")

                if verify_date:
                    print(f"   Verified: {verify_date[:10]}")

                if expiry_date:
                    expiry_dt = datetime.strptime(expiry_date, '%Y-%m-%d')
                    days_until_expiry = (expiry_dt - datetime.now()).days

                    if days_until_expiry < 0:
                        print(f"   Expiry: {expiry_date} (⚠️ EXPIRED)")
                    elif days_until_expiry < 30:
                        print(f"   Expiry: {expiry_date} (⚠️ Expires in {days_until_expiry} days)")
                    else:
                        print(f"   Expiry: {expiry_date}")

                if notes:
                    print(f"   Notes: {notes}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")
