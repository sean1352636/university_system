"""Health portal CLI workflow extracted from the legacy module."""

from __future__ import annotations

import csv
import json
import logging
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

from education_system.systems.university.infrastructure.database.db import (
    DEFAULT_DB_PATH,
    get_connection,
)
from education_system import paths

logger = logging.getLogger(__name__)

def backup_management_menu(auth):
    """Database backup management menu."""
    print("\n--- Database Backup Management ---")

    while True:
        print("\n" + "="*60)
        print("        DATABASE BACKUP MANAGEMENT")
        print("="*60)
        print("1. Create Manual Backup")
        print("2. View Backup History")
        print("3. Restore from Backup (Admin Only)")
        print("0. Return to Main Menu")
        print("="*60)

        choice = input("Enter your choice (0-3): ").strip()

        if choice == '0':
            break
        elif choice == '1':
            create_manual_backup(auth)
        elif choice == '2':
            view_backup_history(auth)
        elif choice == '3':
            restore_from_backup(auth)
        else:
            print("Invalid choice. Please try again.")

def create_manual_backup(auth):
    """Create a manual database backup."""
    print("\n--- Create Manual Backup ---")

    try:
        # Create backups directory
        backup_dir = paths.UNIVERSITY_BACKUP_HEALTH_DIR
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Create backup filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        username = auth.get_username()
        backup_filename = backup_dir / f'health_backup_{timestamp}_{username}.db'

        # Copy the database file
        db_path = DEFAULT_DB_PATH
        if isinstance(db_path, str):
            db_path = Path(db_path)

        if not db_path.exists():
            print(f"\nError: Database file not found at {db_path}")
            return

        # Perform the backup
        print("\nCreating backup...")
        shutil.copy2(db_path, backup_filename)

        # Get backup size
        backup_size = backup_filename.stat().st_size / (1024 * 1024)  # MB

        # Log backup in database
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backup_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backup_filename TEXT NOT NULL,
                backup_size_mb REAL,
                created_by TEXT,
                backup_type TEXT DEFAULT 'manual',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            INSERT INTO backup_history (backup_filename, backup_size_mb, created_by, backup_type)
            VALUES (?, ?, ?, 'manual')
        """, (str(backup_filename), backup_size, username))

        conn.commit()
        backup_id = cursor.lastrowid
        conn.close()

        print("\n✓ Backup created successfully!")
        print("="*60)
        print(f"Backup ID: {backup_id}")
        print(f"Filename: {backup_filename.name}")
        print(f"Location: {backup_dir}")
        print(f"Size: {backup_size:.2f} MB")
        print(f"Created by: {username}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)

        logger.info(f"Manual backup created by {username}: {backup_filename}")

    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        print(f"\nError creating backup: {e}")

def view_backup_history(auth):
    """View backup history."""
    print("\n--- Backup History ---")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Create backup_history table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backup_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backup_filename TEXT NOT NULL,
                backup_size_mb REAL,
                created_by TEXT,
                backup_type TEXT DEFAULT 'manual',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        # Query backup history
        cursor.execute("""
            SELECT id, backup_filename, backup_size_mb, created_by, backup_type, timestamp
            FROM backup_history
            ORDER BY timestamp DESC
            LIMIT 20
        """)

        backups = cursor.fetchall()
        conn.close()

        if backups:
            print("\n" + "="*90)
            print(f"{'ID':<6} {'Filename':<35} {'Size (MB)':<12} {'Type':<10} {'Created By':<15}")
            print("="*90)
            for backup in backups:
                filename = Path(backup['backup_filename']).name
                print(f"{backup['id']:<6} {filename:<35} {backup['backup_size_mb']:<12.2f} "
                      f"{backup['backup_type']:<10} {backup['created_by'] or 'System':<15}")
                print(f"       Created: {backup['timestamp']}")
            print("="*90)
            print(f"\nShowing {len(backups)} most recent backups")

            # Summary statistics
            total_backups = len(backups)
            total_size = sum(b['backup_size_mb'] for b in backups if b['backup_size_mb'])
            print("\nStatistics:")
            print(f"  Total backups shown: {total_backups}")
            print(f"  Total size: {total_size:.2f} MB")

        else:
            print("\nNo backup history found.")
            print("Create your first backup using option 1.")

    except Exception as e:
        logger.error(f"Error viewing backup history: {e}")
        print(f"\nError viewing backup history: {e}")

def restore_from_backup(auth):
    """Restore database from backup (admin only)."""
    print("\n--- Restore from Backup ---")
    print("\n⚠  WARNING: This is an admin-only operation!")
    print("⚠  Restoring will replace the current database!")

    # Check if user is admin
    try:
        user_role = auth.get_role() if hasattr(auth, 'get_role') else None
        if user_role != 'admin':
            print("\n✗ Access Denied: Admin privileges required")
            print("  This operation requires administrator access.")
            logger.warning(f"Unauthorized restore attempt by {auth.get_username()}")
            return
    except Exception:
        print("\n✗ Could not verify admin status")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Show available backups
        cursor.execute("""
            SELECT id, backup_filename, backup_size_mb, timestamp
            FROM backup_history
            ORDER BY timestamp DESC
            LIMIT 10
        """)

        backups = cursor.fetchall()
        conn.close()

        if not backups:
            print("\nNo backups available for restore.")
            return

        print("\nAvailable backups:")
        print("="*80)
        for i, backup in enumerate(backups, 1):
            filename = Path(backup['backup_filename']).name
            print(f"{i}. [{backup['id']}] {filename}")
            print(f"   Size: {backup['backup_size_mb']:.2f} MB | Created: {backup['timestamp']}")

        print("="*80)

        # Select backup to restore
        choice = input("\nEnter backup number to restore (0 to cancel): ").strip()

        if choice == '0':
            print("Restore cancelled.")
            return

        try:
            backup_index = int(choice) - 1
            if backup_index < 0 or backup_index >= len(backups):
                print("Invalid backup number.")
                return
        except ValueError:
            print("Invalid input.")
            return

        selected_backup = backups[backup_index]
        backup_path = Path(selected_backup['backup_filename'])

        if not backup_path.exists():
            print(f"\n✗ Error: Backup file not found at {backup_path}")
            print("  The backup file may have been moved or deleted.")
            return

        # Final confirmation
        print(f"\n⚠  You are about to restore from: {backup_path.name}")
        print("⚠  This will replace the current database!")
        confirm = input("\nType 'RESTORE' to confirm: ").strip()

        if confirm != 'RESTORE':
            print("Restore cancelled.")
            return

        # Create safety backup of current database first
        print("\nCreating safety backup of current database...")
        safety_backup_dir = paths.UNIVERSITY_BACKUP_SAFETY_DIR
        safety_backup_dir.mkdir(parents=True, exist_ok=True)

        safety_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safety_backup = safety_backup_dir / f'pre_restore_backup_{safety_timestamp}.db'

        db_path = Path(DEFAULT_DB_PATH)
        shutil.copy2(db_path, safety_backup)
        print(f"✓ Safety backup created: {safety_backup}")

        # Perform restore
        print(f"\nRestoring from {backup_path.name}...")
        shutil.copy2(backup_path, db_path)

        print("\n✓ Database restored successfully!")
        print("="*60)
        print(f"Restored from: {backup_path.name}")
        print(f"Safety backup: {safety_backup}")
        print(f"Restored by: {auth.get_username()}")
        print("="*60)
        print("\nIMPORTANT: Please restart the application for changes to take effect.")

        logger.info(f"Database restored from {backup_path} by {auth.get_username()}")

    except Exception as e:
        logger.error(f"Error restoring from backup: {e}")
        print(f"\n✗ Error restoring from backup: {e}")
        print("  The database may be in an inconsistent state.")
        print("  Please contact technical support immediately.")
