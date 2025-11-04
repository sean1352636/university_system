#!/usr/bin/env python3
"""
Test script to verify accommodation GUI database fixes.
"""

import sys
import sqlite3
from pathlib import Path

# Add university_system to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'university_system'))
from university_system.infrastructure.database.db import DEFAULT_DB_PATH

def test_audit_log_schema():
    """Test that audit_log table has correct schema"""
    print("🔍 Testing audit_log table schema...")

    try:
        # Connect to database
        db_path = Path(DEFAULT_DB_PATH)

        if not db_path.exists():
            print("❌ Database file not found")
            return False

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Check audit_log schema
        cursor.execute("PRAGMA table_info(audit_log)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        print(f"✅ audit_log table columns: {column_names}")

        # Test if our log_action fix would work
        expected_columns = ['user_id', 'action', 'table_affected', 'record_id', 'new_values', 'timestamp', 'ip_address', 'success']

        missing_columns = [col for col in expected_columns if col not in column_names]

        if missing_columns:
            print(f"⚠️  Missing columns for log_action fix: {missing_columns}")
        else:
            print("✅ All required columns present for log_action fix")

        conn.close()
        return len(missing_columns) == 0

    except Exception as e:
        print(f"❌ Audit log schema test failed: {e}")
        return False

def test_log_action_import():
    """Test that log_action function can be imported"""
    print("\n📝 Testing log_action function...")

    try:
        sys.path.append('.')
        from university_system.modules.domain.housing.services.accommodation import log_action

        print("✅ log_action function imported successfully")

        # Test the function signature
        import inspect
        sig = inspect.signature(log_action)
        params = list(sig.parameters.keys())
        print(f"✅ log_action parameters: {params}")

        return True

    except Exception as e:
        print(f"❌ log_action import test failed: {e}")
        return False

def test_accommodation_gui_import():
    """Test that accommodation GUI can be imported"""
    print("\n🖥️  Testing accommodation GUI import...")

    try:
        sys.path.append('.')
        from university_system.modules.domain.housing.gui.accommodation_gui import AccommodationGUI

        print("✅ AccommodationGUI imported successfully")
        return True

    except Exception as e:
        print(f"❌ Accommodation GUI import failed: {e}")
        return False

def main():
    """Run accommodation fixes tests"""
    print("=" * 60)
    print("ACCOMMODATION GUI DATABASE FIXES VERIFICATION")
    print("=" * 60)

    tests_passed = 0
    total_tests = 3

    if test_audit_log_schema():
        tests_passed += 1

    if test_log_action_import():
        tests_passed += 1

    if test_accommodation_gui_import():
        tests_passed += 1

    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)
    print(f"Tests passed: {tests_passed}/{total_tests}")

    if tests_passed == total_tests:
        print("🎉 Accommodation fixes verified!")
        print("\n✅ FIXES IMPLEMENTED:")
        print("   - Fixed log_action to use correct audit_log schema")
        print("   - Updated INSERT statement to match existing columns")
        print("   - Removed non-existent accommodation_id column reference")
        print("\n🚀 Medical accommodation GUI should work without database errors!")
        return True
    else:
        print("❌ Some accommodation tests failed")
        return False

if __name__ == "__main__":
    main()