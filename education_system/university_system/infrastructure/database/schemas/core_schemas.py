from __future__ import annotations
from datetime import datetime
from education_system.university_system.infrastructure.database.db import get_connection, sqlite3
from education_system.university_system.core.i18n import get_text as _t, init_i18n

# Initialize i18n
init_i18n()

def init_grade_system_db():
    """Initialize the grade system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="grade system"))

        # Create students table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            middle_name TEXT,
            last_name TEXT NOT NULL,
            course TEXT NOT NULL,
            email_address TEXT,
            gender TEXT,
            dob TEXT,
            enrollment_date TEXT DEFAULT (date('now')),
            status TEXT DEFAULT 'Active',
            grade_level TEXT
        )
        ''')

        # Create modules table
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

        # Create student_modules table (enrollment)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_code TEXT,
            module_name TEXT,
            module_type TEXT DEFAULT 'Standard',
            enrollment_date TEXT DEFAULT CURRENT_TIMESTAMP,
            grade TEXT,
            completion_date TEXT,
            status TEXT DEFAULT 'Enrolled',
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="Grade system"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="grade system", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# FINANCE SYSTEM SCHEMAS
# ============================================================================


def init_academics_tables():
    """Initialize academics system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="academics"))

        # Create assignment_submissions table
        cursor.execute('''
        CREATE TABLE assignment_submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assignment_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    submission_date TIMESTAMP NOT NULL,
                    file_path TEXT,
                    file_name TEXT NOT NULL,
                    file_size INTEGER,
                    file_hash TEXT,
                    status TEXT DEFAULT 'submitted',
                    grade REAL,
                    feedback TEXT,
                    late_submission BOOLEAN DEFAULT 0,
                    late_days INTEGER DEFAULT 0,
                    version_number INTEGER DEFAULT 1,
                    is_final_submission BOOLEAN DEFAULT 1,
                    graded_by INTEGER,
                    graded_date TIMESTAMP,
                    FOREIGN KEY (assignment_id) REFERENCES assignments (id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (graded_by) REFERENCES users (id)
                )
        ''')

        # Create assignments table
        cursor.execute('''
        CREATE TABLE assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    module_code TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    instructions TEXT,
                    due_date TIMESTAMP NOT NULL,
                    max_marks INTEGER NOT NULL,
                    file_types_allowed TEXT,
                    max_file_size_mb INTEGER DEFAULT 10,
                    assignment_type TEXT DEFAULT 'individual',
                    group_size_min INTEGER DEFAULT 1,
                    group_size_max INTEGER DEFAULT 1,
                    allow_late_submission BOOLEAN DEFAULT 1,
                    late_penalty_per_day REAL DEFAULT 0,
                    auto_release_grades BOOLEAN DEFAULT 0,
                    peer_review_enabled BOOLEAN DEFAULT 0,
                    rubric_id INTEGER,
                    is_active BOOLEAN DEFAULT 1,
                    created_by INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (module_code) REFERENCES modules (module_code),
                    FOREIGN KEY (created_by) REFERENCES users (id)
                )
        ''')

        # Create attendance_alerts table
        cursor.execute('''
        CREATE TABLE attendance_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_id TEXT UNIQUE,
                    student_id TEXT,
                    module_code TEXT,
                    alert_type TEXT,
                    severity TEXT,
                    message TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    sent_at TEXT,
                    acknowledged_at TEXT,
                    status TEXT DEFAULT 'pending',
                    recipient_email TEXT,
                    recipient_phone TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (module_code) REFERENCES modules (module_code)
                )
        ''')

        # Create attendance_appeals table
        cursor.execute('''
        CREATE TABLE attendance_appeals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    appeal_id TEXT UNIQUE,
                    student_id TEXT,
                    module_code TEXT,
                    attendance_record_id INTEGER,
                    original_status TEXT,
                    requested_status TEXT,
                    reason TEXT,
                    evidence_files TEXT,
                    submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    reviewed_by TEXT,
                    reviewed_at TEXT,
                    decision TEXT,
                    decision_reason TEXT,
                    status TEXT DEFAULT 'pending',
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (module_code) REFERENCES modules (module_code),
                    FOREIGN KEY (attendance_record_id) REFERENCES attendance_records (id)
                )
        ''')

        # Create attendance_audit_log table
        cursor.execute('''
        CREATE TABLE attendance_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    action TEXT,
                    table_name TEXT,
                    record_id TEXT,
                    old_values TEXT,
                    new_values TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    ip_address TEXT,
                    user_agent TEXT
                )
        ''')

        # Create attendance_calendar_links table
        cursor.execute('''
        CREATE TABLE attendance_calendar_links (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        attendance_record_id INTEGER,
                        event_id TEXT,
                        module_code TEXT,
                        date TEXT,
                        created_at TEXT,
                        FOREIGN KEY (attendance_record_id) REFERENCES attendance_records (id),
                        FOREIGN KEY (event_id) REFERENCES events (id)
                    )
        ''')

        # Create attendance_gamification table
        cursor.execute('''
        CREATE TABLE attendance_gamification (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    points INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    badges TEXT,
                    achievements TEXT,
                    streak_days INTEGER DEFAULT 0,
                    best_streak INTEGER DEFAULT 0,
                    last_attendance_date TEXT,
                    total_rewards INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
        ''')

        # Create attendance_policies table
        cursor.execute('''
        CREATE TABLE attendance_policies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    policy_id TEXT UNIQUE,
                    name TEXT,
                    description TEXT,
                    module_code TEXT,
                    course TEXT,
                    min_attendance_percentage REAL,
                    max_consecutive_absences INTEGER,
                    late_tolerance_minutes INTEGER DEFAULT 15,
                    makeup_allowed BOOLEAN DEFAULT 1,
                    auto_fail_threshold REAL,
                    grace_period_days INTEGER DEFAULT 0,
                    effective_from TEXT,
                    effective_until TEXT,
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'active'
                )
        ''')

        # Create attendance_predictions table
        cursor.execute('''
        CREATE TABLE attendance_predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    module_code TEXT,
                    prediction_date TEXT,
                    predicted_attendance_rate REAL,
                    risk_level TEXT,
                    confidence_score REAL,
                    factors TEXT,
                    recommendations TEXT,
                    model_version TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (module_code) REFERENCES modules (module_code)
                )
        ''')

        # Create attendance_settings table
        cursor.execute('''
        CREATE TABLE attendance_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    setting_name TEXT UNIQUE,
                    setting_value TEXT,
                    description TEXT,
                    category TEXT DEFAULT 'general',
                    data_type TEXT DEFAULT 'string',
                    last_modified TEXT DEFAULT CURRENT_TIMESTAMP
                )
        ''')

        # Create course_event_attendance table
        cursor.execute('''
        CREATE TABLE course_event_attendance (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            event_id TEXT NOT NULL,
                            student_id TEXT NOT NULL,
                            attendance_status TEXT DEFAULT 'present',
                            notes TEXT,
                            recorded_at TEXT NOT NULL,
                            FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE,
                            UNIQUE(event_id, student_id)
                        )
        ''')

        # Create event_attendance table
        cursor.execute('''
        CREATE TABLE event_attendance (
                    attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER,
                    student_id TEXT,
                    check_in_time TEXT,
                    check_out_time TEXT,
                    qr_code TEXT,
                    cpd_credits REAL DEFAULT 0.0,
                    attendance_verified BOOLEAN DEFAULT 0,
                    FOREIGN KEY (event_id) REFERENCES union_events (event_id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
        ''')

        # Create event_tag_assignments table
        cursor.execute('''
        CREATE TABLE event_tag_assignments (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            event_id TEXT NOT NULL,
                            tag_id INTEGER NOT NULL,
                            date_added TEXT NOT NULL,
                            FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE,
                            FOREIGN KEY (tag_id) REFERENCES event_tags (id) ON DELETE CASCADE,
                            UNIQUE(event_id, tag_id)
                        )
        ''')

        # Create grade_analytics table
        cursor.execute('''
        CREATE TABLE grade_analytics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        module_code TEXT,
                        assessment_date TEXT,
                        grade_value DECIMAL(5,2),
                        class_average DECIMAL(5,2),
                        percentile_rank INTEGER,
                        trend_direction TEXT,
                        FOREIGN KEY (student_id) REFERENCES students (student_id),
                        FOREIGN KEY (module_code) REFERENCES modules (module_code)
                    )
        ''')

        # Create grade_statistics table
        cursor.execute('''
        CREATE TABLE grade_statistics (
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

        # Create grades table
        cursor.execute('''
        CREATE TABLE grades (
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

        # Create homework_assignments table
        cursor.execute('''
        CREATE TABLE homework_assignments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        module_code TEXT,
                        assignment_title TEXT,
                        description TEXT,
                        assigned_date TEXT,
                        due_date TEXT,
                        completion_status TEXT DEFAULT 'pending',
                        submitted_date TEXT,
                        grade TEXT,
                        teacher_comments TEXT,
                        FOREIGN KEY (student_id) REFERENCES students (student_id),
                        FOREIGN KEY (module_code) REFERENCES modules (module_code)
                    )
        ''')

        # Create housing_assignments table
        cursor.execute('''
        CREATE TABLE housing_assignments (
                    assignment_id TEXT PRIMARY KEY,
                    application_id TEXT,
                    student_id TEXT NOT NULL,
                    room_id TEXT NOT NULL,
                    move_in_date TEXT NOT NULL,
                    planned_move_out_date TEXT NOT NULL,
                    actual_move_out_date TEXT,
                    contract_number TEXT UNIQUE,
                    monthly_rent REAL NOT NULL,
                    status TEXT NOT NULL,
                    assigned_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (application_id) REFERENCES housing_applications (application_id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (room_id) REFERENCES housing_rooms (room_id)
                )
        ''')

        # Create module_grades table
        cursor.execute('''
        CREATE TABLE module_grades (
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

        # Create normalized_grades table
        cursor.execute('''
        CREATE TABLE normalized_grades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    grade_id INTEGER,
                    z_score REAL,
                    percentile REAL,
                    curved_score REAL,
                    curved_letter TEXT,
                    FOREIGN KEY (grade_id) REFERENCES grades (grade_id)
                )
        ''')

        # Create parent_student_relationships table
        cursor.execute('''
        CREATE TABLE parent_student_relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id TEXT,
                    student_id TEXT,
                    relationship_type TEXT,
                    access_level TEXT DEFAULT 'full',
                    date_added TEXT,
                    FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
        ''')

        # Create peer_review_assignments table
        cursor.execute('''
        CREATE TABLE peer_review_assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assignment_id TEXT UNIQUE NOT NULL,
                    session_id TEXT NOT NULL,
                    reviewer_id TEXT NOT NULL,
                    reviewee_id TEXT NOT NULL,
                    submission_id INTEGER,
                    due_date TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (reviewer_id) REFERENCES students (student_id),
                    FOREIGN KEY (reviewee_id) REFERENCES students (student_id),
                    FOREIGN KEY (submission_id) REFERENCES assignment_submissions (id)
                )
        ''')

        # Create staff_assignments table
        cursor.execute('''
        CREATE TABLE staff_assignments (
                    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    staff_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    is_primary BOOLEAN DEFAULT 0,
                    max_concurrent_tickets INTEGER DEFAULT 10,
                    current_ticket_count INTEGER DEFAULT 0,
                    expertise_level INTEGER DEFAULT 1,  -- 1-5 scale
                    auto_assign_enabled BOOLEAN DEFAULT 1
                )
        ''')

        # Create student_absences table
        cursor.execute('''
        CREATE TABLE student_absences (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        absence_date TEXT,
                        return_date TEXT,
                        reason TEXT,
                        reported_by TEXT,
                        reported_date TEXT,
                        notes TEXT,
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create student_activities table
        cursor.execute('''
        CREATE TABLE student_activities (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        activity_id INTEGER,
                        enrollment_date TEXT,
                        status TEXT DEFAULT 'active',
                        FOREIGN KEY (student_id) REFERENCES students (student_id),
                        FOREIGN KEY (activity_id) REFERENCES extracurricular_activities (id)
                    )
        ''')

        # Create student_attendance table
        cursor.execute('''
        CREATE TABLE student_attendance(
          student_id TEXT,
          module_code TEXT,
          date TEXT,
          status TEXT,
          notes TEXT,
          recorded_at TEXT
        )
        ''')

        # Create student_badges table
        cursor.execute('''
        CREATE TABLE student_badges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    badge_id INTEGER,
                    earned_date TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (badge_id) REFERENCES achievement_badges (badge_id)
                )
        ''')

        # Create student_behavior table
        cursor.execute('''
        CREATE TABLE student_behavior (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        incident_date TEXT,
                        behavior_type TEXT,
                        severity TEXT,
                        description TEXT,
                        action_taken TEXT,
                        reported_by TEXT,
                        follow_up_required BOOLEAN DEFAULT 0,
                        resolved BOOLEAN DEFAULT 0,
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create student_biometrics table
        cursor.execute('''
        CREATE TABLE student_biometrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    face_encoding BLOB,
                    face_photo_path TEXT,
                    enrolled_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'active',
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
        ''')

        # Create student_competencies table
        cursor.execute('''
        CREATE TABLE student_competencies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    competency_id INTEGER NOT NULL,
                    level_id INTEGER NOT NULL,
                    assessment_date TEXT,
                    evidence TEXT,
                    FOREIGN KEY (student_id) REFERENCES students(student_id),
                    FOREIGN KEY (competency_id) REFERENCES competencies(competency_id),
                    FOREIGN KEY (level_id) REFERENCES competency_levels(level_id)
                )
        ''')

        # Create student_credits table
        cursor.execute('''
        CREATE TABLE student_credits (
                    credit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    credit_amount DECIMAL(10,2) NOT NULL,
                    currency TEXT DEFAULT 'GBP',
                    credit_source TEXT, -- 'overpayment', 'refund', 'scholarship', 'adjustment'
                    description TEXT,
                    expiry_date TEXT,
                    remaining_amount DECIMAL(10,2) NOT NULL,
                    status TEXT DEFAULT 'active', -- active, used, expired
                    created_by TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
        ''')

        # Create student_demographics table
        cursor.execute('''
        CREATE TABLE student_demographics (
                        student_id TEXT PRIMARY KEY,
                        age_group TEXT,
                        gender TEXT,
                        ethnicity TEXT,
                        native_language TEXT,
                        academic_level TEXT,
                        accommodations TEXT
                    )
        ''')

        # Create student_financial_aid table
        cursor.execute('''
        CREATE TABLE student_financial_aid (
                    aid_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    aid_type_id INTEGER NOT NULL,
                    awarded_amount DECIMAL(10,2) NOT NULL,
                    disbursed_amount DECIMAL(10,2) DEFAULT 0,
                    remaining_amount DECIMAL(10,2) NOT NULL,
                    currency TEXT DEFAULT 'GBP',
                    status TEXT DEFAULT 'pending', -- pending, approved, disbursed, completed, cancelled
                    application_date TEXT,
                    approval_date TEXT,
                    disbursement_schedule TEXT, -- JSON with disbursement dates and amounts
                    repayment_start_date TEXT,
                    monthly_payment_amount DECIMAL(10,2),
                    total_repaid DECIMAL(10,2) DEFAULT 0,
                    approved_by TEXT,
                    notes TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (aid_type_id) REFERENCES financial_aid_types (aid_type_id)
                )
        ''')

        # Create student_medical_info table
        cursor.execute('''
        CREATE TABLE student_medical_info (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        condition_type TEXT,
                        description TEXT,
                        medication_name TEXT,
                        dosage TEXT,
                        administration_time TEXT,
                        emergency_contact TEXT,
                        doctor_contact TEXT,
                        expiry_date TEXT,
                        notes TEXT,
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create student_payment_plans table
        cursor.execute('''
        CREATE TABLE student_payment_plans (
                    payment_plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    template_id INTEGER,
                    total_amount DECIMAL(10,2) NOT NULL,
                    remaining_amount DECIMAL(10,2) NOT NULL,
                    currency TEXT DEFAULT 'GBP',
                    status TEXT DEFAULT 'active', -- active, completed, defaulted, cancelled
                    start_date TEXT NOT NULL,
                    next_due_date TEXT,
                    setup_fee_paid BOOLEAN DEFAULT 0,
                    auto_payment_enabled BOOLEAN DEFAULT 0,
                    payment_method_id INTEGER,
                    notes TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (template_id) REFERENCES payment_plan_templates (template_id)
                )
        ''')

        # Create student_points table
        cursor.execute('''
        CREATE TABLE student_points (
                    points_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    points_earned INTEGER,
                    points_spent INTEGER DEFAULT 0,
                    current_balance INTEGER,
                    activity_type TEXT,
                    activity_description TEXT,
                    earned_date TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
        ''')

        # Create student_requirement_progress table
        cursor.execute('''
        CREATE TABLE student_requirement_progress (
                            id TEXT PRIMARY KEY,
                            student_id TEXT NOT NULL,
                            requirement_id TEXT NOT NULL,
                            credits_completed REAL DEFAULT 0.0,
                            completion_percentage REAL DEFAULT 0.0,
                            status TEXT DEFAULT 'in_progress',
                            completion_date TEXT,
                            notes TEXT,
                            FOREIGN KEY (student_id) REFERENCES students (student_id),
                            FOREIGN KEY (requirement_id) REFERENCES graduation_requirements (id),
                            UNIQUE(student_id, requirement_id)
                        )
        ''')

        # Create student_risk_assessment table
        cursor.execute('''
        CREATE TABLE student_risk_assessment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    risk_score REAL NOT NULL,
                    risk_level TEXT NOT NULL,
                    assessment_date TEXT,
                    prediction_model TEXT,
                    confidence REAL,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
        ''')

        # Create teacher_student_permissions table
        cursor.execute('''
        CREATE TABLE teacher_student_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    teacher_id INTEGER,
                    student_id TEXT,
                    permission_type TEXT,
                    FOREIGN KEY (teacher_id) REFERENCES users (id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
        ''')

        # Create ticket_assignments table
        cursor.execute('''
        CREATE TABLE ticket_assignments (
                    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER,
                    assigned_from INTEGER,
                    assigned_to INTEGER,
                    assignment_reason TEXT,
                    created_at TEXT,
                    FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                    FOREIGN KEY (assigned_from) REFERENCES users (id),
                    FOREIGN KEY (assigned_to) REFERENCES users (id)
                )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="academics"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="academics", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# AI TABLES (11 tables)
# ============================================================================


def init_courses_tables():
    """Initialize courses system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="courses"))

        # Create course_analytics table
        cursor.execute('''
        CREATE TABLE course_analytics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id INTEGER NOT NULL,
                    semester TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    total_enrolled INTEGER DEFAULT 0,
                    total_completed INTEGER DEFAULT 0,
                    average_grade REAL DEFAULT 0.0,
                    completion_rate REAL DEFAULT 0.0,
                    calculated_at TEXT NOT NULL,
                    FOREIGN KEY (course_id) REFERENCES courses (id)
                )
        ''')

        # Create course_categories table
        cursor.execute('''
        CREATE TABLE course_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    color_code TEXT,
                    created_at TEXT NOT NULL
                )
        ''')

        # Create course_history table
        cursor.execute('''
        CREATE TABLE course_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id INTEGER NOT NULL,
                    field_name TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    changed_by TEXT,
                    changed_at TEXT NOT NULL,
                    FOREIGN KEY (course_id) REFERENCES courses (id)
                )
        ''')

        # Create course_requirements table
        cursor.execute('''
        CREATE TABLE course_requirements (
                        requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        course_code TEXT,
                        program TEXT,
                        type_id INTEGER,
                        is_mandatory BOOLEAN DEFAULT 1,
                        deadline_days INTEGER,
                        FOREIGN KEY (type_id) REFERENCES document_types (type_id)
                    )
        ''')

        # Create course_schedule table
        cursor.execute('''
        CREATE TABLE course_schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id INTEGER NOT NULL,
                    semester TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    start_time TEXT,
                    end_time TEXT,
                    days_of_week TEXT,
                    classroom TEXT,
                    instructor_id INTEGER,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (course_id) REFERENCES courses (id),
                    UNIQUE(course_id, semester, year)
                )
        ''')

        # Create course_waitlist table
        cursor.execute('''
        CREATE TABLE course_waitlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    position INTEGER NOT NULL,
                    added_at TEXT NOT NULL,
                    status TEXT DEFAULT 'Waiting',
                    FOREIGN KEY (course_id) REFERENCES courses (id),
                    UNIQUE(course_id, student_id)
                )
        ''')

        # Create courses table
        cursor.execute('''
        CREATE TABLE courses (
                            id TEXT PRIMARY KEY,
                            code TEXT UNIQUE NOT NULL,
                            name TEXT NOT NULL,
                            credits INTEGER DEFAULT 3,
                            department TEXT,
                            instructor_id TEXT,
                            academic_year_id TEXT,
                            semester_id TEXT,
                            status TEXT DEFAULT 'active',
                            date_added TEXT NOT NULL, course_code TEXT, course_name TEXT, level TEXT, credit_hours INTEGER, current_enrollment INTEGER DEFAULT 0, max_enrollment INTEGER DEFAULT 30,
                            FOREIGN KEY (academic_year_id) REFERENCES academic_years (id),
                            FOREIGN KEY (semester_id) REFERENCES semesters (id)
                        )
        ''')

        # Create departments table
        cursor.execute('''
        CREATE TABLE departments (
                    dept_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    manager_id INTEGER,
                    email TEXT,
                    sla_policy_id INTEGER,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (manager_id) REFERENCES users (id),
                    FOREIGN KEY (sla_policy_id) REFERENCES sla_policies (sla_id)
                )
        ''')

        # Create instructors table
        cursor.execute('''
        CREATE TABLE instructors (
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

        # Create module_schedule table
        cursor.execute('''
        CREATE TABLE module_schedule (
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

        # Create semesters table
        cursor.execute('''
        CREATE TABLE semesters (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            academic_year_id TEXT NOT NULL,
                            name TEXT NOT NULL,
                            start_date TEXT NOT NULL,
                            end_date TEXT NOT NULL,
                            registration_start TEXT,
                            registration_end TEXT,
                            final_exams_start TEXT,
                            final_exams_end TEXT,
                            date_added TEXT NOT NULL,
                            FOREIGN KEY (academic_year_id) REFERENCES academic_years (id) ON DELETE CASCADE,
                            UNIQUE(academic_year_id, name),
                            CONSTRAINT valid_semester_dates CHECK (start_date < end_date)
                        )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="courses"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="courses", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# DOCUMENTS TABLES (7 tables)
# ============================================================================


