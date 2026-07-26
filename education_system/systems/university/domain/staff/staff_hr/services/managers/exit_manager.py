"""
Exit Manager - Exit management and turnover analytics.

Provides functionality for:
- Exit interview scheduling
- Exit checklist management
- Turnover rate calculations
- Department-wise analytics
- Retention recommendations
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608


class ExitManager:
    """Manager for exit interviews and turnover analytics."""

    # ==================== EXIT INTERVIEWS ====================

    @staticmethod
    def create_exit_interview(user_id: str, **data) -> int:
        """Create an exit interview record."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO exit_interviews (
                    user_id, interviewer_id, scheduled_date, interview_date,
                    interview_method, status, last_working_day, tenure_months,
                    department, job_title, manager_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                data.get('interviewer_id'),
                data.get('scheduled_date'),
                data.get('interview_date'),
                data.get('interview_method', 'in_person'),
                data.get('status', 'scheduled'),
                data.get('last_working_day'),
                data.get('tenure_months'),
                data.get('department'),
                data.get('job_title'),
                data.get('manager_id'),
            ))
            interview_id = cursor.lastrowid
            log_activity('create', 'exit_interview', details={
                'interview_id': interview_id, 'user_id': user_id
            })
            return interview_id

    @staticmethod
    def get_exit_interview(interview_id: int) -> Optional[Dict[str, Any]]:
        """Get an exit interview by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM exit_interviews WHERE interview_id = ?
            ''', (interview_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_user_exit_interview(user_id: str) -> Optional[Dict[str, Any]]:
        """Get exit interview for a user."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM exit_interviews
                WHERE user_id = ?
                ORDER BY created_at DESC LIMIT 1
            ''', (user_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_pending_interviews(interviewer_id: str = None) -> List[Dict[str, Any]]:
        """Get pending exit interviews."""
        with get_connection() as conn:
            query = '''
                SELECT e.*, p.employee_id
                FROM exit_interviews e
                LEFT JOIN staff_profiles p ON e.user_id = p.user_id
                WHERE e.status IN ('scheduled', 'pending')
            '''
            params = []

            if interviewer_id:
                query += ' AND e.interviewer_id = ?'
                params.append(interviewer_id)

            query += ' ORDER BY e.scheduled_date ASC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_all_exit_interviews(status: str = None, department: str = None,
                                from_date: str = None, to_date: str = None) -> List[Dict[str, Any]]:
        """Get all exit interviews with filters."""
        with get_connection() as conn:
            query = 'SELECT * FROM exit_interviews WHERE 1=1'
            params = []

            if status:
                query += ' AND status = ?'
                params.append(status)

            if department:
                query += ' AND department = ?'
                params.append(department)

            if from_date:
                query += ' AND last_working_day >= ?'
                params.append(from_date)

            if to_date:
                query += ' AND last_working_day <= ?'
                params.append(to_date)

            query += ' ORDER BY last_working_day DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_exit_interview(interview_id: int, **data) -> bool:
        """Update an exit interview."""
        if not data:
            return False

        fields = []
        values = []
        for key, value in data.items():
            if key not in ('interview_id', 'created_at', 'user_id'):
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return False

        fields.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append(interview_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE exit_interviews SET ' + ', '.join(fields) + ' WHERE interview_id = ?',
                values)
            log_activity('update', 'exit_interview', details={
                'interview_id': interview_id, 'updated_fields': list(data.keys())
            })
            return True

    @staticmethod
    def complete_exit_interview(interview_id: int, **feedback) -> bool:
        """Complete an exit interview with feedback."""
        with transaction() as conn:
            conn.execute('''
                UPDATE exit_interviews SET
                    status = 'completed', interview_date = ?,
                    reason_for_leaving = ?, reason_category = ?,
                    destination = ?, new_employer = ?, new_role = ?,
                    salary_factor = ?, career_growth_factor = ?,
                    work_life_balance_factor = ?, management_factor = ?,
                    culture_factor = ?, job_satisfaction_rating = ?,
                    manager_rating = ?, work_environment_rating = ?,
                    growth_opportunities_rating = ?, compensation_rating = ?,
                    overall_rating = ?, liked_most = ?, liked_least = ?,
                    suggestions = ?, would_recommend = ?, would_return = ?,
                    additional_comments = ?, confidential_notes = ?,
                    updated_at = ?
                WHERE interview_id = ?
            ''', (
                datetime.now().isoformat(),
                feedback.get('reason_for_leaving'),
                feedback.get('reason_category'),
                feedback.get('destination'),
                feedback.get('new_employer'),
                feedback.get('new_role'),
                feedback.get('salary_factor', False),
                feedback.get('career_growth_factor', False),
                feedback.get('work_life_balance_factor', False),
                feedback.get('management_factor', False),
                feedback.get('culture_factor', False),
                feedback.get('job_satisfaction_rating'),
                feedback.get('manager_rating'),
                feedback.get('work_environment_rating'),
                feedback.get('growth_opportunities_rating'),
                feedback.get('compensation_rating'),
                feedback.get('overall_rating'),
                feedback.get('liked_most'),
                feedback.get('liked_least'),
                feedback.get('suggestions'),
                feedback.get('would_recommend'),
                feedback.get('would_return'),
                feedback.get('additional_comments'),
                feedback.get('confidential_notes'),
                datetime.now().isoformat(),
                interview_id
            ))

            log_activity('update', 'exit_interview', details={
                'interview_id': interview_id, 'action': 'completed'
            })
            return True

    # ==================== EXIT CHECKLIST TEMPLATES ====================

    @staticmethod
    def get_checklist_templates(department: str = None) -> List[Dict[str, Any]]:
        """Get exit checklist templates."""
        with get_connection() as conn:
            query = '''
                SELECT * FROM exit_checklist_templates
                WHERE is_active = 1
            '''
            params = []

            if department:
                query += ' AND (department = ? OR department IS NULL)'
                params.append(department)

            query += ' ORDER BY is_default DESC, name'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_template_items(template_id: int) -> List[Dict[str, Any]]:
        """Get items for a checklist template."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM exit_checklist_template_items
                WHERE template_id = ?
                ORDER BY order_index
            ''', (template_id,)).fetchall()
            # Add aliases for CLI compatibility
            result = []
            for row in rows:
                item = dict(row)
                item['is_required'] = item.get('is_mandatory', False)
                item['order'] = item.get('order_index', 0)
                result.append(item)
            return result

    @staticmethod
    def create_template(name: str, **data) -> int:
        """Create a new checklist template."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO exit_checklist_templates (
                    name, description, department, role_type, is_default
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                name,
                data.get('description'),
                data.get('department'),
                data.get('role_type'),
                data.get('is_default', False),
            ))
            template_id = cursor.lastrowid
            log_activity('create', 'exit_checklist_template', details={'template_id': template_id})
            return template_id

    @staticmethod
    def add_template_item(template_id: int, task_name: str, **data) -> int:
        """Add an item to a checklist template."""
        with transaction() as conn:
            # Support both CLI and schema column names
            is_mandatory = data.get('is_mandatory', data.get('is_required', True))
            order_index = data.get('order_index', data.get('order', 0))

            cursor = conn.execute('''
                INSERT INTO exit_checklist_template_items (
                    template_id, task_name, description, responsible_party,
                    category, days_before_exit, is_mandatory, order_index
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                template_id,
                task_name,
                data.get('description'),
                data.get('responsible_party'),
                data.get('category'),
                data.get('days_before_exit', 0),
                is_mandatory,
                order_index,
            ))
            item_id = cursor.lastrowid
            log_activity('create', 'exit_checklist_template_item', details={'item_id': item_id})
            return item_id

    # ==================== USER EXIT CHECKLIST ====================

    @staticmethod
    def create_user_checklist(user_id: str, last_working_day: str,
                              template_id: int = None) -> List[int]:
        """Create an exit checklist for a departing user."""
        with transaction() as conn:
            checklist_ids = []

            # Get template items
            if template_id:
                items = ExitManager.get_template_items(template_id)
            else:
                # Get default template
                row = conn.execute('''
                    SELECT template_id FROM exit_checklist_templates
                    WHERE is_default = 1 AND is_active = 1 LIMIT 1
                ''').fetchone()
                if row:
                    items = ExitManager.get_template_items(row['template_id'])
                else:
                    items = []

            last_date = datetime.fromisoformat(last_working_day)

            for item in items:
                due_date = (last_date + timedelta(days=item.get('days_before_exit', 0))).isoformat()

                cursor = conn.execute('''
                    INSERT INTO exit_checklist (
                        user_id, template_id, task_name, description,
                        category, responsible_party, due_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    template_id,
                    item['task_name'],
                    item.get('description'),
                    item.get('category'),
                    item.get('responsible_party'),
                    due_date,
                ))
                checklist_ids.append(cursor.lastrowid)

            log_activity('create', 'exit_checklist', details={
                'user_id': user_id, 'items_created': len(checklist_ids)
            })
            return checklist_ids

    @staticmethod
    def get_user_checklist(user_id: str) -> List[Dict[str, Any]]:
        """Get exit checklist for a user."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM exit_checklist
                WHERE user_id = ?
                ORDER BY due_date, checklist_id
            ''', (user_id,)).fetchall()
            # Add aliases for CLI compatibility
            result = []
            for row in rows:
                item = dict(row)
                # Add aliases (CLI uses is_required/assigned_to, schema uses is_mandatory/responsible_party)
                item['is_required'] = item.get('is_mandatory', False)
                item['assigned_to'] = item.get('responsible_party')
                result.append(item)
            return result

    @staticmethod
    def update_checklist_item(checklist_id: int, **data) -> bool:
        """Update a checklist item."""
        if not data:
            return False

        fields = []
        values = []
        for key, value in data.items():
            if key not in ('checklist_id', 'created_at', 'user_id'):
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return False
        values.append(checklist_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE exit_checklist SET ' + ', '.join(fields) + ' WHERE checklist_id = ?',
                values)
            log_activity('update', 'exit_checklist', details={'checklist_id': checklist_id})
            return True

    @staticmethod
    def complete_checklist_item(checklist_id: int, completed_by: str,
                                notes: str = None) -> bool:
        """Mark a checklist item as completed."""
        with transaction() as conn:
            conn.execute('''
                UPDATE exit_checklist
                SET completed = 1, completed_date = ?, completed_by = ?, notes = ?
                WHERE checklist_id = ?
            ''', (datetime.now().isoformat(), completed_by, notes, checklist_id))
            log_activity('update', 'exit_checklist', details={
                'checklist_id': checklist_id, 'action': 'completed'
            })
            return True

    @staticmethod
    def get_checklist_progress(user_id: str) -> Dict[str, Any]:
        """Get checklist completion progress for a user."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed
                FROM exit_checklist
                WHERE user_id = ?
            ''', (user_id,)).fetchone()

            total = row['total'] if row else 0
            completed = row['completed'] if row else 0

            return {
                'total': total,
                'completed': completed,
                'remaining': total - completed,
                'percentage': round((completed / total) * 100, 1) if total > 0 else 0
            }

    # ==================== KNOWLEDGE TRANSFER ====================

    @staticmethod
    def create_knowledge_transfer(departing_user_id: str, **data) -> int:
        """Create a knowledge transfer record."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO knowledge_transfer (
                    departing_user_id, receiving_user_id, topic, description,
                    documentation_path, priority, status, scheduled_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                departing_user_id,
                data.get('receiving_user_id'),
                data.get('topic'),
                data.get('description'),
                data.get('documentation_path'),
                data.get('priority', 'medium'),
                'pending',
                data.get('scheduled_date'),
            ))
            transfer_id = cursor.lastrowid
            log_activity('create', 'knowledge_transfer', details={
                'transfer_id': transfer_id, 'departing_user_id': departing_user_id
            })
            return transfer_id

    @staticmethod
    def get_knowledge_transfers(user_id: str, as_departing: bool = True) -> List[Dict[str, Any]]:
        """Get knowledge transfer records for a user."""
        with get_connection() as conn:
            if as_departing:
                rows = conn.execute('''
                    SELECT * FROM knowledge_transfer
                    WHERE departing_user_id = ?
                    ORDER BY priority DESC, scheduled_date
                ''', (user_id,)).fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM knowledge_transfer
                    WHERE receiving_user_id = ?
                    ORDER BY priority DESC, scheduled_date
                ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def complete_knowledge_transfer(transfer_id: int, notes: str = None) -> bool:
        """Mark a knowledge transfer as completed."""
        with transaction() as conn:
            conn.execute('''
                UPDATE knowledge_transfer
                SET status = 'completed', completed_date = ?, notes = ?
                WHERE transfer_id = ?
            ''', (datetime.now().isoformat(), notes, transfer_id))
            log_activity('update', 'knowledge_transfer', details={
                'transfer_id': transfer_id, 'action': 'completed'
            })
            return True

    # ==================== TURNOVER ANALYTICS ====================

    @staticmethod
    def calculate_turnover(department: str = None, period_start: str = None,
                          period_end: str = None) -> Dict[str, Any]:
        """Calculate turnover metrics."""
        with get_connection() as conn:
            if not period_start:
                period_start = datetime(datetime.now().year, 1, 1).isoformat()
            if not period_end:
                period_end = datetime.now().isoformat()

            query = '''
                SELECT
                    COUNT(*) as total_exits,
                    SUM(CASE WHEN reason_category = 'voluntary' THEN 1 ELSE 0 END) as voluntary,
                    SUM(CASE WHEN reason_category = 'involuntary' THEN 1 ELSE 0 END) as involuntary,
                    SUM(CASE WHEN reason_category = 'retirement' THEN 1 ELSE 0 END) as retirement,
                    AVG(tenure_months) as avg_tenure
                FROM exit_interviews
                WHERE status = 'completed'
                AND last_working_day BETWEEN ? AND ?
            '''
            params = [period_start, period_end]

            if department:
                query += ' AND department = ?'
                params.append(department)

            row = conn.execute(query, params).fetchone()

            return {
                'period_start': period_start,
                'period_end': period_end,
                'department': department,
                'total_exits': row['total_exits'] or 0,
                'voluntary': row['voluntary'] or 0,
                'involuntary': row['involuntary'] or 0,
                'retirement': row['retirement'] or 0,
                'avg_tenure_months': round(row['avg_tenure'] or 0, 1)
            }

    @staticmethod
    def get_exit_reasons_breakdown(period: str = None,
                                   department: str = None) -> List[Dict[str, Any]]:
        """Get breakdown of exit reasons."""
        with get_connection() as conn:
            query = '''
                SELECT reason_category, reason_for_leaving, COUNT(*) as count
                FROM exit_interviews
                WHERE status = 'completed'
            '''
            params = []

            if period:
                query += ' AND last_working_day LIKE ?'
                params.append(f'{period}%')

            if department:
                query += ' AND department = ?'
                params.append(department)

            query += ' GROUP BY reason_category, reason_for_leaving ORDER BY count DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_satisfaction_trends(period_months: int = 12) -> List[Dict[str, Any]]:
        """Get satisfaction rating trends over time."""
        with get_connection() as conn:
            start_date = (datetime.now() - timedelta(days=period_months * 30)).isoformat()

            rows = conn.execute('''
                SELECT
                    strftime('%Y-%m', last_working_day) as month,
                    AVG(job_satisfaction_rating) as avg_job_satisfaction,
                    AVG(manager_rating) as avg_manager,
                    AVG(work_environment_rating) as avg_environment,
                    AVG(compensation_rating) as avg_compensation,
                    AVG(overall_rating) as avg_overall,
                    COUNT(*) as exit_count
                FROM exit_interviews
                WHERE status = 'completed'
                AND last_working_day >= ?
                GROUP BY strftime('%Y-%m', last_working_day)
                ORDER BY month
            ''', (start_date,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_department_turnover_comparison() -> List[Dict[str, Any]]:
        """Compare turnover rates across departments."""
        with get_connection() as conn:
            year_start = datetime(datetime.now().year, 1, 1).isoformat()

            rows = conn.execute('''
                SELECT
                    department,
                    COUNT(*) as exit_count,
                    AVG(tenure_months) as avg_tenure,
                    AVG(overall_rating) as avg_rating,
                    SUM(CASE WHEN would_recommend = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as recommend_pct
                FROM exit_interviews
                WHERE status = 'completed'
                AND last_working_day >= ?
                AND department IS NOT NULL
                GROUP BY department
                ORDER BY exit_count DESC
            ''', (year_start,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def store_turnover_analytics(department: str, period_start: str,
                                period_end: str, **data) -> int:
        """Store turnover analytics for reporting."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO turnover_analytics (
                    department, period_start, period_end, period_type,
                    headcount_start, headcount_end, voluntary_exits,
                    involuntary_exits, retirements, transfers_out,
                    new_hires, transfers_in, turnover_rate, retention_rate,
                    avg_tenure_months
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                department,
                period_start,
                period_end,
                data.get('period_type', 'monthly'),
                data.get('headcount_start', 0),
                data.get('headcount_end', 0),
                data.get('voluntary_exits', 0),
                data.get('involuntary_exits', 0),
                data.get('retirements', 0),
                data.get('transfers_out', 0),
                data.get('new_hires', 0),
                data.get('transfers_in', 0),
                data.get('turnover_rate'),
                data.get('retention_rate'),
                data.get('avg_tenure_months'),
            ))
            record_id = cursor.lastrowid
            log_activity('create', 'turnover_analytics', details={'record_id': record_id})
            return record_id

    @staticmethod
    def get_retention_recommendations(department: str = None) -> List[Dict[str, Any]]:
        """Generate retention recommendations based on exit data."""
        recommendations = []

        with get_connection() as conn:
            # Analyze common leaving factors
            query = '''
                SELECT
                    SUM(salary_factor) as salary_issues,
                    SUM(career_growth_factor) as growth_issues,
                    SUM(work_life_balance_factor) as balance_issues,
                    SUM(management_factor) as management_issues,
                    SUM(culture_factor) as culture_issues,
                    COUNT(*) as total
                FROM exit_interviews
                WHERE status = 'completed'
                AND last_working_day >= date('now', '-12 months')
            '''
            params = []

            if department:
                query += ' AND department = ?'
                params.append(department)

            row = conn.execute(query, params).fetchone()

            if row and row['total'] > 0:
                total = row['total']

                factors = [
                    ('salary_issues', 'Compensation', 'Review salary bands and benefits packages'),
                    ('growth_issues', 'Career Growth', 'Develop clearer career paths and promotion criteria'),
                    ('balance_issues', 'Work-Life Balance', 'Review workload distribution and flexible working policies'),
                    ('management_issues', 'Management', 'Provide management training and improve feedback mechanisms'),
                    ('culture_issues', 'Culture', 'Conduct culture assessment and address workplace environment'),
                ]

                for factor_key, factor_name, recommendation in factors:
                    if row[factor_key]:
                        percentage = (row[factor_key] / total) * 100
                        if percentage > 30:  # Significant factor
                            recommendations.append({
                                'factor': factor_name,
                                'percentage': round(percentage, 1),
                                'priority': 'High' if percentage > 50 else 'Medium',
                                'recommendation': recommendation
                            })

        # Sort by percentage descending
        recommendations.sort(key=lambda x: x['percentage'], reverse=True)
        return recommendations

    @staticmethod
    def get_exit_statistics() -> Dict[str, Any]:
        """Get overall exit statistics."""
        with get_connection() as conn:
            stats = {}

            # Total interviews this year
            year_start = datetime(datetime.now().year, 1, 1).isoformat()
            row = conn.execute('''
                SELECT COUNT(*) as count FROM exit_interviews
                WHERE last_working_day >= ?
            ''', (year_start,)).fetchone()
            stats['total_this_year'] = row['count'] if row else 0

            # Pending interviews
            row = conn.execute('''
                SELECT COUNT(*) as count FROM exit_interviews
                WHERE status IN ('scheduled', 'pending')
            ''').fetchone()
            stats['pending'] = row['count'] if row else 0

            # Completed interviews
            row = conn.execute('''
                SELECT COUNT(*) as count FROM exit_interviews
                WHERE status = 'completed' AND last_working_day >= ?
            ''', (year_start,)).fetchone()
            stats['completed'] = row['count'] if row else 0

            # Average ratings
            row = conn.execute('''
                SELECT
                    AVG(overall_rating) as avg_rating,
                    AVG(CASE WHEN would_recommend = 1 THEN 100 ELSE 0 END) as recommend_pct
                FROM exit_interviews
                WHERE status = 'completed' AND last_working_day >= ?
            ''', (year_start,)).fetchone()
            stats['avg_rating'] = round(row['avg_rating'] or 0, 1)
            stats['recommend_pct'] = round(row['recommend_pct'] or 0, 1)

            return stats

    # ==================== ADDITIONAL METHODS FOR CLI COMPATIBILITY ====================

    @staticmethod
    def get_all_templates() -> List[Dict[str, Any]]:
        """Get all exit checklist templates with item counts."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT t.*, COUNT(i.item_id) as item_count
                FROM exit_checklist_templates t
                LEFT JOIN exit_checklist_template_items i ON t.template_id = i.template_id
                GROUP BY t.template_id
                ORDER BY t.is_default DESC, t.name
            ''').fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def initiate_exit(user_id: str, exit_type: str, last_working_day: str,
                      reason: str = None, department: str = None,
                      manager_id: str = None) -> int:
        """Initiate an exit process for an employee."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO exit_interviews (
                    user_id, status, last_working_day, reason_for_leaving,
                    reason_category, department, manager_id
                ) VALUES (?, 'pending', ?, ?, ?, ?, ?)
            ''', (user_id, last_working_day, reason, exit_type, department, manager_id))
            interview_id = cursor.lastrowid

            # Create default checklist from default template
            ExitManager.create_user_checklist(user_id, last_working_day)

            log_activity('create', 'exit_process', details={
                'interview_id': interview_id, 'user_id': user_id, 'exit_type': exit_type
            })
            return interview_id

    @staticmethod
    def apply_template(user_id: str, template_id: int) -> int:
        """Apply a checklist template to a user's exit process."""
        # Get user's last working day from exit interview
        interview = ExitManager.get_user_exit_interview(user_id)
        last_working_day = interview.get('last_working_day') if interview else datetime.now().isoformat()

        # Create checklist items from template
        checklist_ids = ExitManager.create_user_checklist(user_id, last_working_day, template_id)
        return len(checklist_ids)

    @staticmethod
    def get_exit_record(user_id: str) -> Optional[Dict[str, Any]]:
        """Get exit record for a user (alias for get_user_exit_interview)."""
        return ExitManager.get_user_exit_interview(user_id)

    @staticmethod
    def search_exits(exit_type: str = None, department: str = None,
                     status: str = None, start_date: str = None,
                     end_date: str = None) -> List[Dict[str, Any]]:
        """Search exit records with filters."""
        with get_connection() as conn:
            query = 'SELECT * FROM exit_interviews WHERE 1=1'
            params = []

            if exit_type:
                query += ' AND reason_category = ?'
                params.append(exit_type)

            if department:
                query += ' AND department = ?'
                params.append(department)

            if status:
                query += ' AND status = ?'
                params.append(status)

            if start_date:
                query += ' AND last_working_day >= ?'
                params.append(start_date)

            if end_date:
                query += ' AND last_working_day <= ?'
                params.append(end_date)

            query += ' ORDER BY last_working_day DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def add_checklist_item(user_id: str, task_name: str, **data) -> int:
        """Add a custom checklist item for a user."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO exit_checklist (
                    user_id, task_name, description, category,
                    responsible_party, due_date
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                task_name,
                data.get('description'),
                data.get('category'),
                data.get('assigned_to') or data.get('responsible_party'),
                data.get('due_date'),
            ))
            checklist_id = cursor.lastrowid
            log_activity('create', 'exit_checklist_item', details={
                'checklist_id': checklist_id, 'user_id': user_id
            })
            return checklist_id

    @staticmethod
    def assign_checklist_item(checklist_id: int, assigned_to: str) -> bool:
        """Assign a checklist item to someone."""
        with transaction() as conn:
            conn.execute('''
                UPDATE exit_checklist SET responsible_party = ? WHERE checklist_id = ?
            ''', (assigned_to, checklist_id))
            log_activity('update', 'exit_checklist_item', details={
                'checklist_id': checklist_id, 'assigned_to': assigned_to
            })
            return True

    @staticmethod
    def remove_checklist_item(checklist_id: int) -> bool:
        """Remove a checklist item."""
        with transaction() as conn:
            conn.execute('DELETE FROM exit_checklist WHERE checklist_id = ?', (checklist_id,))
            log_activity('delete', 'exit_checklist_item', details={'checklist_id': checklist_id})
            return True

    @staticmethod
    def schedule_interview(user_id: str, interviewer_id: str, interview_date: str,
                          interview_time: str = None, location: str = None) -> int:
        """Schedule an exit interview."""
        with transaction() as conn:
            # Check if interview already exists
            existing = ExitManager.get_user_exit_interview(user_id)
            if existing:
                # Update existing
                conn.execute('''
                    UPDATE exit_interviews SET
                        interviewer_id = ?, scheduled_date = ?, status = 'scheduled'
                    WHERE interview_id = ?
                ''', (interviewer_id, interview_date, existing['interview_id']))
                log_activity('update', 'exit_interview', details={
                    'interview_id': existing['interview_id'], 'action': 'scheduled'
                })
                return existing['interview_id']
            else:
                # Create new
                cursor = conn.execute('''
                    INSERT INTO exit_interviews (
                        user_id, interviewer_id, scheduled_date, status
                    ) VALUES (?, ?, ?, 'scheduled')
                ''', (user_id, interviewer_id, interview_date))
                interview_id = cursor.lastrowid
                log_activity('create', 'exit_interview', details={
                    'interview_id': interview_id, 'action': 'scheduled'
                })
                return interview_id

    @staticmethod
    def get_interview(interview_id: int) -> Optional[Dict[str, Any]]:
        """Get an exit interview by ID (alias)."""
        return ExitManager.get_exit_interview(interview_id)

    @staticmethod
    def create_interview(user_id: str, interviewer_id: str, interview_date: str,
                        **feedback) -> int:
        """Create and complete an exit interview in one step."""
        interview_id = ExitManager.create_exit_interview(
            user_id,
            interviewer_id=interviewer_id,
            interview_date=interview_date,
            status='completed'
        )

        # Map feedback fields
        mapped_feedback = {
            'reason_for_leaving': feedback.get('reason_for_leaving'),
            'job_satisfaction_rating': feedback.get('job_satisfaction'),
            'manager_rating': feedback.get('management_rating'),
            'work_environment_rating': feedback.get('work_environment_rating'),
            'growth_opportunities_rating': feedback.get('growth_opportunities_rating'),
            'would_recommend': feedback.get('would_recommend'),
            'would_return': feedback.get('would_return'),
            'liked_most': feedback.get('feedback_positive'),
            'liked_least': feedback.get('feedback_negative'),
            'suggestions': feedback.get('suggestions'),
        }

        ExitManager.complete_exit_interview(interview_id, **mapped_feedback)
        return interview_id

    @staticmethod
    def complete_interview(interview_id: int, **feedback) -> int:
        """Complete an exit interview (alias with field mapping)."""
        mapped_feedback = {
            'reason_for_leaving': feedback.get('reason_for_leaving'),
            'job_satisfaction_rating': feedback.get('job_satisfaction'),
            'manager_rating': feedback.get('management_rating'),
            'work_environment_rating': feedback.get('work_environment_rating'),
            'growth_opportunities_rating': feedback.get('growth_opportunities_rating'),
            'would_recommend': feedback.get('would_recommend'),
            'would_return': feedback.get('would_return'),
            'liked_most': feedback.get('feedback_positive'),
            'liked_least': feedback.get('feedback_negative'),
            'suggestions': feedback.get('suggestions'),
        }

        ExitManager.complete_exit_interview(interview_id, **mapped_feedback)
        return interview_id

    @staticmethod
    def get_turnover_analytics(year: int) -> Dict[str, Any]:
        """Get turnover analytics for a year."""
        period_start = f'{year}-01-01'
        period_end = f'{year}-12-31'

        analytics = ExitManager.calculate_turnover(period_start=period_start, period_end=period_end)

        with get_connection() as conn:
            # Monthly breakdown
            rows = conn.execute('''
                SELECT strftime('%Y-%m', last_working_day) as month, COUNT(*) as count
                FROM exit_interviews
                WHERE last_working_day BETWEEN ? AND ?
                GROUP BY strftime('%Y-%m', last_working_day)
                ORDER BY month
            ''', (period_start, period_end)).fetchall()
            analytics['monthly_exits'] = {row['month']: row['count'] for row in rows}

            # By department
            rows = conn.execute('''
                SELECT department, COUNT(*) as exits
                FROM exit_interviews
                WHERE last_working_day BETWEEN ? AND ? AND department IS NOT NULL
                GROUP BY department
            ''', (period_start, period_end)).fetchall()
            analytics['by_department'] = {
                row['department']: {'exits': row['exits'], 'rate': 0} for row in rows
            }

            # By type
            rows = conn.execute('''
                SELECT reason_category, COUNT(*) as count
                FROM exit_interviews
                WHERE last_working_day BETWEEN ? AND ?
                GROUP BY reason_category
            ''', (period_start, period_end)).fetchall()
            analytics['by_type'] = {row['reason_category'] or 'unknown': row['count'] for row in rows}

            # Voluntary tenure
            row = conn.execute('''
                SELECT AVG(tenure_months) as avg
                FROM exit_interviews
                WHERE last_working_day BETWEEN ? AND ? AND reason_category = 'voluntary'
            ''', (period_start, period_end)).fetchone()
            analytics['avg_tenure_voluntary'] = round(row['avg'] or 0, 1)

            # Turnover rate (simplified)
            analytics['turnover_rate'] = analytics.get('total_exits', 0)

        return analytics

    @staticmethod
    def get_exit_reasons_summary(period: str = None) -> Dict[str, Any]:
        """Get summary of exit reasons."""
        with get_connection() as conn:
            where = "status = 'completed'"
            params = []

            if period:
                where += ' AND last_working_day LIKE ?'
                params.append(f'{period}%')

            # Total interviews
            row = conn.execute(
                'SELECT COUNT(*) as total FROM exit_interviews WHERE ' + where,
                params).fetchone()
            total = row['total'] if row else 0

            # Reasons breakdown
            rows = conn.execute(
                'SELECT reason_for_leaving, COUNT(*) as count'
                ' FROM exit_interviews WHERE ' + where +
                ' GROUP BY reason_for_leaving ORDER BY count DESC',
                params).fetchall()
            reasons = {row['reason_for_leaving'] or 'unspecified': row['count'] for row in rows}

            # Average ratings
            row = conn.execute(
                'SELECT'
                ' AVG(job_satisfaction_rating) as job_satisfaction,'
                ' AVG(manager_rating) as management,'
                ' AVG(work_environment_rating) as work_environment,'
                ' AVG(growth_opportunities_rating) as growth'
                ' FROM exit_interviews WHERE ' + where,
                params).fetchone()

            avg_ratings = {
                'job_satisfaction': row['job_satisfaction'] or 0,
                'management': row['management'] or 0,
                'work_environment': row['work_environment'] or 0,
                'growth': row['growth'] or 0,
            }

            # Would recommend/return
            row = conn.execute(
                'SELECT'
                ' SUM(CASE WHEN would_recommend = 1 THEN 1 ELSE 0 END) as rec_yes,'
                ' SUM(CASE WHEN would_recommend = 0 THEN 1 ELSE 0 END) as rec_no,'
                ' SUM(CASE WHEN would_return = 1 THEN 1 ELSE 0 END) as ret_yes,'
                ' SUM(CASE WHEN would_return = 0 THEN 1 ELSE 0 END) as ret_no'
                ' FROM exit_interviews WHERE ' + where,
                params).fetchone()

            return {
                'total_interviews': total,
                'reasons': reasons,
                'avg_ratings': avg_ratings,
                'would_recommend': {'yes': row['rec_yes'] or 0, 'no': row['rec_no'] or 0},
                'would_return': {'yes': row['ret_yes'] or 0, 'no': row['ret_no'] or 0},
            }

    @staticmethod
    def get_department_turnover_report(department: str = None) -> Dict[str, Any]:
        """Get department turnover report."""
        with get_connection() as conn:
            year_start = datetime(datetime.now().year, 1, 1).isoformat()

            query = '''
                SELECT
                    department,
                    COUNT(*) as exits_12m,
                    AVG(tenure_months) as avg_tenure
                FROM exit_interviews
                WHERE last_working_day >= ? AND department IS NOT NULL
            '''
            params = [year_start]

            if department:
                query += ' AND department = ?'
                params.append(department)

            query += ' GROUP BY department'
            rows = conn.execute(query, params).fetchall()

            report = {}
            for row in rows:
                dept = row['department']
                report[dept] = {
                    'headcount': 'N/A',  # Would need staff count table
                    'exits_12m': row['exits_12m'],
                    'turnover_rate': 0,  # Would need headcount
                    'avg_tenure': round(row['avg_tenure'] or 0, 1),
                    'top_reasons': []
                }

                # Get top reasons for this department
                reasons = conn.execute('''
                    SELECT reason_for_leaving, COUNT(*) as cnt
                    FROM exit_interviews
                    WHERE department = ? AND last_working_day >= ?
                    GROUP BY reason_for_leaving
                    ORDER BY cnt DESC LIMIT 3
                ''', (dept, year_start)).fetchall()
                report[dept]['top_reasons'] = [r['reason_for_leaving'] for r in reasons if r['reason_for_leaving']]

            return report

    @staticmethod
    def update_template(template_id: int, **data) -> bool:
        """Update a checklist template."""
        if not data:
            return False

        fields = []
        values = []
        for key, value in data.items():
            if key not in ('template_id', 'created_at'):
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return False

        values.append(template_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE exit_checklist_templates SET ' + ', '.join(fields) + ' WHERE template_id = ?',
                values)
            log_activity('update', 'exit_checklist_template', details={'template_id': template_id})
            return True

    @staticmethod
    def delete_template(template_id: int) -> bool:
        """Delete a checklist template and its items."""
        with transaction() as conn:
            conn.execute('DELETE FROM exit_checklist_template_items WHERE template_id = ?', (template_id,))
            conn.execute('DELETE FROM exit_checklist_templates WHERE template_id = ?', (template_id,))
            log_activity('delete', 'exit_checklist_template', details={'template_id': template_id})
            return True
