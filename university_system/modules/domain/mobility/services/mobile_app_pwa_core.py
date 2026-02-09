"""
Mobile App (PWA) Infrastructure Core CLI Service

Comprehensive CLI for managing mobile devices, sessions, offline sync,
app installations, and mobile analytics.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json
import secrets
import logging

# Core infrastructure
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.utils.activity_logger import log_activity

# Import i18n for internationalization
from university_system.modules.shared.utils.i18n import (
    get_text,
    get_current_language,
)
from university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)

# Setup logging
logger = logging.getLogger(__name__)


def init_mobile_app_database():
    """Initialize mobile app database tables"""
    try:
        from university_system.infrastructure.database.remaining_features_schema import MOBILE_APP_SCHEMA

        with transaction() as conn:
            conn.executescript(MOBILE_APP_SCHEMA)

        logger.info("Mobile App database tables initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False


# ==================== Mobile Devices Management ====================

def register_mobile_device():
    """Register a new mobile device"""
    print("\n" + "="*60)
    print("REGISTER MOBILE DEVICE")
    print("="*60)

    try:
        user_id = input("Enter User ID: ").strip()
        if not user_id:
            print("❌ User ID is required")
            return

        print("\nDevice Types:")
        print("1. iOS")
        print("2. Android")
        print("3. Web (PWA)")
        device_type_choice = input("Select device type (1-3): ").strip()

        device_types = {'1': 'ios', '2': 'android', '3': 'web'}
        device_type = device_types.get(device_type_choice, 'web')

        device_name = input("Enter device name (e.g., 'iPhone 13', 'Samsung Galaxy'): ").strip()
        os_version = input("Enter OS version (optional): ").strip()
        app_version = input("Enter app version [1.0.0]: ").strip()
        if not app_version:
            app_version = "1.0.0"

        # Generate push token
        push_token = secrets.token_urlsafe(32)

        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO mobile_devices (
                    user_id, device_type, device_name, push_token,
                    os_version, app_version
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, device_type, device_name, push_token,
                  os_version or None, app_version))

            device_id = cursor.lastrowid

        log_activity('register', 'mobile_device', device_id=device_id,
                    details={'user_id': user_id, 'type': device_type})

        print(f"\n✅ Mobile device registered successfully!")
        print(f"Device ID: {device_id}")
        print(f"Push Token: {push_token[:20]}...")

    except Exception as e:
        print(f"❌ Error registering device: {e}")
        logger.error(f"Error registering mobile device: {e}")


def view_mobile_devices():
    """View all registered mobile devices"""
    print("\n" + "="*60)
    print("MOBILE DEVICES")
    print("="*60)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT device_id, user_id, device_type, device_name, os_version,
                   app_version, last_active, is_active, registered_at
            FROM mobile_devices
            ORDER BY last_active DESC
        ''')

        devices = cursor.fetchall()
        conn.close()

        if not devices:
            print("\n📋 No mobile devices found")
            return

        print(f"\nTotal Devices: {len(devices)}\n")
        print(f"{'ID':<6} {'User':<8} {'Type':<10} {'Device':<25} {'Version':<10} {'Last Active':<20} {'Status':<10}")
        print("-" * 110)

        for device in devices:
            dev_id, user_id, dtype, dname, os_ver, app_ver, last_active, active, registered = device
            status = "✅ Active" if active else "❌ Inactive"
            version_str = f"{os_ver or 'N/A'}/{app_ver}"

            print(f"{dev_id:<6} {user_id:<8} {dtype:<10} {dname[:23]:<25} {version_str:<10} {last_active:<20} {status:<10}")

        log_activity('view', 'mobile_devices', details={'count': len(devices)})

    except Exception as e:
        print(f"❌ Error viewing devices: {e}")
        logger.error(f"Error viewing mobile devices: {e}")


def deactivate_mobile_device():
    """Deactivate a mobile device"""
    print("\n" + "="*60)
    print("DEACTIVATE MOBILE DEVICE")
    print("="*60)

    try:
        device_id = input("Enter Device ID to deactivate: ").strip()
        if not device_id:
            print("❌ Device ID is required")
            return

        confirm = input(f"\n⚠️ Deactivate device {device_id}? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Deactivation cancelled")
            return

        with transaction() as conn:
            conn.execute('''
                UPDATE mobile_devices
                SET is_active = 0
                WHERE device_id = ?
            ''', (device_id,))

        log_activity('deactivate', 'mobile_device', device_id=device_id)

        print(f"\n✅ Device {device_id} deactivated successfully")

    except Exception as e:
        print(f"❌ Error deactivating device: {e}")
        logger.error(f"Error deactivating device: {e}")


# ==================== Mobile Sessions Management ====================

def create_mobile_session():
    """Create a new mobile session"""
    print("\n" + "="*60)
    print("CREATE MOBILE SESSION")
    print("="*60)

    try:
        device_id = input("Enter Device ID: ").strip()
        if not device_id:
            print("❌ Device ID is required")
            return

        user_id = input("Enter User ID: ").strip()
        if not user_id:
            print("❌ User ID is required")
            return

        # Generate session token
        session_token = secrets.token_urlsafe(32)

        ip_address = input("Enter IP address (optional): ").strip()
        location = input("Enter location (optional): ").strip()

        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO mobile_sessions (
                    device_id, user_id, session_token, ip_address, location
                ) VALUES (?, ?, ?, ?, ?)
            ''', (device_id, user_id, session_token, ip_address or None, location or None))

            session_id = cursor.lastrowid

            # Update device last_active
            conn.execute('''
                UPDATE mobile_devices
                SET last_active = CURRENT_TIMESTAMP
                WHERE device_id = ?
            ''', (device_id,))

        log_activity('create', 'mobile_session', session_id=session_id,
                    details={'device_id': device_id, 'user_id': user_id})

        print(f"\n✅ Mobile session created successfully!")
        print(f"Session ID: {session_id}")
        print(f"Session Token: {session_token[:20]}...")

    except Exception as e:
        print(f"❌ Error creating session: {e}")
        logger.error(f"Error creating mobile session: {e}")


def view_active_mobile_sessions():
    """View all active mobile sessions"""
    print("\n" + "="*60)
    print("ACTIVE MOBILE SESSIONS")
    print("="*60)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT ms.session_id, ms.user_id, md.device_type, md.device_name,
                   ms.login_time, ms.ip_address, ms.location
            FROM mobile_sessions ms
            JOIN mobile_devices md ON ms.device_id = md.device_id
            WHERE ms.logout_time IS NULL
            ORDER BY ms.login_time DESC
        ''')

        sessions = cursor.fetchall()
        conn.close()

        if not sessions:
            print("\n📋 No active sessions found")
            return

        print(f"\nActive Sessions: {len(sessions)}\n")
        print(f"{'ID':<8} {'User':<8} {'Device Type':<12} {'Device':<25} {'Login Time':<20} {'IP':<16}")
        print("-" * 100)

        for session in sessions:
            sess_id, user_id, dtype, dname, login, ip, loc = session
            print(f"{sess_id:<8} {user_id:<8} {dtype:<12} {dname[:23]:<25} {login:<20} {ip or 'N/A':<16}")

        log_activity('view', 'mobile_sessions', details={'count': len(sessions)})

    except Exception as e:
        print(f"❌ Error viewing sessions: {e}")
        logger.error(f"Error viewing mobile sessions: {e}")


def end_mobile_session():
    """End a mobile session"""
    print("\n" + "="*60)
    print("END MOBILE SESSION")
    print("="*60)

    try:
        session_id = input("Enter Session ID to end: ").strip()
        if not session_id:
            print("❌ Session ID is required")
            return

        with transaction() as conn:
            conn.execute('''
                UPDATE mobile_sessions
                SET logout_time = CURRENT_TIMESTAMP
                WHERE session_id = ?
            ''', (session_id,))

        log_activity('end', 'mobile_session', session_id=session_id)

        print(f"\n✅ Session {session_id} ended successfully")

    except Exception as e:
        print(f"❌ Error ending session: {e}")
        logger.error(f"Error ending session: {e}")


# ==================== Offline Sync Queue Management ====================

def view_offline_sync_queue():
    """View offline sync queue"""
    print("\n" + "="*60)
    print("OFFLINE SYNC QUEUE")
    print("="*60)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT queue_id, device_id, action_type, entity_type,
                   sync_status, created_at
            FROM offline_sync_queue
            WHERE sync_status = 'pending'
            ORDER BY created_at ASC
        ''')

        queue_items = cursor.fetchall()
        conn.close()

        if not queue_items:
            print("\n✅ Sync queue is empty - all data synced!")
            return

        print(f"\nPending Sync Items: {len(queue_items)}\n")
        print(f"{'ID':<8} {'Device':<10} {'Action':<10} {'Entity':<15} {'Status':<12} {'Created':<20}")
        print("-" * 90)

        for item in queue_items:
            queue_id, device_id, action, entity, status, created = item
            print(f"{queue_id:<8} {device_id:<10} {action:<10} {entity:<15} {status:<12} {created:<20}")

        log_activity('view', 'offline_sync_queue', details={'pending': len(queue_items)})

    except Exception as e:
        print(f"❌ Error viewing sync queue: {e}")
        logger.error(f"Error viewing offline sync queue: {e}")


def process_offline_sync():
    """Process offline sync queue"""
    print("\n" + "="*60)
    print("PROCESS OFFLINE SYNC")
    print("="*60)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT queue_id, device_id, action_type, entity_type, data
            FROM offline_sync_queue
            WHERE sync_status = 'pending'
            ORDER BY created_at ASC
            LIMIT 10
        ''')

        queue_items = cursor.fetchall()

        if not queue_items:
            print("\n✅ No pending items to sync")
            conn.close()
            return

        print(f"\nProcessing {len(queue_items)} sync items...")

        processed = 0
        failed = 0

        for item in queue_items:
            queue_id, device_id, action, entity, data = item

            try:
                # Simulate sync processing
                print(f"  Processing queue ID {queue_id}: {action} {entity}...")

                with transaction() as conn:
                    conn.execute('''
                        UPDATE offline_sync_queue
                        SET sync_status = 'synced', synced_at = CURRENT_TIMESTAMP
                        WHERE queue_id = ?
                    ''', (queue_id,))

                processed += 1

            except Exception as e:
                print(f"  ❌ Failed to sync queue ID {queue_id}: {e}")
                with transaction() as conn:
                    conn.execute('''
                        UPDATE offline_sync_queue
                        SET sync_status = 'failed'
                        WHERE queue_id = ?
                    ''', (queue_id,))
                failed += 1

        conn.close()

        print(f"\n✅ Sync complete: {processed} processed, {failed} failed")
        log_activity('process', 'offline_sync', details={'processed': processed, 'failed': failed})

    except Exception as e:
        print(f"❌ Error processing sync: {e}")
        logger.error(f"Error processing offline sync: {e}")


# ==================== Mobile Preferences Management ====================

def view_mobile_preferences():
    """View mobile preferences for a user"""
    print("\n" + "="*60)
    print("VIEW MOBILE PREFERENCES")
    print("="*60)

    try:
        user_id = input("Enter User ID: ").strip()
        if not user_id:
            print("❌ User ID is required")
            return

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT theme, notifications_enabled, offline_mode_enabled,
                   data_saver_mode, auto_sync
            FROM mobile_preferences
            WHERE user_id = ?
        ''', (user_id,))

        prefs = cursor.fetchone()
        conn.close()

        if not prefs:
            print(f"\n📋 No preferences found for user {user_id}")
            print("Default preferences will be used")
            return

        theme, notif, offline, data_saver, auto = prefs

        print(f"\n{'='*60}")
        print(f"Preferences for User {user_id}")
        print(f"{'='*60}")
        print(f"Theme: {theme}")
        print(f"Notifications: {'✅ Enabled' if notif else '❌ Disabled'}")
        print(f"Offline Mode: {'✅ Enabled' if offline else '❌ Disabled'}")
        print(f"Data Saver: {'✅ Enabled' if data_saver else '❌ Disabled'}")
        print(f"Auto Sync: {'✅ Enabled' if auto else '❌ Disabled'}")
        print(f"{'='*60}")

        log_activity('view', 'mobile_preferences', user_id=user_id)

    except Exception as e:
        print(f"❌ Error viewing preferences: {e}")
        logger.error(f"Error viewing mobile preferences: {e}")


def update_mobile_preferences():
    """Update mobile preferences for a user"""
    print("\n" + "="*60)
    print("UPDATE MOBILE PREFERENCES")
    print("="*60)

    try:
        user_id = input("Enter User ID: ").strip()
        if not user_id:
            print("❌ User ID is required")
            return

        print("\nTheme Options:")
        print("1. Light")
        print("2. Dark")
        print("3. Auto")
        theme_choice = input("Select theme (1-3) [current]: ").strip()
        themes = {'1': 'light', '2': 'dark', '3': 'auto'}
        theme = themes.get(theme_choice)

        notif = input("Enable notifications? (y/n) [current]: ").strip().lower()
        offline = input("Enable offline mode? (y/n) [current]: ").strip().lower()
        data_saver = input("Enable data saver? (y/n) [current]: ").strip().lower()
        auto_sync = input("Enable auto sync? (y/n) [current]: ").strip().lower()

        # Build update query
        updates = []
        values = []

        if theme:
            updates.append("theme = ?")
            values.append(theme)
        if notif in ['y', 'n']:
            updates.append("notifications_enabled = ?")
            values.append(1 if notif == 'y' else 0)
        if offline in ['y', 'n']:
            updates.append("offline_mode_enabled = ?")
            values.append(1 if offline == 'y' else 0)
        if data_saver in ['y', 'n']:
            updates.append("data_saver_mode = ?")
            values.append(1 if data_saver == 'y' else 0)
        if auto_sync in ['y', 'n']:
            updates.append("auto_sync = ?")
            values.append(1 if auto_sync == 'y' else 0)

        if not updates:
            print("❌ No changes specified")
            return

        values.append(user_id)

        with transaction() as conn:
            # Check if preferences exist
            cursor = conn.execute('''
                SELECT pref_id FROM mobile_preferences WHERE user_id = ?
            ''', (user_id,))

            exists = cursor.fetchone()

            if exists:
                # Update existing preferences
                query = f"UPDATE mobile_preferences SET {', '.join(updates)} WHERE user_id = ?"
                conn.execute(query, values)
            else:
                # Insert new preferences
                conn.execute('''
                    INSERT INTO mobile_preferences (user_id) VALUES (?)
                ''', (user_id,))
                query = f"UPDATE mobile_preferences SET {', '.join(updates)} WHERE user_id = ?"
                conn.execute(query, values)

        log_activity('update', 'mobile_preferences', user_id=user_id)

        print(f"\n✅ Mobile preferences updated successfully")

    except Exception as e:
        print(f"❌ Error updating preferences: {e}")
        logger.error(f"Error updating mobile preferences: {e}")


# ==================== Mobile Analytics ====================

def view_mobile_analytics():
    """View mobile analytics summary"""
    print("\n" + "="*60)
    print("MOBILE ANALYTICS")
    print("="*60)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Total devices
        cursor.execute("SELECT COUNT(*) FROM mobile_devices")
        total_devices = cursor.fetchone()[0]

        # Active devices
        cursor.execute("SELECT COUNT(*) FROM mobile_devices WHERE is_active = 1")
        active_devices = cursor.fetchone()[0]

        # Devices by type
        cursor.execute('''
            SELECT device_type, COUNT(*)
            FROM mobile_devices
            GROUP BY device_type
        ''')
        devices_by_type = cursor.fetchall()

        # Active sessions
        cursor.execute("SELECT COUNT(*) FROM mobile_sessions WHERE logout_time IS NULL")
        active_sessions = cursor.fetchone()[0]

        # Pending sync items
        cursor.execute("SELECT COUNT(*) FROM offline_sync_queue WHERE sync_status = 'pending'")
        pending_sync = cursor.fetchone()[0]

        # Recent analytics events
        cursor.execute('''
            SELECT event_type, COUNT(*)
            FROM mobile_analytics
            WHERE timestamp >= datetime('now', '-7 days')
            GROUP BY event_type
            ORDER BY COUNT(*) DESC
            LIMIT 5
        ''')
        top_events = cursor.fetchall()

        conn.close()

        print(f"\n📱 DEVICES:")
        print(f"   Total: {total_devices}")
        print(f"   Active: {active_devices}")
        print(f"   Inactive: {total_devices - active_devices}")

        print(f"\n📊 BY DEVICE TYPE:")
        for dtype, count in devices_by_type:
            print(f"   {dtype.capitalize()}: {count}")

        print(f"\n🔌 SESSIONS:")
        print(f"   Active: {active_sessions}")

        print(f"\n🔄 SYNC QUEUE:")
        print(f"   Pending: {pending_sync}")

        if top_events:
            print(f"\n📈 TOP EVENTS (Last 7 Days):")
            for event, count in top_events:
                print(f"   {event}: {count}")

        log_activity('view', 'mobile_analytics')

    except Exception as e:
        print(f"❌ Error viewing analytics: {e}")
        logger.error(f"Error viewing mobile analytics: {e}")


def log_mobile_event():
    """Log a mobile analytics event"""
    print("\n" + "="*60)
    print("LOG MOBILE EVENT")
    print("="*60)

    try:
        user_id = input("Enter User ID (optional): ").strip()
        device_id = input("Enter Device ID (optional): ").strip()

        print("\nCommon Event Types:")
        print("1. page_view")
        print("2. button_click")
        print("3. feature_use")
        print("4. error")
        print("5. custom")

        event_choice = input("Select event type (1-5): ").strip()
        event_types = {'1': 'page_view', '2': 'button_click', '3': 'feature_use', '4': 'error', '5': 'custom'}
        event_type = event_types.get(event_choice, 'custom')

        if event_type == 'custom':
            event_type = input("Enter custom event type: ").strip()

        event_data = input("Enter event data (JSON format, optional): ").strip()

        with transaction() as conn:
            conn.execute('''
                INSERT INTO mobile_analytics (
                    user_id, device_id, event_type, event_data
                ) VALUES (?, ?, ?, ?)
            ''', (user_id or None, device_id or None, event_type, event_data or None))

        log_activity('log', 'mobile_event', details={'event_type': event_type})

        print(f"\n✅ Mobile event logged successfully")

    except Exception as e:
        print(f"❌ Error logging event: {e}")
        logger.error(f"Error logging mobile event: {e}")


# ==================== Main Menu ====================

def display_mobile_app_pwa_menu(auth=None):
    """Main CLI menu for mobile app (PWA) infrastructure"""

    # Initialize database on first run
    init_mobile_app_database()

    while True:
        print("\n" + "="*60)
        print(f"  {get_text('mobile_app.title', default='MOBILE APP (PWA) INFRASTRUCTURE')}")
        print("="*60)
        print(f"\n📱 {get_text('mobile_app.sections.devices', default='MOBILE DEVICES')}")
        print(f"1. {get_text('mobile_app.menu.register', default='Register Mobile Device')}")
        print(f"2. {get_text('mobile_app.menu.view_devices', default='View All Devices')}")
        print(f"3. {get_text('mobile_app.menu.deactivate', default='Deactivate Device')}")
        print(f"\n🔌 {get_text('mobile_app.sections.sessions', default='MOBILE SESSIONS')}")
        print(f"4. {get_text('mobile_app.menu.create_session', default='Create Mobile Session')}")
        print(f"5. {get_text('mobile_app.menu.view_sessions', default='View Active Sessions')}")
        print(f"6. {get_text('mobile_app.menu.end_session', default='End Session')}")
        print(f"\n🔄 {get_text('mobile_app.sections.sync', default='OFFLINE SYNC')}")
        print(f"7. {get_text('mobile_app.menu.view_sync', default='View Sync Queue')}")
        print(f"8. {get_text('mobile_app.menu.process_sync', default='Process Sync Queue')}")
        print(f"\n⚙️ {get_text('mobile_app.sections.preferences', default='PREFERENCES')}")
        print(f"9. {get_text('mobile_app.menu.view_prefs', default='View User Preferences')}")
        print(f"10. {get_text('mobile_app.menu.update_prefs', default='Update User Preferences')}")
        print(f"\n📊 {get_text('mobile_app.sections.analytics', default='ANALYTICS')}")
        print(f"11. {get_text('mobile_app.menu.analytics', default='View Analytics Dashboard')}")
        print(f"12. {get_text('mobile_app.menu.log_event', default='Log Analytics Event')}")
        print(f"\n🌐 {get_text('mobile_app.sections.settings', default='SETTINGS')}")
        print(f"13. {get_text('mobile_app.menu.language', default='Language')}")
        print(f"\n14. {get_text('mobile_app.menu.return', default='Return to Main Menu')}")
        print("="*60)

        choice = input(f"\n{get_text('mobile_app.prompt.choice', default='Enter your choice (1-14)')}: ").strip()

        if choice == '1':
            register_mobile_device()
        elif choice == '2':
            view_mobile_devices()
        elif choice == '3':
            deactivate_mobile_device()
        elif choice == '4':
            create_mobile_session()
        elif choice == '5':
            view_active_mobile_sessions()
        elif choice == '6':
            end_mobile_session()
        elif choice == '7':
            view_offline_sync_queue()
        elif choice == '8':
            process_offline_sync()
        elif choice == '9':
            view_mobile_preferences()
        elif choice == '10':
            update_mobile_preferences()
        elif choice == '11':
            view_mobile_analytics()
        elif choice == '12':
            log_mobile_event()
        elif choice == '13':
            display_language_menu_option()
        elif choice == '14':
            print(get_text('mobile_app.returning', default='Returning to main menu...'))
            break
        else:
            print(get_text('mobile_app.invalid_choice', default='Invalid choice. Please try again.'))

        input("\nPress Enter to continue...")


# Export main function
__all__ = ['display_mobile_app_pwa_menu']
