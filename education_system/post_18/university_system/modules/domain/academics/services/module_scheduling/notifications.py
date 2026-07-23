from education_system.post_18.university_system.infrastructure.database.db import get_connection


class NotificationsMixin:
    def _get_admin_email(self):
        """Get the administrator email address from system settings or users table"""
        try:
            # First try to get from system settings
            admin_email = self.get_system_setting('admin_email')
            if admin_email:
                return admin_email

            # Fallback: Get from users table (first admin user)
            conn = get_connection(self.db_path, row_factory=False)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT email FROM users
                WHERE role = 'admin'
                ORDER BY id
                LIMIT 1
            ''')
            result = cursor.fetchone()
            conn.close()

            if result:
                return result[0]

            # Ultimate fallback
            return 'admin@university.edu'

        except Exception:
            # Return default email if query fails
            return 'admin@university.edu'

    def create_notification(self, recipient_type, recipient_id, message, notification_type="info"):
        """Create a notification by sending an email using the proper email service"""
        try:
            # Import email service
            from education_system.post_18.university_system.infrastructure.email.email_service import send_email

            conn = get_connection(self.db_path, row_factory=False)
            cursor = conn.cursor()

            # Get recipient email based on type
            email_address = None
            recipient_name = "User"

            if recipient_type == 'instructor':
                cursor.execute('SELECT email, first_name, last_name FROM instructors WHERE id = ?', (recipient_id,))
                result = cursor.fetchone()
                if result:
                    email_address, first_name, last_name = result
                    recipient_name = f"{first_name or ''} {last_name or ''}".strip()
            elif recipient_type == 'student':
                cursor.execute('SELECT email, first_name, last_name FROM students WHERE student_id = ?', (recipient_id,))
                result = cursor.fetchone()
                if result:
                    email_address, first_name, last_name = result
                    recipient_name = f"{first_name or ''} {last_name or ''}".strip()

            conn.close()

            # Send email if we have a valid address
            if email_address:
                # Render email from template
                from education_system.post_18.university_system.infrastructure.email.template_utils import render_template

                subject, body = render_template('academics/module_scheduling_notification', {
                    'notification_type': notification_type.replace('_', ' ').title(),
                    'recipient_name': recipient_name,
                    'message': message
                })

                # Fallback if template not found
                if not subject or not body:
                    subject = f"Module Scheduling Notification - {notification_type.replace('_', ' ').title()}"
                    body = f"Dear {recipient_name},\n\n{message}\n\nBest regards,\nUniversity Module Scheduling System"

                send_email(email_address, subject, body)

        except Exception:
            # Silently fail - notifications are optional
            pass

    def send_schedule_change_notifications(self, schedule_id, change_description):
        """Send notifications when schedules change"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        # Get schedule details
        cursor.execute('''
        SELECT ms.module_code, ms.day_of_week, ms.start_time, ms.instructor_id,
               r.building, r.room_number
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        WHERE ms.id = ?
        ''', (schedule_id,))

        schedule = cursor.fetchone()
        if not schedule:
            conn.close()
            return

        module_code, day, start_time, instructor_id, building, room = schedule

        # Notify instructor
        message = f"Schedule change for {module_code}: {change_description}"
        if instructor_id:
            self.create_notification('instructor', str(instructor_id), message, 'schedule_change')

        # Notify students enrolled in the module
        cursor.execute('SELECT student_id FROM student_modules WHERE module_code = ?', (module_code,))
        students = cursor.fetchall()

        for student in students:
            if student[0]:
                self.create_notification('student', student[0], message, 'schedule_change')

        conn.close()
        print(f"Notifications sent for schedule change: {change_description}")

    def get_notifications(self, recipient_type, recipient_id, unread_only=True):
        """Get notifications for a user by checking their emails"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        # Get user email based on type
        email_address = None
        if recipient_type == 'instructor':
            cursor.execute('SELECT email FROM instructors WHERE id = ?', (recipient_id,))
            result = cursor.fetchone()
            if result:
                email_address = result[0]
        elif recipient_type == 'student':
            cursor.execute('SELECT email FROM students WHERE student_id = ?', (recipient_id,))
            result = cursor.fetchone()
            if result:
                email_address = result[0]

        if not email_address:
            conn.close()
            return []

        # Get emails from stored_emails table
        query = '''
        SELECT id, subject, body, created_date
        FROM stored_emails
        WHERE recipient_email = ?
        AND subject LIKE '%Module Scheduling%'
        ORDER BY created_date DESC
        '''

        cursor.execute(query, (email_address,))
        notifications = cursor.fetchall()
        conn.close()

        return notifications

    def mark_notification_read(self, notification_id):
        """Mark a notification as read - no-op for email-based notifications"""
        # Email-based notifications don't use read/unread status in the same way
        # This is kept for backward compatibility but does nothing
        pass

    def email_all_students_on_module(self, module_code, subject, message, include_instructor=True):
        """
        Email all students enrolled in a module, and optionally the instructor.

        Args:
            module_code: The module code to send emails for
            subject: Email subject line
            message: Email body message
            include_instructor: Whether to also email the instructor (default: True)

        Returns:
            dict: Summary of emails sent (students_emailed, instructor_emailed, errors)
        """
        from education_system.post_18.university_system.infrastructure.email.email_service import send_email

        summary = {
            'students_emailed': 0,
            'instructor_emailed': False,
            'errors': []
        }

        try:
            conn = get_connection(self.db_path, row_factory=False)
            cursor = conn.cursor()

            # Get module name for better messaging
            cursor.execute('SELECT module_name FROM modules WHERE module_code = ?', (module_code,))
            module_result = cursor.fetchone()
            module_name = module_result[0] if module_result else module_code

            # Email all students enrolled in the module
            cursor.execute('''
                SELECT DISTINCT s.student_id, s.email, s.first_name, s.last_name
                FROM students s
                INNER JOIN student_modules sm ON s.student_id = sm.student_id
                WHERE sm.module_code = ?
                AND s.email IS NOT NULL
                AND s.email != ''
            ''', (module_code,))

            students = cursor.fetchall()

            for student_id, email, first_name, last_name in students:
                try:
                    student_name = f"{first_name or ''} {last_name or ''}".strip() or "Student"

                    # Render email from template
                    from education_system.post_18.university_system.infrastructure.email.template_utils import render_template

                    template_subject, personalized_message = render_template('academics/module_student_notification', {
                        'custom_subject': subject,
                        'student_name': student_name,
                        'message': message,
                        'module_name': module_name,
                        'module_code': module_code
                    })

                    # Fallback if template not found
                    if not template_subject or not personalized_message:
                        personalized_message = f"Dear {student_name},\n\n{message}\n\nModule: {module_name} ({module_code})\n\nBest regards,\nUniversity Module Scheduling System"

                    send_email(email, subject, personalized_message)
                    summary['students_emailed'] += 1
                except Exception as e:
                    summary['errors'].append(f"Failed to email {email}: {str(e)}")

            # Email instructor if requested
            if include_instructor:
                cursor.execute('''
                    SELECT DISTINCT i.email, i.first_name, i.last_name
                    FROM instructors i
                    INNER JOIN module_schedule ms ON i.id = ms.instructor_id
                    WHERE ms.module_code = ?
                    AND i.email IS NOT NULL
                    AND i.email != ''
                    LIMIT 1
                ''', (module_code,))

                instructor = cursor.fetchone()
                if instructor:
                    email, first_name, last_name = instructor
                    try:
                        instructor_name = f"{first_name or ''} {last_name or ''}".strip() or "Instructor"
                        personalized_message = f"Dear {instructor_name},\n\n{message}\n\nModule: {module_name} ({module_code})\n\nBest regards,\nUniversity Module Scheduling System"

                        send_email(email, subject, personalized_message)
                        summary['instructor_emailed'] = True
                    except Exception as e:
                        summary['errors'].append(f"Failed to email instructor {email}: {str(e)}")

            conn.close()

        except Exception as e:
            summary['errors'].append(f"Database error: {str(e)}")

        return summary
