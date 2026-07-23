"""
Workflow monitoring and analytics
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.infrastructure.workflows.models import WorkflowStatus, ApprovalStatus

logger = logging.getLogger(__name__)


class WorkflowMonitor:
    """
    Monitor workflow execution and performance

    Provides real-time monitoring of:
    - Active workflows
    - Pending approvals
    - Overdue steps
    - Bottlenecks
    - Error tracking
    """

    def __init__(self):
        """Initialize workflow monitor"""
        pass

    def get_active_workflows(self) -> List[Dict[str, Any]]:
        """Get all active workflow instances"""
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT instance_id, workflow_name, status, current_step_id,
                       initiated_by, initiated_at
                FROM workflow_instances
                WHERE status IN ('pending', 'in_progress')
                ORDER BY initiated_at DESC
            ''')
            rows = cursor.fetchall()

        return [
            {
                'instance_id': row[0],
                'workflow_name': row[1],
                'status': row[2],
                'current_step_id': row[3],
                'initiated_by': row[4],
                'initiated_at': row[5],
            }
            for row in rows
        ]

    def get_pending_approvals_count(self, approver: Optional[str] = None) -> int:
        """Get count of pending approvals"""
        with get_connection() as conn:
            if approver:
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM approval_requests
                    WHERE status = 'pending' AND approver = ?
                ''', (approver,))
            else:
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM approval_requests
                    WHERE status = 'pending'
                ''')

            return cursor.fetchone()[0]

    def get_overdue_approvals(self) -> List[Dict[str, Any]]:
        """Get overdue approval requests"""
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT request_id, instance_id, workflow_name, step_name,
                       approver, due_date, created_at
                FROM approval_requests
                WHERE status = 'pending'
                  AND due_date IS NOT NULL
                  AND due_date < ?
                ORDER BY due_date ASC
            ''', (datetime.utcnow(),))
            rows = cursor.fetchall()

        return [
            {
                'request_id': row[0],
                'instance_id': row[1],
                'workflow_name': row[2],
                'step_name': row[3],
                'approver': row[4],
                'due_date': row[5],
                'created_at': row[6],
                'days_overdue': (datetime.utcnow() - datetime.fromisoformat(row[5])).days
            }
            for row in rows
        ]

    def get_workflow_health(self) -> Dict[str, Any]:
        """Get overall workflow system health metrics"""
        with get_connection() as conn:
            # Active workflows
            cursor = conn.execute('''
                SELECT COUNT(*) FROM workflow_instances
                WHERE status IN ('pending', 'in_progress')
            ''')
            active_count = cursor.fetchone()[0]

            # Completed today
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)
            cursor = conn.execute('''
                SELECT COUNT(*) FROM workflow_instances
                WHERE status = 'completed'
                  AND completed_at >= ?
            ''', (today_start,))
            completed_today = cursor.fetchone()[0]

            # Failed/Error
            cursor = conn.execute('''
                SELECT COUNT(*) FROM workflow_instances
                WHERE status = 'error'
            ''')
            error_count = cursor.fetchone()[0]

            # Pending approvals
            cursor = conn.execute('''
                SELECT COUNT(*) FROM approval_requests
                WHERE status = 'pending'
            ''')
            pending_approvals = cursor.fetchone()[0]

            # Overdue approvals
            cursor = conn.execute('''
                SELECT COUNT(*) FROM approval_requests
                WHERE status = 'pending'
                  AND due_date IS NOT NULL
                  AND due_date < ?
            ''', (datetime.utcnow(),))
            overdue_approvals = cursor.fetchone()[0]

        return {
            'active_workflows': active_count,
            'completed_today': completed_today,
            'error_count': error_count,
            'pending_approvals': pending_approvals,
            'overdue_approvals': overdue_approvals,
            'health_score': self._calculate_health_score(
                active_count, error_count, overdue_approvals
            )
        }

    def _calculate_health_score(
        self,
        active: int,
        errors: int,
        overdue: int
    ) -> float:
        """Calculate system health score (0-100)"""
        # Simple scoring algorithm
        score = 100.0

        # Penalize errors
        if errors > 0:
            score -= min(errors * 10, 30)

        # Penalize overdue
        if overdue > 0:
            score -= min(overdue * 5, 20)

        # Penalize high active count (potential bottleneck)
        if active > 100:
            score -= min((active - 100) * 0.5, 20)

        return max(score, 0.0)

    def identify_bottlenecks(self, threshold_hours: int = 48) -> List[Dict[str, Any]]:
        """Identify workflow bottlenecks"""
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT wi.instance_id, wi.workflow_name, wi.current_step_id,
                       ar.step_name, ar.approver, ar.created_at
                FROM workflow_instances wi
                JOIN approval_requests ar ON wi.instance_id = ar.instance_id
                WHERE wi.status = 'in_progress'
                  AND ar.status = 'pending'
                  AND ar.created_at < ?
                ORDER BY ar.created_at ASC
            ''', (datetime.utcnow() - timedelta(hours=threshold_hours),))
            rows = cursor.fetchall()

        return [
            {
                'instance_id': row[0],
                'workflow_name': row[1],
                'step_id': row[2],
                'step_name': row[3],
                'approver': row[4],
                'stuck_since': row[5],
                'hours_stuck': (datetime.utcnow() - datetime.fromisoformat(row[5])).total_seconds() / 3600
            }
            for row in rows
        ]


class WorkflowAnalytics:
    """
    Workflow analytics and performance tracking

    Provides insights into:
    - Completion rates
    - Average processing time
    - Approval patterns
    - Workflow efficiency
    - Trend analysis
    """

    def __init__(self):
        """Initialize workflow analytics"""
        pass

    def get_completion_rate(
        self,
        workflow_id: Optional[str] = None,
        days: int = 30
    ) -> float:
        """Get workflow completion rate"""
        start_date = datetime.utcnow() - timedelta(days=days)

        with get_connection() as conn:
            if workflow_id:
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM workflow_instances
                    WHERE workflow_id = ?
                      AND initiated_at >= ?
                ''', (workflow_id, start_date))
                total = cursor.fetchone()[0]

                cursor = conn.execute('''
                    SELECT COUNT(*) FROM workflow_instances
                    WHERE workflow_id = ?
                      AND status = 'completed'
                      AND initiated_at >= ?
                ''', (workflow_id, start_date))
                completed = cursor.fetchone()[0]
            else:
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM workflow_instances
                    WHERE initiated_at >= ?
                ''', (start_date,))
                total = cursor.fetchone()[0]

                cursor = conn.execute('''
                    SELECT COUNT(*) FROM workflow_instances
                    WHERE status = 'completed'
                      AND initiated_at >= ?
                ''', (start_date,))
                completed = cursor.fetchone()[0]

        return (completed / total * 100) if total > 0 else 0.0

    def get_average_completion_time(
        self,
        workflow_id: Optional[str] = None,
        days: int = 30
    ) -> Optional[float]:
        """Get average workflow completion time in hours"""
        start_date = datetime.utcnow() - timedelta(days=days)

        with get_connection() as conn:
            if workflow_id:
                cursor = conn.execute('''
                    SELECT initiated_at, completed_at
                    FROM workflow_instances
                    WHERE workflow_id = ?
                      AND status = 'completed'
                      AND initiated_at >= ?
                      AND completed_at IS NOT NULL
                ''', (workflow_id, start_date))
            else:
                cursor = conn.execute('''
                    SELECT initiated_at, completed_at
                    FROM workflow_instances
                    WHERE status = 'completed'
                      AND initiated_at >= ?
                      AND completed_at IS NOT NULL
                ''', (start_date,))

            rows = cursor.fetchall()

        if not rows:
            return None

        total_hours = 0.0
        for row in rows:
            initiated = datetime.fromisoformat(row[0])
            completed = datetime.fromisoformat(row[1])
            hours = (completed - initiated).total_seconds() / 3600
            total_hours += hours

        return total_hours / len(rows)

    def get_approval_patterns(self, approver: str, days: int = 30) -> Dict[str, Any]:
        """Get approval patterns for a specific approver"""
        start_date = datetime.utcnow() - timedelta(days=days)

        with get_connection() as conn:
            # Total approvals
            cursor = conn.execute('''
                SELECT COUNT(*) FROM approval_requests
                WHERE approver = ?
                  AND created_at >= ?
                  AND status != 'pending'
            ''', (approver, start_date))
            total = cursor.fetchone()[0]

            # Approved count
            cursor = conn.execute('''
                SELECT COUNT(*) FROM approval_requests
                WHERE approver = ?
                  AND created_at >= ?
                  AND status = 'approved'
            ''', (approver, start_date))
            approved = cursor.fetchone()[0]

            # Rejected count
            cursor = conn.execute('''
                SELECT COUNT(*) FROM approval_requests
                WHERE approver = ?
                  AND created_at >= ?
                  AND status = 'rejected'
            ''', (approver, start_date))
            rejected = cursor.fetchone()[0]

            # Average decision time
            cursor = conn.execute('''
                SELECT created_at, decision_at
                FROM approval_requests
                WHERE approver = ?
                  AND created_at >= ?
                  AND status != 'pending'
                  AND decision_at IS NOT NULL
            ''', (approver, start_date))
            rows = cursor.fetchall()

        avg_decision_time = None
        if rows:
            total_hours = sum(
                (datetime.fromisoformat(row[1]) - datetime.fromisoformat(row[0])).total_seconds() / 3600
                for row in rows
            )
            avg_decision_time = total_hours / len(rows)

        return {
            'approver': approver,
            'total_requests': total,
            'approved': approved,
            'rejected': rejected,
            'approval_rate': (approved / total * 100) if total > 0 else 0.0,
            'average_decision_time_hours': avg_decision_time
        }

    def get_workflow_statistics(
        self,
        workflow_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get comprehensive workflow statistics"""
        return {
            'completion_rate': self.get_completion_rate(workflow_id, days),
            'average_completion_time_hours': self.get_average_completion_time(workflow_id, days),
            'total_instances': self._get_total_instances(workflow_id, days),
            'status_breakdown': self._get_status_breakdown(workflow_id, days),
            'trend': self._get_trend(workflow_id, days)
        }

    def _get_total_instances(
        self,
        workflow_id: Optional[str],
        days: int
    ) -> int:
        """Get total instances"""
        start_date = datetime.utcnow() - timedelta(days=days)

        with get_connection() as conn:
            if workflow_id:
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM workflow_instances
                    WHERE workflow_id = ?
                      AND initiated_at >= ?
                ''', (workflow_id, start_date))
            else:
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM workflow_instances
                    WHERE initiated_at >= ?
                ''', (start_date,))

            return cursor.fetchone()[0]

    def _get_status_breakdown(
        self,
        workflow_id: Optional[str],
        days: int
    ) -> Dict[str, int]:
        """Get breakdown by status"""
        start_date = datetime.utcnow() - timedelta(days=days)

        with get_connection() as conn:
            if workflow_id:
                cursor = conn.execute('''
                    SELECT status, COUNT(*) FROM workflow_instances
                    WHERE workflow_id = ?
                      AND initiated_at >= ?
                    GROUP BY status
                ''', (workflow_id, start_date))
            else:
                cursor = conn.execute('''
                    SELECT status, COUNT(*) FROM workflow_instances
                    WHERE initiated_at >= ?
                    GROUP BY status
                ''', (start_date,))

            rows = cursor.fetchall()

        return {row[0]: row[1] for row in rows}

    def _get_trend(
        self,
        workflow_id: Optional[str],
        days: int
    ) -> str:
        """Get workflow trend (improving/declining/stable)"""
        # Simple trend analysis comparing first and second half
        half_days = days // 2
        start_date = datetime.utcnow() - timedelta(days=days)
        mid_date = datetime.utcnow() - timedelta(days=half_days)

        first_half_rate = self.get_completion_rate(workflow_id, half_days)
        second_half_rate = self.get_completion_rate(workflow_id, days)

        diff = first_half_rate - second_half_rate

        if diff > 5:
            return "improving"
        elif diff < -5:
            return "declining"
        else:
            return "stable"


# Singleton instances
_workflow_monitor: Optional[WorkflowMonitor] = None
_workflow_analytics: Optional[WorkflowAnalytics] = None


def get_workflow_monitor() -> WorkflowMonitor:
    """Get the global workflow monitor instance"""
    global _workflow_monitor
    if _workflow_monitor is None:
        _workflow_monitor = WorkflowMonitor()
    return _workflow_monitor


def get_workflow_analytics() -> WorkflowAnalytics:
    """Get the global workflow analytics instance"""
    global _workflow_analytics
    if _workflow_analytics is None:
        _workflow_analytics = WorkflowAnalytics()
    return _workflow_analytics
