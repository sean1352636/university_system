#!/usr/bin/env python3
"""
Test script for campus events functionality
Tests database schema and basic operations
"""

from university_system.modules.domain.campus.services.campus_events_core import (
    CampusEventManager,
    EventRegistrationManager,
    EventAnnouncementManager,
    EventSponsorManager
)
from university_system.infrastructure.database.db import get_connection


def test_database_schema():
    """Test that database tables have correct schema"""
    print("Testing database schema...")

    with get_connection() as conn:
        # Test event_registrations table
        print("\n1. Checking event_registrations table...")
        cursor = conn.execute("PRAGMA table_info(event_registrations)")
        columns = {row[1] for row in cursor.fetchall()}

        required_columns = {'registration_id', 'event_id', 'user_id', 'user_type',
                          'registration_date', 'attendance_status', 'checked_in_at'}

        if required_columns.issubset(columns):
            print("   ✅ event_registrations table has correct schema")
            print(f"   Columns: {sorted(columns)}")
        else:
            print("   ❌ event_registrations table missing columns")
            print(f"   Missing: {required_columns - columns}")
            return False

        # Test foreign keys
        print("\n2. Checking foreign key constraints...")
        cursor = conn.execute("PRAGMA foreign_key_list(event_registrations)")
        fks = cursor.fetchall()

        has_event_fk = any(fk[2] == 'campus_events' for fk in fks)
        if has_event_fk:
            print("   ✅ event_registrations has foreign key to campus_events")
        else:
            print("   ❌ event_registrations missing foreign key to campus_events")
            return False

        # Test event_sponsors
        print("\n3. Checking event_sponsors foreign key...")
        cursor = conn.execute("PRAGMA foreign_key_list(event_sponsors)")
        fks = cursor.fetchall()

        has_event_fk = any(fk[2] == 'campus_events' for fk in fks)
        if has_event_fk:
            print("   ✅ event_sponsors has foreign key to campus_events")
        else:
            print("   ❌ event_sponsors missing foreign key to campus_events")
            return False

        # Test indexes
        print("\n4. Checking indexes...")
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='event_registrations'")
        indexes = [row[0] for row in cursor.fetchall()]

        if 'idx_event_registrations_event_id' in indexes:
            print("   ✅ Index idx_event_registrations_event_id exists")
        else:
            print("   ⚠️  Index idx_event_registrations_event_id missing (performance may be affected)")

        if 'idx_event_registrations_user' in indexes:
            print("   ✅ Index idx_event_registrations_user exists")
        else:
            print("   ⚠️  Index idx_event_registrations_user missing (performance may be affected)")

    return True


def test_basic_operations():
    """Test basic CRUD operations"""
    print("\n\nTesting basic operations...")

    try:
        # Create an event
        print("\n1. Creating test event...")
        event_id = CampusEventManager.create_event(
            event_name="Test Event",
            event_type="Academic",
            event_category="Student Life",
            organizer_id="test_admin",
            organizer_type="staff",
            event_date="2025-12-01",
            start_time="14:00",
            end_time="16:00",
            location="Main Hall",
            capacity=100,
            registration_required=True,
            is_public=True,
            description="This is a test event"
        )
        print(f"   ✅ Created event with ID: {event_id}")

        # Register for event
        print("\n2. Testing event registration...")
        reg_id = EventRegistrationManager.register_for_event(
            event_id=event_id,
            user_id="test_student",
            user_type="student"
        )
        print(f"   ✅ Created registration with ID: {reg_id}")

        # Add sponsor
        print("\n3. Testing sponsor addition...")
        sponsor_id = EventSponsorManager.add_sponsor(
            event_id=event_id,
            sponsor_name="Test Corporation",
            sponsor_type="corporate",
            contribution_amount=1000.00,
            website_url="https://testcorp.com"
        )
        print(f"   ✅ Added sponsor with ID: {sponsor_id}")

        # Send announcement (without actual email)
        print("\n4. Testing announcement (database only)...")
        announcement_id = EventAnnouncementManager.send_announcement(
            event_id=event_id,
            announcement_text="This is a test announcement",
            sent_to="all_registrants",
            sent_by="test_admin"
        )
        print(f"   ✅ Created announcement with ID: {announcement_id}")
        print("   ℹ️  Email sending was attempted (check logs for details)")

        # Clean up
        print("\n5. Cleaning up test data...")
        with get_connection() as conn:
            conn.execute("DELETE FROM event_announcements WHERE announcement_id = ?", (announcement_id,))
            conn.execute("DELETE FROM event_sponsors WHERE sponsor_id = ?", (sponsor_id,))
            conn.execute("DELETE FROM event_registrations WHERE registration_id = ?", (reg_id,))
            conn.execute("DELETE FROM campus_events WHERE event_id = ?", (event_id,))
            conn.commit()
        print("   ✅ Test data cleaned up")

        return True

    except Exception as e:
        print(f"   ❌ Error during operations: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("="*60)
    print("Campus Events Hub - Testing Suite")
    print("="*60)

    schema_ok = test_database_schema()
    operations_ok = test_basic_operations()

    print("\n" + "="*60)
    print("Test Results:")
    print("="*60)
    print(f"Database Schema: {'✅ PASS' if schema_ok else '❌ FAIL'}")
    print(f"Basic Operations: {'✅ PASS' if operations_ok else '❌ FAIL'}")
    print("="*60)

    if schema_ok and operations_ok:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    exit(main())
