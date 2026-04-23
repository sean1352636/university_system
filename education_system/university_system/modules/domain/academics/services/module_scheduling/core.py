from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from education_system.university_system.modules.domain.academics.services.module_scheduling.constants import DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES
from education_system.university_system.modules.domain.academics.services.module_scheduling.analytics import AnalyticsMixin
from education_system.university_system.modules.domain.academics.services.module_scheduling.conflicts import ConflictsMixin
from education_system.university_system.modules.domain.academics.services.module_scheduling.optimization import OptimizationMixin
from education_system.university_system.modules.domain.academics.services.module_scheduling.import_export import ImportExportMixin
from education_system.university_system.modules.domain.academics.services.module_scheduling.templates import TemplatesMixin
from education_system.university_system.modules.domain.academics.services.module_scheduling.timetables import TimetablesMixin
from education_system.university_system.modules.domain.academics.services.module_scheduling.viewing import ViewingMixin
from education_system.university_system.modules.domain.academics.services.module_scheduling.visualization import VisualizationMixin
from education_system.university_system.modules.domain.academics.services.module_scheduling.notifications import NotificationsMixin
from education_system.university_system.modules.domain.academics.services.module_scheduling.holidays import HolidaysMixin
from education_system.university_system.modules.domain.academics.services.module_scheduling.backup import BackupMixin
from education_system.university_system.modules.domain.academics.services.module_scheduling.settings import SettingsMixin
import os
from datetime import datetime, timedelta


class ModuleScheduler(
    AnalyticsMixin,
    ConflictsMixin,
    OptimizationMixin,
    ImportExportMixin,
    TemplatesMixin,
    TimetablesMixin,
    ViewingMixin,
    VisualizationMixin,
    NotificationsMixin,
    HolidaysMixin,
    BackupMixin,
    SettingsMixin,
):
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = str(DEFAULT_DB_PATH)
        self.db_path = db_path
        self._init_db()
        self._migrate_database()  # Run migrations after table creation
        self._init_config()

    def _init_db(self):
        """Initialize database tables needed for scheduling"""
        with get_connection(self.db_path, row_factory=False) as conn:
            cursor = conn.cursor()

            # Modules reference table (needed for foreign keys and lookups)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS modules (
                module_code TEXT PRIMARY KEY,
                module_name TEXT NOT NULL,
                module_type TEXT,
                credits INTEGER DEFAULT 1,
                description TEXT,
                course TEXT,
                semester TEXT,
                year INTEGER
            )
            ''')

            # Existing tables (keeping your original structure)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS module_schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_code TEXT,
                day_of_week TEXT,
                start_time TEXT,
                end_time TEXT,
                room_id INTEGER,
                instructor_id INTEGER,
                session_type TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (module_code) REFERENCES modules (module_code),
                FOREIGN KEY (room_id) REFERENCES rooms (id),
                FOREIGN KEY (instructor_id) REFERENCES instructors (id)
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_number TEXT,
                building TEXT,
                capacity INTEGER,
                room_type TEXT,
                equipment TEXT,
                notes TEXT,
                is_active BOOLEAN DEFAULT 1
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS instructors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                department TEXT DEFAULT '',
                specialization TEXT DEFAULT '',
                max_courses_per_semester INTEGER DEFAULT 4,
                max_hours_per_week INTEGER DEFAULT 40,
                preferred_days TEXT,
                preferred_times TEXT,
                status TEXT DEFAULT 'Active',
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
            ''')

            # New tables for enhanced features
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedule_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_name TEXT UNIQUE,
                description TEXT,
                template_data TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedule_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_id INTEGER,
                action TEXT,
                old_values TEXT,
                new_values TEXT,
                changed_by TEXT,
                change_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS scheduling_system_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                description TEXT,
                last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedule_conflicts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conflict_type TEXT,
                description TEXT,
                affected_schedules TEXT,
                resolved BOOLEAN DEFAULT 0,
                resolution_notes TEXT,
                detected_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_date TIMESTAMP
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_type TEXT,
                recipient_id TEXT,
                message TEXT,
                notification_type TEXT,
                sent BOOLEAN DEFAULT 0,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sent_date TIMESTAMP
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS holidays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                holiday_name TEXT,
                start_date DATE,
                end_date DATE,
                description TEXT,
                recurring BOOLEAN DEFAULT 0
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS backups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backup_name TEXT,
                backup_path TEXT,
                backup_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                backup_size INTEGER,
                description TEXT
            )
            ''')

            # Initialize default settings
            cursor.execute('INSERT OR IGNORE INTO scheduling_system_settings (key, value, description) VALUES (?, ?, ?)',
                          ('institution_name', 'University', 'Name of the institution'))
            cursor.execute('INSERT OR IGNORE INTO scheduling_system_settings (key, value, description) VALUES (?, ?, ?)',
                          ('semester_start', '', 'Semester start date'))
            cursor.execute('INSERT OR IGNORE INTO scheduling_system_settings (key, value, description) VALUES (?, ?, ?)',
                          ('semester_end', '', 'Semester end date'))
            cursor.execute('INSERT OR IGNORE INTO scheduling_system_settings (key, value, description) VALUES (?, ?, ?)',
                          ('default_session_duration', '60', 'Default session duration in minutes'))
            cursor.execute('INSERT OR IGNORE INTO scheduling_system_settings (key, value, description) VALUES (?, ?, ?)',
                          ('email_notifications', 'False', 'Enable email notifications'))
            cursor.execute('INSERT OR IGNORE INTO scheduling_system_settings (key, value, description) VALUES (?, ?, ?)',
                          ('auto_backup', 'True', 'Enable automatic backups'))

    def _migrate_database(self):
        """Migrate existing database tables to add missing columns"""
        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                with get_connection(self.db_path, row_factory=False) as conn:
                    conn.execute("PRAGMA journal_mode=WAL")  # Enable WAL mode
                    conn.execute("PRAGMA busy_timeout = 30000")  # 30 second timeout
                    cursor = conn.cursor()

                    # Check and add missing columns to instructors table
                    cursor.execute("PRAGMA table_info(instructors)")
                    existing_columns = {row[1] for row in cursor.fetchall()}

                    migrations = []
                    if 'max_hours_per_week' not in existing_columns:
                        migrations.append("ALTER TABLE instructors ADD COLUMN max_hours_per_week INTEGER DEFAULT 40")
                    if 'preferred_days' not in existing_columns:
                        migrations.append("ALTER TABLE instructors ADD COLUMN preferred_days TEXT")
                    if 'preferred_times' not in existing_columns:
                        migrations.append("ALTER TABLE instructors ADD COLUMN preferred_times TEXT")
                    if 'is_active' not in existing_columns:
                        migrations.append("ALTER TABLE instructors ADD COLUMN is_active BOOLEAN DEFAULT 1")
                    if 'specialization' not in existing_columns:
                        migrations.append("ALTER TABLE instructors ADD COLUMN specialization TEXT DEFAULT ''")
                    if 'max_courses_per_semester' not in existing_columns:
                        migrations.append("ALTER TABLE instructors ADD COLUMN max_courses_per_semester INTEGER DEFAULT 4")

                    # Check and add missing columns to rooms table
                    cursor.execute("PRAGMA table_info(rooms)")
                    existing_columns = {row[1] for row in cursor.fetchall()}

                    if 'is_active' not in existing_columns:
                        migrations.append("ALTER TABLE rooms ADD COLUMN is_active BOOLEAN DEFAULT 1")

                    # Add building_id column for compatibility with facilities management system
                    if 'building_id' not in existing_columns:
                        migrations.append("ALTER TABLE rooms ADD COLUMN building_id INTEGER")
                        print("Added building_id column to rooms table for facilities management compatibility")

                    # Add other columns for facilities management compatibility
                    if 'room_name' not in existing_columns:
                        migrations.append("ALTER TABLE rooms ADD COLUMN room_name TEXT")
                    if 'floor_number' not in existing_columns:
                        migrations.append("ALTER TABLE rooms ADD COLUMN floor_number INTEGER")
                    if 'area_sqft' not in existing_columns:
                        migrations.append("ALTER TABLE rooms ADD COLUMN area_sqft REAL")
                    if 'features' not in existing_columns:
                        migrations.append("ALTER TABLE rooms ADD COLUMN features TEXT")
                    if 'accessibility_compliant' not in existing_columns:
                        migrations.append("ALTER TABLE rooms ADD COLUMN accessibility_compliant BOOLEAN DEFAULT 1")
                    if 'status' not in existing_columns:
                        migrations.append("ALTER TABLE rooms ADD COLUMN status TEXT DEFAULT 'available'")

                    # module_schedule: term, status (draft/published), recurrence, what-if linkage.
                    # All additive with safe defaults so existing rows stay valid and the legacy
                    # CLI/services that don't reference these columns keep working unchanged.
                    cursor.execute("PRAGMA table_info(module_schedule)")
                    ms_cols = {row[1] for row in cursor.fetchall()}
                    if 'semester' not in ms_cols:
                        migrations.append("ALTER TABLE module_schedule ADD COLUMN semester TEXT DEFAULT 'Fall'")
                    if 'year' not in ms_cols:
                        # SQLite ALTER TABLE won't accept non-constant DEFAULT, so default to a
                        # placeholder; the GUI/service code populates real values on insert.
                        migrations.append("ALTER TABLE module_schedule ADD COLUMN year INTEGER DEFAULT 0")
                    if 'status' not in ms_cols:
                        migrations.append("ALTER TABLE module_schedule ADD COLUMN status TEXT DEFAULT 'published'")
                    if 'recurrence' not in ms_cols:
                        migrations.append("ALTER TABLE module_schedule ADD COLUMN recurrence TEXT DEFAULT 'weekly'")
                    if 'recurrence_until' not in ms_cols:
                        migrations.append("ALTER TABLE module_schedule ADD COLUMN recurrence_until TEXT")
                    if 'parent_schedule_id' not in ms_cols:
                        migrations.append("ALTER TABLE module_schedule ADD COLUMN parent_schedule_id INTEGER")

                    # Indexes on the columns the GUI/CLI filter or join on
                    # most often. CREATE INDEX IF NOT EXISTS is idempotent.
                    # Composite (semester, year) covers the term filter that
                    # every list/grid view applies; (status) feeds the draft
                    # vs published split; module_code/instructor_id/room_id
                    # back the LIKE/JOIN paths in schedules_tab + reports.
                    migrations.extend([
                        "CREATE INDEX IF NOT EXISTS idx_module_schedule_term "
                        "ON module_schedule(semester, year)",
                        "CREATE INDEX IF NOT EXISTS idx_module_schedule_status "
                        "ON module_schedule(status)",
                        "CREATE INDEX IF NOT EXISTS idx_module_schedule_module_code "
                        "ON module_schedule(module_code)",
                        "CREATE INDEX IF NOT EXISTS idx_module_schedule_day "
                        "ON module_schedule(day_of_week)",
                        "CREATE INDEX IF NOT EXISTS idx_module_schedule_instructor "
                        "ON module_schedule(instructor_id)",
                        "CREATE INDEX IF NOT EXISTS idx_module_schedule_room "
                        "ON module_schedule(room_id)",
                        "CREATE INDEX IF NOT EXISTS idx_schedule_history_schedule "
                        "ON schedule_history(schedule_id)",
                    ])

                    # Execute all migrations
                    for migration in migrations:
                        try:
                            cursor.execute(migration)
                            print(f"Migration executed: {migration}")
                        except sqlite3.Error as e:
                            if "duplicate column name" in str(e).lower():
                                print(f"Migration skipped (already exists): {migration}")
                            else:
                                print(f"Migration failed: {migration} - {e}")

                    conn.commit()
                    return  # Success, exit retry loop

            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    import time
                    print(f"Database locked, retrying in {retry_delay} seconds... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    print(f"Migration failed after {max_retries} attempts: {e}")
            except Exception as e:
                print(f"Migration error: {e}")
                break

    def _init_config(self):
        """Initialize configuration settings"""
        from education_system.university_system.modules.shared.constants import paths
        os.makedirs(str(paths.REPORTS_DIR / 'timetable_reports'), exist_ok=True)
        os.makedirs(str(paths.BACKUP_DIR), exist_ok=True)
        os.makedirs(str(paths.ANALYTICS_DIR), exist_ok=True)
        os.makedirs(str(paths.REPORT_TEMPLATES_DIR), exist_ok=True)

    def _get_known_modules(self):
        """Get all known modules from various sources"""
        with get_connection(self.db_path, row_factory=False) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            # First try to get from modules table
            cursor.execute('SELECT module_code, module_name FROM modules')
            modules_from_table = cursor.fetchall()

            if modules_from_table:
                modules_dict = {code: name for code, name in modules_from_table}
                return modules_dict

            # Fallback: Get unique modules from student_modules
            modules_from_enrollments = []
            try:
                cursor.execute('''
                SELECT DISTINCT module_code, module_name
                FROM student_modules
                WHERE module_code IS NOT NULL AND module_name IS NOT NULL
                ORDER BY module_code
                ''')
                modules_from_enrollments = cursor.fetchall()
            except Exception:
                pass

            # Also get from existing schedules
            cursor.execute('''
            SELECT DISTINCT ms.module_code, COALESCE(m.module_name, 'Unknown') as module_name
            FROM module_schedule ms
            LEFT JOIN modules m ON ms.module_code = m.module_code
            WHERE ms.module_code IS NOT NULL
            ORDER BY ms.module_code
            ''')

            modules_from_schedules = cursor.fetchall()

            # Combine all sources
            all_modules = {}

            # Add from enrollments
            for code, name in modules_from_enrollments:
                all_modules[code] = name

            # Add from schedules (don't overwrite if we already have a name)
            for code, name in modules_from_schedules:
                if code not in all_modules:
                    all_modules[code] = name

            return all_modules

    def get_all_modules(self):
        """Get all modules from the database - public interface"""
        try:
            with get_connection(self.db_path, row_factory=False) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                # Primary: get from modules table (correct source for module data)
                cursor.execute('''
                SELECT module_code, module_name, COALESCE(module_type, 'compulsory') as module_type, rowid
                FROM modules
                WHERE module_code IS NOT NULL
                ORDER BY module_code
                ''')
                modules = cursor.fetchall()

                if modules:
                    return [{
                        'id': str(row[3]),
                        'code': row[0],
                        'name': row[1],
                        'type': row[2],
                        'credits': '',  # Default empty - can be enhanced later
                        'semester': '',  # Default empty - can be enhanced later
                        'instructor': ''  # Default empty - can be enhanced later
                    } for row in modules]

                # Fallback: get from student_modules table if modules table is empty
                cursor.execute('''
                SELECT DISTINCT module_code, module_name, 'Unknown' as module_type, rowid
                FROM student_modules
                WHERE module_code IS NOT NULL
                ORDER BY module_code
                ''')
                student_modules = cursor.fetchall()

                if student_modules:
                    return [{
                        'id': str(row[3]),
                        'code': row[0],
                        'name': row[1] or 'Unknown',
                        'type': row[2],
                        'credits': '',
                        'semester': '',
                        'instructor': ''
                    } for row in student_modules]

                # Final fallback: return empty list
                return []

        except Exception as e:
            print(f"Error getting modules: {e}")
            return []

    def delete_module_schedule(self, schedule_id, force=False, changed_by=None):
        """Delete a module schedule entry.

        force=True skips the interactive `input()` confirmation so the GUI
        can call this safely. changed_by is recorded on the schedule_history
        row.
        """
        try:
            with get_connection(self.db_path, row_factory=False) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                # Snapshot the row + column names so the history record holds
                # the full pre-delete state in one place.
                cursor.execute("PRAGMA table_info(module_schedule)")
                col_names = [c[1] for c in cursor.fetchall()]
                cursor.execute('SELECT * FROM module_schedule WHERE id = ?', (schedule_id,))
                schedule = cursor.fetchone()

                if not schedule:
                    print(f"Schedule ID {schedule_id} does not exist.")
                    return False

                if not force:
                    print(f"Schedule to delete: Module {schedule[1]} on {schedule[2]} at {schedule[3]}-{schedule[4]}")
                    confirm = input("Are you sure you want to delete this schedule? (y/n): ")
                    if confirm.lower() != 'y':
                        print("Deletion cancelled.")
                        return False

                # Log the deletion
                self._log_system_action('schedule_deleted',
                                      f"Deleted schedule ID {schedule_id}: {schedule[1]} on {schedule[2]} {schedule[3]}-{schedule[4]}")

                # Schedule history snapshot before the row vanishes.
                import json as _json
                old_snapshot = _json.dumps(dict(zip(col_names, schedule)), default=str)
                cursor.execute("""
                    INSERT INTO schedule_history
                    (schedule_id, action, old_values, new_values, changed_by)
                    VALUES (?, 'delete', ?, NULL, ?)
                """, (schedule_id, old_snapshot, changed_by or 'system'))

                # Delete the schedule
                cursor.execute('DELETE FROM module_schedule WHERE id = ?', (schedule_id,))

                print(f"Schedule deleted successfully.")

                # Notifications — skip for drafts (which were never visible to students).
                row_status = dict(zip(col_names, schedule)).get('status', 'published')
                if row_status == 'published':
                    self.send_schedule_change_notifications(schedule_id,
                                                          f"Class cancelled: {schedule[1]} on {schedule[2]} {schedule[3]}-{schedule[4]}")

                return True

        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False

    def update_module_schedule(self, schedule_id, **kwargs):
        """Update a module schedule entry.

        Accepts the same new optional fields as add_module_schedule:
        semester, year, status, recurrence, recurrence_until.
        Caller can pass `changed_by=<username>` for the schedule_history row;
        it is stripped from kwargs before building the UPDATE.
        """
        changed_by = kwargs.pop('changed_by', None)
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        # Check if schedule entry exists
        cursor.execute('SELECT * FROM module_schedule WHERE id = ?', (schedule_id,))
        schedule = cursor.fetchone()

        if not schedule:
            print(f"Schedule ID {schedule_id} does not exist.")
            conn.close()
            return False

        # Snapshot column-name -> old-value for the history record so the
        # diff stored in schedule_history is meaningful.
        cursor.execute("PRAGMA table_info(module_schedule)")
        col_names = [c[1] for c in cursor.fetchall()]
        old_values_map = dict(zip(col_names, schedule))

        # Build update query based on provided kwargs
        update_fields = []
        update_values = []

        if 'day_of_week' in kwargs:
            day = kwargs['day_of_week']
            if day not in DAYS_OF_WEEK:
                print(f"Invalid day of week. Must be one of: {', '.join(DAYS_OF_WEEK)}")
                conn.close()
                return False
            update_fields.append("day_of_week = ?")
            update_values.append(day)

        if 'start_time' in kwargs or 'end_time' in kwargs:
            # Get current values for validation
            cursor.execute('SELECT start_time, end_time FROM module_schedule WHERE id = ?', (schedule_id,))
            current_times = cursor.fetchone()
            start_time = kwargs.get('start_time', current_times[0])
            end_time = kwargs.get('end_time', current_times[1])

            # Basic time format validation
            try:
                datetime.strptime(start_time, "%H:%M")
                datetime.strptime(end_time, "%H:%M")
            except ValueError:
                print("Invalid time format. Use HH:MM format (24-hour).")
                conn.close()
                return False

            # Check if start time is before end time
            if start_time >= end_time:
                print("Start time must be before end time.")
                conn.close()
                return False

            if 'start_time' in kwargs:
                update_fields.append("start_time = ?")
                update_values.append(start_time)

            if 'end_time' in kwargs:
                update_fields.append("end_time = ?")
                update_values.append(end_time)

        if 'room_id' in kwargs:
            room_id = kwargs['room_id']
            cursor.execute('SELECT id FROM rooms WHERE id = ?', (room_id,))
            if not cursor.fetchone():
                print(f"Room ID {room_id} does not exist.")
                conn.close()
                return False
            update_fields.append("room_id = ?")
            update_values.append(room_id)

        if 'instructor_id' in kwargs:
            instructor_id = kwargs['instructor_id']
            cursor.execute('SELECT id FROM instructors WHERE id = ?', (instructor_id,))
            if not cursor.fetchone():
                print(f"Instructor ID {instructor_id} does not exist.")
                conn.close()
                return False
            update_fields.append("instructor_id = ?")
            update_values.append(instructor_id)

        if 'session_type' in kwargs:
            session_type = kwargs['session_type']
            if session_type not in SESSION_TYPES:
                print(f"Invalid session type. Must be one of: {', '.join(SESSION_TYPES)}")
                conn.close()
                return False
            update_fields.append("session_type = ?")
            update_values.append(session_type)

        # New optional fields — light validation, accept anything else as-is.
        if 'semester' in kwargs:
            update_fields.append("semester = ?")
            update_values.append(kwargs['semester'])
        if 'year' in kwargs:
            update_fields.append("year = ?")
            update_values.append(int(kwargs['year']))
        if 'status' in kwargs:
            new_status = kwargs['status']
            if new_status not in ("draft", "published", "archived"):
                print(f"Invalid status: {new_status}")
                conn.close()
                return False
            update_fields.append("status = ?")
            update_values.append(new_status)
        if 'recurrence' in kwargs:
            new_rec = kwargs['recurrence']
            if new_rec not in ("none", "weekly", "biweekly"):
                print(f"Invalid recurrence: {new_rec}")
                conn.close()
                return False
            update_fields.append("recurrence = ?")
            update_values.append(new_rec)
        if 'recurrence_until' in kwargs:
            update_fields.append("recurrence_until = ?")
            update_values.append(kwargs['recurrence_until'])

        if not update_fields:
            print("No fields to update.")
            conn.close()
            return False

        # Touch modified_date on every update so listings can sort by recency.
        update_fields.append("modified_date = CURRENT_TIMESTAMP")

        # Get current schedule details for conflict checking
        cursor.execute('''
        SELECT module_code, day_of_week, start_time, end_time, room_id, instructor_id
        FROM module_schedule WHERE id = ?
        ''', (schedule_id,))
        current = cursor.fetchone()
        module_code, current_day, current_start, current_end, current_room, current_instructor = current

        # Check for conflicts with the new schedule
        day = kwargs.get('day_of_week', current_day)
        start_time = kwargs.get('start_time', current_start)
        end_time = kwargs.get('end_time', current_end)
        room_id = kwargs.get('room_id', current_room)
        instructor_id = kwargs.get('instructor_id', current_instructor)

        # Check for room conflicts
        if 'day_of_week' in kwargs or 'start_time' in kwargs or 'end_time' in kwargs or 'room_id' in kwargs:
            conflicts = self._check_room_conflicts(room_id, day, start_time, end_time)
            # Filter out the current schedule
            conflicts = [c for c in conflicts if c[0] != schedule_id]
            if conflicts:
                print(f"Room conflict detected: Room is already scheduled during this time.")
                conn.close()
                return False

        # Check for instructor conflicts
        if 'day_of_week' in kwargs or 'start_time' in kwargs or 'end_time' in kwargs or 'instructor_id' in kwargs:
            conflicts = self._check_instructor_conflicts(instructor_id, day, start_time, end_time)
            # Filter out the current schedule
            conflicts = [c for c in conflicts if c[0] != schedule_id]
            if conflicts:
                print(f"Instructor conflict detected: Instructor is already scheduled during this time.")
                conn.close()
                return False

        # Execute the update
        query = f"UPDATE module_schedule SET {', '.join(update_fields)} WHERE id = ?"
        update_values.append(schedule_id)

        try:
            cursor.execute(query, update_values)

            # Schedule history — record only the columns the caller actually
            # changed, not the full row, so diffs stay readable.
            import json as _json
            tracked = ('day_of_week', 'start_time', 'end_time', 'room_id',
                       'instructor_id', 'session_type', 'semester', 'year',
                       'status', 'recurrence', 'recurrence_until')
            old_diff = {k: old_values_map.get(k) for k in tracked if k in kwargs}
            new_diff = {k: kwargs[k] for k in tracked if k in kwargs}
            if old_diff:  # nothing tracked changed → skip the history row
                cursor.execute("""
                    INSERT INTO schedule_history
                    (schedule_id, action, old_values, new_values, changed_by)
                    VALUES (?, 'update', ?, ?, ?)
                """, (schedule_id, _json.dumps(old_diff), _json.dumps(new_diff),
                      changed_by or 'system'))

            conn.commit()
            print(f"Schedule updated successfully.")
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
        finally:
            conn.close()

    def schedule_module_interactively(self):
        # Show all modules for user to select
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        cursor.execute("SELECT module_code, module_name FROM modules")
        modules = cursor.fetchall()
        conn.close()

        print("Modules:")
        print("=" * 60)
        print(f"{'No.':<5} {'Code':<10} {'Name'}")
        print("-" * 60)
        for idx, (code, name) in enumerate(modules, 1):
            print(f"{idx:<5} {code:<10} {name}")
        print("=" * 60)

        module_choice = int(input("Enter module number: "))
        if not (1 <= module_choice <= len(modules)):
            print("Invalid module selection.")
            return

        module_code = modules[module_choice - 1][0]

        # Continue with rest of inputs
        print("Days of Week:")
        for i, day in enumerate(DAYS_OF_WEEK, 1):
            print(f"{i}. {day}")
        day_index = int(input("Enter day of week (1-5): "))
        day_of_week = DAYS_OF_WEEK[day_index - 1]

        start_time = input("Enter start time (HH:MM, 24-hour format): ")
        end_time = input("Enter end time (HH:MM, 24-hour format): ")

        # Get room ID
        # (repeat similar logic as above for room listing)
        room_id = int(input("Enter room ID: "))

        # Get instructor ID
        instructor_id = int(input("Enter instructor ID: "))

        # Get session type
        session_type = input("Enter session type: ")

        # Call your backend
        self.add_module_schedule(
            module_code, day_of_week, start_time, end_time,
            room_id, instructor_id, session_type
        )

    def add_room(self, room_number, building, capacity, room_type, equipment="", notes=""):
        """Add a new room to the database (enhanced version)"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        try:
            cursor.execute('''
            INSERT INTO rooms (room_number, building, capacity, room_type, equipment, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (room_number, building, capacity, room_type, equipment, notes))

            conn.commit()
            print(f"Room {building}-{room_number} added successfully.")

            # Log the action
            self._log_system_action('room_added', f"Added room {building}-{room_number}")

            return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None
        finally:
            conn.close()

    def add_instructor(self, first_name, last_name, email, department, max_hours=40, preferred_days="", preferred_times=""):
        """Add a new instructor to the database (enhanced version)"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        try:
            cursor.execute('''
            INSERT INTO instructors (first_name, last_name, email, department, max_hours_per_week, preferred_days, preferred_times)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (first_name, last_name, email, department, max_hours, preferred_days, preferred_times))

            conn.commit()
            print(f"Instructor {first_name} {last_name} added successfully.")

            # Log the action
            self._log_system_action('instructor_added', f"Added instructor {first_name} {last_name}")

            return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None
        finally:
            conn.close()

    def add_module_schedule(self, module_code, day_of_week, start_time, end_time,
                            room_id, instructor_id, session_type,
                            semester=None, year=None, status="published",
                            recurrence="weekly", recurrence_until=None,
                            parent_schedule_id=None, changed_by=None):
        """Add a new schedule entry for a module (enhanced with conflict detection).

        New optional kwargs (default to back-compat values so legacy callers stay
        unchanged):
          semester / year       — multi-term planning. Defaults to current term.
          status                — 'draft' | 'published' | 'archived'.
          recurrence            — 'none' | 'weekly' | 'biweekly'.
          recurrence_until      — ISO date string, end of recurrence (NULL = open).
          parent_schedule_id    — non-NULL when this row was cloned from another
                                  (for what-if scenarios).
          changed_by            — username for the schedule_history row.

        Drafts skip room/instructor conflict checks — they're allowed to overlap
        published rows so planners can stage scenarios without fighting the live
        timetable.
        """
        if day_of_week not in DAYS_OF_WEEK:
            print(f"Invalid day of week. Must be one of: {', '.join(DAYS_OF_WEEK)}")
            return False

        try:
            datetime.strptime(start_time, "%H:%M")
            datetime.strptime(end_time, "%H:%M")
        except ValueError:
            print("Invalid time format. Use HH:MM format (24-hour).")
            return False

        if start_time >= end_time:
            print("Start time must be before end time.")
            return False

        # Default term to current calendar year + a sensible season inference.
        if year is None:
            year = datetime.now().year
        if semester is None:
            month = datetime.now().month
            semester = "Spring" if month <= 5 else ("Summer" if month <= 7 else "Fall")
        if status not in ("draft", "published", "archived"):
            status = "published"
        if recurrence not in ("none", "weekly", "biweekly"):
            recurrence = "weekly"

        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        # Validation checks (keeping your original logic)
        cursor.execute('SELECT module_code FROM modules')
        known_modules = {row[0] for row in cursor.fetchall()}
        if module_code not in known_modules:
            print(f"Module {module_code} does not exist.")
            conn.close()
            return False

        cursor.execute('SELECT id FROM rooms WHERE id = ?', (room_id,))
        if not cursor.fetchone():
            print(f"Room ID {room_id} does not exist.")
            conn.close()
            return False

        cursor.execute('SELECT id FROM instructors WHERE id = ?', (instructor_id,))
        if not cursor.fetchone():
            print(f"Instructor ID {instructor_id} does not exist.")
            conn.close()
            return False

        # Enhanced conflict checking — skipped for drafts so what-if scenarios
        # can overlap the live schedule without false-positive blocks.
        if status == "published":
            room_conflicts = self._check_room_conflicts(room_id, day_of_week, start_time, end_time)
            if room_conflicts:
                print(f"Room conflict detected: Room is already scheduled during this time.")
                alternatives = self.find_alternative_slots(day_of_week, start_time, end_time)
                if alternatives:
                    print("Suggested alternatives:")
                    for alt in alternatives[:3]:
                        print(f"  - {alt['day']} {alt['start_time']}-{alt['end_time']}")
                conn.close()
                return False

            instructor_conflicts = self._check_instructor_conflicts(instructor_id, day_of_week, start_time, end_time)
            if instructor_conflicts:
                print(f"Instructor conflict detected: Instructor is already scheduled during this time.")
                conn.close()
                return False

        try:
            cursor.execute("""
            INSERT INTO module_schedule
            (module_code, day_of_week, start_time, end_time, room_id, instructor_id, session_type,
             semester, year, status, recurrence, recurrence_until, parent_schedule_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (module_code, day_of_week, start_time, end_time, room_id, instructor_id, session_type,
                  semester, year, status, recurrence, recurrence_until, parent_schedule_id))

            schedule_id = cursor.lastrowid

            # Schedule history — record the create. JSON snapshot is the new
            # row's user-visible fields so audits show what was created.
            import json as _json
            new_snapshot = _json.dumps({
                "module_code": module_code, "day_of_week": day_of_week,
                "start_time": start_time, "end_time": end_time,
                "room_id": room_id, "instructor_id": instructor_id,
                "session_type": session_type,
                "semester": semester, "year": year, "status": status,
                "recurrence": recurrence, "recurrence_until": recurrence_until,
                "parent_schedule_id": parent_schedule_id,
            })
            cursor.execute("""
                INSERT INTO schedule_history
                (schedule_id, action, old_values, new_values, changed_by)
                VALUES (?, 'create', NULL, ?, ?)
            """, (schedule_id, new_snapshot, changed_by or 'system'))
            conn.commit()

            print(f"Schedule for module {module_code} added successfully.")

            # Log the action
            self._log_system_action('schedule_added', f"Added schedule for {module_code} on {day_of_week} {start_time}-{end_time}")

            # Send notifications — only on publish; drafts are silent so
            # what-if scenarios don't spam students with cancelled-class emails.
            if status == "published":
                self.send_schedule_change_notifications(schedule_id, f"New class scheduled: {module_code} on {day_of_week} {start_time}-{end_time}")

            return schedule_id
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
        finally:
            conn.close()
