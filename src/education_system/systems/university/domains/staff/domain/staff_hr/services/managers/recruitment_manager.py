"""
Recruitment Manager

Handles job postings, applications, interview scheduling,
department KPIs, and budget requests.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.systems.university.domains.staff.domain.staff_hr import access
from education_system.systems.university.domains.staff.domain.staff_hr.services.managers import _people as people
from education_system.systems.university.infrastructure.database.db import get_connection, transaction

try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
except ImportError:
    def log_activity(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)

#: Posting statuses a recruiter may set by hand.
POSTING_STATUSES = ('draft', 'open', 'closed', 'filled', 'cancelled')


def _can_recruit(who: Any, conn) -> bool:
    return access.can(who, 'recruitment', conn) or access.is_hr(who, conn)


def _recruiter(actor: Any, by: Any, conn, what: str) -> dict:
    """The signed-in ``actor`` (else the person ``by`` names), who must be in
    recruitment or HR — applicants' details and hiring decisions are theirs."""
    who = people.decider(actor, by, conn)
    if not _can_recruit(who, conn):
        raise PermissionError(f"Only recruitment or HR can {what}")
    return who


def _sees_drafts(actor: Any, conn) -> bool:
    """Recruitment and HR see draft / closed postings; everyone else only
    open vacancies."""
    return actor is not None and _can_recruit(actor, conn)


class RecruitmentManager:
    """Manager for recruitment and department management."""

    # ==================== JOB POSTINGS ====================

    @staticmethod
    def get_staff_recruitment_postings(status: Optional[str] = None,
                         department: Optional[str] = None,
                         limit: int = 50, actor: Any = None) -> List[Dict[str, Any]]:
        """Get job postings with optional filters (open vacancies only, unless
        ``actor`` is in recruitment or HR)."""
        with get_connection() as conn:
            query = 'SELECT * FROM staff_recruitment_postings WHERE 1=1'
            params = []
            if not _sees_drafts(actor, conn):
                query += " AND status = 'open'"
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
                       actor: Any = None, **data) -> int:
        """Create a new job posting (recruitment or HR: ``actor``, else the
        person ``posted_by`` names)."""
        with transaction() as conn:
            who = _recruiter(actor, posted_by, conn, "create job postings")
            posted_by = who['username']
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
            access.audit(conn, who, 'recruitment.posting_created', entity='staff_recruitment_postings',
                         entity_id=posting_id)
            log_activity('create', 'job_posting', details={
                'posting_id': posting_id, 'title': job_title
            })
            return posting_id

    @staticmethod
    def update_posting_status(posting_id: int, status: str, actor: Any = None) -> bool:
        """Update job posting status (recruitment or HR)."""
        if status not in POSTING_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(POSTING_STATUSES)}")
        with transaction() as conn:
            who = _recruiter(actor, None, conn, "change job postings")
            access.audit(conn, who, f'recruitment.posting_{status}',
                         entity='staff_recruitment_postings', entity_id=posting_id)
            conn.execute('''
                UPDATE staff_recruitment_postings SET status = ? WHERE posting_id = ?
            ''', (status, posting_id))
            return True

    @staticmethod
    def publish_posting(posting_id: int, actor: Any = None) -> bool:
        """Publish a job posting (recruitment or HR)."""
        with transaction() as conn:
            who = _recruiter(actor, None, conn, "publish job postings")
            access.audit(conn, who, 'recruitment.posting_published',
                         entity='staff_recruitment_postings', entity_id=posting_id)
            conn.execute('''
                UPDATE staff_recruitment_postings
                SET status = 'open', post_date = ?
                WHERE posting_id = ? AND status = 'draft'
            ''', (datetime.now().strftime('%Y-%m-%d'), posting_id))
            return True

    @staticmethod
    def get_posting(posting_id: int, actor: Any = None) -> Optional[Dict[str, Any]]:
        """One job posting (an open one, unless ``actor`` is in recruitment or HR)."""
        with get_connection() as conn:
            row = conn.execute('SELECT * FROM staff_recruitment_postings WHERE posting_id = ?',
                               (int(posting_id),)).fetchone()
            if row and row['status'] != 'open' and not _sees_drafts(actor, conn):
                return None
            return dict(row) if row else None

    @staticmethod
    def update_posting(posting_id: int, actor: Any = None, **data) -> bool:
        """Change a posting's details (``None`` values are left as they are;
        recruitment or HR)."""
        allowed = ('job_title', 'department', 'job_type', 'location', 'description',
                   'requirements', 'responsibilities', 'salary_range', 'benefits',
                   'closing_date', 'hiring_manager_id', 'hiring_manager_name')
        changes = {k: v for k, v in data.items() if k in allowed and v not in (None, '')}
        if not changes:
            return False
        with transaction() as conn:
            who = _recruiter(actor, None, conn, "change job postings")
            access.audit(conn, who, 'recruitment.posting_updated',
                         entity='staff_recruitment_postings', entity_id=posting_id,
                         details={'fields': sorted(changes)})
            conn.execute('UPDATE staff_recruitment_postings SET '  # nosec B608 - fixed names
                         + ', '.join(f'{k} = ?' for k in changes) + ' WHERE posting_id = ?',
                         (*changes.values(), int(posting_id)))
            log_activity('update', 'job_posting', details={
                'posting_id': posting_id, 'fields': sorted(changes)})
            return True

    @staticmethod
    def close_posting(posting_id: int, actor: Any = None) -> bool:
        """Close a posting to new applications (recruitment or HR)."""
        return RecruitmentManager.update_posting_status(int(posting_id), 'closed', actor=actor)

    @staticmethod
    def get_active_postings(limit: int = 50, actor: Any = None) -> List[Dict[str, Any]]:
        """Open postings with their application counts (open vacancies are
        public; ``actor`` is accepted for symmetry with the other calls)."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT p.*, (SELECT COUNT(*) FROM staff_recruitment_applications a
                             WHERE a.posting_id = p.posting_id) AS applicant_count
                FROM staff_recruitment_postings p
                WHERE p.status = 'open'
                ORDER BY p.post_date DESC LIMIT ?
            ''', (limit,)).fetchall()
            return [dict(row) for row in rows]

    # ==================== APPLICATIONS ====================

    @staticmethod
    def get_applications(posting_id: Optional[int] = None,
                         status: Optional[str] = None,
                         limit: int = 50, actor: Any = None) -> List[Dict[str, Any]]:
        """Get job applications (recruitment or HR)."""
        with get_connection() as conn:
            _recruiter(actor, None, conn, "see job applications")
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
                           applicant_email: str, actor: Any = None, **data) -> int:
        """Submit a job application — anyone may apply to an open posting;
        recruitment or HR (``actor``) may also enter one for any posting."""
        with transaction() as conn:
            # Get job title
            job = conn.execute('''
                SELECT job_title, status FROM staff_recruitment_postings WHERE posting_id = ?
            ''', (posting_id,)).fetchone()
            if not job:
                raise ValueError(f"Job posting {posting_id} not found")
            if job[1] != 'open' and not _sees_drafts(actor, conn):
                raise ValueError("This vacancy is not open for applications")

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
    def shortlist_application(application_id: int, shortlisted_by: str,
                              actor: Any = None) -> bool:
        """Shortlist an application (recruitment or HR: ``actor``, else the
        person ``shortlisted_by`` names)."""
        with transaction() as conn:
            who = _recruiter(actor, shortlisted_by, conn, "shortlist applications")
            shortlisted_by = who['username']
            access.audit(conn, who, 'recruitment.shortlisted',
                         entity='staff_recruitment_applications', entity_id=application_id)
            conn.execute('''
                UPDATE staff_recruitment_applications
                SET shortlisted = 1, shortlisted_by = ?, shortlisted_date = ?,
                    status = 'shortlisted'
                WHERE application_id = ?
            ''', (shortlisted_by, datetime.now().isoformat(), application_id))
            return True

    @staticmethod
    def reject_application(application_id: int, reason: str, actor: Any = None) -> bool:
        """Reject an application (recruitment or HR)."""
        with transaction() as conn:
            who = _recruiter(actor, None, conn, "reject applications")
            access.audit(conn, who, 'recruitment.rejected',
                         entity='staff_recruitment_applications', entity_id=application_id)
            conn.execute('''
                UPDATE staff_recruitment_applications
                SET status = 'rejected', rejection_reason = ?
                WHERE application_id = ?
            ''', (reason, application_id))
            return True

    @staticmethod
    def get_application(application_id: int, actor: Any = None) -> Optional[Dict[str, Any]]:
        """One application, with its posting's department and job type
        (recruitment or HR)."""
        with get_connection() as conn:
            _recruiter(actor, None, conn, "see job applications")
            row = conn.execute('''
                SELECT a.*, j.department, j.job_type
                FROM staff_recruitment_applications a
                LEFT JOIN staff_recruitment_postings j ON a.posting_id = j.posting_id
                WHERE a.application_id = ?
            ''', (int(application_id),)).fetchone()
            return dict(row) if row else None

    #: Statuses an application can be moved to by hand (offers and hires
    #: move through ``staff_hr.hiring``).
    MANUAL_STATUSES = ('received', 'under_review', 'shortlisted', 'interview_scheduled',
                       'interviewed', 'rejected', 'withdrawn')

    @staticmethod
    def update_application_status(application_id: int, status: str,
                                  notes: Optional[str] = None, actor: Any = None) -> bool:
        """Move an application to a status in :data:`MANUAL_STATUSES`
        (recruitment or HR)."""
        if status not in RecruitmentManager.MANUAL_STATUSES:
            raise ValueError("Offers and hires are made from the Offers and Hire steps; "
                             f"status must be one of: {', '.join(RecruitmentManager.MANUAL_STATUSES)}")
        with transaction() as conn:
            who = _recruiter(actor, None, conn, "change applications")
            current = conn.execute('SELECT status FROM staff_recruitment_applications '
                                   'WHERE application_id = ?', (int(application_id),)).fetchone()
            if not current:
                raise ValueError(f"Application {application_id} not found")
            if current[0] == 'hired':
                raise ValueError("The applicant has been hired")
            conn.execute('''
                UPDATE staff_recruitment_applications
                SET status = ?, notes = COALESCE(?, notes)
                WHERE application_id = ?
            ''', (status, notes, int(application_id)))
            access.audit(conn, who, f'recruitment.application_{status}',
                         entity='staff_recruitment_applications', entity_id=application_id)
            log_activity('update', 'job_application', details={
                'application_id': application_id, 'status': status})
            return True

    @staticmethod
    def get_statistics(actor: Any = None) -> Dict[str, Any]:
        """Headline recruitment numbers (recruitment or HR)."""
        month = datetime.now().strftime('%Y-%m')
        with get_connection() as conn:
            _recruiter(actor, None, conn, "see recruitment statistics")
            def one(sql, *params):
                try:
                    return conn.execute(sql, params).fetchone()[0] or 0
                except Exception:
                    return 0
            return {
                'active_postings': one("SELECT COUNT(*) FROM staff_recruitment_postings "
                                       "WHERE status = 'open'"),
                'total_applicants': one("SELECT COUNT(*) FROM staff_recruitment_applications"),
                'pending_reviews': one("SELECT COUNT(*) FROM staff_recruitment_applications "
                                       "WHERE status IN ('received', 'under_review')"),
                'interviews_scheduled': one("SELECT COUNT(*) FROM staff_recruitment_interviews "
                                            "WHERE status = 'scheduled'"),
                'offers_extended': one("SELECT COUNT(*) FROM staff_hr_offers "
                                       "WHERE status IN ('made', 'accepted')"),
                'hired_this_month': one("SELECT COUNT(*) FROM staff_hr_offers "
                                        "WHERE status = 'hired' AND substr(hired_at, 1, 7) = ?",
                                        month),
            }

    # ==================== INTERVIEWS ====================

    @staticmethod
    def schedule_interview(application_id: int, interview_date: str,
                           interview_time: str, actor: Any = None, **data) -> int:
        """Schedule an interview (recruitment or HR)."""
        with transaction() as conn:
            who = _recruiter(actor, None, conn, "schedule interviews")
            # Get applicant name
            app = conn.execute('''
                SELECT applicant_name FROM staff_recruitment_applications WHERE application_id = ?
            ''', (application_id,)).fetchone()

            cursor = conn.execute('''
                INSERT INTO staff_recruitment_interviews (
                    application_id, applicant_name, interview_type,
                    interview_round, interview_date, interview_time,
                    duration_minutes, location, video_link, interviewers, scheduled_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (application_id, app[0] if app else None,
                  data.get('interview_type', 'in-person'),
                  data.get('interview_round', 1), interview_date,
                  interview_time, data.get('duration_minutes', 60),
                  data.get('location'), data.get('video_link'),
                  data.get('interviewers'), who['username']))

            # Update application status
            conn.execute('''
                UPDATE staff_recruitment_applications SET status = 'interview_scheduled'
                WHERE application_id = ?
            ''', (application_id,))
            access.audit(conn, who, 'recruitment.interview_scheduled',
                         entity='staff_recruitment_interviews', entity_id=cursor.lastrowid)

            return cursor.lastrowid

    @staticmethod
    def get_interviews(application_id: Optional[int] = None,
                       date: Optional[str] = None, actor: Any = None) -> List[Dict[str, Any]]:
        """Get interview schedules (recruitment or HR)."""
        with get_connection() as conn:
            _recruiter(actor, None, conn, "see interviews")
            query = '''
                SELECT i.*, a.applicant_email, j.job_title, j.department
                FROM staff_recruitment_interviews i
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
    def record_interview_feedback(interview_id: int, actor: Any = None, **data) -> bool:
        """Record interview feedback — recruitment, HR, or someone named on
        the interview panel."""
        with transaction() as conn:
            who = people.decider(actor, None, conn)
            if not _can_recruit(who, conn):
                row = conn.execute("SELECT interviewers FROM staff_recruitment_interviews "
                                   "WHERE interview_id = ?", (interview_id,)).fetchone()
                panel = {p.strip().lower() for p in str((row[0] if row else '') or '')
                         .replace(';', ',').split(',') if p.strip()}
                if who['username'].lower() not in panel:
                    raise PermissionError("Only the interview panel, recruitment or HR can "
                                          "record interview feedback")
            access.audit(conn, who, 'recruitment.interview_feedback',
                         entity='staff_recruitment_interviews', entity_id=interview_id)
            conn.execute('''
                UPDATE staff_recruitment_interviews
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
                   actor: Any = None, **data) -> int:
        """Create a new KPI (HR)."""
        with transaction() as conn:
            people.require_hr(people.decider(actor, None, conn), conn, "set department KPIs")
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
                   notes: Optional[str] = None, actor: Any = None) -> bool:
        """Update KPI current value (HR or the KPI's owner)."""
        with transaction() as conn:
            who = people.decider(actor, None, conn)
            owner = conn.execute("SELECT owner_id FROM department_kpis WHERE kpi_id = ?",
                                 (kpi_id,)).fetchone()
            if not (access.is_hr(who, conn)
                    or (owner and owner[0] and access.staff_key(owner[0], conn) == who['username'])):
                raise PermissionError("Only HR or the KPI's owner can update it")
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
                            limit: int = 50, actor: Any = None) -> List[Dict[str, Any]]:
        """Get budget requests: HR sees all, anyone else only their own."""
        with get_connection() as conn:
            who = people.decider(actor, None, conn)
            query = 'SELECT * FROM budget_requests WHERE 1=1'
            params = []
            if not access.is_hr(who, conn):
                query += ' AND requested_by = ?'
                params.append(who['username'])
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
                              actor: Any = None, **data) -> int:
        """Create a budget request (line managers and HR: ``actor``, else the
        person ``requested_by`` names)."""
        with transaction() as conn:
            who = people.decider(actor, requested_by, conn)
            if not access.can(who, 'manager', conn):
                raise PermissionError("Only line managers or HR can raise budget requests")
            requested_by = who['username']
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
                               comments: Optional[str] = None, actor: Any = None) -> bool:
        """Approve a pending budget request (an HR administrator, never on
        their own request)."""
        with transaction() as conn:
            reviewed_by = _review_budget(conn, request_id, actor, reviewed_by, 'approved')
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
                              comments: str, actor: Any = None) -> bool:
        """Reject a pending budget request (as for :meth:`approve_budget_request`)."""
        with transaction() as conn:
            reviewed_by = _review_budget(conn, request_id, actor, reviewed_by, 'rejected')
            conn.execute('''
                UPDATE budget_requests
                SET status = 'rejected', reviewed_by = ?, review_date = ?,
                    review_comments = ?
                WHERE request_id = ?
            ''', (reviewed_by, datetime.now().isoformat(),
                  comments, request_id))
            return True


def _review_budget(conn, request_id: int, actor: Any, reviewed_by: Any, outcome: str) -> str:
    who = people.decider(actor, reviewed_by, conn)
    if not access.is_hr_admin(who, conn):
        raise PermissionError("Only an HR administrator can decide budget requests")
    row = conn.execute("SELECT requested_by, status FROM budget_requests WHERE request_id = ?",
                       (request_id,)).fetchone()
    if not row:
        raise ValueError(f"Budget request {request_id} not found")
    if access.staff_key(row[0], conn) == who['username']:
        raise PermissionError("You cannot decide your own budget request")
    if row[1] not in (None, '', 'pending', 'submitted'):
        raise ValueError("This budget request has already been decided")
    access.audit(conn, who, f'recruitment.budget_{outcome}', entity='budget_requests',
                 entity_id=request_id)
    return who['username']
