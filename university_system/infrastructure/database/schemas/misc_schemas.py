from __future__ import annotations
from datetime import datetime
from university_system.infrastructure.database.db import get_connection, sqlite3
from university_system.core.i18n import get_text as _t, init_i18n
from university_system.core.sql_safety import validate_identifier

# Initialize i18n
init_i18n()

# Import all schema functions needed by initialize_all_schemas
from .core_schemas import init_grade_system_db, init_academics_tables, init_courses_tables
from .finance_schemas import init_finance_system_db, init_finance_tables
from .student_union_schemas import init_student_union_db, init_student_affairs_tables, init_social_tables
from .communication_schemas import init_email_system_db, init_communication_tables
from .health_wellness_schemas import (
    init_health_system_db, init_mental_health_system_db,
    init_health_tables, init_wellness_tables
)
from .lms_schemas import init_lms_system_db
from .attendance_warning_schemas import (
    init_attendance_system_db, init_early_warning_system_db,
    init_peer_support_tables
)
from .degree_audit_schemas import init_degree_audit_system_db
from .career_alumni_schemas import (
    init_career_services_system_db, init_alumni_relations_system_db,
    init_career_tables, init_alumni_tables
)
from .admissions_schemas import init_admissions_crm_system_db
from .analytics_bi_schemas import (
    init_analytics_dashboard_system_db, init_business_intelligence_system_db,
    init_analytics_tables
)
from .campus_events_schemas import init_campus_events_system_db, init_smart_timetable_system_db
from .facilities_housing_schemas import (
    init_facilities_management_system_db, init_housing_tables,
    init_parking_tables, init_travel_tables
)
from .research_integration_schemas import (
    init_research_grants_system_db, init_integration_marketplace_system_db,
    init_integration_tables
)
from .ai_features_schemas import init_ai_features_system_db, init_ai_tables
from .admin_support_schemas import (
    init_course_evaluation_system_db, init_auth_tables, init_audit_tables,
    init_documents_tables, init_support_tables, init_parent_tables,
    init_library_tables, init_commerce_tables, init_other_tables
)
from .aggregators import init_additional_missing_tables

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
            ('idx_transactions_user_id', 'transactions', 'user_id', False),
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

    # Phase 6: Create performance indexes after all tables exist
    print("\n" + "=" * 60)
    print(_t("schemas.creating_indexes_header"))
    print("=" * 60)
    create_performance_indexes()

    print("=" * 60)
    print(_t("schemas.all_initialized_success"))
    print("=" * 60)



# ============================================================================
# MISSING TABLES ADDED FROM DATABASE SCHEMA
# Generated automatically to synchronize with actual database
# ============================================================================

# ============================================================================
# ACADEMICS TABLES (40 tables)
# ============================================================================


