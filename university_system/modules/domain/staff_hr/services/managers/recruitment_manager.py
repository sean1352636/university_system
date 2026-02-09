"""
Recruitment Manager

Handles job postings, applications, interview scheduling,
department KPIs, and budget requests.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from university_system.infrastructure.database.db import get_connection, transaction

try:
    from university_system.modules.shared.utils.activity_logger import log_activity
except ImportError:
    def log_activity(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)


class RecruitmentManager:
    """Manager for recruitment and department management."""

    # ==================== JOB POSTINGS ====================

    @staticmethod
    def get_staff_recruitment_postings(status: Optional[str] = None,
                         department: Optional[str] = None,
                         limit: int = 50) -> List[Dict[str, Any]]:
        """Get job postings with optional filters."""
        with get_connection() as conn:
            query = 'SELECT * FROM staff_recruitment_postings WHERE 1=1'
            params = []
            if status:
                query += ' AND status = ?'
                params.append(status)
            if department:
                query += ' AND department = ?'
                params.append(department)
            query += ' ORDER BY post_date DESC LIMIT ?'
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def create_posting(posted_by: str, job_title: str, department: str,
                       **data) -> int:
        """Create a new job posting."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO staff_recruitment_postings (
                    job_title, department, job_type, location, description,
                    requirements, responsibilities, salary_range, benefits,
                    posted_by, posted_by_name, post_date, closing_date,
                    status, hiring_manager_id, hiring_manager_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (job_title, department, data.get('job_type', 'permanent'),
                  data.get('location'), data.get('description'),
                  data.get('requirements'), data.get('responsibilities'),
                  data.get('salary_range'), data.get('benefits'),
                  posted_by, data.get('posted_by_name'),
                  data.get('post_date', datetime.now().strftime('%Y-%m-%d')),
                  data.get('closing_date'), data.get('status', 'draft'),
                  data.get('hiring_manager_id'), data.get('hiring_manager_name')))
            posting_id = cursor.lastrowid
            log_activity('create', 'job_posting', details={
                'posting_id': posting_id, 'title': job_title
            })
            return posting_id

    @staticmethod
    def update_posting_status(posting_id: int, status: str) -> bool:
        """Update job posting status."""
        with transaction() as conn:
            conn.execute('''
                UPDATE staff_recruitment_postings SET status = ? WHERE posting_id = ?
            ''', (status, posting_id))
            return True

    @staticmethod
    def publish_posting(posting_id: int) -> bool:
        """Publish a job posting."""
        with transaction() as conn:
            conn.execute('''
                UPDATE staff_recruitment_postings
                SET status = 'open', post_date = ?
                WHERE posting_id = ? AND status = 'draft'
            ''', (datetime.now().strftime('%Y-%m-%d'), posting_id))
            return True

    # ==================== APPLICATIONS ====================

    @staticmethod
    def get_applications(posting_id: Optional[int] = None,
                         status: Optional[str] = None,
                         limit: int = 50) -> List[Dict[str, Any]]:
        """Get job applications."""
        with get_connection() as conn:
            query = '''
                SELECT a.*, j.job_title, j.department
                FROM staff_recruitment_applications a
                JOIN staff_recruitment_postings j ON a.posting_id = j.posting_id
                WHERE 1=1
            '''
            params = []
            if posting_id:
                query += ' AND a.posting_id = ?'
                params.append(posting_id)
            if status:
                query += ' AND a.status = ?'
                params.append(status)
            query += ' ORDER BY a.application_date DESC LIMIT ?'
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def submit_application(posting_id: int, applicant_name: str,
                           applicant_email: str, **data) -> int:
        """Submit a job application."""
        with transaction() as conn:
            # Get job title
            job = conn.execute('''
                SELECT job_title FROM staff_recruitment_postings WHERE posting_id = ?
            ''', (posting_id,)).fetchone()

            cursor = conn.execute('''
                INSERT INTO staff_recruitment_applications (
                    posting_id, job_title, applicant_name, applicant_email,
                    applicant_phone, applicant_address, cv_path,
                    cover_letter_path, portfolio_url, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'received')
            ''', (posting_id, job[0] if job else None, applicant_name,
                  applicant_email, data.get('applicant_phone'),
                  data.get('applicant_address'), data.get('cv_path'),
                  data.get('cover_letter_path'), data.get('portfolio_url')))

            # Update applications count
            conn.execute('''
                UPDATE staff_recruitment_postings
                SET applications_count = applications_count + 1
                WHERE posting_id = ?
            ''', (posting_id,))

            return cursor.lastrowid

    @staticmethod
    def shortlist_application(application_id: int, shortlisted_by: str) -> bool:
        """Shortlist an application."""
        with transaction() as conn:
            conn.execute('''
                UPDATE staff_recruitment_applications
                SET shortlisted = 1, shortlisted_by = ?, shortlisted_date = ?,
                    status = 'shortlisted'
                WHERE application_id = ?
            ''', (shortlisted_by, datetime.now().isoformat(), application_id))
            return True

    @staticmethod
    def reject_application(application_id: int, reason: str) -> bool:
        """Reject an application."""
        with transaction() as conn:
            conn.execute('''
                UPDATE staff_recruitment_applications
                SET status = 'rejected', rejection_reason = ?
                WHERE application_id = ?
            ''', (reason, application_id))
            return True

    # ==================== INTERVIEWS ====================

    @staticmethod
    def schedule_interview(application_id: int, interview_date: str,
                           interview_time: str, **data) -> int:
        """Schedule an interview."""
        with transaction() as conn:
            # Get applicant name
            app = conn.execute('''
                SELECT applicant_name FROM staff_recruitment_applications WHERE application_id = ?
            ''', (application_id,)).fetchone()

            cursor = conn.execute('''
                INSERT INTO interview_schedules (
                    application_id, applicant_name, interview_type,
                    interview_round, interview_date, interview_time,
                    duration_minutes, location, video_link, interviewers
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (application_id, app[0] if app else None,
                  data.get('interview_type', 'in-person'),
                  data.get('interview_round', 1), interview_date,
                  interview_time, data.get('duration_minutes', 60),
                  data.get('location'), data.get('video_link'),
                  data.get('interviewers')))

            # Update application status
            conn.execute('''
                UPDATE staff_recruitment_applications SET status = 'interview_scheduled'
                WHERE application_id = ?
            ''', (application_id,))

            return cursor.lastrowid

    @staticmethod
    def get_interviews(application_id: Optional[int] = None,
                       date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get interview schedules."""
        with get_connection() as conn:
            query = '''
                SELECT i.*, a.applicant_email, j.job_title, j.department
                FROM interview_schedules i
                JOIN staff_recruitment_applications a ON i.application_id = a.application_id
                JOIN staff_recruitment_postings j ON a.posting_id = j.posting_id
                WHERE 1=1
            '''
            params = []
            if application_id:
                query += ' AND i.application_id = ?'
                params.append(application_id)
            if date:
                query += ' AND i.interview_date = ?'
                params.append(date)
            query += ' ORDER BY i.interview_date, i.interview_time'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def record_interview_feedback(interview_id: int, **data) -> bool:
        """Record interview feedback."""
        with transaction() as conn:
            conn.execute('''
                UPDATE interview_schedules
                SET status = 'completed', feedback = ?, strengths = ?,
                    concerns = ?, recommendation = ?, overall_score = ?, notes = ?
                WHERE interview_id = ?
            ''', (data.get('feedback'), data.get('strengths'),
                  data.get('concerns'), data.get('recommendation'),
                  data.get('overall_score'), data.get('notes'), interview_id))
            return True

    # ==================== DEPARTMENT KPIs ====================

    @staticmethod
    def get_department_kpis(department: str,
                            year: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get KPIs for a department."""
        with get_connection() as conn:
            query = 'SELECT * FROM department_kpis WHERE department = ?'
            params = [department]
            if year:
                query += ' AND academic_year = ?'
                params.append(year)
            query += ' ORDER BY kpi_category, kpi_name'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def create_kpi(department: str, kpi_name: str, target_value: float,
                   **data) -> int:
        """Create a new KPI."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO department_kpis (
                    department, kpi_name, kpi_description, kpi_category,
                    target_value, current_value, unit, period,
                    academic_year, owner_id, owner_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (department, kpi_name, data.get('kpi_description'),
                  data.get('kpi_category'), target_value,
                  data.get('current_value', 0), data.get('unit'),
                  data.get('period', 'annual'), data.get('academic_year'),
                  data.get('owner_id'), data.get('owner_name')))
            return cursor.lastrowid

    @staticmethod
    def update_kpi(kpi_id: int, current_value: float,
                   notes: Optional[str] = None) -> bool:
        """Update KPI current value."""
        with transaction() as conn:
            # Get target to determine status
            kpi = conn.execute('''
                SELECT target_value FROM department_kpis WHERE kpi_id = ?
            ''', (kpi_id,)).fetchone()

            status = 'on_track'
            if kpi:
                progress = (current_value / kpi[0] * 100) if kpi[0] > 0 else 0
                if progress < 50:
                    status = 'at_risk'
                elif progress < 80:
                    status = 'needs_attention'

            conn.execute('''
                UPDATE department_kpis
                SET current_value = ?, status = ?, last_updated = ?, notes = ?
                WHERE kpi_id = ?
            ''', (current_value, status, datetime.now().isoformat(),
                  notes, kpi_id))
            return True

    # ==================== BUDGET REQUESTS ====================

    @staticmethod
    def get_budget_requests(department: Optional[str] = None,
                            status: Optional[str] = None,
                            limit: int = 50) -> List[Dict[str, Any]]:
        """Get budget requests."""
        with get_connection() as conn:
            query = 'SELECT * FROM budget_requests WHERE 1=1'
            params = []
            if department:
                query += ' AND department = ?'
                params.append(department)
            if status:
                query += ' AND status = ?'
                params.append(status)
            query += ' ORDER BY created_at DESC LIMIT ?'
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def create_budget_request(requested_by: str, department: str,
                              request_title: str, amount: float,
                              **data) -> int:
        """Create a budget request."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO budget_requests (
                    department, requested_by, requested_by_name,
                    request_title, request_description, amount_requested,
                    budget_category, justification, expected_benefits,
                    fiscal_year, priority
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (department, requested_by, data.get('requested_by_name'),
                  request_title, data.get('request_description'), amount,
                  data.get('budget_category'), data.get('justification'),
                  data.get('expected_benefits'), data.get('fiscal_year'),
                  data.get('priority', 'normal')))
            return cursor.lastrowid

    @staticmethod
    def approve_budget_request(request_id: int, reviewed_by: str,
                               approved_amount: float,
                               comments: Optional[str] = None) -> bool:
        """Approve a budget request."""
        with transaction() as conn:
            conn.execute('''
                UPDATE budget_requests
                SET status = 'approved', reviewed_by = ?, review_date = ?,
                    review_comments = ?, approved_amount = ?
                WHERE request_id = ?
            ''', (reviewed_by, datetime.now().isoformat(),
                  comments, approved_amount, request_id))
            return True

    @staticmethod
    def reject_budget_request(request_id: int, reviewed_by: str,
                              comments: str) -> bool:
        """Reject a budget request."""
        with transaction() as conn:
            conn.execute('''
                UPDATE budget_requests
                SET status = 'rejected', reviewed_by = ?, review_date = ?,
                    review_comments = ?
                WHERE request_id = ?
            ''', (reviewed_by, datetime.now().isoformat(),
                  comments, request_id))
            return True
