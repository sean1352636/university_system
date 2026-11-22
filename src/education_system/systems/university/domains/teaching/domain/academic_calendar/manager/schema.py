"""Extracted AcademicCalendarManager schema methods.

The calendar's tables are created by Alembic migrations (the baseline, plus
``f7b9d1e3a5c8`` / ``calendar_year_schema`` for the academic-year tables and
``course_events``). Nothing here creates tables at run time any more: the
manager checks they exist and says clearly which are missing. It no longer
invents an academic year and Fall/Spring semesters on an empty database —
years and terms come from the Academic year menu (``calendar_year``).
"""

from ._shared import DatabaseError, datetime, logger

#: Tables the calendar manager reads and writes; all created by migrations.
REQUIRED_TABLES = (
    "academic_years", "semesters", "event_categories", "event_tags", "event_tag_assignments",
    "courses", "course_events", "resources", "resource_bookings", "calendar_notification_preferences",
    "notification_queue", "search_presets", "recurring_events", "backup_history",
    "unified_events", "unified_event_registrations",
)

DEFAULT_CATEGORIES = (
    ("Academic", "#1E3A8A", "Academic events like lectures, exams"),
    ("Trip", "#15803D", "Educational trips and excursions"),
    ("Holiday", "#7C3AED", "Holidays and breaks"),
    ("Deadline", "#EA580C", "Important deadlines"),
)


class SchemaMixin:
    def _initialize_database(self):
        """Check the schema is in place and add the standard categories."""
        try:
            logger.info("Checking calendar database...")
            self._apply_calendar_year_schema()
            missing = self._missing_tables()
            if missing:
                raise DatabaseError(
                    "The calendar tables are missing: " + ", ".join(missing)
                    + ". Run the database migrations (alembic upgrade head).")
            self._create_default_data()
            logger.info("Calendar database ready")
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Database check failed: {e}")
            raise DatabaseError(f"Failed to check the calendar database: {e}")

    def _apply_calendar_year_schema(self):
        """Idempotent additions owned by migration f7b9d1e3a5c8."""
        from education_system.systems.university.infrastructure.database.schemas import (
            calendar_year_schema,
        )
        conn = getattr(self.db_manager, "conn", None)
        if conn is not None:
            calendar_year_schema.apply_to_connection(conn)

    def _missing_tables(self):
        from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608
        missing = []
        for table in REQUIRED_TABLES:
            try:
                safe_table = validate_identifier(table, "table")
                self.db_manager.execute_query("SELECT 1 FROM [" + safe_table + "] LIMIT 1")
            except Exception:
                missing.append(table)
        return missing

    def _create_minimal_tables(self):
        """No longer creates tables: report what the migrations must add."""
        missing = self._missing_tables()
        if missing:
            logger.error("Calendar tables missing (run the migrations): %s", missing)
            raise DatabaseError("The calendar tables are missing: " + ", ".join(missing)
                                + ". Run the database migrations (alembic upgrade head).")

    def _create_backup_directory(self):
        """Create backup directory if it doesn't exist"""
        try:
            import os
            backup_dir = getattr(self.config, 'backup_directory', 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            logger.debug(f"Backup directory ensured: {backup_dir}")
        except Exception as e:
            logger.warning(f"Could not create backup directory: {e}")

    def _verify_required_tables(self):
        """True when every calendar table exists (they come from migrations)."""
        missing = self._missing_tables()
        if missing:
            logger.error("Calendar tables missing (run the migrations): %s", missing)
            return False
        logger.info("Required tables verified")
        return True

    def _create_default_data(self):
        """The standard event categories (configuration, inserted once)."""
        try:
            current_time = datetime.now().isoformat()
            for name, color, description in DEFAULT_CATEGORIES:
                self.db_manager.execute_update(
                    "INSERT OR IGNORE INTO event_categories (name, color_code, description, "
                    "date_added) VALUES (?, ?, ?, ?)", (name, color, description, current_time))
        except Exception as e:
            logger.warning(f"Default category creation had issues: {e}")
