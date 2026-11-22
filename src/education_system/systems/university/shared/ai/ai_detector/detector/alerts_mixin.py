"""Alerts and notifications mixin for AIDetector - alert thresholds, email alerts, alert queue, escalation.

A reading at or above the review threshold opens an ``ai_detector_alerts``
row (``detector/reading.store``). Reviewing an alert is the integrity review
of that reading (``application/integrity/ai.review_flag``), so the alert
queue, the Academic Integrity window and the API can never disagree:

* dismissing → ``no_concern`` with the reason;
* referring or escalating → ``refer``, which opens an integrity case
  (``integrity_cases``) with the reading as evidence. The case — not the
  detector — decides any outcome, and a reading alone can never lead to a
  penalty.

E-mails go through the university outbox after the change is committed.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Any

from education_system.systems.university.shared.ai.ai_detector.core.constants import logger

LEVELS = ('low', 'medium', 'high', 'critical')
_CASE_TYPES = (("plagiar", "plagiarism"), ("collu", "collusion"),
               ("contract", "contract_cheating"), ("fabric", "fabrication"),
               ("citation", "fabrication"), ("cheat", "cheating"))


def case_type_for(violation_type) -> str:
    """The integrity case type for a detector violation label."""
    text = str(violation_type or "").lower()
    return next((kind for word, kind in _CASE_TYPES if word in text), "ai_misuse")


def _send(emails) -> None:
    if emails:
        from education_system.systems.university.infrastructure.ui.record_screens import (
            send_emails,
        )
        send_emails(emails)


class AlertsMixin:
    """Mixin providing alerts and notifications functions (23-27)."""

    # ── helpers ─────────────────────────────────────────────────────────

    def _audit_chain(self, conn, event, payload) -> None:
        from education_system.systems.university.shared.ai.ai_detector.detector import (
            reading,
        )
        reading._audit(conn, event, payload, self._username())

    @staticmethod
    def _reading_of(conn, ai_result_id=None, submission_id=None):
        """``(ai_result_id, alert row or None)`` for a reading, given the
        reading's result id or the detector's submission id."""
        if ai_result_id is None and submission_id is not None:
            row = conn.execute("SELECT id FROM ai_detector_results WHERE submission_id = ? "
                               "ORDER BY id DESC LIMIT 1", (submission_id,)).fetchone()
            if row is None:
                raise ValueError(f"No reading for submission {submission_id}")
            ai_result_id = row[0]
        alert = conn.execute("SELECT * FROM ai_detector_alerts WHERE ai_result_id = ? "
                             "ORDER BY id DESC LIMIT 1", (ai_result_id,)).fetchone()
        return ai_result_id, alert

    def _refer(self, conn, who, ai_result_id, note, case_type="ai_misuse") -> Dict[str, Any]:
        """Refer a reading (or return the case it is already in)."""
        from education_system.systems.university.application.integrity import ai as integrity_ai
        row = conn.execute("SELECT decision, case_id FROM integrity_ai_reviews WHERE "
                           "ai_result_id = ?", (ai_result_id,)).fetchone()
        if row is not None:
            if row[0] == 'refer':
                return {"case_id": row[1], "emails": []}
            raise ValueError("This reading was reviewed as no concern; open a case by hand in "
                             "Academic Integrity if that has changed")
        return integrity_ai.review_flag(conn, who, ai_result_id, "refer", note,
                                        case_type=case_type)

    # ── thresholds and e-mail settings ──────────────────────────────────

    def configure_alert_thresholds(self, low: float = 0.3, medium: float = 0.5,
                                   high: float = 0.7, critical: float = 0.9) -> Dict[str, Any]:
        """Display bands for readings. ``high`` is the review threshold — the
        integrity setting ``ai_review_threshold`` — so changing it needs an
        integrity officer."""
        if not (0 <= low < medium < high < critical <= 1):
            return {'success': False, 'error': 'Thresholds must be in ascending order between 0 and 1'}
        from education_system.systems.university.application.integrity import (
            access as integrity_access,
        )
        conn = self._get_connection()
        try:
            who = self.require_officer(conn)
            integrity_access.set_setting(conn, who, "ai_review_threshold", high)
            thresholds = {'low': low, 'medium': medium, 'high': high, 'critical': critical}
            for key, value in thresholds.items():
                conn.execute('''
                    INSERT OR REPLACE INTO ai_detector_alert_config
                    (config_key, config_value, updated_at, updated_by)
                    VALUES (?, ?, ?, ?)
                ''', (f'threshold_{key}', str(value), datetime.now().isoformat(), who.username))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        self.alert_thresholds = thresholds
        return {'success': True, 'thresholds': thresholds, 'review_threshold': high,
                'updated_at': datetime.now().isoformat()}

    def setup_email_alerts(self, email: str, risk_levels: List[str] = None,
                           include_details: bool = True) -> Dict[str, Any]:
        """Also e-mail ``email`` about new alerts at ``risk_levels`` (the
        module's staff are always told). Details never include the student's
        text."""
        if not email or '@' not in email:
            return {'success': False, 'error': 'Invalid email address'}
        risk_levels = [r for r in (risk_levels or ['high']) if r in LEVELS]
        if not risk_levels:
            return {'success': False, 'error': 'No valid risk levels specified'}
        conn = self._get_connection()
        try:
            who = self.require_officer(conn)
            conn.execute('''
                INSERT INTO ai_detector_email_alerts
                (email, risk_levels, include_details, is_active, created_at, created_by)
                VALUES (?, ?, ?, 1, ?, ?)
            ''', (email.strip(), ','.join(risk_levels), 1 if include_details else 0,
                  datetime.now().isoformat(), who.username))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return {'success': True, 'email': email, 'risk_levels': risk_levels,
                'include_details': include_details, 'configured_at': datetime.now().isoformat()}

    # ── the queue ───────────────────────────────────────────────────────

    def view_alert_queue(self, risk_level: str = None, include_reviewed: bool = False) -> Dict[str, Any]:
        """Alerts on the modules the signed-in person reviews."""
        conn = self._get_connection()
        try:
            scope, params = self._scope_sql(self._module_scope(conn), "module_code")
            sql = ('SELECT id AS alert_id, submission_id, ai_result_id, student_id, '
                   'submission_title, module_code, assignment_id, risk_level, ai_score, status, '
                   'created_at, reviewed_at, reviewed_by, dismissal_reason, case_id '
                   'FROM ai_detector_alerts WHERE 1 = 1' + scope)
            if not include_reviewed:
                sql += " AND status = 'pending'"
            if risk_level:
                sql += ' AND risk_level = ?'
                params.append(risk_level)
            alerts = [dict(r) for r in conn.execute(sql + ' ORDER BY created_at DESC', params)]
            summary: Dict[str, int] = {}
            for alert in alerts:
                if alert['status'] == 'pending':
                    summary[alert['risk_level']] = summary.get(alert['risk_level'], 0) + 1
        finally:
            conn.close()
        return {'alerts': alerts, 'total': len(alerts), 'summary': summary}

    def dismiss_alert(self, alert_id: str, reason: str, custom_reason: str = None,
                      notes: str = None) -> Dict[str, Any]:
        """No concern: recorded as the integrity review of the reading."""
        from education_system.systems.university.application.integrity import ai as integrity_ai
        if not alert_id:
            return {'success': False, 'error': 'Alert ID is required'}
        reason_text = custom_reason if reason == 'other' and custom_reason else reason
        if not str(reason_text or '').strip():
            return {'success': False, 'error': 'Give the reason'}
        conn = self._get_connection()
        try:
            who = self.require_staff(conn)
            alert = conn.execute('SELECT * FROM ai_detector_alerts WHERE id = ?',
                                 (alert_id,)).fetchone()
            if not alert:
                return {'success': False, 'error': 'Alert not found'}
            if alert['status'] != 'pending':
                return {'success': False, 'error': f'Alert already {alert["status"]}'}
            note = reason_text + (f" — {notes}" if notes else "")
            emails = []
            if alert['ai_result_id']:
                emails = integrity_ai.review_flag(conn, who, alert['ai_result_id'], 'no_concern',
                                                  note)['emails']
            now = datetime.now().isoformat()
            conn.execute('''
                UPDATE ai_detector_alerts
                SET status = 'dismissed', reviewed_at = ?, reviewed_by = ?,
                    dismissal_reason = ?, notes = ?
                WHERE id = ?
            ''', (now, who.username, reason_text, notes, alert_id))
            self._audit_chain(conn, 'alert_dismissed', {'alert_id': alert_id,
                                                        'ai_result_id': alert['ai_result_id'],
                                                        'reason': reason_text})
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        _send(emails)
        logger.info(f"Alert {alert_id} dismissed by {who.username}: {reason_text}")
        return {'success': True, 'alert_id': alert_id, 'dismissed_by': who.username,
                'dismissed_at': now, 'reason': reason_text}

    def refer_alert(self, alert_id: str, note: str, case_type: str = 'ai_misuse') -> Dict[str, Any]:
        """Refer the alert's reading as an integrity case."""
        if not str(note or '').strip():
            return {'success': False, 'error': 'Say why the reading is being referred'}
        conn = self._get_connection()
        try:
            who = self.require_staff(conn)
            alert = conn.execute('SELECT * FROM ai_detector_alerts WHERE id = ?',
                                 (alert_id,)).fetchone()
            if not alert or not alert['ai_result_id']:
                return {'success': False, 'error': 'Alert not found, or it has no reading'}
            out = self._refer(conn, who, alert['ai_result_id'], note.strip(), case_type)
            conn.execute("UPDATE ai_detector_alerts SET status = 'referred', reviewed_at = ?, "
                         "reviewed_by = ?, notes = ?, case_id = ? WHERE id = ?",
                         (datetime.now().isoformat(), who.username, note.strip(),
                          out['case_id'], alert_id))
            self._audit_chain(conn, 'alert_referred', {'alert_id': alert_id,
                                                       'ai_result_id': alert['ai_result_id'],
                                                       'case_id': out['case_id']})
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        _send(out['emails'])
        return {'success': True, 'alert_id': alert_id, 'case_id': out['case_id']}

    def escalate_to_dean(self, submission_id: str, student_id: str, violation_type: str,
                         summary: str, recommended_action: str = None) -> Dict[str, Any]:
        """Escalate a reading: it is referred as an integrity case (the
        integrity officers are told), and the escalation is recorded with the
        case number. ``submission_id`` is the detector's submission id."""
        if not all([submission_id, violation_type, summary]):
            return {'success': False, 'error': 'All required fields must be provided'}
        conn = self._get_connection()
        try:
            who = self.require_staff(conn)
            ai_result_id, alert = self._reading_of(conn, submission_id=submission_id)
            note = summary.strip() + (f" Recommended: {recommended_action}"
                                      if recommended_action else "")
            out = self._refer(conn, who, ai_result_id, note, case_type_for(violation_type))
            real_student = conn.execute(
                "SELECT s.student_id FROM ai_detector_results r JOIN ai_detector_submissions s "
                "ON s.id = r.submission_id WHERE r.id = ?", (ai_result_id,)).fetchone()[0]
            escalation_id = f"ESC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
            now = datetime.now().isoformat()
            conn.execute('''
                INSERT INTO ai_detector_escalations
                (escalation_id, submission_id, student_id, violation_type, summary,
                 recommended_action, status, escalated_by, escalated_at, ai_result_id, case_id)
                VALUES (?, ?, ?, ?, ?, ?, 'referred', ?, ?, ?, ?)
            ''', (escalation_id, str(submission_id), real_student, violation_type, summary,
                  recommended_action, who.username, now, ai_result_id, out['case_id']))
            if alert is not None and alert['status'] == 'pending':
                conn.execute("UPDATE ai_detector_alerts SET status = 'referred', case_id = ?, "
                             "reviewed_at = ?, reviewed_by = ? WHERE id = ?",
                             (out['case_id'], now, who.username, alert['id']))
            self._audit_chain(conn, 'escalated', {'escalation_id': escalation_id,
                                                  'ai_result_id': ai_result_id,
                                                  'case_id': out['case_id']})
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        _send(out['emails'])
        logger.info(f"Reading {ai_result_id} escalated as case {out['case_id']}")
        return {'success': True, 'escalation_id': escalation_id, 'case_id': out['case_id'],
                'status': 'referred', 'escalated_at': now}
