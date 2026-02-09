#!/usr/bin/env python3
"""
Fix finance_refunds table to include student_id column.

This script adds the missing student_id column to finance_refunds table
so that refunds from dentist, gym, and library GUIs can be recorded properly.
"""

from university_system.infrastructure.database.db import transaction
import sys

def fix_finance_refunds_table():
    """Add student_id column to finance_refunds if it doesn't exist."""

    print("=" * 70)
    print("FIXING FINANCE_REFUNDS TABLE")
    print("=" * 70)
    print()

    try:
        with transaction() as conn:
            cursor = conn.cursor()

            # Check if table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='finance_refunds'
            """)

            if not cursor.fetchone():
                print("✗ finance_refunds table does not exist")
                print("  Creating table...")

                cursor.execute('''
                    CREATE TABLE finance_refunds (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        refund_reference TEXT NOT NULL UNIQUE,
                        department TEXT NOT NULL,
                        transaction_id TEXT,
                        amount DECIMAL(10,2) NOT NULL,
                        refund_method TEXT NOT NULL,
                        refund_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        refund_time TEXT,
                        processed_by TEXT,
                        notes TEXT
                    )
                ''')
                print("  ✓ Table created successfully")
                return True

            # Check if student_id column exists
            cursor.execute("PRAGMA table_info(finance_refunds)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'student_id' in columns:
                print("✓ student_id column already exists in finance_refunds")
                print("  No changes needed")
                return True

            # Add student_id column
            print("Adding student_id column to finance_refunds...")
            cursor.execute('''
                ALTER TABLE finance_refunds
                ADD COLUMN student_id TEXT
            ''')
            print("✓ student_id column added successfully")

            # Verify the change
            cursor.execute("PRAGMA table_info(finance_refunds)")
            columns = [row[1] for row in cursor.fetchall()]

            print("\nCurrent columns in finance_refunds:")
            for col in columns:
                print(f"  - {col}")

            return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print()
    success = fix_finance_refunds_table()

    print()
    print("=" * 70)
    if success:
        print("✅ FINANCE_REFUNDS TABLE FIXED SUCCESSFULLY")
    else:
        print("❌ FAILED TO FIX FINANCE_REFUNDS TABLE")
    print("=" * 70)

    sys.exit(0 if success else 1)
