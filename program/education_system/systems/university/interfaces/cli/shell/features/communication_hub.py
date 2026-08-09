"""Component extracted from the legacy menu router."""
from __future__ import annotations
from ..bootstrap.integrations import (
    AuthenticationError,
    PermissionDeniedError,
    ValidationError,
    datetime,
)

def display_communication_hub_menu(auth):
    """Display the unified communication hub CLI menu with all options"""
    from education_system.systems.university.infrastructure.email.config import config
    from education_system.systems.university.infrastructure.email.admin import CommunicationDashboard
    from education_system.systems.university.services.communication.communication_manager import CommunicationManager
    from education_system.systems.university.infrastructure.logs import LOG_MANAGEMENT_AVAILABLE

    # Initialize dashboard for advanced features
    dashboard = CommunicationDashboard(auth=auth)
    is_admin = auth and auth.current_user and auth.current_user.get('role') == 'admin'

    print("\n" + "="*100)
    print("       UNIFIED COMMUNICATION HUB")
    print("="*100)

    print("\n📧 Quick Actions:")
    print(f"{'1.  Send Email':<25} {'2.  Send SMS':<25} {'3.  Push Notification':<25}")

    print("\n📢 Announcements & Messages:")
    print(f"{'4.  Messages Mgmt':<25} {'5.  Create Announcement':<25} {'6.  Manage Announcements':<25} {'7.  Batch Announcement':<25}")

    print("\n💬 Chat & Communication:")
    print(f"{'8.  Chat Rooms':<25} {'9.  Notification Prefs':<25}")

    print("\n⚙️ Email System Configuration:")
    print(f"{'10. Email Settings':<25} {'11. Test Configuration':<25} {'12. Email Templates':<25} {'13. Schedule Emails':<25}")
    print(f"{'14. Queue Status':<25} {'15. Stored Emails':<25}")

    print("\n🌐 Cross-System:")
    print(f"{'C.  Cross-System Messages':<25}")

    print("\n📊 Reports & Analytics:")
    print(f"{'16. Email Reports':<25}", end="")
    if LOG_MANAGEMENT_AVAILABLE:
        print(f" {'17. Activity Logs':<25}", end="")
        if is_admin:
            print(f" {'18. Analytics':<25}", end="")
    print()

    if is_admin:
        print("\n🔧 Administration:")
        print(f"{'19. Admin Messages':<25}")

    print("\n↩️ Navigation:")
    if is_admin and LOG_MANAGEMENT_AVAILABLE:
        print("20. Return to Main Menu")
        max_choice = 20
    elif is_admin or LOG_MANAGEMENT_AVAILABLE:
        print("19. Return to Main Menu")
        max_choice = 19
    else:
        print("17. Return to Main Menu")
        max_choice = 17
    print("="*100)

    while True:
        try:
            choice = input(f"\nEnter your choice (1-{max_choice}): ").strip()

            if choice == '1':
                # Send Email
                try:
                    to_address = input("Enter recipient email: ").strip()
                    subject = input("Enter subject: ").strip()
                    body = input("Enter message body: ").strip()

                    comm_mgr = CommunicationManager()
                    email_id = comm_mgr.queue_email(
                        to_address=to_address,
                        subject=subject,
                        body=body,
                        from_user_id=auth.current_user['user_id']
                    )
                    print(f"✅ Email queued successfully! Email ID: {email_id}")
                except (AuthenticationError, PermissionDeniedError) as e:
                    print(f"❌ Error queuing email: {e}")
            elif choice == '2':
                # Send SMS
                try:
                    phone_number = input("Enter phone number: ").strip()
                    message = input("Enter message: ").strip()

                    comm_mgr = CommunicationManager()
                    sms_id = comm_mgr.queue_sms(
                        phone_number=phone_number,
                        message=message,
                        from_user_id=auth.current_user['user_id']
                    )
                    print(f"✅ SMS queued successfully! SMS ID: {sms_id}")
                except (AuthenticationError, PermissionDeniedError) as e:
                    print(f"❌ Error queuing SMS: {e}")
            elif choice == '3':
                # Send Push Notification
                try:
                    user_id = int(input("Enter recipient user ID: ").strip())
                    title = input("Enter notification title: ").strip()
                    body = input("Enter notification body: ").strip()
                    click_action = input("Enter click action URL (or press Enter to skip): ").strip() or None
                    comm_mgr = CommunicationManager()
                    notif_id = comm_mgr.send_push_notification(
                        user_id=user_id, title=title, body=body, click_action=click_action
                    )
                    if notif_id:
                        print(f"✅ Push notification sent! Notification ID: {notif_id}")
                    else:
                        print("❌ Failed to send push notification.")
                except (AuthenticationError, PermissionDeniedError) as e:
                    print(f"❌ Error sending push notification: {e}")
            elif choice == '4':
                # Messages Management
                from education_system.systems.university.infrastructure.email.admin import display_messages_menu
                display_messages_menu(dashboard)
            elif choice == '5':
                # Create Announcement
                try:
                    title = input("Enter announcement title: ").strip()
                    content = input("Enter announcement content: ").strip()
                    target_audience = input("Enter target audience (all/students/faculty/staff): ").strip()

                    comm_mgr = CommunicationManager()
                    announcement_id = comm_mgr.create_announcement(
                        title=title,
                        content=content,
                        target_audience=target_audience,
                        created_by=auth.current_user['user_id']
                    )
                    print(f"✅ Announcement created successfully! Announcement ID: {announcement_id}")
                except (AuthenticationError, PermissionDeniedError) as e:
                    print(f"❌ Error creating announcement: {e}")
            elif choice == '6':
                # Manage Announcements
                from education_system.systems.university.infrastructure.email.admin import display_announcements_menu
                display_announcements_menu(dashboard)
            elif choice == '7':
                # Send Batch Announcement
                from education_system.systems.university.infrastructure.email.email_service import send_batch_email_form
                send_batch_email_form()
            elif choice == '8':
                # Chat Rooms
                from education_system.systems.university.infrastructure.email.admin import display_chat_rooms_menu
                display_chat_rooms_menu(dashboard)
            elif choice == '9':
                # Notification Preferences
                from education_system.systems.university.infrastructure.email.admin import display_preferences_menu
                display_preferences_menu(dashboard)
            elif choice == '10':
                # Configure Email Settings
                from education_system.systems.university.infrastructure.email.config import configure_email_settings
                configure_email_settings()
            elif choice == '11':
                # Test Email Configuration
                from education_system.systems.university.infrastructure.email.email_service import send_email
                recipient = input("Enter test recipient email (or press Enter to use your email): ").strip()
                if not recipient and auth.current_user:
                    recipient = auth.current_user.get('email', '')
                if recipient:
                    test_subject = "Test Email from University System"
                    test_body = f"This is a test email sent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    if send_email(recipient, test_subject, test_body):
                        print("✅ Test email sent successfully!")
                    else:
                        print("❌ Failed to send test email.")
                else:
                    print("❌ No recipient email provided.")
            elif choice == '12':
                # Manage Email Templates
                from education_system.systems.university.infrastructure.email.templates import template_management_menu
                template_management_menu()
            elif choice == '13':
                # Schedule Emails
                from education_system.systems.university.infrastructure.email.email_service import schedule_email_form
                schedule_email_form()
            elif choice == '14':
                # View Email Queue Status
                from education_system.systems.university.infrastructure.email.email_service import email_queue, get_stored_emails
                if config.get('database_only_mode', True):
                    emails_data = get_stored_emails(limit=1)
                    print(f"\n📊 Stored emails in database: {emails_data['total_count']}")
                    if emails_data['total_count'] > 0:
                        print("Recent stored emails:")
                        recent_emails = get_stored_emails(limit=5)
                        for email in recent_emails['emails']:
                            print(f"  - To: {email['recipient_email']}, Subject: {email['subject'][:50]}...")
                else:
                    queue_size = email_queue.qsize()
                    print(f"\n📊 Current email queue size: {queue_size}")
                input("\nPress Enter to continue...")
            elif choice == '15':
                # View Stored Emails
                from education_system.systems.university.infrastructure.email.email_service import display_stored_emails_menu
                display_stored_emails_menu()
            elif choice == '16':
                # Generate Email Reports
                from education_system.systems.university.infrastructure.email.reports import generate_report_form
                generate_report_form()
            elif choice == '17':
                if LOG_MANAGEMENT_AVAILABLE:
                    # Communication Activity Logs
                    from education_system.systems.university.infrastructure.logs import display_communication_logs_menu
                    display_communication_logs_menu(dashboard)
                elif not is_admin:
                    # Return to main menu (non-admin, no log management)
                    print("Returning to main menu...")
                    break
                else:
                    print("❌ Invalid choice.")
            elif choice == '18':
                if is_admin and LOG_MANAGEMENT_AVAILABLE:
                    # Communication Analytics
                    from education_system.systems.university.infrastructure.logs import display_communication_analytics_menu
                    display_communication_analytics_menu(dashboard)
                else:
                    print("❌ Invalid choice.")
            elif choice == '19':
                if is_admin and not LOG_MANAGEMENT_AVAILABLE:
                    # Admin Message Management (admin without log management)
                    from education_system.systems.university.infrastructure.email.admin import display_admin_message_management_menu
                    display_admin_message_management_menu(dashboard)
                elif is_admin or LOG_MANAGEMENT_AVAILABLE:
                    # Return to main menu
                    print("Returning to main menu...")
                    break
                else:
                    print("❌ Invalid choice.")
            elif choice == '20':
                if is_admin and LOG_MANAGEMENT_AVAILABLE:
                    # Return to main menu (admin with log management)
                    print("Returning to main menu...")
                    break
                else:
                    print("❌ Invalid choice.")
            elif choice.upper() == 'C':
                # Cross-System Messages — links the per-system Email Manager
                # to the shared inter-system messaging CLI.
                from education_system.platform.features.messaging import cross_system_cli
                cross_system_cli.run(auth=auth)
            else:
                print(f"❌ Invalid choice. Please enter a number between 1 and {max_choice}.")

        except KeyboardInterrupt:
            print("\n\nExiting communication hub menu...")
            break
        except (ValueError, TypeError, ValidationError) as e:
            print(f"❌ Error: {e}")
