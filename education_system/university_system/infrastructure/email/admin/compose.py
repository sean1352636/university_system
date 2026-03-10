"""Email composition and user selection mixin for CommunicationDashboard."""

from __future__ import annotations

from education_system.university_system.infrastructure.email.admin._imports import (
    datetime,
    config,
    execute_db_operation,
    handle_exception,
    log_event,
    logger,
    queue_email,
    schedule_send,
    wait_for_email_queue,
)
from education_system.university_system.infrastructure.email.admin.users import search_users, list_all_users


class _ComposeMixin:
    """Mixin providing email composition and role-based sending."""

    @handle_exception
    def send_email_to_role(self, role, subject, body):
        """Send email to all users with a specific role"""
        if not self.auth or not self.auth.current_user:
            logger.info("You must be logged in to send emails.")
            return False

        def _send_to_role(cursor):
            # Get all users with the specified role
            cursor.execute('''
            SELECT id, email, first_name, last_name, username
            FROM users
            WHERE role = ?
            ORDER BY first_name, last_name
            ''', (role,))

            users = cursor.fetchall()

            if not users:
                logger.info(f"No users found with role '{role}'.")
                return False

            logger.info(f"Found {len(users)} users with role '{role}':")
            for user in users[:5]:  # Show first 5
                logger.info(f"  - {user[2]} {user[3]} ({user[1]})")

            if len(users) > 5:
                logger.info(f"  ... and {len(users) - 5} more")

            confirm = input(f"\nSend email to all {len(users)} {role}s? (y/n): ")
            if confirm.lower() != 'y':
                logger.info("Email cancelled.")
                return False

            # Send emails
            success_count = 0
            failure_count = 0

            for user in users:
                try:
                    success = queue_email(user[1], subject, body)
                    if success:
                        success_count += 1
                    else:
                        failure_count += 1
                except Exception as e:
                    log_event('error', f"Error processing email for {user[1]}: {e}")
                    failure_count += 1

            if config.get('database_only_mode', True):
                logger.error(f"\nEmails stored in database: {success_count} successful, {failure_count} failed")
            else:
                logger.error(f"\nEmails queued: {success_count} successful, {failure_count} failed")

            # Log the bulk send
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
            INSERT INTO email_log (recipient, subject, sent_date, status, related_to)
            VALUES (?, ?, ?, ?, ?)
            ''', (
                f"Bulk to {role}s",
                subject,
                current_time,
                'stored' if config.get('database_only_mode', True) else 'bulk_queued',
                f"Bulk Email to {role}s from {self.auth.current_user['username']}"
            ))

            return True

        try:
            return execute_db_operation(_send_to_role)
        except Exception as e:
            log_event('error', f"Error sending bulk email to {role}: {e}")
            return False

    @handle_exception
    def compose_email_with_user_selection(self):
        """Enhanced email composition with user selection interface"""
        if not self.auth or not self.auth.current_user:
            logger.info("You must be logged in to send emails.")
            return False

        logger.info("\nCompose New Email")
        logger.info("=================")

        # Get recipients using the selection interface
        recipients = self.display_user_selection_menu()

        if not recipients:
            logger.info("Email composition cancelled.")
            return False

        logger.info(f"\nComposing email for {len(recipients)} recipient(s):")
        for recipient in recipients:
            logger.info(f"  - {recipient['full_name']} ({recipient['email']})")

        # Get email details
        subject = input("\nEmail Subject: ").strip()
        if not subject:
            logger.info("Subject cannot be empty.")
            return False

        logger.info("\nEmail Body (type 'END' on a new line to finish):")
        body_lines = []
        while True:
            line = input()
            if line == 'END':
                break
            body_lines.append(line)

        body = "\n".join(body_lines)
        if not body:
            logger.info("Email body cannot be empty.")
            return False

        # Ask for email options
        logger.info("\nEmail Options:")
        send_immediately = input("Send immediately? (y/n, default: y): ").strip().lower()
        send_immediately = send_immediately != 'n'

        cc_emails = input("CC emails (comma-separated, optional): ").strip()
        cc_list = [email.strip() for email in cc_emails.split(',') if email.strip()] if cc_emails else None

        bcc_emails = input("BCC emails (comma-separated, optional): ").strip()
        bcc_list = [email.strip() for email in bcc_emails.split(',') if email.strip()] if bcc_emails else None

        # Confirm sending
        logger.info(f"\nEmail Summary:")
        logger.info(f"Subject: {subject}")
        logger.info(f"Recipients: {len(recipients)}")
        logger.info(f"CC: {len(cc_list) if cc_list else 0}")
        logger.info(f"BCC: {len(bcc_list) if bcc_list else 0}")
        logger.info(f"Mode: {'Database Storage' if config.get('database_only_mode', True) else 'SMTP Sending'}")
        logger.info(f"Send immediately: {'Yes' if send_immediately else 'No'}")

        if not send_immediately:
            # Get scheduling details
            logger.info("\nSchedule Email:")
            try:
                year = int(input("Year (YYYY): "))
                month = int(input("Month (MM): "))
                day = int(input("Day (DD): "))
                hour = int(input("Hour (0-23): "))
                minute = int(input("Minute (0-59): "))

                scheduled_date = datetime(year, month, day, hour, minute)

                if scheduled_date <= datetime.now():
                    logger.info("Scheduled date must be in the future.")
                    return False

                logger.info(f"Scheduled for: {scheduled_date}")
            except ValueError:
                logger.info("Invalid date/time format.")
                return False

        confirm = input("\nSend this email? (y/n): ").strip().lower()
        if confirm != 'y':
            logger.info("Email cancelled.")
            return False

        # Send the emails
        success_count = 0
        failure_count = 0

        if send_immediately:
            # Send immediately
            for recipient in recipients:
                try:
                    success = queue_email(
                        recipient['email'],
                        subject,
                        body,
                        cc=cc_list,
                        bcc=bcc_list
                    )
                    if success:
                        success_count += 1
                    else:
                        failure_count += 1
                except Exception as e:
                    log_event('error', f"Error processing email for {recipient['email']}: {e}")
                    failure_count += 1

            if config.get('database_only_mode', True):
                logger.error(f"\nEmails stored in database: {success_count} successful, {failure_count} failed")
            else:
                logger.error(f"\nEmails queued: {success_count} successful, {failure_count} failed")

                if success_count > 0:
                    wait_choice = input("Wait for all emails to be sent? (y/n): ")
                    if wait_choice.lower() == 'y':
                        wait_for_email_queue()
                        logger.info("All emails have been sent.")
        else:
            # Schedule emails
            recipient_emails = [r['email'] for r in recipients]

            # Create a simple template for scheduled sending
            template_name = f"scheduled_email_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Create temporary template
            create_template(template_name, subject, body)

            # Schedule the emails
            result = schedule_send(scheduled_date, recipient_emails, template_name)

            logger.error(f"\nEmails scheduled: {result['success']} successful, {result['failure']} failed")
            logger.info(f"Scheduled for: {scheduled_date}")

        # Log the activity
        try:
            def _log_activity(cursor):
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Log each email sent
                for recipient in recipients:
                    cursor.execute('''
                    INSERT INTO email_log (recipient, subject, sent_date, status, related_to)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (
                        recipient['email'],
                        subject,
                        current_time,
                        'stored' if config.get('database_only_mode', True) else ('queued' if send_immediately else 'scheduled'),
                        f"Manual Email from {self.auth.current_user['username']}"
                    ))
                return True

            execute_db_operation(_log_activity)
        except Exception as e:
            log_event('error', f"Error logging email activity: {e}")

        return True

    @handle_exception
    def display_user_selection_menu(self):
        """Display user selection menu for email composition"""
        selected_recipients = []
        page = 1
        limit = 15
        role_filter = None
        search_term = None

        while True:
            logger.info("\n" + "="*80)
            logger.info("SELECT EMAIL RECIPIENTS")
            logger.info("="*80)

            # Show current selections
            if selected_recipients:
                logger.info(f"Selected Recipients ({len(selected_recipients)}):")
                for i, recipient in enumerate(selected_recipients, 1):
                    logger.info(f"  {i}. {recipient['full_name']} ({recipient['username']}) - {recipient['email']}")
                logger.info("-" * 80)

            # Get users to display
            if search_term:
                users_data = search_users(self.auth, search_term)
                users_result = {
                    'users': users_data[:limit],
                    'total_count': len(users_data),
                    'page': 1,
                    'limit': limit,
                    'total_pages': (len(users_data) + limit - 1) // limit
                }
            else:
                users_result = list_all_users(self.auth, page, limit, role_filter)

            if users_result['total_count'] == 0:
                logger.info("No users found.")
            else:
                # Display filter info
                filter_info = []
                if role_filter:
                    filter_info.append(f"Role: {role_filter}")
                if search_term:
                    filter_info.append(f"Search: {search_term}")

                if filter_info:
                    logger.info(f"Filters: {', '.join(filter_info)}")

                logger.info(f"\nUsers (Page {users_result['page']} of {users_result['total_pages']}):")
                logger.info(f"{'#':<3}{'Name':<25}{'Username':<15}{'Email':<30}{'Role':<10}{'Selected'}")
                logger.info("-" * 80)

                for i, user in enumerate(users_result['users'], 1):
                    # Check if user is already selected
                    is_selected = any(r['id'] == user['id'] for r in selected_recipients)
                    selected_mark = "\u2713" if is_selected else ""

                    # Truncate long names/emails for display
                    name = user['full_name'][:24] if len(user['full_name']) > 24 else user['full_name']
                    username = user['username'][:14] if len(user['username']) > 14 else user['username']
                    email = user['email'][:29] if len(user['email']) > 29 else user['email']

                    logger.info(f"{i:<3}{name:<25}{username:<15}{email:<30}{user['role']:<10}{selected_mark}")

            # Menu options
            logger.info("\nOptions:")
            logger.info("1. Select user by number")
            logger.info("2. Remove selected recipient")
            logger.info("3. Next page") if users_result['page'] < users_result['total_pages'] else None
            logger.info("4. Previous page") if users_result['page'] > 1 else None
            logger.info("5. Filter by role")
            logger.info("6. Search users")
            logger.info("7. Clear filters")
            logger.info("8. Select all on page")
            logger.info("9. Clear all selected")
            logger.info("10. Continue to compose email") if selected_recipients else None
            logger.info("0. Cancel")

            choice = input("\nEnter your choice: ").strip()

            if choice == '1':
                # Select user by number
                try:
                    user_num = int(input("Enter user number to select/deselect: "))
                    if 1 <= user_num <= len(users_result['users']):
                        selected_user = users_result['users'][user_num - 1]

                        # Check if already selected
                        if any(r['id'] == selected_user['id'] for r in selected_recipients):
                            # Remove from selection
                            selected_recipients = [r for r in selected_recipients if r['id'] != selected_user['id']]
                            logger.info(f"Removed {selected_user['full_name']} from selection.")
                        else:
                            # Add to selection
                            selected_recipients.append(selected_user)
                            logger.info(f"Added {selected_user['full_name']} to selection.")
                    else:
                        logger.info("Invalid user number.")
                except ValueError:
                    logger.info("Please enter a valid number.")

            elif choice == '2':
                # Remove selected recipient
                if not selected_recipients:
                    logger.info("No recipients selected.")
                    continue

                logger.info("\nSelected Recipients:")
                for i, recipient in enumerate(selected_recipients, 1):
                    logger.info(f"{i}. {recipient['full_name']} ({recipient['email']})")

                try:
                    remove_num = int(input("Enter number to remove: "))
                    if 1 <= remove_num <= len(selected_recipients):
                        removed = selected_recipients.pop(remove_num - 1)
                        logger.info(f"Removed {removed['full_name']} from selection.")
                    else:
                        logger.info("Invalid number.")
                except ValueError:
                    logger.info("Please enter a valid number.")

            elif choice == '3' and users_result['page'] < users_result['total_pages']:
                # Next page
                page += 1

            elif choice == '4' and users_result['page'] > 1:
                # Previous page
                page -= 1

            elif choice == '5':
                # Filter by role
                logger.info("\nFilter by role:")
                logger.info("1. Students")
                logger.info("2. Staff")
                logger.info("3. Instructors")
                logger.info("4. Admins")
                logger.info("5. Parents")
                logger.info("6. Clear role filter")

                role_choice = input("Enter choice: ").strip()

                if role_choice == '1':
                    role_filter = 'student'
                    page = 1
                elif role_choice == '2':
                    role_filter = 'staff'
                    page = 1
                elif role_choice == '3':
                    role_filter = 'instructor'
                    page = 1
                elif role_choice == '4':
                    role_filter = 'admin'
                    page = 1
                elif role_choice == '5':
                    role_filter = 'parent'
                    page = 1
                elif role_choice == '6':
                    role_filter = None
                    page = 1
                else:
                    logger.info("Invalid choice.")

            elif choice == '6':
                # Search users
                search_term = input("Enter search term (name, username, or email): ").strip()
                if not search_term:
                    search_term = None
                page = 1

            elif choice == '7':
                # Clear filters
                role_filter = None
                search_term = None
                page = 1
                logger.info("Filters cleared.")

            elif choice == '8':
                # Select all on page
                for user in users_result['users']:
                    if not any(r['id'] == user['id'] for r in selected_recipients):
                        selected_recipients.append(user)
                logger.info(f"Added {len(users_result['users'])} users to selection.")

            elif choice == '9':
                # Clear all selected
                if selected_recipients:
                    confirm = input(f"Clear all {len(selected_recipients)} selected recipients? (y/n): ")
                    if confirm.lower() == 'y':
                        selected_recipients = []
                        logger.info("All selections cleared.")
                else:
                    logger.info("No recipients selected.")

            elif choice == '10' and selected_recipients:
                # Continue to compose email
                return selected_recipients

            elif choice == '0':
                # Cancel
                if selected_recipients:
                    confirm = input("Cancel email composition? This will lose your recipient selection. (y/n): ")
                    if confirm.lower() == 'y':
                        return None
                else:
                    return None

            else:
                logger.info("Invalid choice.")
