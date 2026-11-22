"""Trip management storage: the one trip schema and the connection helpers.

This module owns the DDL for every trip table. ``apply(execute)`` creates
them in their current shape and adds the columns an older database lacks;
``init_trip_db`` (here and in the package ``__init__``), the university
schema bootstrap (``facilities_housing_schemas``), the auth integration's
``init_trip_db`` and the alembic migration all run it rather than declaring
the tables themselves. Changing a CHECK on an existing table is the
migration's job (SQLite cannot alter one in place).

``get_db_connection`` / ``safe_db_operation`` are the single implementation
behind both ``trip_management.database`` and the ``trip_management``
package; ``write_transaction`` / ``read_connection`` are what the domain
functions use (``BEGIN IMMEDIATE`` up front, short, no prompts inside).
"""
import sys
from contextlib import contextmanager

from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import _common
from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management._common import sqlite3, get_text, logging, time, traceback

logger = logging.getLogger(__name__)

_PACKAGE = __name__.rsplit('.', 1)[0]

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

# 'planning' is the legacy spelling of 'proposed' and is still accepted.
TRIP_STATUSES = ('proposed', 'planning', 'approved', 'open', 'full', 'closed',
                 'in_progress', 'cancelled', 'completed', 'archived')
LEGACY_TRIP_STATUSES = {'active': 'open', 'planned': 'planning',
                        'upcoming': 'open', 'confirmed': 'approved'}
TRIP_TYPES = ('day', 'residential', 'fieldwork', 'overseas', 'su_social', 'sport', 'other')
TRIP_SOURCES = ('operations', 'su')

PARTICIPANT_STATUSES = ('registered', 'waitlisted', 'offered', 'confirmed',
                        'cancelled', 'attended', 'no_show', 'removed')
LEGACY_PARTICIPANT_STATUSES = {'waitlist': 'waitlisted', 'pending': 'registered',
                               'active': 'registered'}
# Statuses that hold a place on the trip (capacity counts these). An
# 'offered' place is held for the person it was offered to until it expires.
ACTIVE_PARTICIPANT_STATUSES = ('registered', 'offered', 'confirmed', 'attended')
# Statuses from which a person is still "on" the trip for the purposes of
# "already registered" (a cancelled or removed row may be re-used).
CURRENT_PARTICIPANT_STATUSES = ACTIVE_PARTICIPANT_STATUSES + ('waitlisted',)
PAYMENT_STATUSES = ('pending', 'partial', 'paid', 'refunded')


def _in(values):
    return ", ".join(f"'{v}'" for v in values)


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

# Columns added to the original five tables (name, declaration). The CREATE
# statements below include them, so a fresh database and a migrated one end
# up with the same columns.
ADDED_COLUMNS = {
    'trips': (
        ('trip_type', "TEXT DEFAULT 'day'"),
        ('source', "TEXT DEFAULT 'operations'"),
        ('organising_club', 'TEXT'),
        ('module_code', 'TEXT'),
        ('country', 'TEXT'),
        ('is_overseas', 'INTEGER DEFAULT 0'),
        ('fcdo_advice_level', 'TEXT'),
        ('fcdo_checked_at', 'TEXT'),
        ('fcdo_checked_by', 'TEXT'),
        ('insurance_reference', 'TEXT'),
        ('insurance_registered_at', 'TEXT'),
        ('high_risk', 'INTEGER DEFAULT 0'),
        ('involves_minors', 'INTEGER DEFAULT 0'),
        ('involves_vulnerable_adults', 'INTEGER DEFAULT 0'),
        ('min_staff_ratio', 'INTEGER DEFAULT 10'),
        ('requires_first_aider', 'INTEGER DEFAULT 1'),
        ('emergency_contact_24h', 'TEXT'),
        ('budget', 'REAL'),
        ('deposit_amount', 'REAL DEFAULT 0'),
        ('deposit_due', 'TEXT'),
        ('balance_due', 'TEXT'),
        ('refund_policy', 'TEXT'),
        ('hardship_eligible', 'INTEGER DEFAULT 1'),
        ('counts_as_attendance', 'INTEGER DEFAULT 0'),
        ('version', 'INTEGER DEFAULT 1'),
        ('updated_by', 'TEXT'),
        ('archived_at', 'TEXT'),
        ('archived_by', 'TEXT'),
        ('data_purged_at', 'TEXT'),
    ),
    'trip_participants': (
        ('payment_method', 'TEXT'),
        ('payment_reference', 'TEXT'),
        ('cancellation_date', 'TEXT'),
        ('cancellation_reason', 'TEXT'),
        ('waitlist_position', 'INTEGER'),
        ('waitlisted_at', 'TEXT'),
        ('offer_expires_at', 'TEXT'),
        ('conduct_accepted_at', 'TEXT'),
        ('parental_consent_by', 'TEXT'),
        ('parental_consent_at', 'TEXT'),
        ('health_share_consent_at', 'TEXT'),
        ('accessibility_needs', 'TEXT'),
        ('emergency_contact_name', 'TEXT'),
        ('emergency_contact_phone', 'TEXT'),
        ('emergency_contact_relationship', 'TEXT'),
        ('passport_expiry', 'TEXT'),
        ('visa_status', 'TEXT'),
        ('amount_paid', 'REAL DEFAULT 0'),
        ('amount_refunded', 'REAL DEFAULT 0'),
        ('hardship_award', 'REAL DEFAULT 0'),
        ('source', "TEXT DEFAULT 'operations'"),
    ),
    'trip_staff': (
        ('dbs_checked_at', 'TEXT'),
        ('dbs_status', 'TEXT'),
        ('first_aider', 'INTEGER DEFAULT 0'),
    ),
}


def _added(table):
    return "".join(f",\n    {name} {decl}" for name, decl in ADDED_COLUMNS[table])


TRIPS_SQL = f"""
CREATE TABLE IF NOT EXISTS trips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_name TEXT NOT NULL,
    description TEXT,
    destination TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    max_participants INTEGER DEFAULT 50,
    cost REAL DEFAULT 0.0,
    status TEXT DEFAULT 'proposed',
    created_by INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL{_added('trips')},
    FOREIGN KEY (created_by) REFERENCES users (id),
    CHECK (status IN ({_in(TRIP_STATUSES)}))
)"""

TRIP_PARTICIPANTS_SQL = f"""
CREATE TABLE IF NOT EXISTS trip_participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL,
    student_id TEXT,
    user_id INTEGER,
    registration_date TEXT NOT NULL,
    payment_status TEXT DEFAULT 'pending',
    emergency_contact TEXT,
    medical_info TEXT,
    dietary_requirements TEXT,
    status TEXT DEFAULT 'registered'{_added('trip_participants')},
    FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students (student_id),
    FOREIGN KEY (user_id) REFERENCES users (id),
    UNIQUE (trip_id, student_id),
    CHECK (payment_status IN ({_in(PAYMENT_STATUSES)})),
    CHECK (status IN ({_in(PARTICIPANT_STATUSES)}))
)"""

TRIP_STAFF_SQL = f"""
CREATE TABLE IF NOT EXISTS trip_staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL,
    staff_user_id INTEGER NOT NULL,
    role TEXT DEFAULT 'supervisor',
    assigned_date TEXT NOT NULL{_added('trip_staff')},
    FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
    FOREIGN KEY (staff_user_id) REFERENCES users (id),
    UNIQUE (trip_id, staff_user_id),
    CHECK (role IN ('supervisor', 'coordinator', 'medical', 'transport'))
)"""

TRIP_EXPENSES_SQL = """
CREATE TABLE IF NOT EXISTS trip_expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    date TEXT NOT NULL,
    recorded_by INTEGER,
    FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
    FOREIGN KEY (recorded_by) REFERENCES users (id)
)"""

TRIP_ITINERARY_SQL = """
CREATE TABLE IF NOT EXISTS trip_itinerary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL,
    day_number INTEGER NOT NULL,
    activity TEXT NOT NULL,
    location TEXT,
    start_time TEXT,
    end_time TEXT,
    notes TEXT,
    FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
    UNIQUE (trip_id, day_number, start_time)
)"""

# The tables below are new. Trips are archived, never deleted, so their
# foreign keys carry no ON DELETE action: a delete with records attached is
# refused rather than cascading through incidents and approvals.
NEW_TABLES_SQL = (
    """
CREATE TABLE IF NOT EXISTS trip_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL REFERENCES trips (id),
    version INTEGER,
    changed_by TEXT,
    changed_at TEXT,
    action TEXT,
    field TEXT,
    old_value TEXT,
    new_value TEXT
)""",
    """
CREATE TABLE IF NOT EXISTS trip_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL REFERENCES trips (id),
    stage TEXT NOT NULL CHECK (stage IN ('department', 'health_safety', 'finance', 'international')),
    decision TEXT NOT NULL DEFAULT 'pending' CHECK (decision IN ('pending', 'approved', 'rejected', 'returned')),
    decided_by TEXT,
    decided_at TEXT,
    comments TEXT,
    trip_version INTEGER,
    created_at TEXT
)""",
    """
CREATE TABLE IF NOT EXISTS trip_risk_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL REFERENCES trips (id),
    template TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'submitted', 'signed_off', 'returned')),
    assessor TEXT,
    created_at TEXT,
    submitted_at TEXT,
    signed_off_by TEXT,
    signed_off_at TEXT,
    overall_residual TEXT,
    review_notes TEXT,
    trip_version INTEGER
)""",
    """
CREATE TABLE IF NOT EXISTS trip_risk_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id INTEGER NOT NULL REFERENCES trip_risk_assessments (id),
    hazard TEXT,
    who_at_risk TEXT,
    controls TEXT,
    likelihood INTEGER CHECK (likelihood BETWEEN 1 AND 5),
    severity INTEGER CHECK (severity BETWEEN 1 AND 5),
    residual_likelihood INTEGER,
    residual_severity INTEGER,
    owner TEXT
)""",
    """
CREATE TABLE IF NOT EXISTS trip_incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL REFERENCES trips (id),
    kind TEXT NOT NULL CHECK (kind IN ('incident', 'near_miss', 'illness', 'injury', 'safeguarding', 'conduct', 'other')),
    severity TEXT NOT NULL CHECK (severity IN ('minor', 'moderate', 'serious', 'critical')),
    occurred_at TEXT,
    location TEXT,
    description TEXT,
    persons_involved TEXT,
    actions_taken TEXT,
    reported_by TEXT,
    reported_at TEXT,
    riddor_reportable INTEGER DEFAULT 0,
    hs_reference TEXT,
    conduct_case_ref TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'under_review', 'closed')),
    reviewed_by TEXT,
    reviewed_at TEXT,
    review_notes TEXT
)""",
    """
CREATE TABLE IF NOT EXISTS trip_rollcalls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL REFERENCES trips (id),
    label TEXT,
    taken_at TEXT,
    taken_by TEXT
)""",
    """
CREATE TABLE IF NOT EXISTS trip_rollcall_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rollcall_id INTEGER NOT NULL REFERENCES trip_rollcalls (id),
    participant_id INTEGER NOT NULL REFERENCES trip_participants (id),
    present INTEGER,
    note TEXT,
    UNIQUE (rollcall_id, participant_id)
)""",
    """
CREATE TABLE IF NOT EXISTS trip_instalments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL REFERENCES trips (id),
    label TEXT,
    due_date TEXT,
    amount REAL
)""",
    """
CREATE TABLE IF NOT EXISTS trip_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL REFERENCES trips (id),
    respondent TEXT,
    role TEXT,
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    went_well TEXT,
    improve TEXT,
    submitted_at TEXT,
    UNIQUE (trip_id, respondent)
)""",
    """
CREATE TABLE IF NOT EXISTS trip_reconciliations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL UNIQUE REFERENCES trips (id),
    budget REAL,
    actual REAL,
    income REAL,
    notes TEXT,
    signed_off_by TEXT,
    signed_off_at TEXT
)""",
)

NEW_TABLES = ('trip_history', 'trip_approvals', 'trip_risk_assessments', 'trip_risk_items',
              'trip_incidents', 'trip_rollcalls', 'trip_rollcall_entries', 'trip_instalments',
              'trip_evaluations', 'trip_reconciliations')

INDEXES_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_trip_participants_trip_status ON trip_participants (trip_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_trip_participants_user ON trip_participants (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_trips_source ON trips (source, organising_club)",
    "CREATE INDEX IF NOT EXISTS idx_trip_history_trip ON trip_history (trip_id, version)",
    "CREATE INDEX IF NOT EXISTS idx_trip_approvals_trip ON trip_approvals (trip_id, stage)",
    "CREATE INDEX IF NOT EXISTS idx_trip_risk_assessments_trip ON trip_risk_assessments (trip_id)",
    "CREATE INDEX IF NOT EXISTS idx_trip_risk_items_assessment ON trip_risk_items (assessment_id)",
    "CREATE INDEX IF NOT EXISTS idx_trip_incidents_trip ON trip_incidents (trip_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_trip_rollcalls_trip ON trip_rollcalls (trip_id)",
    "CREATE INDEX IF NOT EXISTS idx_trip_instalments_trip ON trip_instalments (trip_id)",
)

CORE_TABLES_SQL = (TRIPS_SQL, TRIP_PARTICIPANTS_SQL, TRIP_STAFF_SQL,
                   TRIP_EXPENSES_SQL, TRIP_ITINERARY_SQL)


def _columns(execute, table):
    return {row[1] for row in execute(f'PRAGMA table_info("{table}")').fetchall()}


def add_missing_columns(execute, table):
    """Add the ``ADDED_COLUMNS`` an existing ``table`` lacks. Returns names added."""
    existing = _columns(execute, table)
    if not existing:
        return []
    added = []
    for name, decl in ADDED_COLUMNS.get(table, ()):
        if name not in existing:
            # db-audit: ignore[DBW001] - literal collection
            execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {decl}')
            added.append(name)
    return added


def apply(execute):
    """Create every trip table in its current shape; add missing columns.

    ``execute`` is ``conn.execute`` (sqlite3) or alembic's
    ``bind.exec_driver_sql`` — anything that runs one statement and returns
    a cursor. Idempotent.
    """
    for ddl in CORE_TABLES_SQL:
        execute(ddl)
    for table in ADDED_COLUMNS:
        for name in add_missing_columns(execute, table):
            logger.info("Added %s.%s", table, name)
    for ddl in NEW_TABLES_SQL:
        execute(ddl)
    for ddl in INDEXES_SQL:
        execute(ddl)
    return True


def create_trip_tables(conn):
    """Run :func:`apply` on ``conn`` (the caller commits)."""
    return apply(conn.execute)


def ensure_participant_payment_columns(conn):
    """Add the columns an existing ``trip_participants`` lacks (kept for callers)."""
    try:
        add_missing_columns(conn.execute, 'trip_participants')
    except sqlite3.Error as e:
        logging.warning("Could not add trip_participants columns: %s", e)


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------

def get_db_connection(timeout=30.0, max_retries=3):
    """Get a database connection with proper timeout and retry logic.

    Uses the centralized get_connection() (row factory on, one connection per
    thread). See :func:`_target_path` for which file it opens.
    """
    from education_system.systems.university.infrastructure.database import db

    # ``trip_management.get_connection`` is a long-standing patch point too.
    get_connection = getattr(sys.modules.get(_PACKAGE), 'get_connection', None) or db.get_connection
    retry_delay = 0.1

    for attempt in range(max_retries):
        try:
            conn = get_connection(db_path=_target_path(), timeout=timeout)
            return conn
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                logging.warning(get_text("mobility.trip_management.database.locked_retrying", "Database locked, retrying... (attempt {attempt})").format(attempt=attempt + 1))
                time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                continue
            logging.error(get_text("mobility.trip_management.database.connection_error_attempts", "Database connection error after {attempts} attempts: {error}").format(attempts=attempt + 1, error=e))
            return None
        except sqlite3.Error as e:
            logging.error(get_text("mobility.trip_management.database.connection_error", "Database connection error: {error}").format(error=e))
            return None
    return None


def _target_path():
    """The database file to open, or ``None`` for the shared university default.

    While ``_common.DEFAULT_DB_PATH`` is the university default, ``None`` is
    passed so ``db.get_connection`` resolves it — that honours the tenant
    database and the test suite's redirect of ``db.DEFAULT_DB_PATH``
    (passing the path explicitly bypassed both). A deliberately different
    ``_common.DEFAULT_DB_PATH`` is used as given.
    """
    import os
    from education_system import paths
    configured = _common.DEFAULT_DB_PATH
    if os.fspath(configured) == os.fspath(paths.UNIVERSITY_DEFAULT_DB_PATH):
        return None
    return configured


def _connect(timeout=30.0):
    """Open a connection through the package's ``get_db_connection``.

    ``trip_management.get_db_connection`` is the long-standing patch point
    (tests replace it there); resolving it at call time keeps that working
    now that the package re-exports this module's implementation.
    """
    package = sys.modules.get(_PACKAGE)
    factory = getattr(package, 'get_db_connection', None) or get_db_connection
    return factory(timeout=timeout)


def safe_db_operation(operation_func, *args, max_retries=3, **kwargs):
    """Run ``operation_func(conn, *args, **kwargs)`` and commit.

    Rolls back and returns ``False`` on any failure — including a failed
    commit — so a half-done write is never kept. Retries only when the
    database is locked. The operation always receives the connection.
    """
    retry_delay = 0.1
    last_error = None
    name = getattr(operation_func, '__name__', operation_func)

    for attempt in range(max_retries):
        conn = None
        try:
            conn = _connect(timeout=30.0)
            if not conn:
                last_error = get_text("mobility.trip_management.database.failed_establish", "Failed to establish database connection")
                if attempt < max_retries - 1:
                    logging.warning(get_text("mobility.trip_management.database.connection_failed_retrying", "Database connection failed, retrying... (attempt {attempt})").format(attempt=attempt + 1))
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                logging.error(get_text("mobility.trip_management.database.connection_failed_attempts", "Database connection failed after {max_retries} attempts").format(max_retries=max_retries))
                return False

            result = operation_func(conn, *args, **kwargs)
            conn.commit()
            return result

        except sqlite3.OperationalError as e:
            last_error = e
            _rollback(conn)
            if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)
                logging.warning(get_text("mobility.trip_management.database.locked_retrying_wait", "Database locked, retrying in {wait_time}s... (attempt {attempt})").format(wait_time=f"{wait_time:.2f}", attempt=attempt + 1))
                time.sleep(wait_time)
                continue
            logging.error(get_text("mobility.trip_management.database.operational_error", "Database operational error: {error}").format(error=e))
            return False

        except Exception as e:
            last_error = e
            _rollback(conn)
            # Log it: swallowing this silently is what hid a rolled-back
            # trip insert behind a "created successfully" message.
            logger.error("trip_management: %s failed, rolled back: %s: %s",
                         name, type(e).__name__, e)
            logging.debug(f"Unexpected error traceback: {traceback.format_exc()}")
            return False

        finally:
            _close(conn)

    logging.error(get_text("mobility.trip_management.database.operation_failed_attempts", "Operation failed after {max_retries} attempts. Last error: {error_type}: {error}").format(max_retries=max_retries, error_type=type(last_error).__name__, error=last_error))
    return False


def _rollback(conn):
    if conn is None:
        return
    try:
        conn.rollback()
    except Exception as rollback_error:
        logging.warning(get_text("mobility.trip_management.database.rollback_failed_unexpected", "Failed to rollback transaction after unexpected error: {error}").format(error=rollback_error))


def _close(conn):
    if conn is None:
        return
    try:
        conn.close()
    except Exception as close_error:
        logging.warning(f"Error closing trip database connection: {type(close_error).__name__}: {close_error}")


@contextmanager
def write_transaction(conn=None):
    """A short write transaction: ``BEGIN IMMEDIATE``, commit or roll back, close.

    With ``conn`` given the caller's connection is used as is and the caller
    owns the commit. The write lock is taken up front, so a check made inside
    the block (capacity, duplicates) cannot be raced by another writer.
    """
    if conn is not None:
        yield conn
        return
    own = _connect()
    if own is None:
        raise sqlite3.OperationalError("could not open the trip database")
    try:
        own.execute("BEGIN IMMEDIATE")
        yield own
        own.commit()
    except BaseException:
        _rollback(own)
        raise
    finally:
        _close(own)


@contextmanager
def read_connection(conn=None):
    """A connection for reads, closed afterwards (``conn`` is passed through)."""
    if conn is not None:
        yield conn
        return
    own = _connect()
    if own is None:
        raise sqlite3.OperationalError("could not open the trip database")
    try:
        yield own
    finally:
        _close(own)


def run_after_commit(pending):
    """Run the deferred notifications collected during a transaction.

    Domain functions append zero-argument callables (bus events, calendar
    notifications, e-mails) to ``pending`` while they write, and call this
    once the transaction has committed. A failing callable is logged, never
    raised: the write has already happened.
    """
    for action in list(pending or ()):
        try:
            action()
        except Exception:
            logger.warning("trip_management: post-commit action failed", exc_info=True)
    if pending is not None:
        del pending[:]


def init_trip_db():
    """Initialize trip management database tables"""
    def create_tables(conn):
        try:
            apply(conn.execute)
            logging.info(get_text("mobility.trip_management.database.tables_created", "Trip management tables created successfully"))
            return True
        except sqlite3.Error as e:
            logging.error(get_text("mobility.trip_management.database.error_creating_tables", "Error creating trip tables: {error}").format(error=e))
            raise

    return safe_db_operation(create_tables)
