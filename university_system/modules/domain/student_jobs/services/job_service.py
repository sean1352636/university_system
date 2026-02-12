"""
Student Job Board Service

Manages on-campus job listings, work-study programs, hour tracking,
skill-based matching, and student employment records.

Features:
- Job posting and management
- Work-study hour tracking
- Skill-based job matching
- Application tracking
- Employer management
- Performance tracking
"""

from __future__ import annotations

from university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.infrastructure.exceptions import DatabaseError, ValidationError
from university_system.modules.shared.utils.activity_logger import log_activity
from university_system.infrastructure.shared_context import get_auth
from university_system.core.sql_safety import validate_identifier

class JobPostingManager:
    """Manages on-campus job postings"""

    @staticmethod
    def create_tables() -> None:
        """Create all required tables for job board"""
        try:
            with transaction() as conn:
                # Job postings table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS campus_job_postings (
                        job_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        department_id INTEGER,
                        employer_name TEXT NOT NULL,
                        job_title TEXT NOT NULL,
                        job_category TEXT NOT NULL,
                        employment_type TEXT NOT NULL CHECK(employment_type IN ('work-study', 'part-time', 'internship', 'temp')),
                        hourly_rate REAL NOT NULL,
                        hours_per_week INTEGER,
                        total_positions INTEGER DEFAULT 1,
                        filled_positions INTEGER DEFAULT 0,
                        job_description TEXT NOT NULL,
                        required_skills TEXT,
                        preferred_skills TEXT,
                        minimum_gpa REAL DEFAULT 0.0,
                        work_authorization_required BOOLEAN DEFAULT 0,
                        location TEXT NOT NULL,
                        schedule_flexibility TEXT,
                        start_date TEXT,
                        end_date TEXT,
                        application_deadline TEXT,
                        contact_email TEXT,
                        contact_phone TEXT,
                        posted_by INTEGER,
                        posted_date TEXT DEFAULT (date('now')),
                        is_active BOOLEAN DEFAULT 1,
                        is_work_study BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (posted_by) REFERENCES users(id)
                    )
                ''')

                # Job applications table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS campus_job_applications (
                        application_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_id INTEGER NOT NULL,
                        student_id TEXT NOT NULL,
                        cover_letter TEXT,
                        resume_url TEXT,
                        availability TEXT,
                        expected_hours_per_week INTEGER,
                        reference_contacts TEXT,
                        application_date TEXT DEFAULT (date('now')),
                        status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'reviewed', 'interview', 'offered', 'accepted', 'rejected', 'withdrawn')),
                        reviewed_by INTEGER,
                        reviewed_date TEXT,
                        notes TEXT,
                        interview_date TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (job_id) REFERENCES campus_job_postings(job_id),
                        FOREIGN KEY (student_id) REFERENCES students(student_id),
                        FOREIGN KEY (reviewed_by) REFERENCES users(id)
                    )
                ''')

                # Student employment records
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS student_employment (
                        employment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        job_id INTEGER NOT NULL,
                        application_id INTEGER,
                        start_date TEXT NOT NULL,
                        end_date TEXT,
                        employment_status TEXT DEFAULT 'active' CHECK(employment_status IN ('active', 'on-leave', 'completed', 'terminated')),
                        hourly_rate REAL NOT NULL,
                        max_hours_per_week INTEGER,
                        supervisor_id INTEGER,
                        department TEXT,
                        position_title TEXT NOT NULL,
                        is_work_study BOOLEAN DEFAULT 0,
                        work_study_allocation REAL DEFAULT 0.0,
                        work_study_used REAL DEFAULT 0.0,
                        performance_rating REAL,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (student_id) REFERENCES students(student_id),
                        FOREIGN KEY (job_id) REFERENCES campus_job_postings(job_id),
                        FOREIGN KEY (application_id) REFERENCES campus_job_applications(application_id)
                    )
                ''')

                # Work hour tracking
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS work_hours_log (
                        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        employment_id INTEGER NOT NULL,
                        student_id TEXT NOT NULL,
                        work_date TEXT NOT NULL,
                        clock_in_time TEXT NOT NULL,
                        clock_out_time TEXT,
                        break_duration_minutes INTEGER DEFAULT 0,
                        total_hours REAL,
                        hourly_rate REAL NOT NULL,
                        earnings REAL,
                        is_work_study BOOLEAN DEFAULT 0,
                        work_study_deduction REAL DEFAULT 0.0,
                        task_description TEXT,
                        supervisor_id INTEGER,
                        approved_by INTEGER,
                        approved_date TEXT,
                        status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected', 'paid')),
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (employment_id) REFERENCES student_employment(employment_id),
                        FOREIGN KEY (student_id) REFERENCES students(student_id),
                        FOREIGN KEY (approved_by) REFERENCES users(id)
                    )
                ''')

                # Student skills inventory
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS student_skills (
                        skill_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        skill_name TEXT NOT NULL,
                        skill_category TEXT CHECK(skill_category IN ('technical', 'language', 'software', 'certification', 'soft-skill', 'other')),
                        proficiency_level TEXT CHECK(proficiency_level IN ('beginner', 'intermediate', 'advanced', 'expert')),
                        years_experience REAL,
                        verified BOOLEAN DEFAULT 0,
                        verified_by INTEGER,
                        verified_date TEXT,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (student_id) REFERENCES students(student_id),
                        UNIQUE(student_id, skill_name)
                    )
                ''')

                # Job skill requirements
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS job_skill_requirements (
                        requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_id INTEGER NOT NULL,
                        skill_name TEXT NOT NULL,
                        is_required BOOLEAN DEFAULT 1,
                        minimum_proficiency TEXT CHECK(minimum_proficiency IN ('beginner', 'intermediate', 'advanced', 'expert')),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (job_id) REFERENCES campus_job_postings(job_id),
                        UNIQUE(job_id, skill_name)
                    )
                ''')

                # Performance reviews
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS student_job_performance (
                        review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        employment_id INTEGER NOT NULL,
                        student_id TEXT NOT NULL,
                        reviewer_id INTEGER NOT NULL,
                        review_date TEXT NOT NULL,
                        review_period_start TEXT,
                        review_period_end TEXT,
                        attendance_rating INTEGER CHECK(attendance_rating BETWEEN 1 AND 5),
                        quality_rating INTEGER CHECK(quality_rating BETWEEN 1 AND 5),
                        initiative_rating INTEGER CHECK(initiative_rating BETWEEN 1 AND 5),
                        teamwork_rating INTEGER CHECK(teamwork_rating BETWEEN 1 AND 5),
                        overall_rating REAL,
                        strengths TEXT,
                        areas_for_improvement TEXT,
                        supervisor_comments TEXT,
                        student_comments TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (employment_id) REFERENCES student_employment(employment_id),
                        FOREIGN KEY (student_id) REFERENCES students(student_id),
                        FOREIGN KEY (reviewer_id) REFERENCES users(id)
                    )
                ''')

                log_activity('create', 'database_tables', details={'module': 'student_jobs', 'action': 'create_tables'})

        except sqlite3.Error as e:
            raise DatabaseError(f"Error creating student jobs tables: {e}") from e

    @staticmethod
    def post_job(employer_name: str, job_title: str, job_category: str,
                 employment_type: str, hourly_rate: float, job_description: str,
                 location: str, **kwargs) -> int:
        """Create a new campus job posting"""
        try:
            auth = get_auth()
            user = auth.get_current_user() if auth.is_logged_in() else None
            posted_by = user.get('id') if user else None

            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO campus_job_postings (
                        employer_name, job_title, job_category, employment_type,
                        hourly_rate, hours_per_week, total_positions, job_description,
                        required_skills, preferred_skills, minimum_gpa, work_authorization_required,
                        location, schedule_flexibility, start_date, end_date, application_deadline,
                        contact_email, contact_phone, posted_by, is_work_study
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    employer_name, job_title, job_category, employment_type,
                    hourly_rate, kwargs.get('hours_per_week'), kwargs.get('total_positions', 1),
                    job_description, kwargs.get('required_skills'), kwargs.get('preferred_skills'),
                    kwargs.get('minimum_gpa', 0.0), kwargs.get('work_authorization_required', 0),
                    location, kwargs.get('schedule_flexibility'), kwargs.get('start_date'),
                    kwargs.get('end_date'), kwargs.get('application_deadline'),
                    kwargs.get('contact_email'), kwargs.get('contact_phone'), posted_by,
                    kwargs.get('is_work_study', 0)
                ))
                job_id = cursor.lastrowid

                # Add skill requirements if provided
                if 'skill_requirements' in kwargs:
                    for skill in kwargs['skill_requirements']:
                        conn.execute('''
                            INSERT INTO job_skill_requirements (job_id, skill_name, is_required, minimum_proficiency)
                            VALUES (?, ?, ?, ?)
                        ''', (job_id, skill['name'], skill.get('required', 1), skill.get('proficiency', 'beginner')))

                log_activity('create', 'campus_job_posting', job_id=job_id, details={'title': job_title, 'employer': employer_name})
                return job_id

        except sqlite3.Error as e:
            raise DatabaseError(f"Error posting job: {e}") from e

    @staticmethod
    def get_active_jobs(filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get all active job postings with optional filters"""
        with get_connection() as conn:
            query = "SELECT * FROM campus_job_postings WHERE is_active = 1"
            params = []

            if filters:
                if 'job_category' in filters:
                    query += " AND job_category = ?"
                    params.append(filters['job_category'])
                if 'employment_type' in filters:
                    query += " AND employment_type = ?"
                    params.append(filters['employment_type'])
                if 'is_work_study' in filters:
                    query += " AND is_work_study = ?"
                    params.append(filters['is_work_study'])
                if 'min_hourly_rate' in filters:
                    query += " AND hourly_rate >= ?"
                    params.append(filters['min_hourly_rate'])
                if 'location' in filters:
                    query += " AND location LIKE ?"
                    params.append(f"%{filters['location']}%")

            query += " ORDER BY posted_date DESC"
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_job_details(job_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific job"""
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT jp.*,
                       (jp.total_positions - jp.filled_positions) as available_positions,
                       COUNT(DISTINCT ja.application_id) as total_applications
                FROM campus_job_postings jp
                LEFT JOIN campus_job_applications ja ON jp.job_id = ja.job_id
                WHERE jp.job_id = ?
                GROUP BY jp.job_id
            ''', (job_id,))
            job = cursor.fetchone()

            if job:
                job_dict = dict(job)
                # Get skill requirements
                cursor = conn.execute('''
                    SELECT * FROM job_skill_requirements WHERE job_id = ?
                ''', (job_id,))
                job_dict['skill_requirements'] = [dict(row) for row in cursor.fetchall()]
                return job_dict
            return None

    @staticmethod
    def update_job(job_id: int, **updates) -> bool:
        """Update job posting details"""
        try:
            with transaction() as conn:
                # Build dynamic UPDATE query
                allowed_fields = ['job_title', 'job_category', 'employment_type', 'hourly_rate',
                                'hours_per_week', 'total_positions', 'job_description', 'required_skills',
                                'preferred_skills', 'minimum_gpa', 'location', 'schedule_flexibility',
                                'start_date', 'end_date', 'application_deadline', 'contact_email',
                                'contact_phone', 'is_active', 'is_work_study']

                update_fields = {k: v for k, v in updates.items() if k in allowed_fields}
                if not update_fields:
                    return False

                set_clause = ", ".join([validate_identifier(k, "column") + " = ?" for k in update_fields.keys()])
                set_clause += ", updated_at = CURRENT_TIMESTAMP"
                values = list(update_fields.values()) + [job_id]

                conn.execute("UPDATE campus_job_postings SET " + set_clause + " WHERE job_id = ?", values)
                log_activity('update', 'campus_job_posting', job_id=job_id, details={'updates': list(update_fields.keys())})
                return True

        except sqlite3.Error as e:
            raise DatabaseError(f"Error updating job: {e}") from e

    @staticmethod
    def deactivate_job(job_id: int) -> bool:
        """Deactivate a job posting"""
        return JobPostingManager.update_job(job_id, is_active=0)

class JobApplicationManager:
    """Manages student job applications"""

    @staticmethod
    def apply_for_job(student_id: str, job_id: int, cover_letter: str = "",
                     resume_url: str = "", availability: str = "",
                     expected_hours: int = 0, reference_contacts: str = "") -> int:
        """Submit job application"""
        try:
            with transaction() as conn:
                # Check if already applied
                cursor = conn.execute('''
                    SELECT application_id FROM campus_job_applications
                    WHERE student_id = ? AND job_id = ? AND status NOT IN ('withdrawn', 'rejected')
                ''', (student_id, job_id))
                if cursor.fetchone():
                    raise ValidationError("Already applied for this job")

                # Check if job is still active and has positions available
                cursor = conn.execute('''
                    SELECT is_active, total_positions, filled_positions
                    FROM campus_job_postings WHERE job_id = ?
                ''', (job_id,))
                job = cursor.fetchone()
                if not job or not job['is_active']:
                    raise ValidationError("Job posting is not active")
                if job['filled_positions'] >= job['total_positions']:
                    raise ValidationError("No positions available")

                cursor = conn.execute('''
                    INSERT INTO campus_job_applications (
                        job_id, student_id, cover_letter, resume_url, availability,
                        expected_hours_per_week, reference_contacts
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (job_id, student_id, cover_letter, resume_url, availability,
                      expected_hours, reference_contacts))

                application_id = cursor.lastrowid
                log_activity('create', 'job_application', application_id=application_id,
                           details={'student_id': student_id, 'job_id': job_id})
                return application_id

        except sqlite3.Error as e:
            raise DatabaseError(f"Error submitting application: {e}") from e

    @staticmethod
    def get_student_applications(student_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all applications for a student"""
        with get_connection() as conn:
            query = '''
                SELECT ja.*, jp.job_title, jp.employer_name, jp.hourly_rate, jp.location
                FROM campus_job_applications ja
                JOIN campus_job_postings jp ON ja.job_id = jp.job_id
                WHERE ja.student_id = ?
            '''
            params = [student_id]

            if status:
                query += " AND ja.status = ?"
                params.append(status)

            query += " ORDER BY ja.application_date DESC"
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_job_applications(job_id: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all applications for a job"""
        with get_connection() as conn:
            query = '''
                SELECT ja.*, s.first_name, s.last_name, s.email, s.major, s.gpa
                FROM campus_job_applications ja
                JOIN students s ON ja.student_id = s.student_id
                WHERE ja.job_id = ?
            '''
            params = [job_id]

            if status:
                query += " AND ja.status = ?"
                params.append(status)

            query += " ORDER BY ja.application_date DESC"
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def update_application_status(application_id: int, status: str, notes: str = "") -> bool:
        """Update application status"""
        try:
            auth = get_auth()
            user = auth.get_current_user() if auth.is_logged_in() else None
            reviewed_by = user.get('id') if user else None

            with transaction() as conn:
                conn.execute('''
                    UPDATE campus_job_applications
                    SET status = ?, notes = ?, reviewed_by = ?, reviewed_date = date('now'),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE application_id = ?
                ''', (status, notes, reviewed_by, application_id))

                log_activity('update', 'job_application', application_id=application_id,
                           details={'status': status})
                return True

        except sqlite3.Error as e:
            raise DatabaseError(f"Error updating application status: {e}") from e

    @staticmethod
    def schedule_interview(application_id: int, interview_date: str) -> bool:
        """Schedule interview for application"""
        return JobApplicationManager.update_application_status(
            application_id, 'interview', f"Interview scheduled for {interview_date}"
        )

class EmploymentManager:
    """Manages student employment records"""

    @staticmethod
    def hire_student(student_id: str, job_id: int, application_id: int,
                    start_date: str, hourly_rate: float, max_hours_per_week: int,
                    position_title: str, is_work_study: bool = False,
                    work_study_allocation: float = 0.0) -> int:
        """Create employment record for hired student"""
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO student_employment (
                        student_id, job_id, application_id, start_date, hourly_rate,
                        max_hours_per_week, position_title, is_work_study, work_study_allocation
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, job_id, application_id, start_date, hourly_rate,
                      max_hours_per_week, position_title, is_work_study, work_study_allocation))

                employment_id = cursor.lastrowid

                # Update application status
                conn.execute('''
                    UPDATE campus_job_applications SET status = 'accepted'
                    WHERE application_id = ?
                ''', (application_id,))

                # Update filled positions count
                conn.execute('''
                    UPDATE campus_job_postings SET filled_positions = filled_positions + 1
                    WHERE job_id = ?
                ''', (job_id,))

                log_activity('create', 'student_employment', employment_id=employment_id,
                           details={'student_id': student_id, 'job_id': job_id})
                return employment_id

        except sqlite3.Error as e:
            raise DatabaseError(f"Error creating employment record: {e}") from e

    @staticmethod
    def get_student_employment(student_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get employment records for a student"""
        with get_connection() as conn:
            query = '''
                SELECT se.*, jp.job_title, jp.employer_name, jp.location
                FROM student_employment se
                JOIN campus_job_postings jp ON se.job_id = jp.job_id
                WHERE se.student_id = ?
            '''
            params = [student_id]

            if active_only:
                query += " AND se.employment_status = 'active'"

            query += " ORDER BY se.start_date DESC"
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def end_employment(employment_id: int, end_date: str, status: str = 'completed') -> bool:
        """End student employment"""
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE student_employment
                    SET end_date = ?, employment_status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE employment_id = ?
                ''', (end_date, status, employment_id))

                # Update filled positions count
                cursor = conn.execute('''
                    SELECT job_id FROM student_employment WHERE employment_id = ?
                ''', (employment_id,))
                job = cursor.fetchone()
                if job:
                    conn.execute('''
                        UPDATE campus_job_postings SET filled_positions = filled_positions - 1
                        WHERE job_id = ?
                    ''', (job['job_id'],))

                log_activity('update', 'student_employment', employment_id=employment_id,
                           details={'status': status, 'end_date': end_date})
                return True

        except sqlite3.Error as e:
            raise DatabaseError(f"Error ending employment: {e}") from e

class WorkHoursManager:
    """Manages work hour tracking and timesheets"""

    @staticmethod
    def clock_in(employment_id: int, student_id: str, work_date: str,
                clock_in_time: str, task_description: str = "") -> int:
        """Clock in for work shift"""
        try:
            with transaction() as conn:
                # Get employment details
                cursor = conn.execute('''
                    SELECT hourly_rate, is_work_study FROM student_employment
                    WHERE employment_id = ? AND employment_status = 'active'
                ''', (employment_id,))
                employment = cursor.fetchone()
                if not employment:
                    raise ValidationError("Employment record not found or not active")

                cursor = conn.execute('''
                    INSERT INTO work_hours_log (
                        employment_id, student_id, work_date, clock_in_time,
                        hourly_rate, is_work_study, task_description
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (employment_id, student_id, work_date, clock_in_time,
                      employment['hourly_rate'], employment['is_work_study'], task_description))

                log_id = cursor.lastrowid
                log_activity('create', 'work_hours_clock_in', log_id=log_id,
                           details={'student_id': student_id, 'work_date': work_date})
                return log_id

        except sqlite3.Error as e:
            raise DatabaseError(f"Error clocking in: {e}") from e

    @staticmethod
    def clock_out(log_id: int, clock_out_time: str, break_duration_minutes: int = 0) -> bool:
        """Clock out from work shift"""
        try:
            with transaction() as conn:
                # Get clock in time and hourly rate
                cursor = conn.execute('''
                    SELECT clock_in_time, hourly_rate, is_work_study, employment_id
                    FROM work_hours_log WHERE log_id = ?
                ''', (log_id,))
                record = cursor.fetchone()
                if not record:
                    raise ValidationError("Work hours record not found")

                # Calculate total hours
                clock_in = datetime.strptime(record['clock_in_time'], '%H:%M')
                clock_out = datetime.strptime(clock_out_time, '%H:%M')
                total_minutes = (clock_out - clock_in).seconds / 60 - break_duration_minutes
                total_hours = round(total_minutes / 60, 2)
                earnings = round(total_hours * record['hourly_rate'], 2)

                # Calculate work-study deduction if applicable
                work_study_deduction = 0.0
                if record['is_work_study']:
                    cursor = conn.execute('''
                        SELECT work_study_allocation, work_study_used
                        FROM student_employment WHERE employment_id = ?
                    ''', (record['employment_id'],))
                    ws = cursor.fetchone()
                    remaining = ws['work_study_allocation'] - ws['work_study_used']
                    work_study_deduction = min(earnings, remaining)

                conn.execute('''
                    UPDATE work_hours_log
                    SET clock_out_time = ?, break_duration_minutes = ?, total_hours = ?,
                        earnings = ?, work_study_deduction = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE log_id = ?
                ''', (clock_out_time, break_duration_minutes, total_hours, earnings,
                      work_study_deduction, log_id))

                log_activity('update', 'work_hours_clock_out', log_id=log_id,
                           details={'total_hours': total_hours, 'earnings': earnings})
                return True

        except sqlite3.Error as e:
            raise DatabaseError(f"Error clocking out: {e}") from e

    @staticmethod
    def get_student_hours(student_id: str, start_date: str = None,
                         end_date: str = None) -> List[Dict[str, Any]]:
        """Get work hours for a student"""
        with get_connection() as conn:
            query = '''
                SELECT wh.*, se.position_title, jp.employer_name
                FROM work_hours_log wh
                JOIN student_employment se ON wh.employment_id = se.employment_id
                JOIN campus_job_postings jp ON se.job_id = jp.job_id
                WHERE wh.student_id = ?
            '''
            params = [student_id]

            if start_date:
                query += " AND wh.work_date >= ?"
                params.append(start_date)
            if end_date:
                query += " AND wh.work_date <= ?"
                params.append(end_date)

            query += " ORDER BY wh.work_date DESC, wh.clock_in_time DESC"
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def approve_hours(log_id: int) -> bool:
        """Approve work hours"""
        try:
            auth = get_auth()
            user = auth.get_current_user() if auth.is_logged_in() else None
            approved_by = user.get('id') if user else None

            with transaction() as conn:
                # Get hours details
                cursor = conn.execute('''
                    SELECT employment_id, work_study_deduction
                    FROM work_hours_log WHERE log_id = ?
                ''', (log_id,))
                record = cursor.fetchone()
                if not record:
                    raise ValidationError("Work hours record not found")

                conn.execute('''
                    UPDATE work_hours_log
                    SET status = 'approved', approved_by = ?, approved_date = date('now'),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE log_id = ?
                ''', (approved_by, log_id))

                # Update work-study used amount
                if record['work_study_deduction'] > 0:
                    conn.execute('''
                        UPDATE student_employment
                        SET work_study_used = work_study_used + ?
                        WHERE employment_id = ?
                    ''', (record['work_study_deduction'], record['employment_id']))

                log_activity('update', 'work_hours_approve', log_id=log_id,
                           details={'approved_by': approved_by})
                return True

        except sqlite3.Error as e:
            raise DatabaseError(f"Error approving hours: {e}") from e

    @staticmethod
    def get_weekly_summary(student_id: str, week_start_date: str) -> Dict[str, Any]:
        """Get weekly hours summary for a student"""
        with get_connection() as conn:
            week_end_date = (datetime.strptime(week_start_date, '%Y-%m-%d') + timedelta(days=6)).strftime('%Y-%m-%d')

            cursor = conn.execute('''
                SELECT
                    COUNT(*) as total_shifts,
                    SUM(total_hours) as total_hours,
                    SUM(earnings) as total_earnings,
                    SUM(work_study_deduction) as total_work_study,
                    SUM(CASE WHEN status = 'approved' THEN total_hours ELSE 0 END) as approved_hours,
                    SUM(CASE WHEN status = 'pending' THEN total_hours ELSE 0 END) as pending_hours
                FROM work_hours_log
                WHERE student_id = ? AND work_date BETWEEN ? AND ?
            ''', (student_id, week_start_date, week_end_date))

            summary = dict(cursor.fetchone())
            summary['week_start'] = week_start_date
            summary['week_end'] = week_end_date
            return summary

class SkillMatchingManager:
    """Manages student skills and job matching"""

    @staticmethod
    def add_student_skill(student_id: str, skill_name: str, skill_category: str = 'other',
                         proficiency_level: str = 'beginner', years_experience: float = 0) -> int:
        """Add skill to student profile"""
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT OR REPLACE INTO student_skills (
                        student_id, skill_name, skill_category, proficiency_level, years_experience
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (student_id, skill_name, skill_category, proficiency_level, years_experience))

                skill_id = cursor.lastrowid
                log_activity('create', 'student_skill', skill_id=skill_id,
                           details={'student_id': student_id, 'skill': skill_name})
                return skill_id

        except sqlite3.Error as e:
            raise DatabaseError(f"Error adding skill: {e}") from e

    @staticmethod
    def get_student_skills(student_id: str) -> List[Dict[str, Any]]:
        """Get all skills for a student"""
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM student_skills WHERE student_id = ?
                ORDER BY skill_category, proficiency_level DESC
            ''', (student_id,))
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def find_matching_jobs(student_id: str, min_match_percentage: int = 50) -> List[Dict[str, Any]]:
        """Find jobs matching student skills"""
        with get_connection() as conn:
            # Get student skills
            cursor = conn.execute('''
                SELECT skill_name, proficiency_level FROM student_skills WHERE student_id = ?
            ''', (student_id,))
            student_skills = {row['skill_name']: row['proficiency_level'] for row in cursor.fetchall()}

            if not student_skills:
                return []

            # Get active jobs with skill requirements
            cursor = conn.execute('''
                SELECT DISTINCT jp.*
                FROM campus_job_postings jp
                JOIN job_skill_requirements jsr ON jp.job_id = jsr.job_id
                WHERE jp.is_active = 1
            ''')
            jobs = []

            proficiency_levels = {'beginner': 1, 'intermediate': 2, 'advanced': 3, 'expert': 4}

            for job in cursor.fetchall():
                job_dict = dict(job)

                # Get job skill requirements
                cursor2 = conn.execute('''
                    SELECT * FROM job_skill_requirements WHERE job_id = ?
                ''', (job['job_id'],))
                requirements = list(cursor2.fetchall())

                if not requirements:
                    continue

                # Calculate match percentage
                required_skills = [r for r in requirements if r['is_required']]
                matched_required = 0
                matched_preferred = 0

                for req in requirements:
                    skill_name = req['skill_name']
                    if skill_name in student_skills:
                        student_prof = proficiency_levels.get(student_skills[skill_name], 0)
                        required_prof = proficiency_levels.get(req['minimum_proficiency'], 0)

                        if student_prof >= required_prof:
                            if req['is_required']:
                                matched_required += 1
                            else:
                                matched_preferred += 1

                total_required = len(required_skills)
                required_match_pct = (matched_required / total_required * 100) if total_required > 0 else 100

                total_preferred = len(requirements) - total_required
                preferred_match_pct = (matched_preferred / total_preferred * 100) if total_preferred > 0 else 0

                overall_match = (required_match_pct * 0.7 + preferred_match_pct * 0.3)

                if overall_match >= min_match_percentage:
                    job_dict['match_percentage'] = round(overall_match, 1)
                    job_dict['required_skills_matched'] = matched_required
                    job_dict['total_required_skills'] = total_required
                    job_dict['preferred_skills_matched'] = matched_preferred
                    jobs.append(job_dict)

            # Sort by match percentage
            jobs.sort(key=lambda x: x['match_percentage'], reverse=True)
            return jobs

    @staticmethod
    def verify_skill(skill_id: int) -> bool:
        """Verify a student skill"""
        try:
            auth = get_auth()
            user = auth.get_current_user() if auth.is_logged_in() else None
            verified_by = user.get('id') if user else None

            with transaction() as conn:
                conn.execute('''
                    UPDATE student_skills
                    SET verified = 1, verified_by = ?, verified_date = date('now')
                    WHERE skill_id = ?
                ''', (verified_by, skill_id))

                log_activity('update', 'student_skill_verify', skill_id=skill_id)
                return True

        except sqlite3.Error as e:
            raise DatabaseError(f"Error verifying skill: {e}") from e

class PerformanceManager:
    """Manages employee performance reviews"""

    @staticmethod
    def create_performance_review(employment_id: int, student_id: str,
                                 review_date: str, review_period_start: str,
                                 review_period_end: str, attendance_rating: int,
                                 quality_rating: int, initiative_rating: int,
                                 teamwork_rating: int, strengths: str = "",
                                 areas_for_improvement: str = "",
                                 supervisor_comments: str = "") -> int:
        """Create performance review"""
        try:
            auth = get_auth()
            user = auth.get_current_user() if auth.is_logged_in() else None
            reviewer_id = user.get('id') if user else None

            # Calculate overall rating
            overall_rating = round((attendance_rating + quality_rating +
                                  initiative_rating + teamwork_rating) / 4, 2)

            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO student_job_performance (
                        employment_id, student_id, reviewer_id, review_date,
                        review_period_start, review_period_end, attendance_rating,
                        quality_rating, initiative_rating, teamwork_rating,
                        overall_rating, strengths, areas_for_improvement, supervisor_comments
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (employment_id, student_id, reviewer_id, review_date,
                      review_period_start, review_period_end, attendance_rating,
                      quality_rating, initiative_rating, teamwork_rating,
                      overall_rating, strengths, areas_for_improvement, supervisor_comments))

                review_id = cursor.lastrowid

                # Update employment performance rating
                conn.execute('''
                    UPDATE student_employment
                    SET performance_rating = ?
                    WHERE employment_id = ?
                ''', (overall_rating, employment_id))

                log_activity('create', 'performance_review', review_id=review_id,
                           details={'student_id': student_id, 'rating': overall_rating})
                return review_id

        except sqlite3.Error as e:
            raise DatabaseError(f"Error creating performance review: {e}") from e

    @staticmethod
    def get_student_reviews(student_id: str) -> List[Dict[str, Any]]:
        """Get all performance reviews for a student"""
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT pr.*, se.position_title, jp.employer_name
                FROM student_job_performance pr
                JOIN student_employment se ON pr.employment_id = se.employment_id
                JOIN campus_job_postings jp ON se.job_id = jp.job_id
                WHERE pr.student_id = ?
                ORDER BY pr.review_date DESC
            ''', (student_id,))
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_average_performance(student_id: str) -> Dict[str, float]:
        """Get average performance ratings for a student"""
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT
                    AVG(attendance_rating) as avg_attendance,
                    AVG(quality_rating) as avg_quality,
                    AVG(initiative_rating) as avg_initiative,
                    AVG(teamwork_rating) as avg_teamwork,
                    AVG(overall_rating) as avg_overall,
                    COUNT(*) as total_reviews
                FROM student_job_performance
                WHERE student_id = ?
            ''', (student_id,))
            return dict(cursor.fetchone())

# Initialize tables on module import
try:
    JobPostingManager.create_tables()
except Exception as e:
    import logging
    logging.getLogger(__name__).warning(f"Could not create student jobs tables: {e}")
