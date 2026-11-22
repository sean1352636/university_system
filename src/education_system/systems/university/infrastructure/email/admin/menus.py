"""Menu and UI functions for the communication dashboard."""

from __future__ import annotations

from education_system.systems.university.infrastructure.email.admin._imports import (
    datetime,
    config,
    configure_email_settings,
    display_announcements_menu,
    display_chat_rooms_menu,
    display_communication_analytics_menu,
    display_communication_logs_menu,
    display_stored_emails_menu,
    execute_db_operation,
    generate_report_form,
    get_stored_emails,
    handle_exception,
    initialize_chat_tables,
    initialize_email_db,
    load_config,
    log_event,
    logger,
    _out,
    _err,
    render_template,
    save_default_templates,
    send_email,
    start_email_workers,
    template_management_menu,
    LOG_MANAGEMENT_AVAILABLE,
)
from education_system.systems.university.infrastructure.email.email_service import (
    send_batch_email_form,
    schedule_email_form,
    email_queue,
    worker_threads,
    stop_email_workers,
    wait_for_email_queue,
)
from education_system.systems.university.infrastructure.utils.config import test_email_configuration
from education_system.systems.university.infrastructure.email import permissions


@handle_exception
def display_messages_menu(dashboard):
    """Enhanced messages menu with FIXED reply functionality"""
    while True:
        _out("\nMessages:")
        _out("=========")
        _out("1. View Inbox")
        _out("2. View Sent Messages")
        _out("3. Compose New Email (Select Recipients)")
        _out("4. Send Email to Role")
        _out("5. View Archived Messages")
        _out("6. Back to Communication Dashboard")

        choice = input("Enter your choice (1-6): ")

        if choice == '1':
            # View inbox
            inbox = dashboard.get_inbox()

            if inbox and inbox['total_count'] > 0:
                _out(f"\nInbox ({inbox['unread_count']} unread):")
                _out("=" * 60)

                for i, message in enumerate(inbox['messages'], 1):
                    if message.get('is_archived'):
                        status = "ARCHIVED"
                    elif not message.get('is_read'):
                        status = "NEW"
                    else:
                        status = "OPENED"
                    _out(f"{i}. [{status}] From: {message['sender']} - Subject: {message['subject']} - {message['sent_at']}")

                _out(f"\nShowing {len(inbox['messages'])} of {inbox['total_count']} messages (Page {inbox['page']} of {inbox['total_pages']})")

                # Handle message reading with FIXED reply
                while True:
                    _out("\nOptions:")
                    _out("1. Read a message")
                    _out("2. Next page")
                    _out("3. Previous page")
                    _out("4. Back to Messages Menu")

                    action = input("Enter choice: ")

                    if action == '1':
                        msg_num = input("Enter message number to read: ")
                        try:
                            msg_index = int(msg_num) - 1
                            if 0 <= msg_index < len(inbox['messages']):
                                message_id = inbox['messages'][msg_index]['id']
                                message = dashboard.read_message(message_id)

                                if message:
                                    _out("\n" + "=" * 60)
                                    _out(f"From: {message['sender']}")
                                    _out(f"To: {message['recipient']}")
                                    _out(f"Subject: {message['subject']}")
                                    _out(f"Date: {message['sent_at']}")
                                    _out("-" * 60)
                                    _out(message['content'])
                                    _out("=" * 60)
                                    # Mark local cache as read so status updates immediately
                                    inbox['messages'][msg_index]['is_read'] = True


                                    # Message actions - with archive support
                                    _out("\nOptions:")
                                    _out("1. Reply")
                                    _out("2. Archive")
                                    _out("3. Delete")
                                    _out("4. Mark as Unread")
                                    _out("5. Back")

                                    msg_action = input("Enter choice: ")

                                    if msg_action == '1':
                                        # Reply functionality
                                        _out(f"\nReplying to message from {message['sender']}")

                                        subject = f"Re: {message['subject']}"
                                        if subject.startswith("Re: Re:"):  # Avoid multiple Re: prefixes
                                            subject = message['subject']
                                            if not subject.startswith("Re: "):
                                                subject = f"Re: {subject}"

                                        _out(f"Reply subject: {subject}")
                                        content = input("Enter your reply: ")

                                        if content:
                                            _out(f"Sending reply to {message['sender']}...")

                                            # Send the reply
                                            reply_result = dashboard.send_message(
                                                message['sender_id'],
                                                subject,
                                                content
                                            )

                                            if reply_result:
                                                _out("\u2713 Reply sent successfully!")
                                                _out(f"The reply has been sent to {message['sender']} and should appear in their inbox.")
                                            else:
                                                _err("\u2717 Failed to send reply. Please check the logs for details.")
                                        else:
                                            _out("Reply cancelled - no content entered.")

                                    elif msg_action == '2':
                                        # Archive message
                                        if dashboard.update_message_status(message_id, 'archive'):
                                            _out("\u2705 Message archived successfully!")
                                            input("Press Enter to continue...")
                                            break  # Go back to inbox
                                        else:
                                            _err("\u274c Failed to archive message.")

                                    elif msg_action == '3':
                                        # Delete message
                                        confirm = input("Are you sure you want to delete this message? (y/n): ")
                                        if confirm.lower() == 'y':
                                            if dashboard.update_message_status(message_id, 'delete'):
                                                _out("\u2705 Message deleted successfully!")
                                                input("Press Enter to continue...")
                                                break  # Go back to inbox
                                            else:
                                                _err("\u274c Failed to delete message.")
                                        else:
                                            _out("Delete cancelled.")

                                    elif msg_action == '4':
                                        # Mark as unread
                                        if dashboard.update_message_status(message_id, 'mark_unread'):
                                            _out("\u2705 Message marked as unread!")
                                        else:
                                            _err("\u274c Failed to mark message as unread.")

                                    elif msg_action == '5':
                                        # Back
                                        break

                                    elif msg_action == '3':
                                        # Enhanced Delete message
                                        _out(f"\nDelete Options for message: {message['subject']}")
                                        _out("=" * 50)

                                        # Get current message status
                                        msg_status = dashboard.get_message_status_info(message_id)

                                        if msg_status:
                                            user_id = dashboard.auth.current_user['id']
                                            sender_id = msg_status['sender_id']
                                            recipient_id = msg_status['recipient_id']
                                            _out(f"Current deletion status: {msg_status['deletion_status'].replace('_', ' ').title()}")

                                            if msg_status['deletion_status'] == 'not_deleted':
                                                _out("\u2192 This will mark the message as deleted for you.")
                                                _out("\u2192 The message will be permanently removed if the other party also deletes it.")
                                            elif msg_status['deletion_status'] == 'sender_deleted' and user_id == recipient_id:
                                                _out("\u2192 The sender has already deleted this message.")
                                                _out("\u2192 Deleting will PERMANENTLY remove it from the database.")
                                            elif msg_status['deletion_status'] == 'recipient_deleted' and user_id == sender_id:
                                                _out("\u2192 The recipient has already deleted this message.")
                                                _out("\u2192 Deleting will PERMANENTLY remove it from the database.")

                                            _out("\nDelete Options:")
                                            _out("1. Standard Delete (mark as deleted)")
                                            if dashboard.auth.current_user['role'] == 'admin':
                                                _out("2. Force Delete (permanently remove immediately - ADMIN ONLY)")
                                            _out("3. Cancel")

                                            delete_choice = input("\nEnter choice: ")

                                            if delete_choice == '1':
                                                # Check if this will result in permanent deletion
                                                will_be_permanent = False
                                                if user_id == sender_id and msg_status['is_deleted_by_recipient']:
                                                    will_be_permanent = True
                                                elif user_id == recipient_id and msg_status['is_deleted_by_sender']:
                                                    will_be_permanent = True

                                                if will_be_permanent:
                                                    confirm = input("\u26a0\ufe0f  This will PERMANENTLY delete the message from the database. Continue? (y/n): ")
                                                else:
                                                    confirm = input("Mark this message as deleted? (y/n): ")

                                                if confirm.lower() == 'y':
                                                    if dashboard.update_message_status(message_id, 'delete'):
                                                        if will_be_permanent:
                                                            _out("\u2705 Message permanently deleted from database!")
                                                        else:
                                                            _out("\u2705 Message marked as deleted successfully!")
                                                            _out("\u2139\ufe0f  Message will be permanently removed if the other party also deletes it.")
                                                    else:
                                                        _err("\u274c Failed to delete message.")
                                                else:
                                                    _out("Delete cancelled.")

                                            elif delete_choice == '2' and dashboard.auth.current_user['role'] == 'admin':
                                                # Admin force delete
                                                confirm = input("\u26a0\ufe0f  ADMIN FORCE DELETE: This will immediately and permanently remove the message. Continue? (y/n): ")
                                                if confirm.lower() == 'y':
                                                    if dashboard.force_delete_message(message_id):
                                                        _out("\u2705 Message force deleted by administrator!")
                                                    else:
                                                        _err("\u274c Failed to force delete message.")
                                                else:
                                                    _out("Force delete cancelled.")

                                            else:
                                                _out("Delete cancelled.")
                                        else:
                                            _out("\u274c Could not retrieve message status information.")

                            else:
                                _out("Invalid message number.")
                        except ValueError:
                            _out("Please enter a number.")

                    elif action == '2':
                        if inbox['page'] < inbox['total_pages']:
                            inbox = dashboard.get_inbox(page=inbox['page'] + 1)

                            _out(f"\nInbox ({inbox['unread_count']} unread):")
                            _out("=" * 60)

                            for i, message in enumerate(inbox['messages'], 1):
                                if message.get('is_archived'):
                                    status = "ARCHIVED"
                                elif not message.get('is_read'):
                                    status = "NEW"
                                else:
                                    status = "OPENED"
                                _out(f"{i}. [{status}] From: {message['sender']} - Subject: {message['subject']} - {message['sent_at']}")

                            _out(f"\nShowing {len(inbox['messages'])} of {inbox['total_count']} messages (Page {inbox['page']} of {inbox['total_pages']})")
                        else:
                            _out("You are already on the last page.")

                    elif action == '3':
                        if inbox['page'] > 1:
                            inbox = dashboard.get_inbox(page=inbox['page'] - 1)

                            _out(f"\nInbox ({inbox['unread_count']} unread):")
                            _out("=" * 60)

                            for i, message in enumerate(inbox['messages'], 1):
                                if message.get('is_archived'):
                                    status = "ARCHIVED"
                                elif not message.get('is_read'):
                                    status = "NEW"
                                else:
                                    status = "OPENED"
                                _out(f"{i}. [{status}] From: {message['sender']} - Subject: {message['subject']} - {message['sent_at']}")

                            _out(f"\nShowing {len(inbox['messages'])} of {inbox['total_count']} messages (Page {inbox['page']} of {inbox['total_pages']})")
                        else:
                            _out("You are already on the first page.")

                    elif action == '4':
                        break
                    else:
                        _out("Invalid choice.")
            else:
                _out("Your inbox is empty.")
                input("Press Enter to continue...")

        elif choice == '2':
            # View sent messages
            sent = dashboard.get_sent_messages()
            if sent and sent['messages']:
                _out("\nSent Messages:")
                _out("=" * 60)

                for i, message in enumerate(sent['messages'], 1):
                    sender = message.get('sender') or (dashboard.auth.current_user['username'] if dashboard.auth and dashboard.auth.current_user else 'Unknown')
                    _out(f"{i}. From: {sender} -> To: {message['recipient']} (Sent: {message['sent_at']})")
                    _out(f"   Subject: {message['subject']}")
                    _out(f"   Message: {message['content']}")

                _out(f"\nShowing {len(sent['messages'])} of {sent['total_count']} messages")
            else:
                _out("No sent messages.")
            input("Press Enter to continue...")

        elif choice == '3':
            dashboard.compose_email_with_user_selection()
            input("Press Enter to continue...")

        elif choice == '4':
            # Send email to role
            _out("\nSend Email to Role:")
            _out("1. All Students")
            _out("2. All Staff")
            _out("3. All Instructors")
            _out("4. All Admins")
            _out("5. All Parents")
            _out("6. Cancel")

            role_choice = input("Select role (1-6): ")

            roles = {
                '1': 'student',
                '2': 'staff',
                '3': 'instructor',
                '4': 'admin',
                '5': 'parent'
            }

            if role_choice in roles:
                role = roles[role_choice]

                subject = input("Email Subject: ")
                if not subject:
                    _out("Subject cannot be empty.")
                    continue

                _out("\nEmail Body (type 'END' on a new line to finish):")
                body_lines = []
                while True:
                    line = input()
                    if line == 'END':
                        break
                    body_lines.append(line)

                body = "\n".join(body_lines)
                if not body:
                    _out("Email body cannot be empty.")
                    continue

                dashboard.send_email_to_role(role, subject, body)
            elif role_choice == '6':
                continue
            else:
                _out("Invalid choice.")

        elif choice == '5':
            # View archived messages - Updated to use dedicated function
            page = 1
            limit = 10

            while True:
                archived = dashboard.get_archived_messages(page=page, limit=limit)

                if not archived or archived['total_count'] == 0:
                    _out("\nYou have no archived messages.")
                    input("Press Enter to continue...")
                    break

                total_pages = archived['total_pages']
                current_page_messages = archived['messages']

                _out(f"\nArchived Messages ({archived['total_count']} messages):")
                _out("=" * 70)

                for i, message in enumerate(archived['messages'], 1):
                    status = "READ" if message['is_read'] else "NEW"
                    _out(f"{i}. [{status}] From: {message['sender']} - Subject: {message['subject']} - {message['sent_at']}")

                _out(f"\nShowing {len(archived['messages'])} of {archived['total_count']} archived messages (Page {archived['page']} of {archived['total_pages']})")

                _out("\nOptions:")
                _out("1. Read a message")
                _out("2. Next page") if page < archived['total_pages'] else _out("2. (No more pages)")
                _out("3. Previous page") if page > 1 else _out("3. (First page)")
                _out("4. Unarchive a message")
                _out("5. Delete a message")
                _out("6. Back to Messages Menu")

                action = input("Enter choice: ")

                if action == '1':
                    # Read a message
                    if not archived['messages']:
                        _out("No messages to read on this page.")
                        continue

                    try:
                        msg_num = int(input("Enter message number to read: "))
                        if 1 <= msg_num <= len(archived['messages']):
                            message_id = archived['messages'][msg_num - 1]['id']
                            message = dashboard.read_message(message_id)

                            if message:
                                _out("\n" + "=" * 60)
                                _out(f"From: {message['sender']}")
                                _out(f"To: {message['recipient']}")
                                _out(f"Subject: {message['subject']}")
                                _out(f"Date: {message['sent_at']}")
                                _out("Status: ARCHIVED")
                                _out("-" * 60)
                                _out(message['content'])
                                _out("=" * 60)

                                # Message actions for archived messages
                                _out("\nMessage Actions:")
                                _out("1. Reply")
                                _out("2. Unarchive")
                                _out("3. Delete")
                                _out("4. Back to Archived Messages")

                                msg_action = input("Enter choice: ")

                                if msg_action == '1':
                                    # Reply to archived message
                                    _out(f"\nReplying to message from {message['sender']}")
                                    subject = f"Re: {message['subject']}"
                                    if subject.startswith("Re: Re:"):
                                        subject = message['subject']
                                        if not subject.startswith("Re: "):
                                            subject = f"Re: {subject}"

                                    _out(f"Reply subject: {subject}")
                                    content = input("Enter your reply: ")

                                    if content:
                                        reply_result = dashboard.send_message(
                                            message['sender_id'],
                                            subject,
                                            content
                                        )

                                        if reply_result:
                                            _out("\u2713 Reply sent successfully!")
                                        else:
                                            _err("\u2717 Failed to send reply.")
                                    else:
                                        _out("Reply cancelled - no content entered.")

                                elif msg_action == '2':
                                    # Unarchive message
                                    if dashboard.update_message_status(message_id, 'unarchive'):
                                        _out("\u2705 Message unarchived successfully!")
                                        # Refresh the archived messages list
                                        archived_messages = [msg for msg in dashboard.get_inbox(include_archived=True)['messages'] if msg['is_archived']]
                                        total_archived = len(archived_messages)
                                        if total_archived == 0:
                                            _out("No more archived messages.")
                                            input("Press Enter to continue...")
                                            break
                                    else:
                                        _err("\u274c Failed to unarchive message.")

                                elif msg_action == '3':
                                    # Delete archived message
                                    confirm = input("Are you sure you want to delete this archived message? (y/n): ")
                                    if confirm.lower() == 'y':
                                        if dashboard.update_message_status(message_id, 'delete'):
                                            _out("\u2705 Message deleted successfully!")
                                            # Refresh the archived messages list
                                            archived_messages = [msg for msg in dashboard.get_inbox(include_archived=True)['messages'] if msg['is_archived']]
                                            total_archived = len(archived_messages)
                                            if total_archived == 0:
                                                _out("No more archived messages.")
                                                input("Press Enter to continue...")
                                                break
                                        else:
                                            _err("\u274c Failed to delete message.")
                                    else:
                                        _out("Delete cancelled.")

                                # Continue showing archived messages after action

                            else:
                                _out("\u274c Could not read message.")
                        else:
                            _out("Invalid message number.")
                    except ValueError:
                        _out("Please enter a valid number.")

                elif action == '2' and page < total_pages:
                    # Next page
                    page += 1

                elif action == '3' and page > 1:
                    # Previous page
                    page -= 1

                elif action == '4':
                    # Unarchive a message
                    if not current_page_messages:
                        _out("No messages to unarchive on this page.")
                        continue

                    try:
                        msg_num = int(input("Enter message number to unarchive: "))
                        if 1 <= msg_num <= len(current_page_messages):
                            message_id = current_page_messages[msg_num - 1]['id']
                            message_subject = current_page_messages[msg_num - 1]['subject']

                            confirm = input(f"Unarchive message '{message_subject}'? (y/n): ")
                            if confirm.lower() == 'y':
                                if dashboard.update_message_status(message_id, 'unarchive'):
                                    _out("\u2705 Message unarchived successfully!")

                                    # Refresh the archived messages list
                                    inbox = dashboard.get_inbox(include_archived=True)
                                    archived_messages = [msg for msg in inbox['messages'] if msg['is_archived']]
                                    total_archived = len(archived_messages)

                                    if total_archived == 0:
                                        _out("No more archived messages.")
                                        input("Press Enter to continue...")
                                        break

                                    # Adjust page if current page is now empty
                                    total_pages = (total_archived + limit - 1) // limit
                                    if page > total_pages and total_pages > 0:
                                        page = total_pages

                                    # Refresh current page messages
                                    start_idx = (page - 1) * limit
                                    end_idx = start_idx + limit
                                    current_page_messages = archived_messages[start_idx:end_idx]

                                else:
                                    _err("\u274c Failed to unarchive message.")
                            else:
                                _out("Unarchive cancelled.")
                        else:
                            _out("Invalid message number.")
                    except ValueError:
                        _out("Please enter a valid number.")

                elif action == '5':
                    # Delete a message
                    if not current_page_messages:
                        _out("No messages to delete on this page.")
                        continue

                    try:
                        msg_num = int(input("Enter message number to delete: "))
                        if 1 <= msg_num <= len(current_page_messages):
                            message_id = current_page_messages[msg_num - 1]['id']
                            message_subject = current_page_messages[msg_num - 1]['subject']

                            # Get message status for enhanced delete feedback
                            msg_status = dashboard.get_message_status_info(message_id) if hasattr(dashboard, 'get_message_status_info') else None

                            if msg_status:
                                _out(f"\nDelete message: {message_subject}")
                                _out("=" * 50)
                                _out(f"Current deletion status: {msg_status['deletion_status'].replace('_', ' ').title()}")

                                user_id = dashboard.auth.current_user['id']
                                will_be_permanent = False

                                if user_id == msg_status['sender_id'] and msg_status['is_deleted_by_recipient']:
                                    will_be_permanent = True
                                elif user_id == msg_status['recipient_id'] and msg_status['is_deleted_by_sender']:
                                    will_be_permanent = True

                                if will_be_permanent:
                                    confirm = input("\u26a0\ufe0f  This will PERMANENTLY delete the message from the database. Continue? (y/n): ")
                                else:
                                    confirm = input("Mark this message as deleted? (y/n): ")
                            else:
                                # Fallback if get_message_status_info is not available
                                confirm = input(f"Delete message '{message_subject}'? (y/n): ")

                            if confirm.lower() == 'y':
                                if dashboard.update_message_status(message_id, 'delete'):
                                    if msg_status and will_be_permanent:
                                        _out("\u2705 Message permanently deleted from database!")
                                    else:
                                        _out("\u2705 Message deleted successfully!")

                                    # Refresh the archived messages list
                                    inbox = dashboard.get_inbox(include_archived=True)
                                    archived_messages = [msg for msg in inbox['messages'] if msg['is_archived']]
                                    total_archived = len(archived_messages)

                                    if total_archived == 0:
                                        _out("No more archived messages.")
                                        input("Press Enter to continue...")
                                        break

                                    # Adjust page if current page is now empty
                                    total_pages = (total_archived + limit - 1) // limit
                                    if page > total_pages and total_pages > 0:
                                        page = total_pages

                                    # Refresh current page messages
                                    start_idx = (page - 1) * limit
                                    end_idx = start_idx + limit
                                    current_page_messages = archived_messages[start_idx:end_idx]

                                else:
                                    _err("\u274c Failed to delete message.")
                            else:
                                _out("Delete cancelled.")
                        else:
                            _out("Invalid message number.")
                    except ValueError:
                        _out("Please enter a valid number.")

        elif choice == '6':
            break

        else:
            _out("Invalid choice. Please try again.")



@handle_exception
def display_preferences_menu(dashboard):
    """Enhanced notification preferences menu"""
    try:
        # Get current preferences
        preferences = dashboard.get_notification_preferences()

        if not preferences:
            # Create default preferences if they don't exist
            preferences = {
                'email_notifications': True,
                'message_notifications': True,
                'announcement_notifications': True,
                'chat_notifications': True,
                'daily_digest': False
            }
            dashboard.update_notification_preferences(preferences)

        while True:
            _out("\nNotification Preferences:")
            _out("========================")
            _out(f"1. Email Notifications: {'Enabled' if preferences['email_notifications'] else 'Disabled'}")
            _out(f"2. Message Notifications: {'Enabled' if preferences['message_notifications'] else 'Disabled'}")
            _out(f"3. Announcement Notifications: {'Enabled' if preferences['announcement_notifications'] else 'Disabled'}")
            _out(f"4. Chat Notifications: {'Enabled' if preferences['chat_notifications'] else 'Disabled'}")
            _out(f"5. Daily Digest: {'Enabled' if preferences['daily_digest'] else 'Disabled'}")
            _out("6. Save Changes")
            _out("7. Reset to Defaults")
            _out("8. Back to Communication Dashboard")

            choice = input("Enter your choice (1-8): ")

            if choice == '1':
                preferences['email_notifications'] = not preferences['email_notifications']
                _out(f"Email Notifications {'Enabled' if preferences['email_notifications'] else 'Disabled'}")
            elif choice == '2':
                preferences['message_notifications'] = not preferences['message_notifications']
                _out(f"Message Notifications {'Enabled' if preferences['message_notifications'] else 'Disabled'}")
            elif choice == '3':
                preferences['announcement_notifications'] = not preferences['announcement_notifications']
                _out(f"Announcement Notifications {'Enabled' if preferences['announcement_notifications'] else 'Disabled'}")
            elif choice == '4':
                preferences['chat_notifications'] = not preferences['chat_notifications']
                _out(f"Chat Notifications {'Enabled' if preferences['chat_notifications'] else 'Disabled'}")
            elif choice == '5':
                preferences['daily_digest'] = not preferences['daily_digest']
                _out(f"Daily Digest {'Enabled' if preferences['daily_digest'] else 'Disabled'}")
            elif choice == '6':
                # Save changes
                if dashboard.update_notification_preferences(preferences):
                    _out("Preferences saved successfully!")
                else:
                    _err("Failed to save preferences.")
                input("Press Enter to continue...")
            elif choice == '7':
                # Reset to defaults
                confirm = input("Reset all preferences to defaults? (y/n): ")
                if confirm.lower() == 'y':
                    preferences = {
                        'email_notifications': True,
                        'message_notifications': True,
                        'announcement_notifications': True,
                        'chat_notifications': True,
                        'daily_digest': False
                    }
                    _out("Preferences reset to defaults.")
            elif choice == '8':
                break
            else:
                _out("Invalid choice. Please try again.")
    except Exception as e:
        log_event('error', f"Error displaying preferences menu: {e}")
        _err("An error occurred while managing preferences.")
        input("Press Enter to continue...")



def display_admin_message_management_menu(dashboard):
    """Admin-only message management menu"""
    if not dashboard.auth or dashboard.auth.current_user['role'] != 'admin':
        _out("Access denied. Administrator privileges required.")
        return

    while True:
        _out("\nAdmin Message Management:")
        _out("========================")
        _out("1. View All Messages")
        _out("2. Search Messages")
        _out("3. Cleanup Deleted Messages")
        _out("4. Force Delete Message")
        _out("5. Message Statistics")
        _out("6. Back to Communication Dashboard")

        choice = input("Enter your choice (1-6): ")

        if choice == '1':
            # View all messages
            def _get_all_messages(cursor):
                cursor.execute('''
                SELECT m.id, s.username as sender, r.username as recipient,
                       m.subject, m.sent_at, m.is_read, m.is_deleted_by_sender,
                       m.is_deleted_by_recipient
                FROM messages m
                JOIN users s ON m.sender_id = s.id
                JOIN users r ON m.recipient_id = r.id
                ORDER BY m.sent_at DESC
                LIMIT 20
                ''')
                return cursor.fetchall()

            try:
                messages = execute_db_operation(_get_all_messages)

                if messages:
                    _out("\nAll Messages (Last 20):")
                    _out("=" * 100)
                    _out(f"{'ID':<5}{'Sender':<15}{'Recipient':<15}{'Subject':<25}{'Date':<20}{'Status':<15}")
                    _out("-" * 100)

                    for msg in messages:
                        msg_id, sender, recipient, subject, sent_at, is_read, del_sender, del_recipient = msg

                        # Determine status
                        if del_sender and del_recipient:
                            status = "BOTH_DELETED"
                        elif del_sender:
                            status = "SENDER_DEL"
                        elif del_recipient:
                            status = "RECIPIENT_DEL"
                        elif is_read:
                            status = "READ"
                        else:
                            status = "UNREAD"

                        # Truncate long subjects
                        subj_display = subject[:22] + "..." if len(subject) > 22 else subject

                        _out(f"{msg_id:<5}{sender:<15}{recipient:<15}{subj_display:<25}{sent_at:<20}{status:<15}")
                else:
                    _out("No messages found.")
            except Exception as e:
                _err(f"Error retrieving messages: {e}")

            input("\nPress Enter to continue...")

        elif choice == '2':
            # Search messages
            search_term = input("Enter search term (username or subject): ")
            if search_term:
                def _search_messages(cursor):
                    cursor.execute('''
                    SELECT m.id, s.username as sender, r.username as recipient,
                           m.subject, m.sent_at, m.is_read, m.is_deleted_by_sender,
                           m.is_deleted_by_recipient
                    FROM messages m
                    JOIN users s ON m.sender_id = s.id
                    JOIN users r ON m.recipient_id = r.id
                    WHERE s.username LIKE ? OR r.username LIKE ? OR m.subject LIKE ?
                    ORDER BY m.sent_at DESC
                    LIMIT 50
                    ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
                    return cursor.fetchall()

                try:
                    results = execute_db_operation(_search_messages)
                    _out(f"\nSearch Results for '{search_term}': {len(results)} found")
                    # Display similar to option 1
                except Exception as e:
                    _err(f"Error searching messages: {e}")

            input("\nPress Enter to continue...")

        elif choice == '3':
            # Cleanup deleted messages
            confirm = input("Clean up messages deleted by both parties? (y/n): ")
            if confirm.lower() == 'y':
                cleaned = dashboard.cleanup_deleted_messages()
                _out(f"\u2705 Cleaned up {cleaned} deleted messages.")
            else:
                _out("Cleanup cancelled.")

            input("\nPress Enter to continue...")

        elif choice == '4':
            # Force delete message
            try:
                msg_id = int(input("Enter message ID to force delete: "))

                # Show message details first
                msg_status = dashboard.get_message_status_info(msg_id)
                if msg_status:
                    _out("\nMessage Details:")
                    _out(f"ID: {msg_status['id']}")
                    _out(f"Subject: {msg_status['subject']}")
                    _out(f"Sent: {msg_status['sent_at']}")
                    _out(f"Status: {msg_status['deletion_status']}")

                    confirm = input(f"\nForce delete message {msg_id}? (y/n): ")
                    if confirm.lower() == 'y':
                        if dashboard.force_delete_message(msg_id):
                            _out("\u2705 Message force deleted successfully!")
                        else:
                            _err("\u274c Failed to force delete message.")
                    else:
                        _out("Force delete cancelled.")
                else:
                    _out(f"Message {msg_id} not found.")
            except ValueError:
                _out("Invalid message ID.")

            input("\nPress Enter to continue...")

        elif choice == '5':
            # Message statistics
            def _get_message_stats(cursor):
                cursor.execute('SELECT COUNT(*) FROM messages')
                total_messages = cursor.fetchone()[0]

                cursor.execute('SELECT COUNT(*) FROM messages WHERE is_read = 0')
                unread_messages = cursor.fetchone()[0]

                cursor.execute('SELECT COUNT(*) FROM messages WHERE is_deleted_by_sender = 1 AND is_deleted_by_recipient = 1')
                both_deleted = cursor.fetchone()[0]

                cursor.execute('SELECT COUNT(*) FROM messages WHERE is_deleted_by_sender = 1 OR is_deleted_by_recipient = 1')
                partially_deleted = cursor.fetchone()[0]

                return total_messages, unread_messages, both_deleted, partially_deleted

            try:
                total, unread, both_del, partial_del = execute_db_operation(_get_message_stats)

                _out("\nMessage Statistics:")
                _out("=" * 30)
                _out(f"Total Messages: {total}")
                _out(f"Unread Messages: {unread}")
                _out(f"Messages deleted by both parties: {both_del}")
                _out(f"Messages deleted by one party: {partial_del - both_del}")
                _out(f"Active Messages: {total - both_del}")
            except Exception as e:
                _err(f"Error getting statistics: {e}")

            input("\nPress Enter to continue...")

        elif choice == '6':
            break
        else:
            _out("Invalid choice. Please try again.")



def _show_outbox_status():
    """The e-mail outbox: delivery mode and message counts."""
    from education_system.systems.university.application.mail import admin as email_admin
    from education_system.systems.university.infrastructure.database.db import get_connection
    from education_system.systems.university.infrastructure.email import outbox_delivery
    st = outbox_delivery.status()
    conn = get_connection(None, row_factory=False)
    try:
        summary = email_admin.summary(conn)
        conn.commit()
    finally:
        conn.close()
    _out(f"\nDelivery mode: {st['mode']}   live ready: {'yes' if st['live_ready'] else 'no'}")
    counts = summary["counts"]
    _out("Outbox: " + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "empty"))
    _out(f"Waiting: {summary['waiting']}   problems (failed/bounced): {summary['problems']}")


def display_communication_dashboard(auth=None):
    """Display the integrated communication dashboard menu with enhanced logging"""
    # Lazy import to avoid circular dependency
    from education_system.systems.university.infrastructure.email.admin import CommunicationDashboard

    # Use the same database path as the auth system
    if auth and hasattr(auth, 'db_path'):
        dashboard = CommunicationDashboard(db_path=auth.db_path, auth=auth)
    else:
        dashboard = CommunicationDashboard(auth=auth)

    # Email initialization
    load_config()
    save_default_templates()
    initialize_email_db()
    initialize_chat_tables()

    # Start email workers if configuration is complete and not in database-only mode
    if config['sender_email'] and not config.get('database_only_mode', True):
        if config['smtp_server']:
            start_email_workers()

    while True:
        if not auth or not auth.current_user:
            _out("You must be logged in to access the communication dashboard.")
            break

        mode_indicator = " [DB Mode]" if config.get('database_only_mode', True) else " [SMTP Mode]"
        is_admin = auth.current_user.get('role') == 'admin'

        # Check for notifications
        pending_invitations = dashboard.get_pending_invitations()
        notification_text = ""
        if pending_invitations:
            notification_text = f" (Chat invitations: {len(pending_invitations)})"

        _out(f"\nCommunication Dashboard{mode_indicator}{notification_text}:")
        _out("========================")
        _out("1. Messages")
        _out("2. Announcements")
        _out("3. Chat Rooms")
        _out("4. Notification Preferences")
        _out("5. Configure Email Settings")
        _out("6. Test Email Configuration")
        _out("7. Manage Email Templates")
        _out("8. Send Batch Announcement")
        _out("9. Schedule Emails")
        _out("10. View Email Queue Status")
        _out("11. Generate Email Reports")
        _out("12. View Stored Emails")

        # Enhanced logging options
        if LOG_MANAGEMENT_AVAILABLE:
            _out("13. View Communication Activity Logs")
            if is_admin:
                _out("14. Communication Analytics")
                _out("15. Admin Message Management")
                _out("16. Return to Main Menu")
                max_choice = 16
            else:
                _out("14. Return to Main Menu")
                max_choice = 14
        else:
            if is_admin:
                _out("13. Admin Message Management")
                _out("14. Return to Main Menu")
                max_choice = 14
            else:
                _out("13. Return to Main Menu")
                max_choice = 13

        choice = input(f"Enter your choice (1-{max_choice}): ")

        if choice == '1':
            display_messages_menu(dashboard)
        elif choice == '2':
            display_announcements_menu(dashboard)
        elif choice == '3':
            display_chat_rooms_menu(dashboard)
        elif choice == '4':
            display_preferences_menu(dashboard)
        elif choice in ('5', '6', '7', '9', '10') and not permissions.is_email_admin(auth):
            _out(permissions.DENIED)
        elif choice == '8' and not permissions.can_send_bulk(auth):
            _out(permissions.DENIED_BULK)
        elif choice == '5':
            configure_email_settings()
        elif choice == '6':
            if config.get('database_only_mode', True):
                _out("Test emails are stored in database when in Database Only mode.")
                recipient = input("Enter test recipient email: ")
                if recipient:
                    subject, body = render_template("test_email_database_mode", {
                        "sender_email": config['sender_email'],
                        "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "signature": config['email_signature']
                    })

                    if send_email(recipient, subject, body):
                        _out("Test email stored in database successfully!")
                    else:
                        _err("Failed to store test email.")
            else:
                recipient = input("Enter test recipient email (leave empty to send to yourself): ")
                test_email_configuration(recipient if recipient else None)
            input("\nPress Enter to continue...")
        elif choice == '7':
            template_management_menu()
        elif choice == '8':
            send_batch_email_form()
        elif choice == '9':
            schedule_email_form()
        elif choice == '10':
            _show_outbox_status()
            input("\nPress Enter to continue...")
        elif choice == '11':
            generate_report_form()
        elif choice == '12':
            display_stored_emails_menu(auth)
        elif choice == '13' and LOG_MANAGEMENT_AVAILABLE:
            display_communication_logs_menu(dashboard)
        elif choice == '14' and LOG_MANAGEMENT_AVAILABLE and is_admin:
            display_communication_analytics_menu(dashboard)
        elif (choice == '13' and not LOG_MANAGEMENT_AVAILABLE and not is_admin) or \
             (choice == '14' and LOG_MANAGEMENT_AVAILABLE and not is_admin) or \
             (choice == '14' and not LOG_MANAGEMENT_AVAILABLE and is_admin) or \
             (choice == '15' and is_admin) or \
             (choice == '16' and is_admin):
            # Handle admin message management
            if choice in ['13', '14', '15'] and is_admin:
                display_admin_message_management_menu(dashboard)
            else:
                # Return to main menu
                if worker_threads and not config.get('database_only_mode', True):
                    if email_queue.qsize() > 0:
                        wait = input(f"There are {email_queue.qsize()} emails in the queue. Wait for them to be sent? (y/n): ")
                        if wait.lower() == 'y':
                            wait_for_email_queue()
                    stop_email_workers()
                _out("Returning to main menu...")
                break
        else:
            _out("Invalid choice. Please try again.")
