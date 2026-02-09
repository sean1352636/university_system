"""Announcement management helpers."""

from __future__ import annotations

from datetime import datetime

from university_system.infrastructure.email.email_db_utilities import execute_db_operation
from university_system.infrastructure.email.email_service import send_bulk
from university_system.modules.shared.utils.logs import handle_exception, log_event
from university_system.modules.shared.utils.i18n import get_text as _t, init_i18n

init_i18n()


@handle_exception
def send_batch_announcement(title, body, filter_criteria=None):
    """Send a batch announcement to multiple students"""
    def _send_batch(cursor):
        # Build the query based on filter criteria
        query = "SELECT student_id, email_address, title, first_name, middle_name, last_name FROM students"
        params = []
        
        if filter_criteria:
            conditions = []
            
            if 'course' in filter_criteria:
                conditions.append("course = ?")
                params.append(filter_criteria['course'])
            
            if 'registration_year' in filter_criteria:
                conditions.append("substr(registration_datetime, 1, 4) = ?")
                params.append(str(filter_criteria['registration_year']))
            
            if 'module_code' in filter_criteria:
                # Join with student_modules to filter by module
                query = """
                SELECT s.student_id, s.email_address, s.title, s.first_name, s.middle_name, s.last_name 
                FROM students s
                JOIN student_modules sm ON s.student_id = sm.student_id
                """
                conditions.append("sm.module_code = ?")
                params.append(filter_criteria['module_code'])
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
        
        # Execute the query
        cursor.execute(query, params)
        students = cursor.fetchall()
        
        return students
    
    try:
        students = execute_db_operation(_send_batch)
        
        # Prepare for bulk send
        recipients = []
        template_vars_list = []
        
        for student in students:
            student_id, email_address, title, first_name, middle_name, last_name = student
            
            # Add to recipients list
            recipients.append(email_address)
            
            # Prepare template variables
            template_vars = {
                'student_id': student_id,
                'title': title,
                'first_name': first_name,
                'middle_name': middle_name or '',
                'last_name': last_name,
                'announcement_title': title,
                'announcement_body': body
            }
            
            template_vars_list.append(template_vars)
        
        # Send emails in bulk
        result = send_bulk(recipients, 'general_announcement', template_vars_list)
        
        log_event('info', f"Batch announcement processed: {result['success']} successful, {result['failure']} failed")
        return (result['success'], result['failure'], result['total'])
        
    except Exception as e:
        log_event('error', f"Error sending batch announcement: {e}")
        return (0, 0, 0)



@handle_exception
def display_announcements_menu(dashboard):
    """Display the announcements menu and handle user choices - FIXED VERSION"""
    while True:
        print("\n" + _t("announcements.title") + ":")
        print("=============")
        print("1. " + _t("announcements.view_active"))
        print("2. " + _t("announcements.create_new"))
        print("3. " + _t("announcements.update"))
        print("4. " + _t("announcements.back_to_dashboard"))

        choice = input(_t("announcements.enter_choice") + " (1-4): ")

        if choice == '1':
            # View active announcements
            announcements = dashboard.get_announcements()

            if announcements and announcements['total_count'] > 0:
                print("\n" + _t("announcements.active_announcements") + ":")
                print("=" * 70)

                for i, announcement in enumerate(announcements['announcements'], 1):
                    urgent = "[URGENT] " if announcement.get('is_urgent') else ""
                    viewed = "" if announcement.get('is_viewed') else "[NEW] "
                    print(f"{i}. {viewed}{urgent}{announcement.get('title')} - By {announcement.get('creator')} - {announcement.get('created_at')}")

                print("\n" + _t("announcements.showing_count", shown=len(announcements['announcements']), total=announcements['total_count'], page=announcements['page'], pages=announcements['total_pages']))

                # Add pagination and view options here
                input("\n" + _t("common.press_enter"))
            else:
                print(_t("announcements.no_active"))
                input(_t("common.press_enter"))

        elif choice == '2':
            # Check if user has permission to create announcements
            if dashboard.auth.current_user['role'] not in ['admin', 'staff', 'instructor']:
                print(_t("announcements.no_permission_create"))
                input(_t("common.press_enter"))
                continue

            # Create new announcement - FIXED VERSION
            print("\n" + _t("announcements.create_title") + ":")
            title = input(_t("announcements.announcement_title") + ": ").strip()

            if not title:
                print(_t("announcements.title_empty"))
                input(_t("common.press_enter"))
                continue

            print("\n" + _t("announcements.announcement_body_hint"))
            content_lines = []
            while True:
                line = input()
                if line == "END":
                    break
                content_lines.append(line)
            content = "\n".join(content_lines)

            if not content:
                print(_t("announcements.content_empty"))
                input(_t("common.press_enter"))
                continue

            print("\n" + _t("announcements.target_audience") + ":")
            print("1. " + _t("announcements.all_users"))
            print("2. " + _t("announcements.students_only"))
            print("3. " + _t("announcements.staff_only"))
            print("4. " + _t("announcements.instructors_only"))

            audience_choice = input(_t("announcements.choose_target") + " (1-4): ").strip()

            if audience_choice == '1':
                target_audience = "all"
            elif audience_choice == '2':
                target_audience = "students"
            elif audience_choice == '3':
                target_audience = "staff"
            elif audience_choice == '4':
                target_audience = "instructors"
            else:
                print(_t("announcements.invalid_using_all"))
                target_audience = "all"

            is_urgent_input = input(_t("announcements.mark_urgent") + " (y/n): ").strip().lower()
            is_urgent = 1 if is_urgent_input == 'y' else 0

            # Get dates with proper validation - FIXED
            start_date_input = input(_t("announcements.start_date_prompt") + ": ").strip()
            end_date_input = input(_t("announcements.end_date_prompt") + ": ").strip()

            # Handle start date
            if not start_date_input:
                start_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            else:
                try:
                    # Validate the date format
                    datetime.strptime(start_date_input, '%Y-%m-%d %H:%M:%S')
                    start_date = start_date_input
                except ValueError:
                    print(_t("announcements.invalid_start_date"))
                    start_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Handle end date
            end_date = None
            if end_date_input:
                try:
                    # Validate the date format
                    datetime.strptime(end_date_input, '%Y-%m-%d %H:%M:%S')
                    end_date = end_date_input
                except ValueError:
                    print(_t("announcements.invalid_end_date"))
                    end_date = None

            # Create the announcement
            try:
                result = dashboard.create_announcement(title, content, target_audience, is_urgent, start_date, end_date)

                if result:
                    print(_t("announcements.created_success"))
                    log_event('info', f"Announcement '{title}' created by {dashboard.auth.current_user['username']}")
                else:
                    print(_t("announcements.failed_create"))
                    log_event('error', f"Failed to create announcement '{title}'")

            except Exception as e:
                print(_t("announcements.error_creating", error=str(e)))
                log_event('error', f"Exception creating announcement: {e}")

            input(_t("common.press_enter"))
        
        elif choice == '3':
            # Update announcement functionality - FIXED VERSION
            try:
                # Check if user has permission to update announcements
                if dashboard.auth.current_user['role'] not in ['admin', 'staff', 'instructor']:
                    print(_t("announcements.no_permission_update"))
                    input(_t("common.press_enter"))
                    continue

                # Get list of announcements created by this user
                def _get_user_announcements(cursor):
                    cursor.execute('''
                    SELECT a.id, a.title, a.content, a.target_audience, a.is_urgent,
                           a.start_date, a.end_date, a.is_active
                    FROM announcements a
                    WHERE a.creator_id = ?
                    ORDER BY a.created_at DESC
                    ''', (dashboard.auth.current_user['id'],))

                    return cursor.fetchall()

                announcements = execute_db_operation(_get_user_announcements)

                if not announcements:
                    print("\n" + _t("announcements.no_announcements_created"))
                    input(_t("common.press_enter"))
                    continue

                print("\n" + _t("announcements.your_announcements") + ":")
                print("=" * 80)
                print(f"{_t('common.id'):<5}{_t('common.title'):<35}{_t('announcements.status'):<10}{_t('announcements.start_date'):<20}{_t('announcements.end_date'):<20}")
                print("-" * 80)

                for announcement in announcements:
                    ann_id, title, content, target_audience, is_urgent, start_date, end_date, is_active = announcement
                    status = _t("announcements.active") if is_active else _t("announcements.inactive")

                    # Truncate title if too long
                    disp_title = title[:32] + "..." if len(title) > 32 else title

                    print(f"{ann_id:<5}{disp_title:<35}{status:<10}{start_date:<20}{end_date if end_date else _t('common.none'):<20}")

                # Select announcement to update
                ann_choice = input("\n" + _t("announcements.enter_id_update") + ": ").strip()
                if not ann_choice or not ann_choice.isdigit() or int(ann_choice) == 0:
                    continue
                
                ann_id = int(ann_choice)
                
                # Get the selected announcement
                def _get_announcement(cursor):
                    cursor.execute('''
                    SELECT a.id, a.title, a.content, a.target_audience, a.is_urgent, 
                           a.start_date, a.end_date, a.is_active
                    FROM announcements a
                    WHERE a.id = ? AND a.creator_id = ?
                    ''', (ann_id, dashboard.auth.current_user['id']))
                    
                    return cursor.fetchone()
                
                announcement = execute_db_operation(_get_announcement)
                
                if not announcement:
                    print(_t("announcements.not_found_or_no_permission"))
                    input(_t("common.press_enter"))
                    continue

                ann_id, title, content, target_audience, is_urgent, start_date, end_date, is_active = announcement

                print("\n" + _t("announcements.update_announcement") + ":")
                print("=" * 80)
                print(f"{_t('announcements.current_title')}: {title}")
                print(f"{_t('announcements.current_status')}: {_t('announcements.active') if is_active else _t('announcements.inactive')}")
                print(f"{_t('announcements.current_target')}: {target_audience}")
                print(f"{_t('announcements.current_urgency')}: {_t('announcements.urgent') if is_urgent else _t('announcements.normal')}")
                print(f"{_t('announcements.start_date')}: {start_date}")
                print(f"{_t('announcements.end_date')}: {end_date if end_date else _t('common.none')}")
                print("-" * 80)
                print(_t("announcements.content_preview") + ":")

                # Show content preview (first 100 chars)
                content_preview = content[:100] + "..." if len(content) > 100 else content
                print(content_preview)
                print("=" * 80)

                # Update menu
                print("\n" + _t("announcements.what_to_update"))
                print("1. " + _t("announcements.title_option"))
                print("2. " + _t("announcements.content_option"))
                print("3. " + _t("announcements.target_option"))
                print("4. " + _t("announcements.urgency_option"))
                print("5. " + _t("announcements.dates_option"))
                print("6. " + _t("announcements.status_option"))
                print("7. " + _t("announcements.cancel_option"))

                update_choice = input("\n" + _t("announcements.enter_option") + " (1-7): ").strip()
                
                # Initialize dictionary to track changes
                updates = {}
                
                if update_choice == '1':
                    # Update title
                    new_title = input(_t("announcements.enter_new_title", current=title) + ": ").strip()
                    if new_title and new_title != title:
                        updates['title'] = new_title

                elif update_choice == '2':
                    # Update content
                    print("\n" + _t("announcements.current_content") + ":")
                    print("-" * 80)
                    print(content)
                    print("-" * 80)

                    print("\n" + _t("announcements.enter_new_content"))
                    new_content_lines = []
                    while True:
                        line = input()
                        if line == "END":
                            break
                        new_content_lines.append(line)

                    new_content = "\n".join(new_content_lines)

                    if new_content and new_content != content:
                        updates['content'] = new_content

                elif update_choice == '3':
                    # Update target audience
                    print("\n" + _t("announcements.target_audience") + ":")
                    print("1. " + _t("announcements.all_users"))
                    print("2. " + _t("announcements.students_only"))
                    print("3. " + _t("announcements.staff_only"))
                    print("4. " + _t("announcements.instructors_only"))

                    audience_choice = input(_t("announcements.choose_target_current", current=target_audience) + ": ").strip()

                    new_target = None
                    if audience_choice == '1':
                        new_target = "all"
                    elif audience_choice == '2':
                        new_target = "students"
                    elif audience_choice == '3':
                        new_target = "staff"
                    elif audience_choice == '4':
                        new_target = "instructors"

                    if new_target and new_target != target_audience:
                        updates['target_audience'] = new_target

                elif update_choice == '4':
                    # Update urgency
                    current_urgency = _t("announcements.urgent") if is_urgent else _t("announcements.normal")
                    new_urgency = input(_t("announcements.mark_urgent_current", current=current_urgency) + ": ").strip().lower()

                    if new_urgency in ['y', 'n']:
                        new_is_urgent = 1 if new_urgency == 'y' else 0
                        if new_is_urgent != is_urgent:
                            updates['is_urgent'] = new_is_urgent

                elif update_choice == '5':
                    # Update dates - FIXED VERSION
                    print(_t("announcements.current_start_date", date=start_date))
                    new_start = input(_t("announcements.new_start_date") + ": ").strip()

                    print(_t("announcements.current_end_date", date=end_date if end_date else _t("common.none")))
                    new_end = input(_t("announcements.new_end_date") + ": ").strip()

                    # Validate date formats
                    valid_dates = True
                    if new_start:
                        try:
                            datetime.strptime(new_start, '%Y-%m-%d %H:%M:%S')
                            updates['start_date'] = new_start
                        except ValueError:
                            print(_t("announcements.invalid_start_format"))
                            valid_dates = False

                    if new_end and new_end.lower() != 'remove':
                        try:
                            datetime.strptime(new_end, '%Y-%m-%d %H:%M:%S')
                            updates['end_date'] = new_end
                        except ValueError:
                            print(_t("announcements.invalid_end_format"))
                            valid_dates = False
                    elif new_end and new_end.lower() == 'remove':
                        updates['end_date'] = None

                    if not valid_dates:
                        print(_t("announcements.dates_cancelled"))
                        input(_t("common.press_enter"))
                        continue

                elif update_choice == '6':
                    # Update active status
                    current_status = _t("announcements.active") if is_active else _t("announcements.inactive")
                    new_status = input(_t("announcements.set_active", current=current_status) + ": ").strip().lower()

                    if new_status in ['y', 'n']:
                        new_is_active = 1 if new_status == 'y' else 0
                        if new_is_active != is_active:
                            updates['is_active'] = new_is_active

                elif update_choice == '7':
                    # Cancel
                    continue

                else:
                    print(_t("common.invalid_choice"))
                    input(_t("common.press_enter"))
                    continue

                # Apply updates if any
                if not updates:
                    print(_t("announcements.no_changes"))
                    input(_t("common.press_enter"))
                    continue

                # Confirm changes
                print("\n" + _t("announcements.making_changes"))
                for field, value in updates.items():
                    if field == 'end_date' and value is None:
                        print(f"- {field}: " + _t("announcements.removing_end_date"))
                    else:
                        print(f"- {field}: {value}")

                confirm = input("\n" + _t("announcements.confirm_changes") + " (y/n): ").strip().lower()
                if confirm != 'y':
                    print(_t("announcements.update_cancelled"))
                    input(_t("common.press_enter"))
                    continue
                
                # Update in database
                try:
                    # Build the SQL query dynamically
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    def _update_announcement(cursor):
                        # Start building the query
                        query_parts = []
                        params = []
                        
                        for field, value in updates.items():
                            query_parts.append(f"{field} = ?")
                            params.append(value)
                        
                        # Always update the 'updated_at' field
                        query_parts.append("updated_at = ?")
                        params.append(current_time)
                        
                        # Add the WHERE clause parameters
                        params.extend([ann_id, dashboard.auth.current_user['id']])
                        
                        # Execute the query
                        cursor.execute(f'''
                        UPDATE announcements
                        SET {", ".join(query_parts)}
                        WHERE id = ? AND creator_id = ?
                        ''', params)
                        
                        # Log the action
                        dashboard._log_communication_action(
                            dashboard.auth.current_user['id'],
                            "update_announcement",
                            f"Updated announcement #{ann_id}: {title}"
                        )
                        return True
                    
                    execute_db_operation(_update_announcement)
                    print(_t("announcements.updated_success"))

                except Exception as e:
                    log_event('error', f"Error updating announcement: {e}")
                    print(_t("announcements.error_updating", error=str(e)))

                input(_t("common.press_enter"))

            except Exception as e:
                log_event('error', f"Error in update announcement: {e}")
                print(_t("announcements.error_occurred", error=str(e)))
                input(_t("common.press_enter"))

        elif choice == '4':
            break

        else:
            print(_t("common.invalid_choice"))



@handle_exception  
def create_announcement_safe(dashboard, title, content, target_audience, is_urgent=0, start_date=None, end_date=None):
    """Safe version of create_announcement with better error handling"""
    
    # Check authentication and permissions
    if not dashboard.auth or not dashboard.auth.current_user:
        log_event('error', "Must be logged in to create announcements")
        return False
    
    # Only staff, admin, and instructors can create announcements
    allowed_roles = ['admin', 'staff', 'instructor']
    if dashboard.auth.current_user['role'] not in allowed_roles:
        log_event('error', "Permission denied to create announcements")
        return False
    
    # Validate inputs
    if not title or not content or not target_audience:
        log_event('error', "Title, content, and target audience are required")
        return False
    
    # Set dates with proper error handling
    now = datetime.now()
    current_date = now.strftime('%Y-%m-%d %H:%M:%S')
    
    if not start_date:
        start_date = current_date
    
    # Validate date formats if provided
    try:
        if start_date:
            datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
        if end_date:
            datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
    except ValueError as e:
        log_event('error', f"Invalid date format: {e}")
        return False
    
    def _create_announcement_op(cursor):
        try:
            creator_id = dashboard.auth.current_user['id']
            
            cursor.execute('''
            INSERT INTO announcements (creator_id, title, content, target_audience, is_urgent, start_date, end_date, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (creator_id, title, content, target_audience, is_urgent, start_date, end_date, current_date, current_date))
            
            announcement_id = cursor.lastrowid
            
            # Log the action for auditing
            dashboard._log_communication_action(creator_id, "create_announcement", f"Announcement created: {title}")
            
            # Send email notifications to target audience (with error handling)
            try:
                _send_announcement_notifications(cursor, target_audience, title, content)
            except Exception as e:
                log_event('warning', f"Error sending announcement notifications: {e}")
                # Don't fail the entire operation for notification errors
            
            return announcement_id
            
        except Exception as e:
            log_event('error', f"Database error creating announcement: {e}")
            return False
    
    try:
        result = execute_db_operation(_create_announcement_op)
        if result:
            log_event('info', f"Announcement created successfully with ID {result}")
        return result
    except Exception as e:
        log_event('error', f"Error creating announcement: {e}")
        return False



def _send_announcement_notifications(cursor, target_audience, title, content):
    """Helper function to send announcement notifications"""
    
    # Build recipient query based on target audience
    if target_audience == 'all':
        cursor.execute('''
        SELECT u.id, u.email, np.email_notifications, np.announcement_notifications 
        FROM users u
        LEFT JOIN notification_preferences np ON u.id = np.user_id
        ''')
    elif target_audience == 'students':
        cursor.execute('''
        SELECT u.id, u.email, np.email_notifications, np.announcement_notifications 
        FROM users u
        LEFT JOIN notification_preferences np ON u.id = np.user_id
        WHERE u.role = 'student'
        ''')
    elif target_audience == 'staff':
        cursor.execute('''
        SELECT u.id, u.email, np.email_notifications, np.announcement_notifications 
        FROM users u
        LEFT JOIN notification_preferences np ON u.id = np.user_id
        WHERE u.role IN ('staff', 'admin')
        ''')
    elif target_audience == 'instructors':
        cursor.execute('''
        SELECT u.id, u.email, np.email_notifications, np.announcement_notifications 
        FROM users u
        LEFT JOIN notification_preferences np ON u.id = np.user_id
        WHERE u.role = 'instructor'
        ''')
    else:
        log_event('warning', f"Target audience '{target_audience}' not implemented for notifications")
        return

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
                'title': '',  # These would need to be populated with actual user data
                'first_name': '',
                'last_name': ''
            }
            template_vars_list.append(template_vars)
    
    if recipient_emails:
        try:
            send_bulk(recipient_emails, 'general_announcement', template_vars_list)
            log_event('info', f"Sent announcement notifications to {len(recipient_emails)} recipients")
        except Exception as e:
            log_event('error', f"Error sending bulk announcement notifications: {e}")
            raise



@handle_exception
def mark_announcement_viewed(dashboard, announcement_id):
    """Mark an announcement as viewed by the current user"""
    if not dashboard.auth or not dashboard.auth.current_user:
        log_event('error', "Must be logged in to mark announcements as viewed")
        return False
    
    def _mark_viewed(cursor):
        user_id = dashboard.auth.current_user['id']
        viewed_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Check if already viewed
        cursor.execute('''
        SELECT id FROM announcement_viewers 
        WHERE announcement_id = ? AND viewer_id = ?
        ''', (announcement_id, user_id))
        
        if cursor.fetchone():
            return True  # Already viewed
        
        # Mark as viewed
        cursor.execute('''
        INSERT INTO announcement_viewers (announcement_id, viewer_id, viewed_at)
        VALUES (?, ?, ?)
        ''', (announcement_id, user_id, viewed_at))
        
        return True
    
    try:
        return execute_db_operation(_mark_viewed)
    except Exception as e:
        log_event('error', f"Error marking announcement as viewed: {e}")
        return False



@handle_exception
def get_announcement_by_id(dashboard, announcement_id):
    """Get a specific announcement by ID"""
    if not dashboard.auth or not dashboard.auth.current_user:
        return None
    
    def _get_announcement(cursor):
        cursor.execute('''
        SELECT a.id, a.creator_id, u.username as creator_username, a.title, a.content,
               a.target_audience, a.is_urgent, a.start_date, a.end_date, a.created_at,
               a.updated_at, a.is_active
        FROM announcements a
        JOIN users u ON a.creator_id = u.id
        WHERE a.id = ?
        ''', (announcement_id,))
        
        row = cursor.fetchone()
        if row:
            return {
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
                'updated_at': row[10],
                'is_active': bool(row[11])
            }
        return None
    
    try:
        return execute_db_operation(_get_announcement)
    except Exception as e:
        log_event('error', f"Error getting announcement: {e}")
        return None



@handle_exception
def deactivate_announcement(dashboard, announcement_id):
    """Deactivate (hide) an announcement"""
    if not dashboard.auth or not dashboard.auth.current_user:
        return False
    
    def _deactivate_announcement(cursor):
        user_id = dashboard.auth.current_user['id']
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Check if user can deactivate this announcement
        cursor.execute('''
        SELECT creator_id FROM announcements WHERE id = ?
        ''', (announcement_id,))
        
        result = cursor.fetchone()
        if not result:
            return False
        
        creator_id = result[0]
        
        # Only creator or admin can deactivate
        if user_id != creator_id and dashboard.auth.current_user['role'] != 'admin':
            log_event('error', f"User {user_id} cannot deactivate announcement {announcement_id}")
            return False
        
        # Deactivate the announcement
        cursor.execute('''
        UPDATE announcements 
        SET is_active = 0, updated_at = ?
        WHERE id = ?
        ''', (current_time, announcement_id))
        
        # Log the action
        dashboard._log_communication_action(
            user_id,
            "deactivate_announcement",
            f"Deactivated announcement #{announcement_id}"
        )
        
        return True
    
    try:
        return execute_db_operation(_deactivate_announcement)
    except Exception as e:
        log_event('error', f"Error deactivating announcement: {e}")
        return False
