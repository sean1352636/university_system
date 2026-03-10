"""Alerts and notifications mixin for AIDetector - alert thresholds, email alerts, alert queue, escalation."""

import uuid
from datetime import datetime
from typing import Dict, List, Any

from education_system.university_system.utils.ai.ai_detector.core.constants import logger


class AlertsMixin:
    """Mixin providing alerts and notifications functions (23-27)."""

    # ============================================================================
    # ALERTS & NOTIFICATIONS (23-27)
    # ============================================================================

    def configure_alert_thresholds(self, low: float = 0.3, medium: float = 0.5,
                                   high: float = 0.7, critical: float = 0.9) -> Dict[str, Any]:
        """
        Set custom alert thresholds for different risk levels.

        Args:
            low: Threshold for low risk (default 0.3)
            medium: Threshold for medium risk (default 0.5)
            high: Threshold for high risk (default 0.7)
            critical: Threshold for critical risk (default 0.9)

        Returns:
            Dict with success status and configured thresholds
        """
        try:
            # Validate thresholds are in order
            if not (0 <= low < medium < high < critical <= 1):
                return {'success': False, 'error': 'Thresholds must be in ascending order between 0 and 1'}

            conn = self._get_connection()
            cursor = conn.cursor()

            # Create alert_config table if not exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_detector_alert_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_key TEXT UNIQUE NOT NULL,
                    config_value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    updated_by TEXT
                )
            ''')

            thresholds = {
                'low': low,
                'medium': medium,
                'high': high,
                'critical': critical
            }

            # Store thresholds
            for key, value in thresholds.items():
                cursor.execute('''
                    INSERT OR REPLACE INTO ai_detector_alert_config
                    (config_key, config_value, updated_at, updated_by)
                    VALUES (?, ?, ?, ?)
                ''', (f'threshold_{key}', str(value), datetime.now().isoformat(),
                      self.current_user.get('username') if self.current_user else None))

            conn.commit()
            conn.close()

            # Update instance thresholds
            self.alert_thresholds = thresholds

            logger.info(f"Alert thresholds configured: {thresholds}")
            return {
                'success': True,
                'thresholds': thresholds,
                'updated_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error configuring alert thresholds: {e}")
            return {'success': False, 'error': str(e)}

    def setup_email_alerts(self, email: str, risk_levels: List[str] = None,
                          include_details: bool = True) -> Dict[str, Any]:
        """
        Configure automatic email alerts for high-risk submissions.

        Args:
            email: Recipient email address
            risk_levels: List of risk levels to trigger alerts (default: ['high', 'critical'])
            include_details: Whether to include full analysis details in email

        Returns:
            Dict with success status and configuration details
        """
        try:
            if not email or '@' not in email:
                return {'success': False, 'error': 'Invalid email address'}

            if risk_levels is None:
                risk_levels = ['high', 'critical']

            valid_levels = ['low', 'medium', 'high', 'critical']
            risk_levels = [r for r in risk_levels if r in valid_levels]

            if not risk_levels:
                return {'success': False, 'error': 'No valid risk levels specified'}

            conn = self._get_connection()
            cursor = conn.cursor()

            # Create email alerts table if not exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_detector_email_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    risk_levels TEXT NOT NULL,
                    include_details INTEGER NOT NULL DEFAULT 1,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    created_by TEXT
                )
            ''')

            # Insert or update email alert config
            cursor.execute('''
                INSERT INTO ai_detector_email_alerts
                (email, risk_levels, include_details, is_active, created_at, created_by)
                VALUES (?, ?, ?, 1, ?, ?)
            ''', (email, ','.join(risk_levels), 1 if include_details else 0,
                  datetime.now().isoformat(),
                  self.current_user.get('username') if self.current_user else None))

            conn.commit()
            conn.close()

            logger.info(f"Email alerts configured for {email}")
            return {
                'success': True,
                'email': email,
                'risk_levels': risk_levels,
                'include_details': include_details,
                'configured_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error setting up email alerts: {e}")
            return {'success': False, 'error': str(e)}

    def view_alert_queue(self, risk_level: str = None) -> Dict[str, Any]:
        """
        View pending alerts awaiting instructor review.

        Args:
            risk_level: Optional filter by risk level

        Returns:
            Dict with alerts list and summary
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Create alerts table if not exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_detector_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id TEXT NOT NULL,
                    student_id TEXT NOT NULL,
                    submission_title TEXT,
                    risk_level TEXT NOT NULL,
                    ai_score REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    reviewed_at TEXT,
                    reviewed_by TEXT,
                    dismissal_reason TEXT,
                    notes TEXT
                )
            ''')

            # Build query
            query = '''
                SELECT id as alert_id, submission_id, student_id, submission_title,
                       risk_level, ai_score, status, created_at
                FROM ai_detector_alerts
                WHERE status = 'pending'
            '''
            params = []

            if risk_level:
                query += ' AND risk_level = ?'
                params.append(risk_level)

            query += ' ORDER BY created_at DESC'

            cursor.execute(query, params)
            rows = cursor.fetchall()

            alerts = []
            for row in rows:
                alerts.append({
                    'alert_id': row['alert_id'],
                    'submission_id': row['submission_id'],
                    'student_id': row['student_id'],
                    'submission_title': row['submission_title'],
                    'risk_level': row['risk_level'],
                    'ai_score': row['ai_score'],
                    'created_at': row['created_at']
                })

            # Get summary counts
            cursor.execute('''
                SELECT risk_level, COUNT(*) as count
                FROM ai_detector_alerts
                WHERE status = 'pending'
                GROUP BY risk_level
            ''')
            summary_rows = cursor.fetchall()
            summary = {row['risk_level']: row['count'] for row in summary_rows}

            conn.close()

            return {
                'alerts': alerts,
                'total': len(alerts),
                'summary': summary
            }

        except Exception as e:
            logger.error(f"Error viewing alert queue: {e}")
            return {'error': str(e)}

    def dismiss_alert(self, alert_id: str, reason: str, custom_reason: str = None,
                     notes: str = None) -> Dict[str, Any]:
        """
        Dismiss false positive alerts with reason logging.

        Args:
            alert_id: ID of the alert to dismiss
            reason: Dismissal reason code
            custom_reason: Custom reason if 'other' selected
            notes: Additional notes

        Returns:
            Dict with success status and dismissal details
        """
        try:
            if not alert_id:
                return {'success': False, 'error': 'Alert ID is required'}

            conn = self._get_connection()
            cursor = conn.cursor()

            # Check if alert exists
            cursor.execute('SELECT id, status FROM ai_detector_alerts WHERE id = ?', (alert_id,))
            alert = cursor.fetchone()

            if not alert:
                conn.close()
                return {'success': False, 'error': 'Alert not found'}

            if alert['status'] != 'pending':
                conn.close()
                return {'success': False, 'error': f'Alert already {alert["status"]}'}

            dismissal_reason = custom_reason if reason == 'other' and custom_reason else reason
            dismissed_by = self.current_user.get('username') if self.current_user else 'unknown'
            dismissed_at = datetime.now().isoformat()

            cursor.execute('''
                UPDATE ai_detector_alerts
                SET status = 'dismissed', reviewed_at = ?, reviewed_by = ?,
                    dismissal_reason = ?, notes = ?
                WHERE id = ?
            ''', (dismissed_at, dismissed_by, dismissal_reason, notes, alert_id))

            conn.commit()
            conn.close()

            logger.info(f"Alert {alert_id} dismissed by {dismissed_by}: {dismissal_reason}")
            return {
                'success': True,
                'alert_id': alert_id,
                'dismissed_by': dismissed_by,
                'dismissed_at': dismissed_at,
                'reason': dismissal_reason
            }

        except Exception as e:
            logger.error(f"Error dismissing alert: {e}")
            return {'success': False, 'error': str(e)}

    def escalate_to_dean(self, submission_id: str, student_id: str, violation_type: str,
                        summary: str, recommended_action: str = None) -> Dict[str, Any]:
        """
        Escalate serious cases directly to academic dean's queue.

        Args:
            submission_id: ID of the submission
            student_id: ID of the student
            violation_type: Type of violation
            summary: Brief case summary
            recommended_action: Optional recommended action

        Returns:
            Dict with success status and escalation details
        """
        try:
            if not all([submission_id, student_id, violation_type, summary]):
                return {'success': False, 'error': 'All required fields must be provided'}

            conn = self._get_connection()
            cursor = conn.cursor()

            # Create escalations table if not exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_detector_escalations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    escalation_id TEXT UNIQUE NOT NULL,
                    submission_id TEXT NOT NULL,
                    student_id TEXT NOT NULL,
                    violation_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    recommended_action TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    escalated_by TEXT,
                    escalated_at TEXT NOT NULL,
                    reviewed_by TEXT,
                    reviewed_at TEXT,
                    resolution TEXT,
                    notes TEXT
                )
            ''')

            escalation_id = f"ESC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
            escalated_by = self.current_user.get('username') if self.current_user else 'unknown'
            escalated_at = datetime.now().isoformat()

            cursor.execute('''
                INSERT INTO ai_detector_escalations
                (escalation_id, submission_id, student_id, violation_type, summary,
                 recommended_action, escalated_by, escalated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (escalation_id, submission_id, student_id, violation_type, summary,
                  recommended_action, escalated_by, escalated_at))

            conn.commit()
            conn.close()

            logger.info(f"Case escalated to dean: {escalation_id} for student {student_id}")
            return {
                'success': True,
                'escalation_id': escalation_id,
                'status': 'pending',
                'escalated_at': escalated_at
            }

        except Exception as e:
            logger.error(f"Error escalating to dean: {e}")
            return {'success': False, 'error': str(e)}
