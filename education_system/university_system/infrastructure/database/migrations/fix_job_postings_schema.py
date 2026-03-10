"""
Migration: Fix job_postings table schema

This migration renames the old job_postings table and creates the new one
with the correct schema for Staff HR v2.
"""

from education_system.university_system.infrastructure.database.db import transaction
import logging

logger = logging.getLogger(__name__)


def migrate():
    """Run the migration to fix job_postings schema."""
    try:
        with transaction() as conn:
            cursor = conn.cursor()

            # Check if old table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='job_postings'
            """)

            if cursor.fetchone():
                # Check if it has the old schema (job_id column)
                cursor.execute("PRAGMA table_info(job_postings)")
                columns = {col[1] for col in cursor.fetchall()}

                if 'job_id' in columns and 'posting_id' not in columns:
                    logger.info("Found old job_postings schema, migrating...")

                    # Rename old table
                    cursor.execute("""
                        ALTER TABLE job_postings
                        RENAME TO job_postings_old
                    """)

                    # Create new table with correct schema
                    cursor.execute('''
                        CREATE TABLE job_postings (
                            posting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            job_title TEXT NOT NULL,
                            department TEXT NOT NULL,
                            job_type TEXT DEFAULT 'permanent',
                            location TEXT,
                            description TEXT,
                            requirements TEXT,
                            responsibilities TEXT,
                            salary_range TEXT,
                            benefits TEXT,
                            posted_by TEXT NOT NULL,
                            posted_by_name TEXT,
                            post_date TEXT,
                            closing_date TEXT,
                            status TEXT DEFAULT 'draft',
                            hiring_manager_id TEXT,
                            hiring_manager_name TEXT,
                            applications_count INTEGER DEFAULT 0,
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')

                    # Migrate data from old table to new
                    cursor.execute("""
                        INSERT INTO job_postings (
                            job_title, department, job_type, location,
                            description, requirements, salary_range,
                            posted_by, post_date, created_at
                        )
                        SELECT
                            COALESCE(job_title, 'Unknown Position'),
                            COALESCE(company_name, 'General'),
                            COALESCE(job_type, 'permanent'),
                            location,
                            job_description,
                            requirements,
                            salary_range,
                            COALESCE(posted_by, 'system'),
                            COALESCE(post_date, CURRENT_TIMESTAMP),
                            COALESCE(post_date, CURRENT_TIMESTAMP)
                        FROM job_postings_old
                    """)

                    rows_migrated = cursor.rowcount
                    logger.info(f"Migrated {rows_migrated} job postings to new schema")

                    # Drop old table
                    cursor.execute("DROP TABLE job_postings_old")

                    print(f"✓ Migrated {rows_migrated} job postings to new schema")
                else:
                    logger.info("job_postings table already has correct schema")
                    print("✓ job_postings schema is up to date")

            return True

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        print(f"✗ Migration failed: {e}")
        return False


if __name__ == "__main__":
    migrate()
