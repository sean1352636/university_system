"""Student self-service flows for the document manager.

These console flows back the student menu (see ``handle_student_choice`` in
``manager.py``). ``create_notification`` and ``get_file_upload_details`` are
provided by ``UploadMixin``; ``my_notifications`` lives in ``NotificationsMixin``.
"""

from education_system.post_18.university_system.modules.shared.utils.document_manager._common import (
    datetime, timedelta, sqlite3,
    get_connection,
)


class StudentSelfServiceMixin:
    def view_my_documents(self):
        """Student view of their own documents"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get student ID from username
            cursor.execute('SELECT student_id FROM students WHERE first_name || " " || last_name = ?', (self.current_user,))
            result = cursor.fetchone()

            if not result:
                # Try to find by username pattern
                cursor.execute('''
                SELECT student_id, first_name, last_name
                FROM students
                WHERE LOWER(first_name || last_name) LIKE LOWER(?)
                ''', (f'%{self.current_user}%',))
                result = cursor.fetchone()

                if not result:
                    print("Could not find your student record. Please contact administration.")
                    conn.close()
                    return

            student_id = result[0]

            # Get student info
            cursor.execute('SELECT first_name, last_name, course, year FROM students WHERE student_id = ?', (student_id,))
            student_info = cursor.fetchone()

            print("\n📄 MY DOCUMENTS")
            print(f"Student: {student_info[0]} {student_info[1]} (ID: {student_id})")
            print(f"Course: {student_info[2]}, Year: {student_info[3]}")
            print("=" * 80)

            # Get all documents
            cursor.execute('''
            SELECT sd.document_id, dt.type_name, sd.original_filename,
                   sd.upload_date, sd.expiry_date, sd.verification_status,
                   sd.version_number, sd.verification_notes
            FROM student_documents sd
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.student_id = ? AND sd.is_current_version = 1
            ORDER BY dt.sort_order, sd.upload_date DESC
            ''', (student_id,))

            documents = cursor.fetchall()

            if documents:
                print(f"{'Type':<25} {'Status':<12} {'Upload Date':<12} {'Expiry':<12} {'Version':<8} {'Notes'}")
                print("-" * 80)

                for doc in documents:
                    doc_id, type_name, filename, upload_date, expiry_date, status, version, notes = doc

                    expiry_display = expiry_date[:10] if expiry_date else "N/A"
                    upload_display = upload_date[:10] if upload_date else "N/A"
                    notes_display = notes[:20] + "..." if notes and len(notes) > 20 else notes or ""

                    print(f"{type_name:<25} {status:<12} {upload_display:<12} {expiry_display:<12} {version:<8} {notes_display}")
            else:
                print("No documents uploaded yet.")

            # Show missing required documents
            cursor.execute('''
            SELECT dt.type_name, dt.description
            FROM document_types dt
            WHERE dt.is_required = 1 AND dt.type_id NOT IN (
                SELECT sd.type_id FROM student_documents sd
                WHERE sd.student_id = ? AND sd.is_current_version = 1
            )
            ORDER BY dt.sort_order
            ''', (student_id,))

            missing_docs = cursor.fetchall()

            if missing_docs:
                print(f"\n⚠️ MISSING REQUIRED DOCUMENTS ({len(missing_docs)}):")
                print("-" * 60)
                for type_name, description in missing_docs:
                    print(f"• {type_name} - {description}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def student_upload_document(self):
        """Allow student to upload their own documents"""
        print("\n📤 UPLOAD DOCUMENT")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get student ID (simplified for demo)
            student_id = input("Enter your student ID: ").strip()

            # Verify student
            cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?', (student_id,))
            student = cursor.fetchone()

            if not student:
                print("Student ID not found.")
                conn.close()
                return

            print(f"Uploading for: {student[0]} {student[1]}")

            # Show available document types
            cursor.execute('''
            SELECT type_id, type_name, description, max_file_size_mb, allowed_formats
            FROM document_types
            WHERE is_active = 1
            ORDER BY is_required DESC, sort_order
            ''')

            doc_types = cursor.fetchall()

            print("\nAvailable Document Types:")
            for i, (type_id, type_name, desc, max_size, formats) in enumerate(doc_types):
                print(f"{i+1}. {type_name} (Max: {max_size}MB, Formats: {formats})")
                print(f"   {desc}")

            try:
                choice = int(input("\nSelect document type: ")) - 1
                if choice < 0 or choice >= len(doc_types):
                    print("Invalid selection.")
                    conn.close()
                    return

                selected_type = doc_types[choice]
                type_id, type_name, desc, max_size, allowed_formats = selected_type

            except ValueError:
                print("Invalid input.")
                conn.close()
                return

            # Get file upload details
            file_info = self.get_file_upload_details(allowed_formats, max_size)
            if not file_info:
                conn.close()
                return

            file_path, original_filename, file_size, file_hash = file_info

            # Insert document
            upload_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            INSERT INTO student_documents
            (student_id, type_id, file_path, original_filename, upload_date,
             verification_status, uploaded_by, file_size, file_hash, workflow_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, type_id, file_path, original_filename, upload_date,
                  'Pending', f'student_{student_id}', file_size, file_hash, 'submitted'))

            document_id = cursor.lastrowid

            # Create notification for admin
            self.create_notification(cursor, 'admin', 'student_document_uploaded',
                                   f'Student Document Uploaded: {type_name}',
                                   f'Student {student_id} ({student[0]} {student[1]}) has uploaded {type_name}.',
                                   document_id)

            conn.commit()
            conn.close()

            print("\n✅ Document uploaded successfully!")
            print(f"Document ID: {document_id}")
            print("Status: Pending Review")
            print("You will be notified once the document is reviewed.")

        except sqlite3.Error as e:
            print(f"Upload error: {e}")

    def student_dashboard(self):
        """Student dashboard with progress overview"""
        print("\n📊 MY DASHBOARD")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get student ID (simplified)
            student_id = input("Enter your student ID: ").strip()

            # Get student info
            cursor.execute('SELECT first_name, last_name, course, year FROM students WHERE student_id = ?', (student_id,))
            student = cursor.fetchone()

            if not student:
                print("Student not found.")
                conn.close()
                return

            print(f"\nWelcome, {student[0]} {student[1]}!")
            print(f"Course: {student[2]}, Year: {student[3]}")
            print("=" * 60)

            # Document completion status
            cursor.execute('''
            SELECT COUNT(DISTINCT dt.type_id) as required_count
            FROM document_types dt
            WHERE dt.is_required = 1
            ''')

            total_required = cursor.fetchone()[0]

            cursor.execute('''
            SELECT COUNT(DISTINCT sd.type_id) as submitted_count
            FROM student_documents sd
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.student_id = ? AND dt.is_required = 1 AND sd.is_current_version = 1
            ''', (student_id,))

            submitted_required = cursor.fetchone()[0]

            completion_rate = (submitted_required / total_required) * 100 if total_required > 0 else 0

            print("📈 COMPLETION STATUS:")
            print(f"Required Documents: {submitted_required}/{total_required} ({completion_rate:.1f}%)")

            # Progress bar
            progress_bar = "█" * int(completion_rate / 10) + "░" * (10 - int(completion_rate / 10))
            print(f"Progress: [{progress_bar}] {completion_rate:.1f}%")

            # Recent activity
            print("\n🕒 RECENT ACTIVITY:")
            cursor.execute('''
            SELECT dt.type_name, sd.upload_date, sd.verification_status
            FROM student_documents sd
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.student_id = ? AND sd.is_current_version = 1
            ORDER BY sd.upload_date DESC
            LIMIT 5
            ''', (student_id,))

            recent_docs = cursor.fetchall()

            if recent_docs:
                for doc_type, upload_date, status in recent_docs:
                    upload_display = upload_date[:10] if upload_date else "Unknown"
                    print(f"• {doc_type} - {status} ({upload_display})")
            else:
                print("No recent activity.")

            # Urgent actions needed
            print("\n⚠️ ACTION REQUIRED:")

            # Missing required documents
            cursor.execute('''
            SELECT dt.type_name
            FROM document_types dt
            WHERE dt.is_required = 1 AND dt.type_id NOT IN (
                SELECT sd.type_id FROM student_documents sd
                WHERE sd.student_id = ? AND sd.is_current_version = 1
            )
            LIMIT 3
            ''', (student_id,))

            missing_docs = cursor.fetchall()

            if missing_docs:
                print("Missing Required Documents:")
                for (type_name,) in missing_docs:
                    print(f"• Upload {type_name}")
            else:
                print("✅ All required documents submitted!")

            # Expiring documents
            future_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

            cursor.execute('''
            SELECT dt.type_name, sd.expiry_date
            FROM student_documents sd
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.student_id = ? AND sd.expiry_date <= ? AND sd.expiry_date >= ?
            AND sd.is_current_version = 1
            ''', (student_id, future_date, datetime.now().strftime('%Y-%m-%d')))

            expiring_docs = cursor.fetchall()

            if expiring_docs:
                print("\nDocuments Expiring Soon:")
                for type_name, expiry_date in expiring_docs:
                    print(f"• {type_name} expires on {expiry_date}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Dashboard error: {e}")

    def check_my_requirements(self):
        """Student check their document requirements"""
        print("\n📋 MY DOCUMENT REQUIREMENTS")

        student_id = input("Enter your student ID: ").strip()

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get student info
            cursor.execute('SELECT first_name, last_name, course, year FROM students WHERE student_id = ?', (student_id,))
            student = cursor.fetchone()

            if not student:
                print("Student not found.")
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
        print("\n📊 MY DOCUMENT STATUS")

        student_id = input("Enter your student ID: ").strip()

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

            print("\n📄 DOCUMENT STATUS DETAILS")
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
