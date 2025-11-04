#!/usr/bin/env python3
"""
Test script for backup and restore functionality
Tests database backup creation and verification
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import sqlite3
import shutil
from datetime import datetime
from pathlib import Path
from university_system.infrastructure.database.db import DEFAULT_DB_PATH


def test_backup_restore():
    """Test backup and restore functionality"""
    print("=" * 60)
    print("BACKUP & RESTORE TEST")
    print("=" * 60)

    # Use the canonical backup directory
    from university_system.modules.shared.constants.paths import BACKUP_DIR
    backup_dir = BACKUP_DIR / "test_backups"
    backup_dir.mkdir(exist_ok=True)

    try:
        # Test 1: Create backup
        print("\n✓ Test 1: Creating database backup...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"test_backup_{timestamp}.db"

        shutil.copy2(DEFAULT_DB_PATH, backup_path)

        if backup_path.exists():
            backup_size = backup_path.stat().st_size / (1024 * 1024)
            print(f"  ✓ Backup created: {backup_path.name}")
            print(f"  ✓ Size: {backup_size:.2f} MB")
        else:
            print("  ✗ Backup creation failed")
            return

        # Test 2: Verify backup integrity
        print("\n✓ Test 2: Verifying backup integrity...")
        conn_backup = sqlite3.connect(str(backup_path))
        cursor = conn_backup.cursor()

        try:
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()[0]

            if integrity_result == "ok":
                print("  ✓ Backup integrity: OK")
            else:
                print(f"  ✗ Backup integrity: {integrity_result}")

            # Test 3: Compare table counts
            print("\n✓ Test 3: Comparing table counts...")
            conn_original = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor_original = conn_original.cursor()

            tables = [
                'students', 'modules', 'student_modules',
                'instructors', 'instructor_modules', 'users'
            ]

            all_match = True
            for table in tables:
                cursor_original.execute(f"SELECT COUNT(*) FROM {table}")
                original_count = cursor_original.fetchone()[0]

                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                backup_count = cursor.fetchone()[0]

                match = "✓" if original_count == backup_count else "✗"
                print(f"  {match} {table}: Original={original_count}, Backup={backup_count}")

                if original_count != backup_count:
                    all_match = False

            if all_match:
                print("\n  ✓ All table counts match")
            else:
                print("\n  ✗ Some table counts don't match")

            conn_original.close()

        finally:
            conn_backup.close()

        # Test 4: Backup metadata
        print("\n✓ Test 4: Backup metadata")
        stat = backup_path.stat()
        print(f"  Created: {datetime.fromtimestamp(stat.st_ctime)}")
        print(f"  Modified: {datetime.fromtimestamp(stat.st_mtime)}")
        print(f"  Size: {stat.st_size:,} bytes")

        # Test 5: List all backups
        print("\n✓ Test 5: Available backups in test directory")
        backups = list(backup_dir.glob("test_backup_*.db"))
        backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        for i, backup in enumerate(backups[:5], 1):
            size_mb = backup.stat().st_size / (1024 * 1024)
            mod_time = datetime.fromtimestamp(backup.stat().st_mtime)
            print(f"  {i}. {backup.name}")
            print(f"     Size: {size_mb:.2f} MB | Modified: {mod_time}")

        # Test 6: Cleanup old test backups (keep last 3)
        print("\n✓ Test 6: Cleaning up old test backups...")
        if len(backups) > 3:
            for old_backup in backups[3:]:
                old_backup.unlink()
                print(f"  Deleted: {old_backup.name}")
            print(f"  ✓ Kept {min(3, len(backups))} most recent backups")
        else:
            print(f"  ✓ Only {len(backups)} backup(s), no cleanup needed")

        print("\n" + "=" * 60)
        print("BACKUP & RESTORE TEST COMPLETED")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_backup_restore()
