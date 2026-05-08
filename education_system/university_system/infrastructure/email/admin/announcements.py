"""Announcements mixin for CommunicationDashboard."""

from __future__ import annotations

from education_system.university_system.infrastructure.email.admin._imports import (
    datetime,
    execute_db_operation,
    handle_exception,
    log_event,
    send_bulk,
)


class _AnnouncementsMixin:
    """Mixin providing announcement creation and retrieval."""

    @handle_exception
    def create_announcement(self, title, content, target_audience, is_urgent=0, start_date=None, end_date=None):
        """Create a new announcement"""
        # Check authentication and permissions
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to create announcements")
            return False

        # Only staff, admin, and instructors can create announcements
        allowed_roles = ['admin', 'staff', 'instructor']
        if self.auth.current_user['role'] not in allowed_roles:
            log_event('error', "Permission denied to create announcements")
            return False

        # Validate inputs
        if not title or not content or not target_audience:
            log_event('error', "Title, content, and target audience are required")
            return False

        # Set dates
        now = datetime.now()
        current_date = now.strftime('%Y-%m-%d %H:%M:%S')
        start_date = start_date if start_date else current_date

        # Validate date formats
        try:
            datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
            if end_date:
                datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            log_event('error', "Invalid date format. Use YYYY-MM-DD HH:MM:SS")
            return False

        def _create_announcement_op(cursor):
            creator_id = self.auth.current_user['id']

            cursor.execute('''
            INSERT INTO announcements (creator_id, title, content, target_audience, is_urgent, start_date, end_date, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (creator_id, title, content, target_audience, is_urgent, start_date, end_date, current_date, current_date))

            announcement_id = cursor.lastrowid

            # Log the action for auditing (pass cursor to avoid nested transactions)
            self._log_communication_action(creator_id, "create_announcement", f"Announcement created: {title}", cursor=cursor)

            # Send email notifications to target audience
            if target_audience == 'all':
                cursor.execute('''
                SELECT u.id, u.email,
                       COALESCE(up.email_notifications, 1) AS email_notifications,
                       1 AS announcement_notifications
                FROM users u
                LEFT JOIN user_preferences up ON CAST(u.id AS TEXT) = up.user_id
                ''')
            elif target_audience == 'students':
                cursor.execute('''
                SELECT u.id, u.email,
                       COALESCE(up.email_notifications, 1) AS email_notifications,
                       1 AS announcement_notifications
                FROM users u
                LEFT JOIN user_preferences up ON CAST(u.id AS TEXT) = up.user_id
                WHERE u.role = 'student'
                ''')
            elif target_audience == 'staff':
                cursor.execute('''
                SELECT u.id, u.email,
                       COALESCE(up.email_notifications, 1) AS email_notifications,
                       1 AS announcement_notifications
                FROM users u
                LEFT JOIN user_preferences up ON CAST(u.id AS TEXT) = up.user_id
                WHERE u.role IN ('staff', 'admin')
                ''')
            elif target_audience == 'instructors':
                cursor.execute('''
                SELECT u.id, u.email,
                       COALESCE(up.email_notifications, 1) AS email_notifications,
                       1 AS announcement_notifications
                FROM users u
                LEFT JOIN user_preferences up ON CAST(u.id AS TEXT) = up.user_id
                WHERE u.role = 'instructor'
                ''')
            else:
                # Specific course or department — not supported
                log_event(
                    'warning',
                    f"Target audience '{target_audience}' not implemented; skipping notifications."
                )
                return announcement_id

            recipients = cursor.fetchall()

            # Use bulk sending for announcements
            recipient_emails = []
            template_vars_list = []

            for recipient in recipients:
                recipient_id = recipient[0]
                recipient_email = recipient[1]
                email_notifications = recipient[2] if recipient[2] is not None else 1
                announcement_notifications = recipient[3] if recipient[3] is not None else 1

                if email_notifications and announcement_notifications:
                    recipient_emails.append(recipient_email)
                    template_vars = {
                        'announcement_title': title,
                        'announcement_body': content,
                        'title': '',  # These would need to be populated in a real implementation
                        'first_name': '',
                        'last_name': ''
                    }
                    template_vars_list.append(template_vars)

            if recipient_emails:
                send_bulk(recipient_emails, 'general_announcement', template_vars_list)

            return announcement_id

        try:
            result = execute_db_operation(_create_announcement_op)
            if result:
                log_event('info', "Announcement created successfully!")
            return result
        except Exception as e:
            log_event('error', f"Error creating announcement: {e}")
            return False

    @handle_exception
    def get_announcements(self, page=1, limit=10):
        """Get active announcements relevant to the current user"""
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to view announcements")
            return {'announcements': [], 'total_count': 0, 'page': page, 'limit': limit, 'total_pages': 0}

        user_id = self.auth.current_user['id']
        user_role = self.auth.current_user['role']
        current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        offset = (page - 1) * limit

        def _get_announcements(cursor):
            # Set role-based audience filters
            role_map = {
                'student': ['all', 'students'],
                'instructor': ['all', 'instructors'],
                'staff': ['all', 'staff'],
                'admin': ['all', 'staff']
            }

            audiences = role_map.get(user_role, ['all'])  # fallback to 'all' if unknown role
            role_placeholders = ','.join('?' for _ in audiences)

            # Fetch announcements
            query = f'''
                SELECT a.id, a.creator_id, u.username AS creator_username, a.title, a.content,
                       a.target_audience, a.is_urgent, a.start_date, a.end_date, a.created_at,
                       EXISTS (
                           SELECT 1 FROM announcement_viewers av
                           WHERE av.announcement_id = a.id AND av.viewer_id = ?
                       ) as is_viewed
                FROM announcements a
                JOIN users u ON a.creator_id = u.id
                WHERE a.is_active = 1
                  AND a.start_date <= ?
                  AND (a.end_date IS NULL OR a.end_date >= ?)
                  AND a.target_audience IN ({role_placeholders})
                ORDER BY a.is_urgent DESC, a.created_at DESC
                LIMIT ? OFFSET ?
            '''
            cursor.execute(query, (user_id, current_date, current_date, *audiences, limit, offset))

            announcements = []
            for row in cursor.fetchall():
                announcements.append({
                    'id': row[0],
                    'creator_id': row[1],
                    'creator': row[2],
                    'title': row[3],
                    'content': row[4],
                    'target_audience': row[5],
                    'is_urgent': bool(row[6]),
                    'start_date': row[7],
                    'end_date': row[8],
                    'created_at': row[9],
                    'is_viewed': bool(row[10])
                })

            # Count total relevant announcements
            count_query = f'''
                SELECT COUNT(*) FROM announcements a
                WHERE a.is_active = 1
                  AND a.start_date <= ?
                  AND (a.end_date IS NULL OR a.end_date >= ?)
                  AND a.target_audience IN ({role_placeholders})
            '''
            cursor.execute(count_query, (current_date, current_date, *audiences))
            total_count = cursor.fetchone()[0]

            return {
                'announcements': announcements,
                'total_count': total_count,
                'page': page,
                'limit': limit,
                'total_pages': (total_count + limit - 1) // limit if limit > 0 else 1
            }

        try:
            return execute_db_operation(_get_announcements)
        except Exception as e:
            log_event('error', f"Error getting announcements: {e}")
            return {'announcements': [], 'total_count': 0, 'page': page, 'limit': limit, 'total_pages': 0}
