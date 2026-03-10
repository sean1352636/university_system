#!/usr/bin/env python3
"""
Migration: Add missing columns to student_modules table

This migration adds the following columns to the student_modules table:
- module_type: Type of module (Standard, Elective, etc.)
- module_name: Name of the module
- grade: Student's grade in the module
- completion_date: Date when the module was completed
- status: Enrollment status (default: 'Enrolled')

These columns were missing from the original schema but are required
by the advanced search and analytics features.
"""

from education_system.university_system.infrastructure.database.db import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from education_system.university_system.core import paths
from education_system.university_system.core.i18n import get_text

def run_migration():
    """Run the migration to add missing columns to student_modules"""
    try:
        conn = sqlite3.connect(paths.DEFAULT_DB_PATH)
        cursor = conn.cursor()

        print(get_text("migrations.student_modules.starting"))

        # Check existing columns
        cursor.execute("PRAGMA table_info(student_modules)")
        existing_columns = {col[1] for col in cursor.fetchall()}
        print(get_text("migrations.student_modules.existing_columns", columns=existing_columns))

        columns_to_add = {
            'module_type': "ALTER TABLE student_modules ADD COLUMN module_type TEXT DEFAULT 'Standard'",
            'module_name': "ALTER TABLE student_modules ADD COLUMN module_name TEXT",
            'grade': "ALTER TABLE student_modules ADD COLUMN grade TEXT",
            'completion_date': "ALTER TABLE student_modules ADD COLUMN completion_date TEXT",
            'status': "ALTER TABLE student_modules ADD COLUMN status TEXT DEFAULT 'Enrolled'"
        }

        # Add missing columns
        for col_name, sql in columns_to_add.items():
            if col_name not in existing_columns:
                print(f"Adding column: {col_name}")
                cursor.execute(sql)
                print(f"✓ Added column: {col_name}")
            else:
                print(f"⊙ Column already exists: {col_name}")

        conn.commit()

        # Populate module_type and module_name from modules table
        print("\nPopulating data from modules table...")

        cursor.execute("""
            UPDATE student_modules
            SET module_type = (
                SELECT module_type
                FROM modules
                WHERE modules.module_code = student_modules.module_code
            )
            WHERE module_code IN (SELECT module_code FROM modules)
            AND (module_type IS NULL OR module_type = 'Standard')
        """)
        rows_updated = cursor.rowcount
        print(f"✓ Updated module_type for {rows_updated} records")

        cursor.execute("""
            UPDATE student_modules
            SET module_name = (
                SELECT module_name
                FROM modules
                WHERE modules.module_code = student_modules.module_code
            )
            WHERE module_code IN (SELECT module_code FROM modules)
            AND module_name IS NULL
        """)
        rows_updated = cursor.rowcount
        print(f"✓ Updated module_name for {rows_updated} records")

        conn.commit()

        # Verify final schema
        cursor.execute("PRAGMA table_info(student_modules)")
        final_columns = cursor.fetchall()

        print("\nFinal schema for student_modules:")
        print("-" * 60)
        for col in final_columns:
            col_id, name, dtype, notnull, default, pk = col
            print(f"  {name:<20} {dtype:<10} {f'DEFAULT {default}' if default else ''}")
        print("-" * 60)

        conn.close()
        print("\n✓ Migration completed successfully!")
        return True

    except sqlite3.Error as e:
        print(f"\n✗ Migration failed: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Student Modules Table Migration")
    print("=" * 60)
    print()

    success = run_migration()

    if success:
        print("\nMigration completed. You can now use the advanced search")
        print("and analytics features without column errors.")
        sys.exit(0)
    else:
        print("\nMigration failed. Please check the error messages above.")
        sys.exit(1)
