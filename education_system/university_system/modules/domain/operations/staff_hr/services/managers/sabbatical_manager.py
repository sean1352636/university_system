"""
Sabbatical / Study Leave Manager

Provides functionality for:
- Sabbatical application management
- Eligibility checking
- Three-level approval workflow
- Progress reporting
- Return planning
"""

from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608


class SabbaticalManager:
    """Manager for sabbatical and study leave applications."""

    # ==================== APPLICATION LIFECYCLE ====================

    @staticmethod
    def create_application(user_id: str, title: str, sabbatical_type: str = 'research',
                           research_proposal: str = None, host_institution: str = None,
                           start_date: str = None, end_date: str = None,
                           pay_percentage: int = 100, cover_arrangements: str = None,
                           funding_details: str = None, department: str = None) -> int:
        """Create a sabbatical application (draft)."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO sabbatical_applications (
                    user_id, title, sabbatical_type, research_proposal,
                    host_institution, start_date, end_date, pay_percentage,
                    cover_arrangements, funding_details, department,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                title,
                sabbatical_type,
                research_proposal,
                host_institution,
                start_date,
                end_date,
                pay_percentage,
                cover_arrangements,
                funding_details,
                department,
                'draft',
                datetime.now().isoformat(),
                datetime.now().isoformat(),
            ))
            application_id = cursor.lastrowid
            log_activity('create', 'sabbatical_application', details={
                'application_id': application_id, 'user_id': user_id,
                'sabbatical_type': sabbatical_type
            })
            return application_id

    @staticmethod
    def get_application(application_id: int) -> Optional[Dict[str, Any]]:
        """Get a single application by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM sabbatical_applications
                WHERE application_id = ?
            ''', (application_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_user_applications(user_id: str, status: str = None) -> List[Dict[str, Any]]:
        """Get applications for a user. Optionally filter by status."""
        with get_connection() as conn:
            query = '''
                SELECT * FROM sabbatical_applications
                WHERE user_id = ?
            '''
            params = [user_id]

            if status:
                query += ' AND status = ?'
                params.append(status)

            query += ' ORDER BY created_at DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_application(application_id: int, **data) -> None:
        """Update application fields. Only allowed when status is 'draft'."""
        if not data:
            return

        allowed_fields = {
            'title', 'sabbatical_type', 'research_proposal', 'host_institution',
            'start_date', 'end_date', 'pay_percentage', 'cover_arrangements',
            'funding_details',
        }

        fields = []
        values = []
        for key, value in data.items():
            if key in allowed_fields:
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return

        fields.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append(application_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE sabbatical_applications SET ' + ', '.join(fields) +
                " WHERE application_id = ? AND status = 'draft'",
                values)
            log_activity('update', 'sabbatical_application', details={
                'application_id': application_id,
                'updated_fields': list(data.keys())
            })

    @staticmethod
    def submit_application(application_id: int, user_id: str) -> None:
        """Submit application for approval.

        Checks eligibility, updates status, creates three approval levels,
        and logs the activity.
        """
        eligibility = SabbaticalManager.check_eligibility(user_id)
        if not eligibility['is_eligible']:
            raise ValueError(
                f"User is not eligible for sabbatical: {eligibility['reason']}"
            )

        with transaction() as conn:
            conn.execute('''
                UPDATE sabbatical_applications
                SET status = 'pending_approval', updated_at = ?
                WHERE application_id = ? AND status = 'draft'
            ''', (datetime.now().isoformat(), application_id))

            for level in ('department', 'faculty', 'provost'):
                conn.execute('''
                    INSERT INTO sabbatical_approvals (
                        application_id, approval_level, status, created_at
                    ) VALUES (?, ?, ?, ?)
                ''', (application_id, level, 'pending', datetime.now().isoformat()))

            log_activity('update', 'sabbatical_application', details={
                'application_id': application_id,
                'action': 'submitted',
                'user_id': user_id
            })

    # ==================== ELIGIBILITY ====================

    @staticmethod
    def check_eligibility(user_id: str) -> Dict[str, Any]:
        """Check if user is eligible for sabbatical.

        Checks the sabbatical_eligibility table first, then falls back to
        calculating from staff_contracts and previous sabbatical history.
        """
        with get_connection() as conn:
            # Check sabbatical_eligibility table first
            row = conn.execute('''
                SELECT * FROM sabbatical_eligibility
                WHERE user_id = ?
            ''', (user_id,)).fetchone()

            if row:
                record = dict(row)
                return {
                    'is_eligible': bool(record.get('is_eligible')),
                    'years_of_service': record.get('years_of_service', 0),
                    'last_sabbatical_end': record.get('last_sabbatical_end'),
                    'next_eligible_date': record.get('next_eligible_date'),
                    'reason': record.get('reason', ''),
                }

            # Calculate from staff_contracts
            contract_row = conn.execute('''
                SELECT MIN(start_date) as earliest_start
                FROM staff_contracts
                WHERE user_id = ?
            ''', (user_id,)).fetchone()

            if not contract_row or not contract_row['earliest_start']:
                return {
                    'is_eligible': False,
                    'years_of_service': 0,
                    'last_sabbatical_end': None,
                    'next_eligible_date': None,
                    'reason': 'No employment record found',
                }

            earliest_start = date.fromisoformat(str(contract_row['earliest_start']))
            today = date.today()
            years_of_service = (today - earliest_start).days / 365.25

            # Check last completed sabbatical
            last_sabbatical = conn.execute('''
                SELECT end_date FROM sabbatical_applications
                WHERE user_id = ? AND status = 'completed'
                ORDER BY end_date DESC LIMIT 1
            ''', (user_id,)).fetchone()

            last_sabbatical_end = None
            if last_sabbatical and last_sabbatical['end_date']:
                last_sabbatical_end = str(last_sabbatical['end_date'])

            # Determine eligibility
            is_eligible = True
            reason = 'Eligible for sabbatical'
            next_eligible_date = None

            if years_of_service < 6:
                is_eligible = False
                years_remaining = 6 - years_of_service
                next_eligible_date = (
                    today + timedelta(days=int(years_remaining * 365.25))
                ).isoformat()
                reason = (
                    f'Insufficient years of service ({years_of_service:.1f} years). '
                    f'Minimum 6 years required.'
                )
            elif last_sabbatical_end:
                last_end_date = date.fromisoformat(last_sabbatical_end)
                years_since_last = (today - last_end_date).days / 365.25
                if years_since_last < 6:
                    is_eligible = False
                    years_remaining = 6 - years_since_last
                    next_eligible_date = (
                        today + timedelta(days=int(years_remaining * 365.25))
                    ).isoformat()
                    reason = (
                        f'Last sabbatical ended {years_since_last:.1f} years ago. '
                        f'Must wait 6 years between sabbaticals.'
                    )

            return {
                'is_eligible': is_eligible,
                'years_of_service': round(years_of_service, 2),
                'last_sabbatical_end': last_sabbatical_end,
                'next_eligible_date': next_eligible_date,
                'reason': reason,
            }

    @staticmethod
    def update_eligibility(user_id: str, **data) -> None:
        """Update or create eligibility record."""
        with transaction() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO sabbatical_eligibility (
                    user_id, is_eligible, years_of_service,
                    last_sabbatical_end, next_eligible_date, reason, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                data.get('is_eligible', False),
                data.get('years_of_service', 0),
                data.get('last_sabbatical_end'),
                data.get('next_eligible_date'),
                data.get('reason', ''),
                datetime.now().isoformat(),
            ))
            log_activity('update', 'sabbatical_eligibility', details={
                'user_id': user_id
            })

    # ==================== APPROVAL WORKFLOW ====================

    @staticmethod
    def approve_application(approval_id: int, approver_id: str,
                            comments: str = None) -> None:
        """Approve at one level.

        Updates the approval record, checks if all three levels are approved,
        and if so updates the application status to 'approved'.
        """
        with transaction() as conn:
            conn.execute('''
                UPDATE sabbatical_approvals
                SET status = 'approved', approver_id = ?, comments = ?,
                    reviewed_date = ?
                WHERE approval_id = ?
            ''', (approver_id, comments, datetime.now().isoformat(), approval_id))

            # Get the application_id for this approval
            approval_row = conn.execute('''
                SELECT application_id FROM sabbatical_approvals
                WHERE approval_id = ?
            ''', (approval_id,)).fetchone()

            if approval_row:
                application_id = approval_row['application_id']

                # Check if all levels are now approved
                pending_count = conn.execute('''
                    SELECT COUNT(*) as cnt FROM sabbatical_approvals
                    WHERE application_id = ? AND status != 'approved'
                ''', (application_id,)).fetchone()

                if pending_count['cnt'] == 0:
                    conn.execute('''
                        UPDATE sabbatical_applications
                        SET status = 'approved', updated_at = ?
                        WHERE application_id = ?
                    ''', (datetime.now().isoformat(), application_id))

                log_activity('update', 'sabbatical_approval', details={
                    'approval_id': approval_id,
                    'application_id': application_id,
                    'action': 'approved',
                    'approver': approver_id
                })

    @staticmethod
    def reject_application(approval_id: int, approver_id: str,
                           comments: str = None) -> None:
        """Reject application.

        Updates the approval record and sets the application status to 'rejected'.
        """
        with transaction() as conn:
            conn.execute('''
                UPDATE sabbatical_approvals
                SET status = 'rejected', approver_id = ?, comments = ?,
                    reviewed_date = ?
                WHERE approval_id = ?
            ''', (approver_id, comments, datetime.now().isoformat(), approval_id))

            # Get the application_id and reject the whole application
            approval_row = conn.execute('''
                SELECT application_id FROM sabbatical_approvals
                WHERE approval_id = ?
            ''', (approval_id,)).fetchone()

            if approval_row:
                application_id = approval_row['application_id']

                conn.execute('''
                    UPDATE sabbatical_applications
                    SET status = 'rejected', updated_at = ?
                    WHERE application_id = ?
                ''', (datetime.now().isoformat(), application_id))

                log_activity('update', 'sabbatical_approval', details={
                    'approval_id': approval_id,
                    'application_id': application_id,
                    'action': 'rejected',
                    'approver': approver_id
                })

    @staticmethod
    def get_pending_approvals(approver_id: str = None) -> List[Dict[str, Any]]:
        """Get pending sabbatical approvals."""
        with get_connection() as conn:
            query = '''
                SELECT sa.*, app.title, app.user_id, app.sabbatical_type,
                       app.start_date, app.end_date, app.department
                FROM sabbatical_approvals sa
                JOIN sabbatical_applications app
                    ON sa.application_id = app.application_id
                WHERE sa.status = 'pending'
            '''
            params = []

            if approver_id:
                query += ' AND sa.approver_id = ?'
                params.append(approver_id)

            query += ' ORDER BY sa.created_at ASC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    # ==================== PROGRESS REPORTING ====================

    @staticmethod
    def submit_progress_report(application_id: int, report_type: str = 'interim',
                               content: str = '', achievements: str = None,
                               challenges: str = None) -> int:
        """Submit a progress report for a sabbatical."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO sabbatical_progress_reports (
                    application_id, report_type, content, achievements,
                    challenges, report_date, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                application_id,
                report_type,
                content,
                achievements,
                challenges,
                datetime.now().isoformat(),
                'submitted',
            ))
            report_id = cursor.lastrowid
            log_activity('create', 'sabbatical_progress_report', details={
                'report_id': report_id, 'application_id': application_id,
                'report_type': report_type
            })
            return report_id

    @staticmethod
    def get_progress_reports(application_id: int) -> List[Dict[str, Any]]:
        """Get progress reports for an application."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM sabbatical_progress_reports
                WHERE application_id = ?
                ORDER BY report_date DESC
            ''', (application_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def review_progress_report(report_id: int, reviewer_id: str,
                               status: str, comments: str = None) -> None:
        """Review a progress report."""
        with transaction() as conn:
            conn.execute('''
                UPDATE sabbatical_progress_reports
                SET status = ?, reviewer_id = ?, review_comments = ?,
                    review_date = ?
                WHERE report_id = ?
            ''', (status, reviewer_id, comments,
                  datetime.now().isoformat(), report_id))
            log_activity('update', 'sabbatical_progress_report', details={
                'report_id': report_id, 'action': 'reviewed',
                'status': status, 'reviewer': reviewer_id
            })

    # ==================== RETURN PLANNING ====================

    @staticmethod
    def create_return_plan(application_id: int, return_date: str,
                           transition_period_weeks: int = 4,
                           research_outputs: str = None,
                           knowledge_sharing_plan: str = None) -> int:
        """Create a return plan for a sabbatical."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO sabbatical_return_plans (
                    application_id, return_date, transition_period_weeks,
                    research_outputs, knowledge_sharing_plan,
                    status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                application_id,
                return_date,
                transition_period_weeks,
                research_outputs,
                knowledge_sharing_plan,
                'pending',
                datetime.now().isoformat(),
            ))
            plan_id = cursor.lastrowid
            log_activity('create', 'sabbatical_return_plan', details={
                'plan_id': plan_id, 'application_id': application_id
            })
            return plan_id

    @staticmethod
    def get_return_plan(application_id: int) -> Optional[Dict[str, Any]]:
        """Get return plan for an application."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM sabbatical_return_plans
                WHERE application_id = ?
            ''', (application_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def update_return_plan(plan_id: int, **data) -> None:
        """Update return plan details."""
        if not data:
            return

        fields = []
        values = []
        for key, value in data.items():
            if key not in ('plan_id', 'application_id', 'created_at'):
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return

        fields.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append(plan_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE sabbatical_return_plans SET ' + ', '.join(fields) +
                ' WHERE plan_id = ?',
                values)
            log_activity('update', 'sabbatical_return_plan', details={
                'plan_id': plan_id, 'updated_fields': list(data.keys())
            })

    @staticmethod
    def complete_return(application_id: int, user_id: str) -> None:
        """Complete the return from sabbatical.

        Updates application status, return plan status, and eligibility records.
        """
        now = datetime.now().isoformat()
        today = date.today()
        next_eligible = (today + timedelta(days=int(6 * 365.25))).isoformat()

        with transaction() as conn:
            # Update application status to completed
            conn.execute('''
                UPDATE sabbatical_applications
                SET status = 'completed', updated_at = ?
                WHERE application_id = ?
            ''', (now, application_id))

            # Update return plan status to completed
            conn.execute('''
                UPDATE sabbatical_return_plans
                SET status = 'completed', updated_at = ?
                WHERE application_id = ?
            ''', (now, application_id))

            # Update sabbatical eligibility
            conn.execute('''
                INSERT OR REPLACE INTO sabbatical_eligibility (
                    user_id, is_eligible, last_sabbatical_end,
                    next_eligible_date, reason, updated_at
                ) VALUES (?, 0, ?, ?, ?, ?)
            ''', (
                user_id,
                today.isoformat(),
                next_eligible,
                'Sabbatical recently completed. Next eligible in 6 years.',
                now,
            ))

            log_activity('update', 'sabbatical_application', details={
                'application_id': application_id,
                'action': 'return_completed',
                'user_id': user_id
            })
