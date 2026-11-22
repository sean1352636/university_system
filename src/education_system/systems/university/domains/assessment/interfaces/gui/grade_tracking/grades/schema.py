"""Grade database initialization and migration."""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t
from . import *
from education_system.systems.university.infrastructure.database.schemas.modules_table import ensure_modules_table
from education_system.systems.university.infrastructure.database.schemas.modules_table import ensure_student_modules_table
from education_system.systems.university.infrastructure.database.schemas.students_table import ensure_students_table

DEFAULT_DB_PATH = paths.UNIVERSITY_DEFAULT_DB_PATH

_CENTRALDEFAULT_DB_PATH = paths.UNIVERSITY_DEFAULT_DB_PATH

_original_sqlite3_connect_grade = sqlite3.connect

def _patched_sqlite3_connect_grade(database, *args, **kwargs):
    try:
        db_name = os.path.basename(str(database)) if database else ""
        if not database or db_name in (str(DEFAULT_DB_PATH), "student_grading_system.db"):
            return _original_sqlite3_connect_grade(str(_CENTRALDEFAULT_DB_PATH), *args, **kwargs)
    except Exception:
        logger.debug("Suppressed exception", exc_info=True)
    return _original_sqlite3_connect_grade(database, *args, **kwargs)

sqlite3.connect = _patched_sqlite3_connect_grade

def init_basic_database():
    """Initialize the basic database tables that are missing"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Create students table
        ensure_students_table(cursor)

        # Create modules table
        ensure_modules_table(cursor)

        # Create student_modules table (enrollment)
        ensure_student_modules_table(cursor)

        # Create assessments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assessments (
        assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        assessment_name TEXT NOT NULL,
        assessment_type TEXT NOT NULL,
        module_code TEXT NOT NULL,
        max_points REAL NOT NULL,
        weight REAL NOT NULL,
        due_date TEXT,
        date_created TEXT DEFAULT (datetime('now')),
        description TEXT,
        rubric TEXT,
        FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        # Ensure rubric column exists for legacy databases.
        ensure_column_exists(cursor, 'assessments', 'rubric', 'TEXT')

        conn.commit()
        conn.close()
        return True

    except sqlite3.Error as e:
        messagebox.showerror(_t('gui.academics.grade_tracking.grades.schema.dialogs.database_error', default="Database Error"), f"Database error: {e}")
        return False

def init_enhanced_grades_db():
    """Initialize the enhanced grades database with all required tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Create base grade tables if they don't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS grades (
        grade_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        assessment_id INTEGER,
        score REAL,
        letter_grade TEXT,
        submission_date TEXT,
        comments TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id)
        )
        ''')

        # Enforce grade integrity at the database boundary as well as in the
        # GUI. Legacy databases receive the same protections here.
        ensure_column_exists(cursor, 'grades', 'updated_at', "TEXT DEFAULT ''")
        ensure_column_exists(cursor, 'grades', 'version', 'INTEGER NOT NULL DEFAULT 1')
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_grades_student_assessment "
            "ON grades(student_id, assessment_id)"
        )
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS grades_validate_score
            BEFORE INSERT ON grades
            WHEN NEW.score IS NULL OR NEW.score != NEW.score
                 OR NEW.score > 1e308 OR NEW.score < -1e308
                 OR NEW.score < 0
                 OR NEW.score > (SELECT max_points FROM assessments
                                 WHERE assessment_id = NEW.assessment_id)
            BEGIN SELECT RAISE(ABORT, 'invalid grade score'); END
        ''')
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS grades_validate_score_update
            BEFORE UPDATE OF score, assessment_id ON grades
            WHEN NEW.score IS NULL OR NEW.score != NEW.score
                 OR NEW.score > 1e308 OR NEW.score < -1e308
                 OR NEW.score < 0
                 OR NEW.score > (SELECT max_points FROM assessments
                                 WHERE assessment_id = NEW.assessment_id)
            BEGIN SELECT RAISE(ABORT, 'invalid grade score'); END
        ''')

        # Optimistic-concurrency enforcement at the DB boundary. The version
        # column and updated_at were application-managed, so a writer that
        # forgot them (the legacy dialogs did) silently won a lost-update race.
        # This trigger bumps version and stamps updated_at on EVERY update, so
        # the lost-update protection holds no matter which code path writes —
        # GUI validation can no longer be the only thing standing between two
        # concurrent edits. Guarded on version to avoid recursing on its own
        # UPDATE.
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS grades_bump_version
            AFTER UPDATE ON grades
            FOR EACH ROW
            WHEN NEW.version = OLD.version
            BEGIN
                UPDATE grades
                SET version = OLD.version + 1,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE grade_id = NEW.grade_id;
            END
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS module_grades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        module_code TEXT,
        final_score REAL,
        final_grade TEXT,
        completion_date TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        # Enhanced tables for statistics and analytics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS grade_statistics (
        stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
        assessment_id INTEGER,
        mean REAL,
        median REAL,
        std_dev REAL,
        min_score REAL,
        max_score REAL,
        q1 REAL,
        q3 REAL,
        skewness REAL,
        kurtosis REAL,
        date_calculated TEXT,
        FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS normalized_grades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        grade_id INTEGER,
        z_score REAL,
        percentile REAL,
        curved_score REAL,
        curved_letter TEXT,
        FOREIGN KEY (grade_id) REFERENCES grades (grade_id)
        )
        ''')

        # Predictive analytics tables
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS risk_factors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        factor_name TEXT,
        factor_value REAL,
        assessment_id INTEGER,
        date_calculated TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS risk_details (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        risk_factor_id INTEGER,
        detail TEXT,
        weight REAL,
        created_at TEXT,
        FOREIGN KEY (risk_factor_id) REFERENCES risk_factors (id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS intervention_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        description TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS recommended_interventions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        risk_factor_id INTEGER,
        intervention_type_id INTEGER,
        recommended_date TEXT,
        status TEXT DEFAULT 'pending',
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (risk_factor_id) REFERENCES risk_factors (id),
        FOREIGN KEY (intervention_type_id) REFERENCES intervention_types (id)
        )
        ''')

        # Exam marking control, module-result standing and board locks
        # (normally applied by migration a3c5e7f9b2d4; idempotent here).
        from education_system.systems.university.infrastructure.database.schemas import grade_results_schema
        grade_results_schema.apply(
            cursor.execute,
            lambda table: {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')})

        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        messagebox.showerror(_t('gui.academics.grade_tracking.grades.schema.dialogs.database_error', default="Database Error"), f"Database error: {e}")
        return False
