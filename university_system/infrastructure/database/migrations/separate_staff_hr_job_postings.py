"""
Migration: Separate Staff HR and Career Services job_postings tables

This migration renames the Staff HR job_postings table to staff_recruitment_postings
to avoid conflicts with the Career Services job_postings table.
"""

from university_system.infrastructure.database.db import transaction
import logging

logger = logging.getLogger(__name__)


def migrate():
    """Run the migration to separate job_postings tables."""
    try:
        with transaction() as conn:
            cursor = conn.cursor()

            # Check if job_postings table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='job_postings'
            """)

            if cursor.fetchone():
                # Check which schema it has
                cursor.execute("PRAGMA table_info(job_postings)")
                columns = {col[1] for col in cursor.fetchall()}

                # If it has posting_id, it's the Staff HR version
                if 'posting_id' in columns:
                    logger.info("Found Staff HR job_postings table, renaming to staff_recruitment_postings...")

                    # Rename the table
                    cursor.execute("""
                        ALTER TABLE job_postings
                        RENAME TO staff_recruitment_postings
                    """)

                    # Update job_applications table to reference new table
                    cursor.execute("""
                        SELECT name FROM sqlite_master
                        WHERE type='table' AND name='job_applications'
                    """)

                    if cursor.fetchone():
                        # Check if job_applications has posting_id column
                        cursor.execute("PRAGMA table_info(job_applications)")
                        app_columns = {col[1] for col in cursor.fetchall()}

                        if 'posting_id' in app_columns:
                            # This is Staff HR's job_applications, rename it too
                            cursor.execute("""
                                ALTER TABLE job_applications
                                RENAME TO staff_recruitment_applications
                            """)
                            logger.info("Renamed job_applications to staff_recruitment_applications")

                    logger.info("Successfully renamed Staff HR tables")
                    print("✓ Renamed Staff HR job_postings → staff_recruitment_postings")
                    print("✓ Renamed Staff HR job_applications → staff_recruitment_applications")

                elif 'job_id' in columns:
                    logger.info("job_postings table already uses Career Services schema (job_id)")
                    print("✓ job_postings table is already Career Services version")
                else:
                    logger.warning("Unknown job_postings schema")
                    print("⚠ Unknown job_postings schema")
            else:
                logger.info("No job_postings table found - will be created on first use")
                print("✓ No existing job_postings table to migrate")

            return True

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        print(f"✗ Migration failed: {e}")
        return False


if __name__ == "__main__":
    migrate()
