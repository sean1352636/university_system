#!/usr/bin/env python3
"""
MFA Unique Contacts Migration
Ensures that email addresses and phone numbers can only be linked to one user account.
This prevents MFA bypass attacks where an attacker could link their victim's phone/email to their own account.
"""

import sqlite3
import os
import sys
from datetime import datetime

# Add path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from modules.shared.constants.paths import DEFAULT_DB_PATH


def run_migration(db_path=None):
    """Execute MFA unique contacts database migration"""
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("Running MFA unique contacts migration...")

        # Step 1: Check for existing duplicates
        print("\n1. Checking for duplicate MFA contacts...")
        cursor.execute("""
            SELECT method_type, method_identifier, COUNT(*) as user_count, GROUP_CONCAT(user_id) as user_ids
            FROM mfa_methods
            WHERE method_type IN ('email', 'sms')
            AND method_identifier IS NOT NULL
            AND is_enabled = 1
            GROUP BY method_type, method_identifier
            HAVING COUNT(*) > 1
        """)

        duplicates = cursor.fetchall()

        if duplicates:
            print(f"\n⚠️  WARNING: Found {len(duplicates)} duplicate MFA contacts:")
            for method_type, identifier, count, user_ids in duplicates:
                print(f"   - {method_type.upper()}: {identifier} (used by {count} users: {user_ids})")

            print("\n   These duplicates must be resolved before applying unique constraints.")
            print("   Please contact the affected users to update their MFA settings.")
            print("   Skipping unique constraint creation for now.")

            # Log duplicates to a file for admin review
            log_file = os.path.join(os.path.dirname(db_path), '..', 'logs', 'mfa_duplicate_contacts.log')
            os.makedirs(os.path.dirname(log_file), exist_ok=True)

            with open(log_file, 'a') as f:
                f.write(f"\n{'='*80}\n")
                f.write(f"Migration check at {datetime.now().isoformat()}\n")
                f.write(f"{'='*80}\n")
                for method_type, identifier, count, user_ids in duplicates:
                    f.write(f"{method_type.upper()}: {identifier} - Users: {user_ids}\n")

            print(f"\n   Duplicates logged to: {log_file}")
            print("\n❌ Migration partially completed - manual intervention required")
            return False
        else:
            print("   ✓ No duplicates found")

        # Step 2: Create partial unique indexes for email and SMS
        # These indexes only apply to enabled methods, allowing disabled methods to share identifiers
        print("\n2. Creating unique indexes for MFA contacts...")

        # Unique index for email addresses
        try:
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_mfa_methods_unique_email
                ON mfa_methods(method_identifier)
                WHERE method_type = 'email' AND is_enabled = 1
            """)
            print("   ✓ Created unique index for email addresses")
        except sqlite3.IntegrityError as e:
            print(f"   ✗ Failed to create email unique index: {e}")
            conn.rollback()
            return False

        # Unique index for phone numbers
        try:
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_mfa_methods_unique_phone
                ON mfa_methods(method_identifier)
                WHERE method_type = 'sms' AND is_enabled = 1
            """)
            print("   ✓ Created unique index for phone numbers")
        except sqlite3.IntegrityError as e:
            print(f"   ✗ Failed to create phone unique index: {e}")
            conn.rollback()
            return False

        # Step 3: Verify indexes were created
        print("\n3. Verifying indexes...")
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND name LIKE 'idx_mfa_methods_unique_%'
        """)

        indexes = cursor.fetchall()
        print(f"   ✓ Created {len(indexes)} unique indexes:")
        for index in indexes:
            print(f"     - {index[0]}")

        conn.commit()

        print("\n" + "="*80)
        print("✅ MFA unique contacts migration completed successfully!")
        print("="*80)
        print("\nSummary:")
        print("  • Email addresses must now be unique across all user accounts")
        print("  • Phone numbers must now be unique across all user accounts")
        print("  • Each contact can only be linked to one MFA-enabled account")
        print("  • This prevents MFA bypass attacks and improves security")
        print("\nNote: Users can still update their own MFA contacts.")
        print("="*80)

        return True

    except Exception as e:
        conn.rollback()
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


def rollback_migration(db_path=None):
    """Rollback the unique contacts migration"""
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("Rolling back MFA unique contacts migration...")

        # Drop the unique indexes
        cursor.execute("DROP INDEX IF EXISTS idx_mfa_methods_unique_email")
        cursor.execute("DROP INDEX IF EXISTS idx_mfa_methods_unique_phone")

        conn.commit()
        print("✓ Migration rolled back successfully")
        return True

    except Exception as e:
        conn.rollback()
        print(f"✗ Rollback failed: {e}")
        return False
    finally:
        conn.close()


if __name__ == '__main__':
    import sys

    # Check for rollback flag
    if len(sys.argv) > 1 and sys.argv[1] == '--rollback':
        db_path = sys.argv[2] if len(sys.argv) > 2 else None
        success = rollback_migration(db_path)
    else:
        db_path = sys.argv[1] if len(sys.argv) > 1 else None
        success = run_migration(db_path)

    sys.exit(0 if success else 1)
