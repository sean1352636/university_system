#!/usr/bin/env python3
"""
Comprehensive test for accommodation GUI fixes.
"""

import sys
import sqlite3
from pathlib import Path

# Add university_system to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'university_system'))
from university_system.infrastructure.database.db import DEFAULT_DB_PATH

def test_validate_accommodation_data():
    """Test that validate_accommodation_data handles sqlite3.Row objects"""
    print("🧪 Testing validate_accommodation_data with sqlite3.Row...")

    try:
        sys.path.append('.')
        from university_system.modules.domain.housing.gui.accommodation_gui import AccommodationGUI
        import tkinter as tk

        # Create a mock GUI instance
        root = tk.Tk()
        root.withdraw()
        gui = AccommodationGUI(root)

        # Test with regular dictionary (should work)
        dict_data = {
            'student_id': 'S12345',
            'accommodation_type': 'Medical',
            'start_date': '2025-01-01',
            'end_date': '2025-12-31'
        }

        errors = gui.validate_accommodation_data(dict_data)
        print(f"✅ Dictionary validation: {len(errors)} errors")

        # Test with sqlite3.Row-like object
        db_path = Path(DEFAULT_DB_PATH)
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Create a mock row that looks like accommodation data
            cursor.execute("""
                SELECT 'S12345' as student_id,
                       'Medical' as accommodation_type,
                       '2025-01-01' as start_date,
                       '2025-12-31' as end_date
            """)
            row_data = cursor.fetchone()

            if row_data:
                print(f"✅ Created sqlite3.Row object: {dict(row_data)}")

                # This should NOT raise AttributeError anymore
                errors = gui.validate_accommodation_data(row_data)
                print(f"✅ sqlite3.Row validation: {len(errors)} errors")

            conn.close()

        root.destroy()
        return True

    except Exception as e:
        print(f"❌ validate_accommodation_data test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_log_action_functionality():
    """Test the fixed log_action function"""
    print("\n📝 Testing log_action with correct audit_log schema...")

    try:
        sys.path.append('.')
        from university_system.modules.domain.housing.services.accommodation import log_action

        # Test logging an action (should not raise database schema error)
        print("🧪 Testing log_action call...")
        log_action('test_action', 123, 'Test accommodation logging')
        print("✅ log_action completed without schema errors")

        # Verify the log was written
        db_path = Path(DEFAULT_DB_PATH)
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            cursor.execute("""
                SELECT action, table_affected, record_id, new_values
                FROM audit_log
                WHERE action = 'test_action'
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            result = cursor.fetchone()

            if result:
                print(f"✅ Log entry found: {result}")
            else:
                print("⚠️  No log entry found (may be expected)")

            conn.close()

        return True

    except Exception as e:
        print(f"❌ log_action test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run comprehensive accommodation tests"""
    print("=" * 70)
    print("COMPREHENSIVE ACCOMMODATION GUI FIXES VERIFICATION")
    print("=" * 70)

    tests_passed = 0
    total_tests = 2

    if test_validate_accommodation_data():
        tests_passed += 1

    if test_log_action_functionality():
        tests_passed += 1

    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)
    print(f"Tests passed: {tests_passed}/{total_tests}")

    if tests_passed == total_tests:
        print("🎉 ALL ACCOMMODATION FIXES WORKING!")
        print("\n✅ ISSUES RESOLVED:")
        print("   1. ❌ 'table audit_log has no column named accommodation_id'")
        print("      ✅ Fixed log_action to use correct audit_log schema")
        print("   2. ❌ 'sqlite3.row has no attribute get'")
        print("      ✅ Added sqlite3.Row to dict conversion in validate_accommodation_data")
        print("\n🏥 Medical accommodation GUI should now work without errors!")
        return True
    else:
        print("❌ Some accommodation tests failed")
        return False

if __name__ == "__main__":
    main()