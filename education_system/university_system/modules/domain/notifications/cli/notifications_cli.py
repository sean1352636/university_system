"""
Smart Notifications Hub CLI Interface

Provides command-line interface for managing notifications with filtering,
preferences, and notification center functionality.

Features:
- View notifications (unread, all, by channel)
- Mark as read/unread
- Configure preferences (quiet hours, channels, methods)
- Set priority filters
- Enable/disable daily digest
- Clear old notifications
- View notification settings
- Notification statistics
"""

from typing import Optional
from datetime import datetime

from education_system.university_system.modules.domain.notifications.services.notifications_service import (
    NotificationsService,
    NotificationPriority,
    NotificationChannel
)
from education_system.university_system.infrastructure.shared_context import get_auth


class NotificationsCLI:
    """CLI interface for Smart Notifications Hub"""

    def __init__(self):
        """Initialize CLI with service instance"""
        self.service = NotificationsService()
        self.auth = get_auth()

    def main_menu(self) -> None:
        """Display main notifications menu"""
        while True:
            self._print_header()
            print("\n=== Smart Notifications Hub ===")
            print("1.  View Notifications")
            print("2.  View Unread Notifications")
            print("3.  View by Channel")
            print("4.  View by Priority")
            print("5.  Mark Notification as Read")
            print("6.  Mark All as Read")
            print("7.  Archive Notification")
            print("8.  Notification Settings")
            print("9.  Channel Preferences")
            print("10. Quiet Hours Settings")
            print("11. Daily Digest Settings")
            print("12. Clear Old Notifications")
            print("13. Notification Statistics")
            print("14. Create Test Notification")
            print("0.  Return to Main Menu")

            choice = input("\nEnter your choice: ").strip()

            if choice == '1':
                self.view_notifications()
            elif choice == '2':
                self.view_unread_notifications()
            elif choice == '3':
                self.view_by_channel()
            elif choice == '4':
                self.view_by_priority()
            elif choice == '5':
                self.mark_as_read()
            elif choice == '6':
                self.mark_all_as_read()
            elif choice == '7':
                self.archive_notification()
            elif choice == '8':
                self.view_settings()
            elif choice == '9':
                self.manage_channel_preferences()
            elif choice == '10':
                self.configure_quiet_hours()
            elif choice == '11':
                self.configure_daily_digest()
            elif choice == '12':
                self.clear_old_notifications()
            elif choice == '13':
                self.show_statistics()
            elif choice == '14':
                self.create_test_notification()
            elif choice == '0':
                break
            else:
                print("Invalid choice. Please try again.")

    def _print_header(self) -> None:
        """Print header with unread count"""
        if not self.auth.is_logged_in():
            return

        user_id = self.auth.get_current_user()['user_id']
        unread_count = self.service.get_unread_count(user_id)

        if unread_count > 0:
            print(f"\n{'='*60}")
            print(f"  You have {unread_count} unread notification(s)")
            print(f"{'='*60}")

    def _get_priority_symbol(self, priority: str) -> str:
        """Get symbol for priority level"""
        symbols = {
            'urgent': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '🔵'
        }
        return symbols.get(priority.lower(), '⚪')

    def _format_notification(self, notification: dict, detailed: bool = False) -> str:
        """Format notification for display"""
        priority_symbol = self._get_priority_symbol(notification['priority'])
        read_symbol = '✓' if notification['is_read'] else '●'

        title = notification['title']
        channel = notification['channel'].upper()
        created = notification['created_at']

        # Basic format
        output = f"[{notification['notification_id']:4d}] {read_symbol} {priority_symbol} [{channel:10s}] {title}"

        if detailed:
            output += f"\n       Message: {notification['message']}"
            output += f"\n       Created: {created}"
            if notification['source_system']:
                output += f"\n       Source: {notification['source_system']}"

        return output

    # ==================== View Notifications ====================

    def view_notifications(self, limit: int = 20) -> None:
        """View all notifications"""
        if not self.auth.is_logged_in():
            print("Please log in first.")
            return

        user_id = self.auth.get_current_user()['user_id']
        notifications = self.service.get_notifications(user_id, limit=limit)

        if not notifications:
            print("\n✓ No notifications.")
            return

        print(f"\n=== All Notifications (showing {len(notifications)}) ===\n")
        for notif in notifications:
            print(self._format_notification(notif))

        # Show details option
        print("\nEnter notification ID to view details (or press Enter to return):")
        choice = input().strip()

        if choice.isdigit():
            self._view_notification_details(int(choice), user_id)

    def view_unread_notifications(self) -> None:
        """View only unread notifications"""
        if not self.auth.is_logged_in():
            print("Please log in first.")
            return

        user_id = self.auth.get_current_user()['user_id']
        notifications = self.service.get_notifications(user_id, unread_only=True, limit=50)

        if not notifications:
            print("\n✓ No unread notifications.")
            return

        print(f"\n=== Unread Notifications ({len(notifications)}) ===\n")
        for notif in notifications:
            print(self._format_notification(notif, detailed=True))

    def view_by_channel(self) -> None:
        """View notifications filtered by channel"""
        if not self.auth.is_logged_in():
            print("Please log in first.")
            return

        print("\n=== Filter by Channel ===")
        print("1. Academic")
        print("2. Social")
        print("3. Financial")
        print("4. Health")
        print("5. Housing")
        print("6. Events")
        print("7. System")

        choice = input("\nSelect channel: ").strip()

        channel_map = {
            '1': 'academic',
            '2': 'social',
            '3': 'financial',
            '4': 'health',
            '5': 'housing',
            '6': 'events',
            '7': 'system'
        }

        channel = channel_map.get(choice)
        if not channel:
            print("Invalid channel.")
            return

        user_id = self.auth.get_current_user()['user_id']
        notifications = self.service.get_notifications(user_id, channel=channel, limit=30)

        if not notifications:
            print(f"\nNo notifications in {channel.upper()} channel.")
            return

        print(f"\n=== {channel.upper()} Notifications ({len(notifications)}) ===\n")
        for notif in notifications:
            print(self._format_notification(notif))

    def view_by_priority(self) -> None:
        """View notifications filtered by priority"""
        if not self.auth.is_logged_in():
            print("Please log in first.")
            return

        print("\n=== Filter by Priority ===")
        print("1. Urgent")
        print("2. High")
        print("3. Medium")
        print("4. Low")

        choice = input("\nSelect priority: ").strip()

        priority_map = {
            '1': 'urgent',
            '2': 'high',
            '3': 'medium',
            '4': 'low'
        }

        priority = priority_map.get(choice)
        if not priority:
            print("Invalid priority.")
            return

        user_id = self.auth.get_current_user()['user_id']
        notifications = self.service.get_notifications(user_id, priority=priority, limit=30)

        if not notifications:
            print(f"\nNo {priority.upper()} priority notifications.")
            return

        print(f"\n=== {priority.upper()} Priority Notifications ({len(notifications)}) ===\n")
        for notif in notifications:
            print(self._format_notification(notif, detailed=True))

    def _view_notification_details(self, notification_id: int, user_id: str) -> None:
        """View detailed information about a notification"""
        notifications = self.service.get_notifications(user_id, limit=1000)
        notification = next((n for n in notifications if n['notification_id'] == notification_id), None)

        if not notification:
            print("Notification not found.")
            return

        print(f"\n{'='*60}")
        print(f"Notification ID: {notification['notification_id']}")
        print(f"{'='*60}")
        print(f"Channel:     {notification['channel'].upper()}")
        print(f"Priority:    {notification['priority'].upper()} {self._get_priority_symbol(notification['priority'])}")
        print(f"Status:      {'READ' if notification['is_read'] else 'UNREAD'}")
        print(f"Title:       {notification['title']}")
        print(f"Message:     {notification['message']}")
        print(f"Created:     {notification['created_at']}")

        if notification['read_at']:
            print(f"Read At:     {notification['read_at']}")

        if notification['source_system']:
            print(f"Source:      {notification['source_system']}")

        if notification['expires_at']:
            print(f"Expires:     {notification['expires_at']}")

        print(f"{'='*60}")

    # ==================== Actions ====================

    def mark_as_read(self) -> None:
        """Mark a notification as read"""
        if not self.auth.is_logged_in():
            print("Please log in first.")
            return

        notification_id = input("\nEnter notification ID to mark as read: ").strip()

        if not notification_id.isdigit():
            print("Invalid ID.")
            return

        user_id = self.auth.get_current_user()['user_id']
        success = self.service.mark_as_read(int(notification_id), user_id)

        if success:
            print("✓ Notification marked as read.")
        else:
            print("✗ Notification not found or already read.")

    def mark_all_as_read(self) -> None:
        """Mark all notifications as read"""
        if not self.auth.is_logged_in():
            print("Please log in first.")
            return

        print("\n1. Mark all notifications as read")
        print("2. Mark all in specific channel as read")

        choice = input("\nSelect option: ").strip()

        user_id = self.auth.get_current_user()['user_id']
        channel = None

        if choice == '2':
            print("\nSelect channel:")
            print("1. Academic  2. Social  3. Financial  4. Health")
            print("5. Housing   6. Events  7. System")

            channel_choice = input("\nChannel: ").strip()
            channel_map = {
                '1': 'academic', '2': 'social', '3': 'financial', '4': 'health',
                '5': 'housing', '6': 'events', '7': 'system'
            }
            channel = channel_map.get(channel_choice)

            if not channel:
                print("Invalid channel.")
                return

        count = self.service.mark_all_as_read(user_id, channel)

        if count > 0:
            msg = f"✓ Marked {count} notification(s) as read"
            if channel:
                msg += f" in {channel.upper()} channel"
            print(msg + ".")
        else:
            print("No unread notifications to mark.")

    def archive_notification(self) -> None:
        """Archive a notification"""
        if not self.auth.is_logged_in():
            print("Please log in first.")
            return

        notification_id = input("\nEnter notification ID to archive: ").strip()

        if not notification_id.isdigit():
            print("Invalid ID.")
            return

        user_id = self.auth.get_current_user()['user_id']
        success = self.service.archive_notification(int(notification_id), user_id)

        if success:
            print("✓ Notification archived.")
        else:
            print("✗ Notification not found.")

    # ==================== Settings ====================

    def view_settings(self) -> None:
        """View current notification settings"""
        if not self.auth.is_logged_in():
            print("Please log in first.")
            return

        user_id = self.auth.get_current_user()['user_id']
        prefs = self.service.get_preferences(user_id)

        print("\n" + "="*60)
        print("NOTIFICATION SETTINGS")
        print("="*60)

        print(f"\nQuiet Hours:")
        print(f"  Start: {prefs.get('quiet_hours_start', 'Not set')}")
        print(f"  End:   {prefs.get('quiet_hours_end', 'Not set')}")

        print(f"\nDaily Digest:")
        print(f"  Enabled: {'Yes' if prefs.get('daily_digest_enabled') else 'No'}")
        print(f"  Time:    {prefs.get('daily_digest_time', 'Not set')}")

        print(f"\nBundling:")
        print(f"  Enabled:     {'Yes' if prefs.get('bundle_notifications') else 'No'}")
        print(f"  Time Window: {prefs.get('bundle_time_window', 0)} seconds")

        print(f"\nLast Updated: {prefs.get('updated_at', 'Never')}")
        print("="*60)

    def manage_channel_preferences(self) -> None:
        """Manage channel-specific preferences"""
        if not self.auth.is_logged_in():
            print("Please log in first.")
            return

        user_id = self.auth.get_current_user()['user_id']
        settings = self.service.get_channel_settings(user_id)

        print("\n" + "="*80)
        print("CHANNEL PREFERENCES")
        print("="*80)
        print(f"{'Channel':<12} {'Enabled':<8} {'Min Priority':<12} {'Push':<6} {'Email':<6} {'SMS':<6}")
        print("-"*80)

        for setting in settings:
            print(f"{setting['channel']:<12} "
                  f"{'Yes' if setting['enabled'] else 'No':<8} "
                  f"{setting['min_priority'].upper():<12} "
                  f"{'Yes' if setting['push_enabled'] else 'No':<6} "
                  f"{'Yes' if setting['email_enabled'] else 'No':<6} "
                  f"{'Yes' if setting['sms_enabled'] else 'No':<6}")

        print("="*80)

        # Modify channel settings
        print("\nWould you like to modify a channel's settings? (y/n): ", end='')
        if input().strip().lower() == 'y':
            self._modify_channel_settings(user_id)

    def _modify_channel_settings(self, user_id: str) -> None:
        """Modify settings for a specific channel"""
        print("\nSelect channel:")
        print("1. Academic  2. Social  3. Financial  4. Health")
        print("5. Housing   6. Events  7. System")

        choice = input("\nChannel: ").strip()
        channel_map = {
            '1': 'academic', '2': 'social', '3': 'financial', '4': 'health',
            '5': 'housing', '6': 'events', '7': 'system'
        }

        channel = channel_map.get(choice)
        if not channel:
            print("Invalid channel.")
            return

        print(f"\nConfiguring {channel.upper()} channel:")

        # Enable/disable
        print("Enable this channel? (y/n): ", end='')
        enabled = input().strip().lower() == 'y'

        # Minimum priority
        print("\nMinimum priority level:")
        print("1. Low  2. Medium  3. High  4. Urgent")
        priority_choice = input("Priority: ").strip()
        priority_map = {'1': 'low', '2': 'medium', '3': 'high', '4': 'urgent'}
        min_priority = priority_map.get(priority_choice, 'low')

        # Delivery methods
        print("\nEnable push notifications? (y/n): ", end='')
        push_enabled = input().strip().lower() == 'y'

        print("Enable email notifications? (y/n): ", end='')
        email_enabled = input().strip().lower() == 'y'

        print("Enable SMS notifications? (y/n): ", end='')
        sms_enabled = input().strip().lower() == 'y'

        # Update settings
        success = self.service.update_channel_settings(
            user_id, channel,
            enabled=enabled,
            min_priority=min_priority,
            push_enabled=push_enabled,
            email_enabled=email_enabled,
            sms_enabled=sms_enabled
        )

        if success:
            print(f"\n✓ {channel.upper()} channel settings updated.")
        else:
            print("\n✗ Failed to update settings.")

    def configure_quiet_hours(self) -> None:
        """Configure quiet hours"""
        if not self.auth.is_logged_in():
            print("Please log in first.")
            return

        user_id = self.auth.get_current_user()['user_id']

        print("\n=== Configure Quiet Hours ===")
        print("During quiet hours, only urgent notifications will be delivered.")

        start = input("\nQuiet hours START time (HH:MM, e.g., 22:00): ").strip()
        end = input("Quiet hours END time (HH:MM, e.g., 08:00): ").strip()

        # Validate format
        try:
            datetime.strptime(start, '%H:%M')
            datetime.strptime(end, '%H:%M')
        except ValueError:
            print("✗ Invalid time format. Use HH:MM (24-hour format).")
            return

        success = self.service.update_preferences(
            user_id,
            quiet_hours_start=start,
            quiet_hours_end=end
        )

        if success:
            print(f"\n✓ Quiet hours set: {start} - {end}")
        else:
            print("\n✗ Failed to update quiet hours.")

    def configure_daily_digest(self) -> None:
        """Configure daily digest settings"""
        if not self.auth.is_logged_in():
            print("Please log in first.")
            return

        user_id = self.auth.get_current_user()['user_id']

        print("\n=== Configure Daily Digest ===")
        print("Daily digest sends a summary of all notifications once per day")
        print("instead of sending them individually.")

        print("\nEnable daily digest? (y/n): ", end='')
        enabled = input().strip().lower() == 'y'

        digest_time = None
        if enabled:
            digest_time = input("\nPreferred digest time (HH:MM, e.g., 08:00): ").strip()

            # Validate format
            try:
                datetime.strptime(digest_time, '%H:%M')
            except ValueError:
                print("✗ Invalid time format. Use HH:MM (24-hour format).")
                return

        success = self.service.update_preferences(
            user_id,
            daily_digest_enabled=enabled,
            daily_digest_time=digest_time if enabled else None
        )

        if success:
            if enabled:
                print(f"\n✓ Daily digest enabled at {digest_time}")
            else:
                print("\n✓ Daily digest disabled")
        else:
            print("\n✗ Failed to update digest settings.")

    # ==================== Maintenance ====================

    def clear_old_notifications(self) -> None:
        """Clear old read notifications"""
        if not self.auth.is_logged_in():
            print("Please log in first.")
            return

        print("\n=== Clear Old Notifications ===")
        days = input("Delete read notifications older than how many days? (default: 30): ").strip()

        if not days:
            days = 30
        elif not days.isdigit():
            print("Invalid number of days.")
            return
        else:
            days = int(days)

        user_id = self.auth.get_current_user()['user_id']
        count = self.service.delete_old_notifications(user_id, days)

        print(f"\n✓ Deleted {count} old notification(s).")

    # ==================== Statistics ====================

    def show_statistics(self) -> None:
        """Show notification statistics"""
        if not self.auth.is_logged_in():
            print("Please log in first.")
            return

        user_id = self.auth.get_current_user()['user_id']
        stats = self.service.get_notification_stats(user_id)

        print("\n" + "="*60)
        print("NOTIFICATION STATISTICS")
        print("="*60)

        print(f"\nOverall:")
        print(f"  Total Notifications:  {stats['total']}")
        print(f"  Unread:              {stats['unread']}")
        print(f"  Urgent:              {stats['urgent']}")
        print(f"  Today:               {stats['today']}")

        print(f"\nBy Channel:")
        for channel, count in stats['by_channel'].items():
            print(f"  {channel.upper():<12} {count:>4}")

        print("="*60)

    # ==================== Testing ====================

    def create_test_notification(self) -> None:
        """Create a test notification"""
        if not self.auth.is_logged_in():
            print("Please log in first.")
            return

        user_id = self.auth.get_current_user()['user_id']

        print("\n=== Create Test Notification ===")

        # Channel
        print("\nChannel:")
        print("1. Academic  2. Social  3. Financial  4. Health")
        print("5. Housing   6. Events  7. System")
        channel_choice = input("Select: ").strip()
        channel_map = {
            '1': 'academic', '2': 'social', '3': 'financial', '4': 'health',
            '5': 'housing', '6': 'events', '7': 'system'
        }
        channel = channel_map.get(channel_choice, 'system')

        # Priority
        print("\nPriority:")
        print("1. Low  2. Medium  3. High  4. Urgent")
        priority_choice = input("Select: ").strip()
        priority_map = {'1': 'low', '2': 'medium', '3': 'high', '4': 'urgent'}
        priority = priority_map.get(priority_choice, 'medium')

        # Content
        title = input("\nTitle: ").strip() or "Test Notification"
        message = input("Message: ").strip() or "This is a test notification from the Notifications Hub."

        # Create notification
        notification_id = self.service.create_notification(
            user_id=user_id,
            channel=channel,
            priority=priority,
            title=title,
            message=message,
            source_system="Test System"
        )

        print(f"\n✓ Test notification created (ID: {notification_id})")


def main():
    """Main entry point for CLI"""
    cli = NotificationsCLI()
    cli.main_menu()


if __name__ == "__main__":
    main()
