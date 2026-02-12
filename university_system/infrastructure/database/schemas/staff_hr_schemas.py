"""
Staff HR Management Database Schemas

Creates tables for:
- Leave Management (leave_types, leave_requests, leave_balances)
- Time & Attendance (time_entries, timesheets)
- Training & Certifications (training_courses, training_enrollments, certifications)
- Performance Appraisals (appraisal_cycles, appraisal_records, appraisal_goals)
- Onboarding/Offboarding (onboarding_templates, onboarding_template_tasks,
                          onboarding_assignments, onboarding_task_progress)
"""

from __future__ import annotations

from university_system.infrastructure.database.db import sqlite3
from datetime import datetime

from university_system.infrastructure.database.db import get_connection

def init_staff_hr_schemas():
    """Initialize all Staff HR Management tables."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # ==================== LEAVE MANAGEMENT ====================

            # Leave Types Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS leave_types (
                    leave_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    max_days_per_year INTEGER DEFAULT 0,
                    requires_approval BOOLEAN DEFAULT 1,
                    is_paid BOOLEAN DEFAULT 1,
                    color_code TEXT DEFAULT '#3498db',
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Leave Requests Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS leave_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    leave_type_id INTEGER NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    total_days REAL NOT NULL,
                    reason TEXT,
                    document_path TEXT,
                    status TEXT DEFAULT 'pending',
                    approved_by TEXT,
                    approved_date TEXT,
                    rejection_reason TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (leave_type_id) REFERENCES leave_types(leave_type_id)
                )
            ''')

            # Leave Balances Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS leave_balances (
                    balance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    leave_type_id INTEGER NOT NULL,
                    year INTEGER NOT NULL,
                    allocated_days REAL DEFAULT 0,
                    used_days REAL DEFAULT 0,
                    carried_over REAL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, leave_type_id, year),
                    FOREIGN KEY (leave_type_id) REFERENCES leave_types(leave_type_id)
                )
            ''')

            # ==================== TIME & ATTENDANCE ====================

            # Time Entries Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS time_entries (
                    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    entry_date TEXT NOT NULL,
                    clock_in TEXT NOT NULL,
                    clock_out TEXT,
                    break_minutes INTEGER DEFAULT 0,
                    work_type TEXT DEFAULT 'regular',
                    location TEXT DEFAULT 'office',
                    notes TEXT,
                    is_manual BOOLEAN DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Timesheets Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS timesheets (
                    timesheet_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    week_start TEXT NOT NULL,
                    week_end TEXT NOT NULL,
                    total_hours REAL DEFAULT 0,
                    regular_hours REAL DEFAULT 0,
                    overtime_hours REAL DEFAULT 0,
                    status TEXT DEFAULT 'draft',
                    submitted_date TEXT,
                    approved_by TEXT,
                    approved_date TEXT,
                    rejection_reason TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, week_start)
                )
            ''')

            # ==================== TRAINING & CERTIFICATIONS ====================

            # Training Courses Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS training_courses (
                    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    provider TEXT,
                    duration_hours REAL,
                    passing_score REAL DEFAULT 70,
                    is_mandatory BOOLEAN DEFAULT 0,
                    recertification_months INTEGER,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Training Enrollments Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS training_enrollments (
                    enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    course_id INTEGER NOT NULL,
                    enrolled_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    due_date TEXT,
                    started_date TEXT,
                    completed_date TEXT,
                    status TEXT DEFAULT 'enrolled',
                    score REAL,
                    attempts INTEGER DEFAULT 0,
                    certificate_path TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (course_id) REFERENCES training_courses(course_id)
                )
            ''')

            # Certifications Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS certifications (
                    cert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    issuing_body TEXT,
                    credential_id TEXT,
                    issue_date TEXT,
                    expiry_date TEXT,
                    document_path TEXT,
                    status TEXT DEFAULT 'active',
                    reminder_sent BOOLEAN DEFAULT 0,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ==================== PERFORMANCE APPRAISALS ====================

            # Appraisal Cycles Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS appraisal_cycles (
                    cycle_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    self_review_deadline TEXT,
                    manager_review_deadline TEXT,
                    status TEXT DEFAULT 'draft',
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Appraisal Records Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS appraisal_records (
                    appraisal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    reviewer_id TEXT,
                    self_rating REAL,
                    manager_rating REAL,
                    final_rating REAL,
                    self_comments TEXT,
                    manager_comments TEXT,
                    strengths TEXT,
                    areas_for_improvement TEXT,
                    development_plan TEXT,
                    status TEXT DEFAULT 'pending',
                    self_submitted_date TEXT,
                    manager_submitted_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (cycle_id) REFERENCES appraisal_cycles(cycle_id),
                    UNIQUE(cycle_id, user_id)
                )
            ''')

            # Appraisal Goals Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS appraisal_goals (
                    goal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    cycle_id INTEGER,
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT DEFAULT 'performance',
                    target_date TEXT,
                    progress INTEGER DEFAULT 0,
                    weight REAL DEFAULT 1.0,
                    status TEXT DEFAULT 'active',
                    completion_notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (cycle_id) REFERENCES appraisal_cycles(cycle_id)
                )
            ''')

            # ==================== ONBOARDING/OFFBOARDING ====================

            # Onboarding Templates Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS onboarding_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    role TEXT,
                    department TEXT,
                    template_type TEXT DEFAULT 'onboarding',
                    estimated_days INTEGER DEFAULT 30,
                    is_active BOOLEAN DEFAULT 1,
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Onboarding Template Tasks Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS onboarding_template_tasks (
                    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT DEFAULT 'general',
                    assigned_to_role TEXT DEFAULT 'employee',
                    due_days INTEGER DEFAULT 0,
                    is_required BOOLEAN DEFAULT 1,
                    order_num INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (template_id) REFERENCES onboarding_templates(template_id)
                )
            ''')

            # Onboarding Assignments Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS onboarding_assignments (
                    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    template_id INTEGER NOT NULL,
                    assigned_by TEXT,
                    start_date TEXT NOT NULL,
                    target_completion_date TEXT,
                    actual_completion_date TEXT,
                    status TEXT DEFAULT 'in_progress',
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (template_id) REFERENCES onboarding_templates(template_id)
                )
            ''')

            # Onboarding Task Progress Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS onboarding_task_progress (
                    progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assignment_id INTEGER NOT NULL,
                    task_id INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    assigned_to TEXT,
                    due_date TEXT,
                    completed_by TEXT,
                    completed_date TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (assignment_id) REFERENCES onboarding_assignments(assignment_id),
                    FOREIGN KEY (task_id) REFERENCES onboarding_template_tasks(task_id),
                    UNIQUE(assignment_id, task_id)
                )
            ''')

            # ==================== INDEXES ====================

            # Leave indexes
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_leave_requests_user
                ON leave_requests(user_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_leave_requests_status
                ON leave_requests(status)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_leave_balances_user
                ON leave_balances(user_id)
            ''')

            # Time indexes
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_time_entries_user
                ON time_entries(user_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_time_entries_date
                ON time_entries(entry_date)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_timesheets_user
                ON timesheets(user_id)
            ''')

            # Training indexes
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_training_enrollments_user
                ON training_enrollments(user_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_certifications_user
                ON certifications(user_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_certifications_expiry
                ON certifications(expiry_date)
            ''')

            # Appraisal indexes
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_appraisal_records_user
                ON appraisal_records(user_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_appraisal_goals_user
                ON appraisal_goals(user_id)
            ''')

            # Onboarding indexes
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_onboarding_assignments_user
                ON onboarding_assignments(user_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_onboarding_task_progress_assignment
                ON onboarding_task_progress(assignment_id)
            ''')

            conn.commit()

            # Insert default leave types
            _insert_default_leave_types(cursor)
            conn.commit()

            print("Staff HR schemas initialized successfully")

    except sqlite3.Error as e:
        print(f"Error initializing Staff HR schemas: {e}")
        raise

def _insert_default_leave_types(cursor):
    """Insert default leave types if they don't exist."""
    default_types = [
        ('Annual Leave', 'Paid annual vacation leave', 25, 1, 1, '#27ae60'),
        ('Sick Leave', 'Leave for illness or medical appointments', 10, 1, 1, '#e74c3c'),
        ('Personal Leave', 'Leave for personal matters', 5, 1, 1, '#3498db'),
        ('Bereavement', 'Leave for family bereavement', 5, 0, 1, '#7f8c8d'),
        ('Parental Leave', 'Maternity/Paternity leave', 90, 1, 1, '#9b59b6'),
        ('Study Leave', 'Leave for educational purposes', 10, 1, 0, '#f39c12'),
        ('Unpaid Leave', 'Unpaid leave of absence', 30, 1, 0, '#95a5a6'),
        ('Emergency Leave', 'Emergency situations', 3, 0, 1, '#c0392b'),
    ]

    for leave_type in default_types:
        cursor.execute('''
            INSERT OR IGNORE INTO leave_types
            (name, description, max_days_per_year, requires_approval, is_paid, color_code)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', leave_type)

def _insert_default_training_courses(cursor):
    """Insert default training courses if they don't exist."""
    default_courses = [
        ('Health & Safety Basics', 'Essential health and safety training', 'Compliance', 2.0, 1),
        ('Data Protection & GDPR', 'Understanding data protection requirements', 'Compliance', 1.5, 1),
        ('Equality & Diversity', 'Workplace equality and diversity awareness', 'Compliance', 1.0, 1),
        ('Fire Safety', 'Fire safety procedures and evacuation', 'Safety', 1.0, 1),
        ('IT Security Awareness', 'Cybersecurity best practices', 'IT', 1.0, 1),
        ('First Aid Basics', 'Basic first aid training', 'Safety', 4.0, 0),
        ('Leadership Skills', 'Developing leadership capabilities', 'Development', 8.0, 0),
        ('Communication Skills', 'Effective workplace communication', 'Development', 4.0, 0),
    ]

    for course in default_courses:
        cursor.execute('''
            INSERT OR IGNORE INTO training_courses
            (name, description, category, duration_hours, is_mandatory)
            VALUES (?, ?, ?, ?, ?)
        ''', course)

if __name__ == '__main__':
    init_staff_hr_schemas()
