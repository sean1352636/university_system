from __future__ import annotations
from datetime import datetime
from education_system.university_system.infrastructure.database.db import get_connection, sqlite3
from education_system.university_system.core.i18n import get_text as _t, init_i18n
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608

# Initialize i18n
init_i18n()

# Import all schema functions needed by initialize_all_schemas
from education_system.university_system.infrastructure.database.schemas.core_schemas import init_grade_system_db, init_academics_tables, init_courses_tables
from education_system.university_system.infrastructure.database.schemas.finance_schemas import init_finance_system_db, init_finance_tables
from education_system.university_system.infrastructure.database.schemas.student_union_schemas import init_student_union_db, init_student_affairs_tables, init_social_tables
from education_system.university_system.infrastructure.database.schemas.communication_schemas import init_email_system_db, init_communication_tables
from education_system.university_system.infrastructure.database.schemas.health_wellness_schemas import (
    init_health_system_db, init_mental_health_system_db,
    init_health_tables, init_wellness_tables
)
from education_system.university_system.infrastructure.database.schemas.lms_schemas import init_lms_system_db
from education_system.university_system.infrastructure.database.schemas.attendance_warning_schemas import (
    init_attendance_system_db, init_early_warning_system_db,
    init_peer_support_tables
)
from education_system.university_system.infrastructure.database.schemas.degree_audit_schemas import init_degree_audit_system_db
from education_system.university_system.infrastructure.database.schemas.career_alumni_schemas import (
    init_career_services_system_db, init_alumni_relations_system_db,
    init_career_tables, init_alumni_tables
)
from education_system.university_system.infrastructure.database.schemas.admissions_schemas import init_admissions_crm_system_db
from education_system.university_system.infrastructure.database.schemas.analytics_bi_schemas import (
    init_analytics_dashboard_system_db, init_business_intelligence_system_db,
    init_analytics_tables
)
from education_system.university_system.infrastructure.database.schemas.campus_events_schemas import init_campus_events_system_db, init_smart_timetable_system_db
from education_system.university_system.infrastructure.database.schemas.facilities_housing_schemas import (
    init_facilities_management_system_db, init_housing_tables,
    init_parking_tables, init_travel_tables
)
from education_system.university_system.infrastructure.database.schemas.research_integration_schemas import (
    init_research_grants_system_db, init_integration_marketplace_system_db,
    init_integration_tables
)
from education_system.university_system.infrastructure.database.schemas.ai_features_schemas import init_ai_features_system_db, init_ai_tables
from education_system.university_system.infrastructure.database.schemas.admin_support_schemas import (
    init_course_evaluation_system_db, init_auth_tables, init_audit_tables,
    init_documents_tables, init_support_tables, init_parent_tables,
    init_library_tables, init_commerce_tables, init_other_tables
)
from education_system.university_system.infrastructure.database.schemas.aggregators import init_additional_missing_tables

def init_academic_transfer_history():
    """Create academic_transfer_history table and add previous_system columns to students."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS academic_transfer_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            source_system TEXT NOT NULL,
            source_student_id TEXT NOT NULL,
            transfer_date TEXT NOT NULL DEFAULT (datetime('now')),
            data_json TEXT NOT NULL
        )
        ''')

        # Migration: add previous_system columns to students if missing
        cols = {r[1] for r in conn.execute("PRAGMA table_info(students)").fetchall()}
        if "previous_system" not in cols:
            conn.execute("ALTER TABLE students ADD COLUMN previous_system TEXT")
        if "previous_system_id" not in cols:
            conn.execute("ALTER TABLE students ADD COLUMN previous_system_id TEXT")

        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"Error initializing academic_transfer_history: {e}")
        if 'conn' in locals():
            conn.close()


def create_performance_indexes():
    """
    Create database indexes for frequently-queried columns.

    This function adds indexes to improve query performance for common operations
    like student lookups, enrollment queries, grade filtering, and transaction searches.
    All indexes use IF NOT EXISTS to be idempotent.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.creating_indexes"))

        # Define all indexes: (index_name, table_name, columns, is_unique)
        indexes = [
            # Student-related indexes
            ('idx_students_email', 'students', 'email_address', False),
            ('idx_students_status', 'students', 'status', False),
            ('idx_students_course', 'students', 'course', False),
            ('idx_students_enrollment_date', 'students', 'enrollment_date', False),

            # Module enrollment indexes
            ('idx_student_modules_student_id', 'student_modules', 'student_id', False),
            ('idx_student_modules_module_code', 'student_modules', 'module_code', False),
            ('idx_student_modules_status', 'student_modules', 'status', False),
            ('idx_student_modules_student_module', 'student_modules', 'student_id, module_code', False),

            # User/Auth indexes
            ('idx_users_username', 'users', 'username', True),
            ('idx_users_email', 'users', 'email', False),
            ('idx_users_role', 'users', 'role', False),
            ('idx_users_status', 'users', 'status', False),

            # Session indexes
            ('idx_sessions_user_id', 'sessions', 'user_id', False),
            ('idx_sessions_token', 'sessions', 'session_token', True),
            ('idx_sessions_expires', 'sessions', 'expires_at', False),

            # Finance indexes
            ('idx_payments_student_id', 'payments', 'student_id', False),
            ('idx_payments_date', 'payments', 'payment_date', False),
            ('idx_payments_status', 'payments', 'status', False),
            ('idx_fee_assignments_student_id', 'fee_assignments', 'student_id', False),
            ('idx_fee_assignments_due_date', 'fee_assignments', 'due_date', False),
            ('idx_invoices_student_id', 'invoices', 'student_id', False),
            ('idx_invoices_status', 'invoices', 'status', False),

            # Course/Assignment indexes
            ('idx_courses_course_code', 'courses', 'course_code', True),
            ('idx_courses_department', 'courses', 'department', False),
            ('idx_assignments_course_id', 'assignments', 'course_id', False),
            ('idx_assignments_due_date', 'assignments', 'due_date', False),
            ('idx_assignment_submissions_student_id', 'assignment_submissions', 'student_id', False),
            ('idx_assignment_submissions_assignment_id', 'assignment_submissions', 'assignment_id', False),
            ('idx_assignment_submissions_student_assignment', 'assignment_submissions', 'student_id, assignment_id', False),

            # Grade indexes
            ('idx_grades_student_id', 'grades', 'student_id', False),
            ('idx_grades_course_id', 'grades', 'course_id', False),
            ('idx_grades_student_course', 'grades', 'student_id, course_id', False),

            # Attendance indexes
            ('idx_attendance_records_student_id', 'attendance_records', 'student_id', False),
            ('idx_attendance_records_course_id', 'attendance_records', 'course_id', False),
            ('idx_attendance_records_date', 'attendance_records', 'date', False),
            ('idx_attendance_records_student_course_date', 'attendance_records', 'student_id, course_id, date', False),

            # Email indexes
            ('idx_email_queue_status', 'email_queue', 'status', False),
            ('idx_email_queue_scheduled', 'email_queue', 'scheduled_time', False),
            ('idx_email_queue_recipient', 'email_queue', 'recipient_email', False),
            ('idx_email_logs_recipient', 'email_logs', 'recipient_email', False),
            ('idx_email_logs_sent_at', 'email_logs', 'sent_at', False),

            # Activity/Audit indexes
            ('idx_activity_logs_user_id', 'activity_logs', 'user_id', False),
            ('idx_activity_logs_action', 'activity_logs', 'action', False),
            ('idx_activity_logs_timestamp', 'activity_logs', 'timestamp', False),
            ('idx_audit_logs_user_id', 'audit_logs', 'user_id', False),
            ('idx_audit_logs_action', 'audit_logs', 'action', False),
            ('idx_audit_logs_timestamp', 'audit_logs', 'created_at', False),

            # Shop/Commerce indexes
            ('idx_shop_transactions_user_id', 'shop_transactions', 'user_id', False),
            ('idx_shop_transactions_student_id', 'shop_transactions', 'student_id', False),
            ('idx_shop_transactions_date', 'shop_transactions', 'transaction_date', False),
            ('idx_shop_products_category', 'shop_products', 'category', False),
            ('idx_shop_inventory_product_id', 'shop_inventory', 'product_id', False),

            # Health indexes
            ('idx_health_records_student_id', 'health_records', 'student_id', False),
            ('idx_appointments_student_id', 'appointments', 'student_id', False),
            ('idx_appointments_date', 'appointments', 'appointment_date', False),
            ('idx_appointments_status', 'appointments', 'status', False),

            # Housing indexes
            ('idx_room_assignments_student_id', 'room_assignments', 'student_id', False),
            ('idx_room_assignments_room_id', 'room_assignments', 'room_id', False),
            ('idx_housing_applications_student_id', 'housing_applications', 'student_id', False),
            ('idx_housing_applications_status', 'housing_applications', 'status', False),

            # Library indexes
            ('idx_book_loans_student_id', 'book_loans', 'student_id', False),
            ('idx_book_loans_book_id', 'book_loans', 'book_id', False),
            ('idx_book_loans_due_date', 'book_loans', 'due_date', False),
            ('idx_book_loans_status', 'book_loans', 'status', False),

            # Support ticket indexes
            ('idx_support_tickets_user_id', 'support_tickets', 'user_id', False),
            ('idx_support_tickets_status', 'support_tickets', 'status', False),
            ('idx_support_tickets_priority', 'support_tickets', 'priority', False),
            ('idx_support_tickets_created_at', 'support_tickets', 'created_at', False),

            # Student clubs indexes
            ('idx_student_clubs_status', 'student_clubs', 'status', False),
            ('idx_student_clubs_created_date', 'student_clubs', 'created_date', False),
            ('idx_student_clubs_club_id', 'student_clubs', 'club_id', False),

            # Union events indexes
            ('idx_union_events_status', 'union_events', 'status', False),
            ('idx_union_events_event_date', 'union_events', 'event_date', False),
            ('idx_union_events_created_by', 'union_events', 'created_by', False),

            # General transactions indexes (finance)
            ('idx_transactions_student_id', 'transactions', 'student_id', False),
            ('idx_transactions_transaction_date', 'transactions', 'transaction_date', False),
            ('idx_transactions_status', 'transactions', 'status', False),
            ('idx_transactions_type', 'transactions', 'transaction_type', False),

            # Health records indexes
            ('idx_health_records_patient_id', 'health_records', 'patient_id', False),
            ('idx_health_records_record_date', 'health_records', 'record_date', False),
            ('idx_health_records_record_type', 'health_records', 'record_type', False),

            # Enrollments indexes (course enrollments)
            ('idx_enrollments_student_id', 'enrollments', 'student_id', False),
            ('idx_enrollments_course_id', 'enrollments', 'course_id', False),
            ('idx_enrollments_status', 'enrollments', 'status', False),
            ('idx_enrollments_enrollment_date', 'enrollments', 'enrollment_date', False),

            # Internship indexes
            ('idx_internships_status', 'internships', 'status', False),
            ('idx_internships_deadline_date', 'internships', 'deadline_date', False),
            ('idx_internship_applications_student_id', 'internship_applications', 'student_id', False),
            ('idx_internship_applications_status', 'internship_applications', 'status', False),

            # Menu items and restaurant orders indexes
            ('idx_menu_items_category', 'menu_items', 'category', False),
            ('idx_menu_items_available', 'menu_items', 'available', False),
            ('idx_restaurant_orders_customer_id', 'restaurant_orders', 'customer_id', False),
            ('idx_restaurant_orders_status', 'restaurant_orders', 'status', False),
            ('idx_restaurant_orders_order_date', 'restaurant_orders', 'order_date', False),
        ]

        indexes_created = 0
        indexes_skipped = 0

        for index_name, table_name, columns, is_unique in indexes:
            try:
                # Validate identifiers for defense-in-depth
                validate_identifier(index_name, "index name")
                validate_identifier(table_name, "table name")
                for col in columns.split(', '):
                    validate_identifier(col.strip(), "column name")
                unique_clause = "UNIQUE " if is_unique else ""
                cursor.execute(f"""
                    CREATE {unique_clause}INDEX IF NOT EXISTS {index_name}
                    ON {table_name}({columns})
                """)
                indexes_created += 1
            except Exception as e:
                # Table might not exist yet, skip silently
                indexes_skipped += 1

        conn.commit()
        conn.close()

        print(_t("schemas.indexes_created", created=indexes_created, skipped=indexes_skipped))

    except Exception as e:
        print(_t("schemas.indexes_error", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# MASTER INITIALIZATION
# ============================================================================


def initialize_all_schemas():
    """Initialize all system database schemas"""
    print("=" * 60)
    print(_t("schemas.init_all_header"))
    print("=" * 60)

    # Original systems
    init_grade_system_db()
    init_finance_system_db()
    init_student_union_db()
    init_email_system_db()
    init_health_system_db()

    # Phase 1: HIGH Priority Features
    init_lms_system_db()
    # Shared LMS tables (cross-system foundation)
    try:
        from education_system.shared.lms.schema import create_lms_tables
        conn = get_connection()
        create_lms_tables(conn)
        conn.close()
    except Exception as e:
        print(f"Warning: shared LMS tables init: {e}")
    init_attendance_system_db()
    init_mental_health_system_db()
    init_early_warning_system_db()

    # Phase 2: MEDIUM-HIGH Priority Features
    init_degree_audit_system_db()
    init_career_services_system_db()
    init_admissions_crm_system_db()
    init_analytics_dashboard_system_db()

    # Phase 3: MEDIUM Priority Features
    init_smart_timetable_system_db()
    init_campus_events_system_db()
    init_alumni_relations_system_db()
    init_research_grants_system_db()
    init_facilities_management_system_db()
    init_course_evaluation_system_db()
    init_business_intelligence_system_db()
    init_ai_features_system_db()
    init_integration_marketplace_system_db()

    # Phase 4: Missing tables from database schema
    print("\n" + "=" * 60)
    print(_t("schemas.init_missing_tables_header"))
    print("=" * 60)
    init_academics_tables()
    init_ai_tables()
    init_alumni_tables()
    init_analytics_tables()
    init_audit_tables()
    init_auth_tables()
    init_career_tables()
    init_commerce_tables()
    init_communication_tables()
    init_courses_tables()
    init_documents_tables()
    init_finance_tables()
    init_health_tables()
    init_housing_tables()
    init_integration_tables()
    init_library_tables()
    init_other_tables()
    init_parent_tables()
    init_parking_tables()
    init_peer_support_tables()
    init_social_tables()
    init_student_affairs_tables()
    init_support_tables()
    init_travel_tables()
    init_wellness_tables()

    # Phase 5: Additional missing tables (109 tables)
    print("\n" + "=" * 60)
    print(_t("schemas.init_additional_tables_header"))
    print("=" * 60)
    init_additional_missing_tables()

    # Phase 5.5: Academic transfer history table and migrations
    init_academic_transfer_history()

    # Phase 6: Create performance indexes after all tables exist
    print("\n" + "=" * 60)
    print(_t("schemas.creating_indexes_header"))
    print("=" * 60)
    create_performance_indexes()

    # Phase 7: Per-domain schema initializers that aren't part of the
    # centralized schema files. These create tables for the standalone
    # commerce/health/academics/etc. service modules. Each call is
    # individually guarded so a failure in one domain doesn't block others.
    print("\n" + "=" * 60)
    print("Initializing per-domain schemas...")
    print("=" * 60)
    _init_per_domain_schemas()

    print("=" * 60)
    print(_t("schemas.all_initialized_success"))
    print("=" * 60)


def _init_per_domain_schemas():
    """Call every domain-specific schema initializer. Each is best-effort:
    a failure in one module is logged and skipped so the rest still run.

    Each entry is (module_path, target). `target` may be:
      - "func_name"             → call module.func_name()
      - ("Class",)              → instantiate Class() (auto-init in __init__)
      - ("Class", "method")     → Class().method() — explicit init call
      - ("Class.method",)       → call Class.method() (staticmethod)
      - ("@conn", "func_name")  → open default DB conn, call func(conn)
    """
    import logging
    from education_system.university_system.infrastructure.database.db import get_connection

    initializers = [
        # Schemas folder leftovers
        ("infrastructure.database.schemas.staff_hr_schemas_all", "init_staff_hr_schemas"),
        # Per-domain schema.py files
        ("modules.domain.student_affairs.equality_diversity.schema", "migrate"),
        ("modules.domain.health.records.db.schema", "init_enhanced_health_db"),
        ("modules.domain.finance.services.financial_aid.schema", ("@conn", "create_financial_aid_tables")),
        ("modules.domain.academics.services.virtual_classroom.schema", ("@conn", "create_virtual_classroom_tables")),
        # Academics
        ("modules.domain.academics.apprenticeships.apprenticeship_system", ("Database",)),
        ("modules.domain.academics.course_evaluation.course_evaluation_system", ("Database",)),
        ("modules.domain.academics.course_evaluation.lecturer_evaluation", ("Database",)),
        ("modules.domain.academics.grading.grade_calculation.db_init", "init_enhanced_grades_db"),
        ("modules.domain.academics.gui.academic_calendar.database", "init_calendar_database"),
        ("modules.domain.academics.placements.placement_tracker", ("Database",)),
        ("modules.domain.academics.services.attendance.db", "init_enhanced_attendance_db"),
        ("modules.domain.academics.services.library.database", "init_library_db"),
        ("modules.domain.academics.tutor_groups.services.tutor_group_service", ("TutorGroupService", "init_schema")),
        # Campus & career
        ("modules.domain.campus.equipment.services.equipment_core", "init_equipment_db"),
        ("modules.domain.career.student_jobs.services.job_service", ("JobPostingManager.create_tables",)),
        # Commerce — standalone shop sub-systems
        ("modules.domain.commerce.barber.services.barber_core", "init_barber_db"),
        ("modules.domain.commerce.barber.services.barber_core", "init_extended_barber_db"),
        ("modules.domain.commerce.betting.services.betting_core", "init_betting_db"),
        ("modules.domain.commerce.butcher.services.butcher_core", "init_butcher_db"),
        ("modules.domain.commerce.carrental.services.carrental_core", "init_carrental_db"),
        ("modules.domain.commerce.cinema.cinema_portals", "ensure_cinema_tables"),
        ("modules.domain.commerce.gym.services.gym_core", "init_gym_db"),
        ("modules.domain.commerce.musicshop.services.musicshop_core", "init_musicshop_db"),
        ("modules.domain.commerce.nailbar.services.nailbar_core", "init_nailbar_db"),
        ("modules.domain.commerce.phoneshop.services.phoneshop_core", "init_phoneshop_db"),
        ("modules.domain.commerce.services.grocery.grocery_service", "init_grocery_db"),
        ("modules.domain.commerce.services.shop_management.database", "init_shop_db"),
        ("modules.domain.commerce.services.takeaway.takeaway_service", "init_takeaway_db"),
        # Communications
        ("modules.domain.communications.mail.services.mail_post_core", "init_mail_db"),
        # Finance
        ("modules.domain.finance.budget.services.budget_service", ("BudgetManager.create_tables",)),
        ("modules.domain.finance.bursary.services.bursary_service", ("BursaryService", "init_schema")),
        ("modules.domain.finance.core.finance_db_operations", "init_enhanced_finance_db"),
        ("modules.domain.finance.scholarship_finder.services.scholarship_service", ("ScholarshipDatabase.create_tables",)),
        # Health (health_portal/database.py is a Mixin, not standalone — skipped)
        ("modules.domain.health.dentist.services.dentist_core", "init_dentist_db"),
        ("modules.domain.health.portal.health_portal_core", "init_enhanced_health_db"),
        # Housing
        ("modules.domain.housing.services.accommodation.db", "init_accommodation_db"),
        ("modules.domain.housing.services.housing_accommodation.database", "init_housing_db"),
        # Legal
        ("modules.domain.legal.services.legal_services_core", "init_legal_services_db"),
        # Mobility
        ("modules.domain.mobility.services.trip_management.database", "init_trip_db"),
        # Research
        ("modules.domain.research.services.university_research", ("Database",)),
        # Staff HR
        ("modules.domain.staff_hr.background_checks.university_bg_checker", ("Database",)),
        # Student affairs
        ("modules.domain.student_affairs.employer_portal.services.employer_portal_service",
            ("EmployerPortalService", "init_schema")),
        ("modules.domain.student_affairs.services.alumni_management.database", "init_alumni_db"),
        ("modules.domain.student_affairs.services.early_warning.outcomes.intervention_outcomes_service",
            ("InterventionOutcomesService", "init_schema")),
        ("modules.domain.student_affairs.services.helpdesk.database", "init_helpdesk_db"),
        ("modules.domain.student_affairs.services.internship_management", "init_internship_db"),
    ]
    base = "education_system.university_system."
    ok = 0
    failed = []
    for mod_path, target in initializers:
        full = base + mod_path
        try:
            module = __import__(full, fromlist=["__"])

            if isinstance(target, str):
                # module-level function
                getattr(module, target)()
                label = target

            elif isinstance(target, tuple) and len(target) == 1 and target[0] == "@conn":
                # Shouldn't happen — see 2-element @conn form below
                raise RuntimeError("malformed @conn entry")

            elif isinstance(target, tuple) and target[0] == "@conn":
                # ("@conn", "func_name") — open conn, pass to func
                func_name = target[1]
                conn = get_connection()
                try:
                    getattr(module, func_name)(conn)
                    conn.commit()
                finally:
                    conn.close()
                label = func_name

            elif isinstance(target, tuple) and len(target) == 1:
                # ("Class",) → instantiate (auto-init in __init__)
                # OR ("Class.method",) → staticmethod call
                spec = target[0]
                if "." in spec:
                    cls_name, method_name = spec.split(".", 1)
                    getattr(getattr(module, cls_name), method_name)()
                    label = spec
                else:
                    getattr(module, spec)()
                    label = f"{spec}()"

            elif isinstance(target, tuple) and len(target) == 2:
                # ("Class", "method") → Class().method()
                cls_name, method_name = target
                cls = getattr(module, cls_name)
                getattr(cls(), method_name)()
                label = f"{cls_name}().{method_name}()"

            else:
                raise RuntimeError(f"unknown target shape: {target!r}")

            ok += 1
        except Exception as e:
            failed.append((mod_path, str(target), str(e)[:140]))
            logging.debug("Domain init skipped %s %s: %s", mod_path, target, e)

    print(f"  Per-domain schemas: {ok} initialized, {len(failed)} skipped")
    for mod_path, target_repr, err in failed:
        logging.info("  skipped %s %s — %s", mod_path, target_repr, err)



# ============================================================================
# MISSING TABLES ADDED FROM DATABASE SCHEMA
# Generated automatically to synchronize with actual database
# ============================================================================

# ============================================================================
# ACADEMICS TABLES (40 tables)
# ============================================================================


