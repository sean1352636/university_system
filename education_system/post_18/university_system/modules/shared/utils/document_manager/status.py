from education_system.post_18.university_system.modules.shared.utils.document_manager._common import (
    datetime, timedelta, sqlite3,
    get_connection, _t, log_event,
    EMAIL_SYSTEM_AVAILABLE, send_email, render_template,
)


class StatusMixin:
    def check_document_expiry(self):
        """Check for expiring documents and send notifications"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get expiry settings
            try:
                days_ahead = int(input("Check for documents expiring within how many days? (default: 30): ") or "30")
            except ValueError:
                days_ahead = 30

            future_date = (datetime.now() + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
            today = datetime.now().strftime('%Y-%m-%d')

            # Find expiring documents
            cursor.execute('''
            SELECT sd.document_id, sd.owner_id as student_id, s.first_name, s.last_name, s.email_address,
                   dt.type_name, sd.expiry_date, sd.original_filename,
                   julianday(sd.expiry_date) - julianday('now') as days_until_expiry
            FROM documents sd
            JOIN students s ON sd.owner_id = s.student_id
            JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
            WHERE sd.expiry_date BETWEEN ? AND ?
            AND sd.verification_status = 'Verified'
            AND sd.is_current_version = 1
            ORDER BY sd.expiry_date ASC
            ''', (today, future_date))

            expiring_docs = cursor.fetchall()

            # Find already expired documents
            cursor.execute('''
            SELECT sd.document_id, sd.owner_id as student_id, s.first_name, s.last_name, s.email_address,
                   dt.type_name, sd.expiry_date, sd.original_filename
            FROM documents sd
            JOIN students s ON sd.owner_id = s.student_id
            JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
            WHERE sd.expiry_date < ?
            AND sd.verification_status != 'Expired'
            AND sd.is_current_version = 1
            ORDER BY sd.expiry_date ASC
            ''', (today,))

            expired_docs = cursor.fetchall()

            print(_t("shared.utils.document_manager.expiry_check_results", default="\nDocument Expiry Check Results:"))
            print(_t("shared.utils.document_manager.docs_expiring_within", default="Documents expiring within {days} days: {count}", days=days_ahead, count=len(expiring_docs)))
            print(_t("shared.utils.document_manager.docs_already_expired", default="Documents already expired: {count}", count=len(expired_docs)))

            if expiring_docs:
                print(_t("shared.utils.document_manager.docs_expiring_soon_header", default="\nDocuments Expiring Soon:"))
                print("-" * 80)
                for doc in expiring_docs:
                    doc_id, student_id, first_name, last_name, email, doc_type, expiry_date, filename, days_left = doc
                    student_name = f"{first_name} {last_name}".strip()
                    print(_t("shared.utils.document_manager.expiry_doc_line", default="ID: {doc_id} | {student_name} | {doc_type} | Expires: {expiry_date} ({days} days)", doc_id=doc_id, student_name=student_name, doc_type=doc_type, expiry_date=expiry_date, days=int(days_left)))

            if expired_docs:
                print(_t("shared.utils.document_manager.expired_docs_header", default="\nExpired Documents:"))
                print("-" * 80)
                for doc in expired_docs:
                    doc_id, student_id, first_name, last_name, email, doc_type, expiry_date, filename = doc
                    student_name = f"{first_name} {last_name}".strip()
                    print(_t("shared.utils.document_manager.expired_doc_line", default="ID: {doc_id} | {student_name} | {doc_type} | Expired: {expiry_date}", doc_id=doc_id, student_name=student_name, doc_type=doc_type, expiry_date=expiry_date))

            # Send notifications
            if expiring_docs or expired_docs:
                send_notifications = input("\nSend email notifications? (y/n): ").strip().lower()

                if send_notifications == 'y':
                    notification_count = 0

                    # Process expiring documents
                    for doc in expiring_docs:
                        doc_id, student_id, first_name, last_name, email_address, doc_type, expiry_date, filename, days_left = doc

                        if email_address and EMAIL_SYSTEM_AVAILABLE:
                            student_name = f"{first_name} {last_name}".strip()
                            days_left_int = int(days_left)

                            template_vars = {
                                'student_name': student_name,
                                'document_type': doc_type,
                                'document_id': doc_id,
                                'filename': filename,
                                'expiry_date': expiry_date,
                                'days_left': days_left_int
                            }

                            subject, body = render_template('document_expiry_warning', template_vars)

                            if send_email(email_address, subject, body):
                                notification_count += 1
                                log_event('info', f"Expiry warning sent to {email_address} for document {doc_id}")

                    # Process expired documents
                    for doc in expired_docs:
                        doc_id, student_id, first_name, last_name, email_address, doc_type, expiry_date, filename = doc

                        # Mark as expired in database
                        cursor.execute('''
                        UPDATE documents
                        SET verification_status = 'Expired'
                        WHERE document_id = ?
                        ''', (doc_id,))

                        if email_address and EMAIL_SYSTEM_AVAILABLE:
                            student_name = f"{first_name} {last_name}".strip()

                            template_vars = {
                                'student_name': student_name,
                                'document_type': doc_type,
                                'document_id': doc_id,
                                'filename': filename,
                                'expiry_date': expiry_date
                            }

                            subject, body = render_template('document_expired', template_vars)

                            if send_email(email_address, subject, body):
                                notification_count += 1
                                log_event('info', f"Expiry notification sent to {email_address} for expired document {doc_id}")

                    conn.commit()
                    print(_t("shared.utils.document_manager.processed_notifications", default="\nProcessed {count} email notifications", count=notification_count))

                else:
                    print(_t("shared.utils.document_manager.notifications_skipped", default="Notifications skipped"))
            else:
                print(_t("shared.utils.document_manager.no_expiry_notifications", default="No documents require expiry notifications"))

            conn.close()

        except sqlite3.Error as e:
            print(_t("shared.utils.document_manager.database_error", default="Database error: {error}", error=str(e)))
            log_event('error', f"Database error in check_document_expiry: {e}")

    def update_document_status(self):
        """Update document status with email notifications"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get document to update
            document_id = input(_t("shared.utils.document_manager.prompt_document_id", default="Enter document ID to update: ")).strip()
            if not document_id.isdigit():
                print(_t("shared.utils.document_manager.invalid_document_id", default="Invalid document ID."))
                conn.close()
                return

            # Get document details
            cursor.execute('''
            SELECT sd.document_id, sd.owner_id as student_id, s.first_name, s.last_name, s.email_address,
                   dt.type_name, sd.verification_status, sd.original_filename
            FROM documents sd
            JOIN students s ON sd.owner_id = s.student_id
            JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
            WHERE sd.document_id = ? AND sd.is_current_version = 1
            ''', (document_id,))

            doc_info = cursor.fetchone()

            if not doc_info:
                print(_t("shared.utils.document_manager.document_not_found", default="Document not found."))
                conn.close()
                return

            doc_id, student_id, first_name, last_name, email_address, doc_type, current_status, filename = doc_info
            student_name = f"{first_name} {last_name}".strip()

            print(_t("shared.utils.document_manager.document_info", default="\nDocument: {doc_type} for {student_name}", doc_type=doc_type, student_name=student_name))
            print(_t("shared.utils.document_manager.current_status", default="Current Status: {status}", status=current_status))
            print(_t("shared.utils.document_manager.file_info", default="File: {filename}", filename=filename))

            print(_t("shared.utils.document_manager.new_status_options", default="\nNew Status Options:"))
            print(_t("shared.utils.document_manager.status_option_verified", default="1. Verified"))
            print(_t("shared.utils.document_manager.status_option_rejected", default="2. Rejected"))
            print(_t("shared.utils.document_manager.status_option_pending", default="3. Pending"))
            print(_t("shared.utils.document_manager.status_option_expired", default="4. Expired"))
            print(_t("shared.utils.document_manager.status_option_under_review", default="5. Under Review"))

            choice = input(_t("shared.utils.document_manager.prompt_choose_status", default="Choose new status (1-5): ")).strip()

            status_map = {
                '1': 'Verified',
                '2': 'Rejected',
                '3': 'Pending',
                '4': 'Expired',
                '5': 'Under Review'
            }

            if choice not in status_map:
                print(_t("shared.utils.document_manager.invalid_choice", default="Invalid choice. Please try again."))
                conn.close()
                return

            new_status = status_map[choice]
            notes = input(_t("shared.utils.document_manager.prompt_verification_notes", default="Verification notes (optional): ")).strip()

            # Update document status
            verification_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S') if new_status != 'Pending' else None

            cursor.execute('''
            UPDATE documents
            SET verification_status = ?, verification_date = ?, verification_notes = ?
            WHERE document_id = ?
            ''', (new_status, verification_date, notes, doc_id))

            # Create notification
            if new_status == 'Verified':
                notification_title = f"Document Verified: {doc_type}"
                notification_message = f"Your {doc_type} has been verified and approved."
            elif new_status == 'Rejected':
                notification_title = f"Document Rejected: {doc_type}"
                notification_message = f"Your {doc_type} has been rejected. {notes if notes else 'Please contact the registrar for details.'}"
            else:
                notification_title = f"Document Status Updated: {doc_type}"
                notification_message = f"Your {doc_type} status has been updated to {new_status}."

            self.create_notification(cursor, student_id, 'status_update',
                                   notification_title, notification_message, doc_id)

            conn.commit()
            conn.close()

            print(_t("shared.utils.document_manager.status_updated", default="\nDocument status updated to: {status}", status=new_status))

            # Send detailed email notification
            if EMAIL_SYSTEM_AVAILABLE and email_address:
                try:
                    template_vars = {
                        'student_name': student_name,
                        'document_type': doc_type,
                        'document_id': doc_id,
                        'filename': filename,
                        'verification_date': verification_date,
                        'notes': notes or ''
                    }

                    if new_status == 'Verified':
                        subject, body = render_template('document_verified', template_vars)
                    elif new_status == 'Rejected':
                        subject, body = render_template('document_rejected', template_vars)
                    else:
                        template_vars['status'] = new_status
                        template_vars['updated_date'] = verification_date or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        subject, body = render_template('document_notification', template_vars)

                    if send_email(email_address, subject, body):
                        log_event('info', f"Status update email sent to {email_address}")
                        print(_t("shared.utils.document_manager.status_email_sent", default="Status update email sent to {email}", email=email_address))
                    else:
                        log_event('warning', f"Failed to send status update email to {email_address}")

                except Exception as e:
                    log_event('error', f"Error sending status update email: {e}")
                    print(_t("shared.utils.document_manager.status_updated_email_failed", default="Status updated but email notification failed"))

        except sqlite3.Error as e:
            print(_t("shared.utils.document_manager.database_error", default="Database error: {error}", error=str(e)))
            log_event('error', f"Database error in update_document_status: {e}")
