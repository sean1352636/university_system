"""
SQL Safety Utilities - Centralized validation for dynamic SQL identifiers.

This module provides validation functions to prevent SQL injection attacks
when table names, column names, or field names must be dynamically included
in SQL queries.

This module is in the core package and has no dependencies on infrastructure
or modules, preventing circular imports.

Usage:
    from education_system.university_system.core.sql_safety import (
        validate_table_name,
        validate_column_name,
        validate_identifier,
        safe_alter_table_add_column,
        SQLIdentifierError,
    )

    # Validate table name before using in query
    safe_table = validate_table_name(user_input)
    cursor.execute(f"SELECT * FROM [{safe_table}]")
"""

import re
import sqlite3
import logging
from typing import Set, Optional, FrozenSet
from functools import lru_cache

logger = logging.getLogger(__name__)


def escape_like(search: str) -> str:
    """Escape special LIKE wildcard characters in a search term."""
    return search.replace("%", "\\%").replace("_", "\\_")


class SQLIdentifierError(ValueError):
    """Raised when an invalid SQL identifier is detected."""
    pass

# Known system tables in the university_system database
# NOTE: The database contains 1000+ tables. This is a core subset used for validation
# when no database connection is available. ALWAYS prefer passing conn parameter
# to validate_table_name() for database verification against actual schema.
KNOWN_TABLES: FrozenSet[str] = frozenset({
    # Core tables
    'students',
    'users',
    'user_accounts',
    'modules',
    'student_modules',
    'courses',
    'course_prerequisites',
    'course_schedule',
    'enrollments',
    'grades',
    'staff',

    # Authentication tables
    'sessions',
    'login_attempts',
    'mfa_tokens',
    'password_reset_tokens',
    'user_permissions',
    'roles',
    'role_permissions',
    'permissions',

    # Academic tables
    'assignments',
    'submissions',
    'attendance',
    'attendance_records',
    'attendance_sessions',
    'schedules',
    'module_grades',
    'assignment_submissions',
    'instructor_modules',
    'timetables',
    'student_timetables',
    'instructor_schedules',
    'student_grades',
    'student_attendance',
    'academic_calendar',
    'academic_calendar_events',
    'course_sections',
    'instructors',
    'departments',
    'assessments',
    'exams',
    'degree_programs',
    'academic_misconduct_cases',
    'plagiarism_results',
    'forensic_cases',
    'lms_courses',
    'lms_quizzes',
    'lms_gradebook',

    # Finance tables
    'transactions',
    'invoices',
    'payments',
    'scholarships',
    'scholarship_applications',
    'financial_aid',
    'financial_aid_applications',
    'aid_packages',
    'budgets',
    'fees',
    'meal_accounts',

    # Communication tables
    'messages',
    'chat_rooms',
    'chat_room_members',
    'chat_messages',
    'notifications',
    'notification_preferences',
    'email_queue',
    'email_metrics',
    'scheduled_emails',
    'emails',
    'email_templates',
    'newsletters',
    'group_messages',
    'announcements',

    # Student affairs tables
    'clubs',
    'student_clubs',
    'club_members',
    'unified_events',
    'unified_event_registrations',
    'mentorship',
    'mentorship_relationships',
    'alumni',
    'helpdesk_tickets',
    'support_tickets',
    'kb_articles',
    'faqs',
    'study_groups',
    'polls',
    'election_candidates',
    'union_representatives',
    'lost_found',
    'advising_appointments',
    'tutoring_offers',

    # Health tables
    'health_records',
    'health_appointments',
    'appointments',
    'prescriptions',
    'immunizations',
    'mental_health_appointments',
    'mental_health_resources',
    'counseling_appointments',
    'crisis_resources',

    # Housing tables
    'accommodations',
    'accommodation_requests',
    'room_assignments',
    'maintenance_requests',
    'housing_rooms',
    'housing_applications',

    # Campus tables
    'buildings',
    'rooms',
    'room_bookings',
    'campus_tours',
    'campus_events',
    'resource_bookings',
    'space_utilization',
    'parking_permits',
    'parking_spaces',
    'police_cases',
    'police_officers',
    'police_complaints',
    'police_criminals',
    'police_evidence',

    # Facility tables
    'facility_bookings',
    'facility_assets',
    'equipment',
    'equipment_checkouts',
    'equipment_rentals',
    'equipment_maintenance',

    # Career and research tables
    'job_postings',
    'research_projects',

    # Admission tables
    'admission_prospects',
    'admission_applications',

    # Document tables
    'document_repository',
    'student_documents',
    'document_workflow',
    'documents',

    # Portfolio tables
    'badges',
    'public_profiles',
    'resumes',

    # Credential tables
    'blockchain_credentials',
    'digital_badges',
    'micro_credentials',
    'certifications',

    # Early warning tables
    'early_warning_profiles',
    'early_warning_interventions',

    # Emergency tables
    'emergency_alerts',
    'incidents',

    # Virtual classroom tables
    'virtual_classrooms',
    'virtual_sessions',
    'virtual_study_rooms',

    # Evaluation tables
    'feedback_submissions',
    'evaluation_templates',
    'survey_responses',
    'course_evaluations',

    # Parent tables
    'parent_accounts',
    'parent_messages',
    'parent_conferences',
    'parent_documents',

    # HR tables - base
    'leave_types',
    'leave_requests',
    'leave_balances',
    'time_entries',
    'shifts',
    'timesheets',
    'training_courses',
    'training_enrollments',
    'appraisal_cycles',
    'appraisal_records',
    'appraisal_goals',
    'onboarding_templates',
    'onboarding_template_tasks',
    'onboarding_assignments',
    'onboarding_task_progress',

    # HR tables - v2 (staff profiles & academic)
    'staff_profiles',
    'staff_documents',
    'staff_workload',
    'staff_schedules',
    'teaching_portfolios',
    'research_profiles',
    'student_supervisions',
    'external_examiners',
    'examiner_assignments',
    'peer_observations',
    'document_approvals',
    'document_approval_history',
    'interdepartmental_requests',
    'access_cards',
    'key_assignments',
    'visitor_registrations',
    'staff_announcements',
    'announcement_reads',
    'committees',
    'committee_members',
    'meeting_minutes',
    'staff_noticeboard',
    'staff_recruitment_postings',
    'staff_recruitment_applications',
    'interview_schedules',
    'department_kpis',
    'budget_requests',

    # HR tables - v3 (assets)
    'asset_categories',
    'assets',
    'asset_assignments',
    'asset_issues',
    'asset_maintenance',
    'asset_audit_log',
    'asset_requests',
    'asset_transfers',
    'asset_depreciation',

    # HR tables - v4 (contracts, expenses, grievances, exit)
    'staff_contracts',
    'contract_amendments',
    'probation_reviews',
    'contract_renewal_alerts',
    'expense_categories',
    'expense_claims',
    'expense_approvals',
    'reimbursements',
    'expense_policies',
    'grievance_categories',
    'grievances',
    'grievance_actions',
    'grievance_meetings',
    'disciplinary_records',
    'disciplinary_actions',
    'disciplinary_appeals',
    'exit_interviews',
    'exit_checklist_templates',
    'exit_checklist_template_items',
    'exit_checklist',
    'knowledge_transfer',
    'turnover_analytics',
    'exit_reasons_summary',

    # Security tables
    'security_desk_tickets',

    # Commerce tables
    'orders',
    'products',
    'inventory',
    'dining_plans',
    'menu_items',

    # Logging tables
    'logs',
    'activity_logs',
    'audit_trail',
    'error_logs',
    'search_analytics',

    # Backup/System tables
    'backup_metadata',
    'schema_migrations',
    'system_config',
    'scheduled_reports',

    # AI/Analytics tables
    'ai_detector_submissions',
    'search_history',
    'analytics_data',

    # Encryption tables
    'encryption_keys',
    'encrypted_fields_metadata',

    # Library tables
    'books',
    'book_loans',

    # Charity shop tables
    'charity_shop_stock',
    'charity_shop_customers',
    'charity_shop_donations',
    'charity_shop_donors',
    'charity_shop_staff',
    'charity_shop_gift_cards',
    'charity_shop_price_history',
    'charity_shop_sales',
    'charity_shop_bundles',
    'charity_shop_promotions',
    'charity_shop_layaway',
    'charity_shop_loyalty',
    'charity_shop_archived',
    'charity_shop_locations',
    'charity_shop_shifts',
    'charity_shop_tasks',
    'charity_shop_wishlists',
    'charity_shop_feedback',
    'charity_shop_referrals',

    # Scheduling and portfolio tables
    'module_schedule',
    'discovery_events',
    'campus_events',
    'project_milestones',
    'portfolios',
    'portfolio_items',
    'student_skills',
    'mobile_preferences',
    'rubrics',
    'assignment_templates',

    # Audit and preferences tables
    'audit_log',
    'user_preferences',

    # Shop tables
    'shop_products',

    # Email tables
    'email_log',
    'email_log_html',
    'email_attachments',
    'email_deliveries',

    # Realtime tables
    'realtime_subscriptions',
    'realtime_channels',
    'realtime_notifications',

    # Campus and accommodation tables
    # campus_event_registrations merged into unified_event_registrations
    'medical_accommodations',
    'accommodation_notes',
    'disability_records',
    'accommodation_templates',

    # Cinema GUI tables
    'movies',
    'screenings',
    'seats',
    'bookings',
    'booked_seats',
    'promo_codes',
    'members',
    'reviews',
    'waitlist',
    'gift_cards',
    'favorites',
    'movie_series',
    'movie_series_link',
    'coming_soon',
    'season_passes',
    'seat_holds',
    'cinema_referrals',
})

# Known columns for common tables (subset - add more as needed)
KNOWN_COLUMNS: FrozenSet[str] = frozenset({
    # Common columns
    'id', 'created_at', 'updated_at', 'status',

    # Student columns
    'student_id', 'first_name', 'last_name', 'email', 'gender',
    'date_of_birth', 'dob', 'age', 'course', 'registration_datetime',
    'enrollment_date', 'phone', 'address',

    # User columns
    'user_id', 'username', 'password_hash', 'salt', 'role',
    'is_active', 'last_login', 'mfa_enabled',

    # Message columns
    'sender_id', 'recipient_id', 'subject', 'body', 'message',
    'content', 'sent_at', 'read_at', 'is_read', 'is_archived',
    'is_deleted_by_sender', 'is_deleted_by_recipient', 'attachment_path',
    'assignment_id',

    # Chat columns
    'room_id', 'max_members', 'description', 'joined_at', 'is_admin',

    # Generic columns
    'name', 'title', 'description', 'type', 'value', 'timestamp',
})

# Valid SQL identifier pattern (alphanumeric and underscores only)
_IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

def is_valid_identifier_format(identifier: str) -> bool:
    """
    Check if a string matches valid SQL identifier format.

    Valid identifiers:
    - Start with a letter or underscore
    - Contain only letters, numbers, and underscores
    - Are not empty
    - Are reasonably sized (max 128 chars)

    Args:
        identifier: The string to validate

    Returns:
        True if format is valid, False otherwise
    """
    if not identifier or not isinstance(identifier, str):
        return False
    if len(identifier) > 128:
        return False
    return bool(_IDENTIFIER_PATTERN.match(identifier))

def validate_table_name(
    table_name: str,
    allowed_tables: Optional[Set[str]] = None,
    conn: Optional[sqlite3.Connection] = None
) -> str:
    """
    Validate a table name for safe use in SQL queries.

    This function performs multiple validation checks:
    1. Format validation (valid SQL identifier characters)
    2. Whitelist validation (against known tables or provided set)
    3. Optional database verification (table actually exists)

    Args:
        table_name: The table name to validate
        allowed_tables: Optional set of allowed table names. If None,
                       uses KNOWN_TABLES constant.
        conn: Optional database connection to verify table exists

    Returns:
        The validated table name (unchanged if valid)

    Raises:
        SQLIdentifierError: If validation fails

    Example:
        >>> safe_table = validate_table_name('students')
        >>> cursor.execute(f"SELECT * FROM {safe_table}")
    """
    if not is_valid_identifier_format(table_name):
        logger.warning(f"Invalid table name format rejected: {table_name!r}")
        raise SQLIdentifierError(
            f"Invalid table name format: {table_name!r}. "
            "Table names must start with a letter or underscore and "
            "contain only alphanumeric characters and underscores."
        )

    # Normalize to lowercase for comparison
    table_lower = table_name.lower()

    # Check against whitelist
    whitelist = allowed_tables if allowed_tables is not None else KNOWN_TABLES
    whitelist_lower = {t.lower() for t in whitelist}

    if table_lower not in whitelist_lower:
        # If connection provided, verify against actual database
        if conn is not None:
            try:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,)
                )
                if cursor.fetchone() is None:
                    logger.warning(f"Table name not in database: {table_name!r}")
                    raise SQLIdentifierError(
                        f"Table '{table_name}' does not exist in the database."
                    )
                # Table exists in database, allow it
                return table_name
            except sqlite3.Error as e:
                logger.error(f"Database error validating table name: {e}")
                raise SQLIdentifierError(f"Could not validate table name: {e}")

        logger.warning(f"Table name not in whitelist: {table_name!r}")
        raise SQLIdentifierError(
            f"Table '{table_name}' is not in the allowed tables list. "
            "If this is a valid table, add it to KNOWN_TABLES in sql_safety.py"
        )

    return table_name

def validate_column_name(
    column_name: str,
    allowed_columns: Optional[Set[str]] = None,
    table_name: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> str:
    """
    Validate a column name for safe use in SQL queries.

    Args:
        column_name: The column name to validate
        allowed_columns: Optional set of allowed column names
        table_name: Optional table name to validate column against
        conn: Optional database connection for schema verification

    Returns:
        The validated column name

    Raises:
        SQLIdentifierError: If validation fails
    """
    if not is_valid_identifier_format(column_name):
        logger.warning(f"Invalid column name format rejected: {column_name!r}")
        raise SQLIdentifierError(
            f"Invalid column name format: {column_name!r}. "
            "Column names must start with a letter or underscore and "
            "contain only alphanumeric characters and underscores."
        )

    # Normalize to lowercase for comparison
    column_lower = column_name.lower()

    # If table and connection provided, validate against actual schema
    if table_name is not None and conn is not None:
        try:
            # First validate the table name
            validate_table_name(table_name, conn=conn)

            # Get actual columns from table
            cursor = conn.execute(f"PRAGMA table_info([{table_name}])")  # nosec B608 - table_name validated above
            actual_columns = {row[1].lower() for row in cursor.fetchall()}

            if column_lower not in actual_columns:
                raise SQLIdentifierError(
                    f"Column '{column_name}' does not exist in table '{table_name}'."
                )
            return column_name
        except sqlite3.Error as e:
            logger.error(f"Database error validating column name: {e}")
            raise SQLIdentifierError(f"Could not validate column name: {e}")

    # Check against whitelist
    if allowed_columns is not None:
        allowed_lower = {c.lower() for c in allowed_columns}
        if column_lower not in allowed_lower:
            raise SQLIdentifierError(
                f"Column '{column_name}' is not in the allowed columns list."
            )
    elif column_lower not in {c.lower() for c in KNOWN_COLUMNS}:
        # Log warning but allow - column might be valid but not in our list
        logger.debug(f"Column '{column_name}' not in KNOWN_COLUMNS, allowing anyway")

    return column_name

def validate_identifier(identifier: str, identifier_type: str = "identifier") -> str:
    """
    Generic validation for any SQL identifier (table, column, index, etc.).

    This performs only format validation, not whitelist checking.
    Use validate_table_name or validate_column_name for stricter validation.

    Args:
        identifier: The identifier to validate
        identifier_type: Type description for error messages

    Returns:
        The validated identifier

    Raises:
        SQLIdentifierError: If format validation fails
    """
    if not is_valid_identifier_format(identifier):
        raise SQLIdentifierError(
            f"Invalid {identifier_type} format: {identifier!r}. "
            f"{identifier_type.capitalize()}s must start with a letter or underscore "
            "and contain only alphanumeric characters and underscores."
        )
    return identifier

def get_valid_tables(conn: Optional[sqlite3.Connection] = None) -> Set[str]:
    """
    Get the set of valid table names.

    If a connection is provided, returns actual tables from the database.
    Otherwise, returns the KNOWN_TABLES constant.

    Args:
        conn: Optional database connection

    Returns:
        Set of valid table names
    """
    if conn is not None:
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            return {row[0] for row in cursor.fetchall()}
        except sqlite3.Error as e:
            logger.error(f"Error getting tables from database: {e}")
            return set(KNOWN_TABLES)
    return set(KNOWN_TABLES)

def get_valid_columns(
    table_name: str,
    conn: sqlite3.Connection
) -> Set[str]:
    """
    Get valid column names for a specific table from the database.

    Args:
        table_name: The table to get columns for
        conn: Database connection

    Returns:
        Set of column names for the table

    Raises:
        SQLIdentifierError: If table name is invalid
    """
    # Validate table name first
    validate_table_name(table_name, conn=conn)

    try:
        cursor = conn.execute(f"PRAGMA table_info([{table_name}])")  # nosec B608 - table_name validated by validate_table_name above
        return {row[1] for row in cursor.fetchall()}
    except sqlite3.Error as e:
        logger.error(f"Error getting columns for table {table_name}: {e}")
        raise SQLIdentifierError(f"Could not get columns for table: {e}")

def safe_table_query(table_name: str, conn: Optional[sqlite3.Connection] = None) -> str:
    """
    Create a safe table reference for use in SQL queries.

    Validates the table name and returns it wrapped in square brackets
    for additional safety.

    Args:
        table_name: The table name to validate and format
        conn: Optional database connection for verification

    Returns:
        Safe table reference string (e.g., "[students]")

    Raises:
        SQLIdentifierError: If validation fails
    """
    validated = validate_table_name(table_name, conn=conn)
    return f"[{validated}]"

def validate_field_for_query(
    field_name: str,
    allowed_fields: Set[str],
    field_type: str = "field"
) -> str:
    """
    Validate a field name against a specific whitelist for query use.

    This is useful when you have a specific set of fields that are valid
    for a particular query context.

    Args:
        field_name: The field name to validate
        allowed_fields: Set of allowed field names for this context
        field_type: Type description for error messages

    Returns:
        The validated field name

    Raises:
        SQLIdentifierError: If validation fails
    """
    if not is_valid_identifier_format(field_name):
        raise SQLIdentifierError(
            f"Invalid {field_type} format: {field_name!r}"
        )

    # Case-insensitive comparison
    allowed_lower = {f.lower() for f in allowed_fields}
    if field_name.lower() not in allowed_lower:
        raise SQLIdentifierError(
            f"Invalid {field_type}: '{field_name}'. "
            f"Allowed values: {', '.join(sorted(allowed_fields))}"
        )

    return field_name

# Valid SQLite column types for ALTER TABLE validation
VALID_SQLITE_TYPES: FrozenSet[str] = frozenset({
    'TEXT', 'INTEGER', 'REAL', 'BLOB', 'NUMERIC',
    'INT', 'TINYINT', 'SMALLINT', 'MEDIUMINT', 'BIGINT',
    'UNSIGNED', 'BIG', 'INT2', 'INT8',
    'CHARACTER', 'VARCHAR', 'VARYING', 'NCHAR', 'NATIVE',
    'NVARCHAR', 'CLOB',
    'DOUBLE', 'PRECISION', 'FLOAT',
    'BOOLEAN', 'DATE', 'DATETIME',
})

class ColumnDefinition:
    """Represents a validated column definition for ALTER TABLE operations."""

    def __init__(self, name: str, type_def: str):
        self.name = name
        self.type_def = type_def

    def __repr__(self) -> str:
        return f"ColumnDefinition(name={self.name!r}, type_def={self.type_def!r})"

def validate_column_definition(
    column_name: str,
    column_type: str,
    table_name: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> ColumnDefinition:
    """
    Validate a column name and type definition for use in ALTER TABLE statements.

    Args:
        column_name: The column name to add
        column_type: The column type definition (e.g., "TEXT", "INTEGER DEFAULT 0")
        table_name: Optional table name to check for existing columns
        conn: Optional database connection for schema verification

    Returns:
        ColumnDefinition object with validated name and type

    Raises:
        SQLIdentifierError: If validation fails
    """
    # Validate column name format
    if not is_valid_identifier_format(column_name):
        raise SQLIdentifierError(
            f"Invalid column name format: {column_name!r}. "
            "Column names must start with a letter or underscore and "
            "contain only alphanumeric characters and underscores."
        )

    # Validate column type starts with a valid SQLite type
    if not column_type or not isinstance(column_type, str):
        raise SQLIdentifierError(
            f"Invalid column type: {column_type!r}. Type definition is required."
        )

    # Extract base type (first word, uppercase)
    type_parts = column_type.strip().split()
    if not type_parts:
        raise SQLIdentifierError(
            f"Invalid column type: {column_type!r}. Type definition is empty."
        )

    base_type = type_parts[0].upper()

    if base_type not in VALID_SQLITE_TYPES:
        raise SQLIdentifierError(
            f"Invalid column type: '{base_type}'. "
            f"Must be one of: {', '.join(sorted(VALID_SQLITE_TYPES))}"
        )

    # If table and connection provided, check if column already exists
    if table_name is not None and conn is not None:
        try:
            # Validate table name first
            validate_table_name(table_name, conn=conn)

            # Check existing columns
            cursor = conn.execute(f"PRAGMA table_info([{table_name}])")  # nosec B608 - table_name validated above
            existing_columns = {row[1].lower() for row in cursor.fetchall()}

            if column_name.lower() in existing_columns:
                raise SQLIdentifierError(
                    f"Column '{column_name}' already exists in table '{table_name}'."
                )
        except sqlite3.Error as e:
            logger.error(f"Database error validating column definition: {e}")
            raise SQLIdentifierError(f"Could not validate column definition: {e}")

    return ColumnDefinition(name=column_name, type_def=column_type)

def safe_alter_table_add_column(
    table_name: str,
    column_name: str,
    column_type: str,
    conn: sqlite3.Connection,
    if_not_exists: bool = True
) -> bool:
    """
    Safely add a column to a table with full validation.

    Args:
        table_name: The table to add the column to
        column_name: The name of the new column
        column_type: The type definition for the new column
        conn: Database connection
        if_not_exists: If True, silently skip if column exists (default True)

    Returns:
        True if column was added, False if it already existed (when if_not_exists=True)

    Raises:
        SQLIdentifierError: If validation fails
        sqlite3.Error: If database operation fails
    """
    # Validate table name
    validated_table = validate_table_name(table_name, conn=conn)

    # Check if column already exists
    cursor = conn.execute(f"PRAGMA table_info([{validated_table}])")  # nosec B608 - validated by validate_table_name
    existing_columns = {row[1].lower() for row in cursor.fetchall()}

    if column_name.lower() in existing_columns:
        if if_not_exists:
            logger.debug(f"Column '{column_name}' already exists in '{table_name}', skipping")
            return False
        raise SQLIdentifierError(
            f"Column '{column_name}' already exists in table '{table_name}'."
        )

    # Validate column definition
    col_def = validate_column_definition(column_name, column_type)

    # Execute the ALTER TABLE statement
    sql = f"ALTER TABLE [{validated_table}] ADD COLUMN [{col_def.name}] {col_def.type_def}"  # nosec B608 - all identifiers validated
    logger.info(f"Adding column: {sql}")
    conn.execute(sql)

    return True

def get_table_schema(
    table_name: str,
    conn: sqlite3.Connection
) -> dict:
    """
    Get the complete schema for a table.

    Args:
        table_name: The table to get schema for
        conn: Database connection

    Returns:
        Dictionary with table schema information

    Raises:
        SQLIdentifierError: If table name is invalid
    """
    # Validate table name
    validated_table = validate_table_name(table_name, conn=conn)

    try:
        cursor = conn.execute(f"PRAGMA table_info([{validated_table}])")  # nosec B608 - validated by validate_table_name
        columns = []
        column_names = set()

        for row in cursor.fetchall():
            col_info = {
                'cid': row[0],
                'name': row[1],
                'type': row[2],
                'notnull': bool(row[3]),
                'default': row[4],
                'pk': bool(row[5])
            }
            columns.append(col_info)
            column_names.add(row[1].lower())

        return {
            'name': validated_table,
            'columns': columns,
            'column_names': column_names
        }
    except sqlite3.Error as e:
        logger.error(f"Error getting schema for table {table_name}: {e}")
        raise SQLIdentifierError(f"Could not get table schema: {e}")


def build_where_clause(conditions: list) -> str:
    """
    Build a safe WHERE clause from a list of condition strings.

    Each condition should use ? placeholders for values (e.g., "student_id = ?").
    Returns an empty string if no conditions are provided.

    Args:
        conditions: List of SQL condition strings using ? placeholders

    Returns:
        WHERE clause string (e.g., " WHERE student_id = ? AND status = ?")
        or empty string if no conditions

    Example:
        >>> conditions = ["student_id = ?", "status = ?"]
        >>> build_where_clause(conditions)
        ' WHERE student_id = ? AND status = ?'
    """
    if not conditions:
        return ""
    return " WHERE " + " AND ".join(conditions)


def build_update_set(data: dict, allowed_fields: list) -> tuple:
    """
    Build a safe SET clause for UPDATE statements from a data dict.

    Only fields present in both ``data`` and ``allowed_fields`` are included.
    Field names are validated as safe SQL identifiers.

    Args:
        data: Dictionary of field names to values
        allowed_fields: List of permitted field names

    Returns:
        Tuple of (set_clause_string, values_list).
        set_clause_string is e.g. "status = ?, name = ?"
        values_list is the corresponding parameter values

    Raises:
        SQLIdentifierError: If a field name has invalid format

    Example:
        >>> data = {"status": "active", "name": "Test"}
        >>> set_str, vals = build_update_set(data, ["status", "name", "email"])
        >>> set_str
        'status = ?, name = ?'
        >>> vals
        ['active', 'Test']
    """
    clauses = []
    values = []
    for field in allowed_fields:
        if field in data:
            validate_identifier(field, "column")
            clauses.append(field + " = ?")
            values.append(data[field])
    return ", ".join(clauses), values


__all__ = [
    "escape_like",
    "SQLIdentifierError",
    "KNOWN_TABLES",
    "KNOWN_COLUMNS",
    "VALID_SQLITE_TYPES",
    "ColumnDefinition",
    "is_valid_identifier_format",
    "validate_table_name",
    "validate_column_name",
    "validate_identifier",
    "get_valid_tables",
    "get_valid_columns",
    "safe_table_query",
    "validate_field_for_query",
    "validate_column_definition",
    "safe_alter_table_add_column",
    "get_table_schema",
    "build_where_clause",
    "build_update_set",
]
