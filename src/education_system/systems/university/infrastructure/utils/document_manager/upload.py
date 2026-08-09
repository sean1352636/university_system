from education_system.systems.university.infrastructure.utils.document_manager._common import (
    os, hashlib, datetime, sqlite3,
    get_connection, get_current_user, _t, log_event,
    EMAIL_SYSTEM_AVAILABLE, send_email, render_template,
)


class UploadMixin:
    def upload_student_document(self):
        """Enhanced document upload with versioning support and integrated email notifications"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get student ID
            student_id = self.select_student(cursor)
            if not student_id:
                conn.close()
                return

            # Get document type
            type_info = self.select_document_type(cursor)
            if not type_info:
                conn.close()
                return

            type_id, type_name, has_expiry, max_size, allowed_formats = type_info

            # Check for existing documents of this type
            cursor.execute('''
            SELECT document_id, version_number, original_filename
            FROM documents
            WHERE owner_id = ? AND source_type = 'student' AND type_id = ? AND is_current_version = 1
            ''', (student_id, type_id))

            existing_doc = cursor.fetchone()

            if existing_doc:
                print(_t("shared.utils.document_manager.existing_doc_found", default="\nExisting document found: {filename} (Version {version})", filename=existing_doc[2], version=existing_doc[1]))
                print(_t("shared.utils.document_manager.option_upload_new_version", default="1. Upload new version (replace existing)"))
                print(_t("shared.utils.document_manager.option_upload_additional", default="2. Upload additional document"))
                print(_t("shared.utils.document_manager.option_cancel", default="3. Cancel"))

                choice = input("Choose option (1-3): ").strip()
                if choice == '3':
                    conn.close()
                    return
                elif choice == '1':
                    # Create new version
                    new_version = existing_doc[1] + 1
                    parent_doc_id = existing_doc[0]

                    # Mark existing as not current
                    cursor.execute('''
                    UPDATE documents
                    SET is_current_version = 0
                    WHERE document_id = ?
                    ''', (existing_doc[0],))
                else:
                    new_version = 1
                    parent_doc_id = None
            else:
                new_version = 1
                parent_doc_id = None

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

            # Get tags
            tags = self.select_tags(cursor)

            # Insert document record
            upload_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            INSERT INTO documents
            (source_type, owner_id, type_id, file_path, original_filename, upload_date, expiry_date,
             verification_status, version_number, parent_document_id, uploaded_by,
             file_size, file_hash, tags, workflow_status)
            VALUES ('student', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, type_id, file_path, original_filename, upload_date, expiry_date,
                  'Pending', new_version, parent_doc_id, self.current_user, file_size, file_hash, tags, 'submitted'))

            document_id = cursor.lastrowid

            # Bus broadcast (#1) — chatbot re-indexes, evidence panels
            # refresh, anyone subscribed to dm.document.changed picks
            # this up. Best-effort.
            try:
                from education_system.systems.university.services.bus.document_bus import (
                    publish_document_changed,
                )
                publish_document_changed(
                    document_id=document_id,
                    action="uploaded",
                    domain="student",
                    ref_id=str(student_id),
                    name=type_name,
                )
            except Exception:
                pass

            # Create workflow steps
            self.create_workflow_steps(cursor, document_id, type_id)

            # Create notification in database
            self.create_notification(cursor, student_id, 'document_uploaded',
                                   f'Document Uploaded: {type_name}',
                                   f'Your {type_name} has been uploaded successfully and is pending verification.',
                                   document_id)

            conn.commit()
            conn.close()

            print(_t("shared.utils.document_manager.document_uploaded_success", default="\nDocument uploaded successfully!"))
            print(_t("shared.utils.document_manager.document_id", default="Document ID: {doc_id}", doc_id=document_id))
            print(_t("shared.utils.document_manager.version", default="Version: {version}", version=new_version))
            print(_t("shared.utils.document_manager.status_pending_verification", default="Status: Pending Verification"))

            # Send email notification using integrated email system
            if EMAIL_SYSTEM_AVAILABLE:
                try:
                    # Get student details for email
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                    SELECT email_address, first_name, last_name
                    FROM students WHERE student_id = ?
                    ''', (student_id,))
                    student_data = cursor.fetchone()
                    conn.close()

                    if student_data:
                        email_address, first_name, last_name = student_data

                        # Use template email for better formatting
                        template_vars = {
                            'student_name': f"{first_name} {last_name}".strip() or "Student",
                            'document_type': type_name,
                            'document_id': document_id,
                            'version': new_version,
                            'upload_date': upload_date
                        }

                        subject, body = render_template('document_upload_confirmation', template_vars)

                        if send_email(email_address, subject, body):
                            log_event('info', f"Document upload confirmation email sent to {email_address}")
                            print(_t("shared.utils.document_manager.email_sent", default="Confirmation email sent to {email}", email=email_address))
                        else:
                            log_event('warning', f"Failed to send confirmation email to {email_address}")
                            print(_t("shared.utils.document_manager.email_failed", default="Document uploaded but email notification failed"))
                    else:
                        log_event('warning', f"Could not find email address for student {student_id}")

                except Exception as e:
                    log_event('error', f"Error sending document upload notification: {e}")
                    print(_t("shared.utils.document_manager.email_failed", default="Document uploaded but email notification failed"))
            else:
                print(_t("shared.utils.document_manager.email_system_unavailable", default="Document uploaded (email system not available)"))

        except sqlite3.Error as e:
            print(_t("shared.utils.document_manager.database_error", default="Database error: {error}", error=str(e)))
            log_event('error', f"Database error in upload_student_document: {e}")

    def select_student(self, cursor):
        """Enhanced student selection with search"""
        student_id = input("Enter student ID (leave blank to search): ").strip()

        if student_id:
            cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?', (student_id,))
            student = cursor.fetchone()
            if student:
                print(f"Selected: {student[0]} {student[1]} (ID: {student_id})")
                return student_id
            else:
                print(_t("shared.utils.document_manager.student_not_found", default="Student not found."))
                return None

        # Search functionality
        search_term = input("Enter search term (name or partial ID): ").strip()
        if not search_term:
            return None

        cursor.execute('''
        SELECT student_id, first_name, last_name, course, year
        FROM students
        WHERE first_name LIKE ? OR last_name LIKE ? OR student_id LIKE ?
        ORDER BY last_name, first_name
        LIMIT 20
        ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))

        students = cursor.fetchall()

        if not students:
            print("No students found.")
            return None

        print("\nSearch Results:")
        for i, (id, first_name, last_name, course, year) in enumerate(students):
            print(f"{i+1}. {last_name}, {first_name} (ID: {id}) - {course} Year {year}")

        try:
            choice = int(input("\nSelect student number: ")) - 1
            if 0 <= choice < len(students):
                return students[choice][0]
            else:
                print(_t("shared.utils.document_manager.invalid_selection", default="Invalid selection."))
                return None
        except ValueError:
            print(_t("shared.utils.document_manager.invalid_input", default="Invalid input."))
            return None

    def select_document_type(self, cursor):
        """Enhanced document type selection with categories"""
        cursor.execute('''
        SELECT type_id, type_name, description, has_expiry, max_file_size_mb,
               allowed_formats, category, is_required
        FROM document_types
        WHERE is_active = 1
        ORDER BY category, sort_order, type_name
        ''')

        doc_types = cursor.fetchall()

        if not doc_types:
            print("No document types available.")
            return None

        print("\nAvailable Document Types:")
        current_category = None

        for i, (type_id, type_name, desc, has_expiry, max_size, formats, category, required) in enumerate(doc_types):
            if category != current_category:
                print(f"\n📁 {category.upper()}:")
                current_category = category

            required_text = " (Required)" if required else ""
            expiry_text = " (Expires)" if has_expiry else ""
            size_text = f" (Max: {max_size}MB)"

            print(f"  {i+1}. {type_name}{required_text}{expiry_text}{size_text}")
            print(f"      {desc}")
            print(f"      Formats: {formats}")

        try:
            choice = int(input("\nSelect document type: ")) - 1
            if 0 <= choice < len(doc_types):
                selected = doc_types[choice]
                return (selected[0], selected[1], selected[3], selected[4], selected[5])
            else:
                print(_t("shared.utils.document_manager.invalid_selection", default="Invalid selection."))
                return None
        except ValueError:
            print(_t("shared.utils.document_manager.invalid_input", default="Invalid input."))
            return None

    def get_file_upload_details(self, allowed_formats, max_size_mb):
        """Get file upload details with validation"""
        print("\nFile Requirements:")
        print(f"Allowed formats: {allowed_formats}")
        print(f"Maximum size: {max_size_mb}MB")

        file_path = input("Enter file path: ").strip()

        if not file_path or not os.path.exists(file_path):
            print(_t("shared.utils.document_manager.file_not_found", default="File not found."))
            return None

        # Validate file format
        file_ext = os.path.splitext(file_path)[1][1:].lower()
        if file_ext not in allowed_formats.lower().split(','):
            print(f"Invalid file format. Allowed: {allowed_formats}")
            return None

        # Validate file size
        file_size = os.path.getsize(file_path)
        file_size_mb = file_size / (1024 * 1024)

        if file_size_mb > max_size_mb:
            print(f"File too large. Maximum size: {max_size_mb}MB")
            return None

        # Generate file hash for duplicate detection
        with open(file_path, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()

        original_filename = os.path.basename(file_path)

        return file_path, original_filename, file_size, file_hash

    def get_expiry_date(self):
        """Get expiry date with validation"""
        while True:
            expiry_input = input("Enter expiry date (YYYY-MM-DD): ").strip()

            try:
                expiry_date = datetime.strptime(expiry_input, '%Y-%m-%d')

                if expiry_date <= datetime.now():
                    print("Expiry date must be in the future.")
                    continue

                return expiry_input
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")

    def select_tags(self, cursor):
        """Select tags for document"""
        cursor.execute('SELECT tag_name, description FROM document_tags ORDER BY tag_name')
        tags = cursor.fetchall()

        if not tags:
            return ""

        print("\nAvailable Tags (select multiple with commas):")
        for i, (tag_name, desc) in enumerate(tags):
            print(f"{i+1}. {tag_name} - {desc}")

        selection = input("Select tag numbers (e.g., 1,3,5) or press Enter to skip: ").strip()

        if not selection:
            return ""

        try:
            selected_indices = [int(x.strip()) - 1 for x in selection.split(',')]
            selected_tags = [tags[i][0] for i in selected_indices if 0 <= i < len(tags)]
            return ','.join(selected_tags)
        except ValueError:
            print("Invalid selection. No tags added.")
            return ""

    def create_workflow_steps(self, cursor, document_id, type_id):
        """Create workflow steps for document approval"""
        # Get document type requirements
        cursor.execute('SELECT requires_approval FROM document_types WHERE type_id = ?', (type_id,))
        requires_approval = cursor.fetchone()[0]

        if not requires_approval:
            return

        # Default workflow steps
        workflow_steps = [
            ('Initial Review', 1, 'registrar'),
            ('Verification', 2, 'admin'),
            ('Final Approval', 3, 'dean')
        ]

        for step_name, step_order, assigned_to in workflow_steps:
            cursor.execute('''
            INSERT INTO document_workflow (document_id, step_name, step_order, assigned_to, status)
            VALUES (?, ?, ?, ?, ?)
            ''', (document_id, step_name, step_order, assigned_to, 'pending'))

    def create_notification(self, cursor, recipient_id, notification_type, title, message, document_id=None):
        """Create a notification with integrated email system support"""
        # Insert notification into database. Best-effort: the standalone
        # ``notifications`` table has been retired, so a missing table must
        # never break the document operation that triggered this. The email
        # path below still runs so recipients are informed.
        try:
            cursor.execute('''
            INSERT INTO notifications (recipient_id, notification_type, title, message, created_date, related_document_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (recipient_id, notification_type, title, message, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), document_id))
        except Exception:
            pass

        # Send email notification if email system is available
        if EMAIL_SYSTEM_AVAILABLE:
            try:
                # Get recipient email address
                cursor.execute('''
                SELECT email_address, first_name, last_name
                FROM students WHERE student_id = ?
                ''', (recipient_id,))

                recipient_data = cursor.fetchone()
                if recipient_data:
                    email_address, first_name, last_name = recipient_data
                    recipient_name = f"{first_name} {last_name}".strip() or "Student"

                    # Format email content
                    template_vars = {
                        'student_name': recipient_name,
                        'title': title,
                        'message': message
                    }

                    subject, body = render_template('document_notification', template_vars)

                    # Send email
                    if send_email(email_address, subject, body):
                        log_event('info', f"Notification email sent to {email_address} for {notification_type}")
                    else:
                        log_event('warning', f"Failed to send notification email to {email_address}")
                else:
                    log_event('warning', f"Could not find email address for recipient {recipient_id}")

            except Exception as e:
                log_event('error', f"Error sending notification email: {e}")
