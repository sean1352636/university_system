from education_system.university_system.modules.shared.utils.document_manager._common import (
    datetime, timedelta, sqlite3,
    get_connection, _t, log_event,
    EMAIL_SYSTEM_AVAILABLE,
)


class NotificationsMixin:
    def notification_center(self):
        """Notification management center"""
        print("\n🔔 NOTIFICATION CENTER")
        print("1. View Pending Notifications")
        print("2. Send Custom Notification")
        print("3. Notification Campaign")
        print("4. Notification Templates")
        print("5. Return to Main Menu")

        choice = input("\nChoose option (1-5): ").strip()

        if choice == '1':
            self.view_pending_notifications()
        elif choice == '2':
            self.send_custom_notification()
        elif choice == '3':
            self.bulk_notification_campaign()
        elif choice == '4':
            self.notification_templates()

    def my_notifications(self):
        """Show student's notifications"""
        print(_t("shared.utils.document_manager.my_notifications_header", default="\n🔔 MY NOTIFICATIONS"))

        student_id = input(_t("shared.utils.document_manager.prompt_enter_student_id", default="Enter your student ID: ")).strip()

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT notification_id, notification_type, title, message,
                   created_date, is_read, priority
            FROM notifications
            WHERE recipient_id = ?
            ORDER BY created_date DESC
            LIMIT 20
            ''', (student_id,))

            notifications = cursor.fetchall()

            if not notifications:
                print(_t("shared.utils.document_manager.no_notifications_found", default="No notifications found."))
                conn.close()
                return

            print(f"\n📬 YOUR NOTIFICATIONS ({len(notifications)} total)")
            print("=" * 80)

            unread_count = 0

            for notification in notifications:
                notif_id, notif_type, title, message, created_date, is_read, priority = notification

                if not is_read:
                    unread_count += 1

                read_indicator = "📖" if is_read else "📩"
                priority_indicator = "🔴" if priority == 'high' else "🟡" if priority == 'medium' else "⚪"

                created_display = created_date[:16] if created_date else "Unknown"

                print(f"\n{read_indicator} {priority_indicator} {title}")
                print(f"   {message}")
                print(f"   {created_display}")

            print(f"\n📊 Summary: {unread_count} unread, {len(notifications)} total")

            # Mark as read option
            if unread_count > 0:
                mark_read = input("\nMark all as read? (y/n): ").strip().lower()
                if mark_read == 'y':
                    cursor.execute('''
                    UPDATE notifications
                    SET is_read = 1
                    WHERE recipient_id = ? AND is_read = 0
                    ''', (student_id,))

                    conn.commit()
                    print(_t("shared.utils.document_manager.all_notifications_read", default="All notifications marked as read."))

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def send_custom_notification(self):
        """Send a custom notification to selected users"""
        try:
            print("\n📧 SEND CUSTOM NOTIFICATION")

            print("\nRecipient Selection:")
            print("1. Specific Student")
            print("2. All Students")
            print("3. Students by Program")
            print("4. Students with Expiring Documents")

            choice = input("\nChoose option (1-4): ").strip()

            recipients = []
            conn = get_connection()
            cursor = conn.cursor()

            if choice == '1':
                student_id = self.select_student(cursor)
                if student_id:
                    recipients = [student_id]

            elif choice == '2':
                cursor.execute('SELECT student_id FROM students')
                recipients = [row[0] for row in cursor.fetchall()]

            elif choice == '3':
                program = input("Enter program name: ").strip()
                cursor.execute('SELECT student_id FROM students WHERE program = ?', (program,))
                recipients = [row[0] for row in cursor.fetchall()]

            elif choice == '4':
                days = input("Documents expiring within how many days? ").strip()
                days = int(days) if days else 30
                future_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')

                cursor.execute('''
                SELECT DISTINCT owner_id
                FROM documents
                WHERE source_type = 'student'
                AND expiry_date <= ? AND expiry_date >= date('now')
                ''', (future_date,))
                recipients = [row[0] for row in cursor.fetchall()]

            if not recipients:
                print("No recipients found.")
                conn.close()
                return

            print(f"\nFound {len(recipients)} recipients.")

            title = input("Notification title: ").strip()
            message = input("Notification message: ").strip()
            priority = input("Priority (normal/high/urgent): ").strip() or 'normal'

            confirm = input(f"\nSend notification to {len(recipients)} recipients? (y/n): ").strip().lower()

            if confirm == 'y':
                for recipient_id in recipients:
                    self.create_notification(cursor, recipient_id, 'custom', title, message)

                conn.commit()
                print(f"✅ Notifications queued for {len(recipients)} recipients.")
            else:
                print(_t("shared.utils.document_manager.operation_cancelled", default="Operation cancelled."))

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def bulk_notification_send(self):
        """Send bulk notifications"""
        # Alias to send_custom_notification
        self.send_custom_notification()

    def bulk_notification_campaign(self):
        """Create and manage notification campaigns"""
        try:
            print("\n📢 NOTIFICATION CAMPAIGN")

            campaign_name = input("Campaign name: ").strip()

            print("\nCampaign Type:")
            print("1. Document Reminder Campaign")
            print("2. Expiry Warning Campaign")
            print("3. Compliance Check Campaign")
            print("4. General Announcement")

            choice = input("\nChoose campaign type (1-4): ").strip()

            conn = get_connection()
            cursor = conn.cursor()

            if choice == '1':
                # Find students with missing required documents
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name
                FROM students s
                CROSS JOIN document_types dt
                LEFT JOIN documents sd ON s.student_id = sd.owner_id
                    AND sd.source_type = 'student'
                    AND dt.type_id = sd.type_id AND sd.is_current_version = 1
                WHERE dt.is_required = 1 AND dt.is_active = 1 AND sd.document_id IS NULL
                ''')

                students = cursor.fetchall()

                for student_id, first_name, last_name in students:
                    title = f"Document Reminder: {campaign_name}"
                    message = f"Dear {first_name}, you have required documents that need to be submitted."
                    self.create_notification(cursor, student_id, 'campaign', title, message)

                conn.commit()
                print(f"✅ Campaign sent to {len(students)} students.")

            elif choice == '2':
                days = int(input("Warn about documents expiring within how many days? ").strip() or "30")
                future_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')

                cursor.execute('''
                SELECT DISTINCT sd.owner_id as student_id, s.first_name, dt.type_name, sd.expiry_date
                FROM documents sd
                JOIN document_types dt ON sd.type_id = dt.type_id
                JOIN students s ON sd.owner_id = s.student_id
                WHERE sd.expiry_date <= ? AND sd.expiry_date >= date('now')
                  AND sd.is_current_version = 1
                ''', (future_date,))

                expiring = cursor.fetchall()

                for student_id, first_name, doc_type, expiry_date in expiring:
                    title = f"Document Expiry Warning: {doc_type}"
                    message = f"Dear {first_name}, your {doc_type} expires on {expiry_date}. Please renew."
                    self.create_notification(cursor, student_id, 'expiry_warning', title, message)

                conn.commit()
                print(f"✅ Expiry warnings sent to {len(expiring)} students.")

            elif choice == '4':
                # General announcement to all
                cursor.execute('SELECT student_id FROM students')
                all_students = cursor.fetchall()

                title = input("Announcement title: ").strip()
                message = input("Announcement message: ").strip()

                for student_id, in all_students:
                    self.create_notification(cursor, student_id, 'announcement', title, message)

                conn.commit()
                print(f"✅ Announcement sent to {len(all_students)} students.")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def view_pending_notifications(self):
        """View notifications that are pending delivery"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT notification_id, recipient_id, notification_type, title,
                   message, created_date, priority
            FROM notifications
            WHERE is_sent = 0
            ORDER BY priority DESC, created_date ASC
            ''')

            pending = cursor.fetchall()

            print("\n📬 PENDING NOTIFICATIONS")
            print("=" * 80)

            if not pending:
                print("No pending notifications.")
                conn.close()
                return

            for notif in pending:
                notif_id, recipient, notif_type, title, message, created, priority = notif

                print(f"\nNotification ID: {notif_id}")
                print(f"To: {recipient}")
                print(f"Type: {notif_type}")
                print(f"Priority: {priority}")
                print(f"Title: {title}")
                print(f"Message: {message[:100]}...")
                print(f"Created: {created}")
                print("-" * 80)

            print(f"\nTotal Pending: {len(pending)}")

            # Option to mark as sent or delete
            action = input("\nActions: (m)ark as sent, (d)elete, (q)uit: ").strip().lower()

            if action == 'm':
                cursor.execute('UPDATE notifications SET is_sent = 1 WHERE is_sent = 0')
                conn.commit()
                print("✅ All pending notifications marked as sent.")
            elif action == 'd':
                confirm = input("Delete all pending notifications? (y/n): ").strip().lower()
                if confirm == 'y':
                    cursor.execute('DELETE FROM notifications WHERE is_sent = 0')
                    conn.commit()
                    print("✅ Pending notifications deleted.")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def notification_templates(self):
        """Manage notification email templates"""
        print("\n📧 NOTIFICATION TEMPLATES")

        if not EMAIL_SYSTEM_AVAILABLE:
            print("Email system not available.")
            return

        print("\nAvailable Templates:")
        print("1. Document Upload Confirmation")
        print("2. Document Verification Notification")
        print("3. Document Expiry Warning")
        print("4. Document Rejection Notice")
        print("5. Workflow Step Completion")
        print("6. Custom Template")

        print("\nNote: Templates are managed by the email system.")
        print("Template files location: university_system/infrastructure/email/templates/")

        edit = input("\nWould you like to view template variables? (y/n): ").strip().lower()

        if edit == 'y':
            print("\nCommon Template Variables:")
            print("  {student_name} - Student's full name")
            print("  {student_id} - Student ID")
            print("  {document_type} - Type of document")
            print("  {document_id} - Document ID")
            print("  {upload_date} - Upload date")
            print("  {expiry_date} - Expiry date")
            print("  {status} - Document status")
            print("  {verification_notes} - Verification notes")
