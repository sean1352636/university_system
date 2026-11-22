"""Integration mixin for AI detector.

* :meth:`generate_gdpr_data_export` — a subject access export of one
  student's AI-writing data (integrity officers): their readings with
  comments (``integrity_ai.export``), alerts, escalations and detector
  activity about them, written owner-only to a chosen folder or under
  ``exports/ai_detector/gdpr``.
* :meth:`push_to_academic_record` — sanctions are not the detector's to
  give. This refers the reading as an integrity case (or adds to the case it
  is already in) and records the proposed sanction for the integrity
  officer, who decides the outcome through the case.
"""

import os
import uuid
from datetime import datetime
from typing import Dict, Any

from education_system.systems.university.shared.ai.ai_detector.core.constants import logger
from education_system.systems.university.shared.ai.ai_detector.detector.alerts_mixin import (
    _send, case_type_for,
)
from education_system.systems.university.shared.ai.ai_detector.detector.audit_privacy_mixin import (
    export_dir, write_private,
)


class IntegrationMixin:
    """Mixin providing integration methods for external systems."""

    def generate_gdpr_data_export(self, student_id: str, student_email: str = None,
                                  request_reference: str = None,
                                  include_analysis_details: bool = True,
                                  include_audit_trail: bool = True,
                                  export_format: str = 'json',
                                  output_dir: str = None) -> Dict[str, Any]:
        """Everything the detector holds about ``student_id``."""
        from education_system.systems.university.application.integrity import ai as integrity_ai
        conn = self._get_connection()
        try:
            who = self.require_officer(conn)
            student = str(student_id)
            if not conn.execute("SELECT 1 FROM students WHERE student_id = ?",
                                (student,)).fetchone():
                raise ValueError(f"No student {student_id}")
            readings = integrity_ai.export(conn, student)
            if not include_analysis_details:
                for r in readings:
                    r.pop('detailed_results', None)
            alerts = [dict(a) for a in conn.execute(
                'SELECT * FROM ai_detector_alerts WHERE student_id = ?', (student,))]
            escalations = [dict(e) for e in conn.execute(
                'SELECT * FROM ai_detector_escalations WHERE student_id = ?', (student,))]
            activity = [dict(a) for a in conn.execute(
                'SELECT * FROM ai_detector_activity_log WHERE target_id = ?', (student,))
                ] if include_audit_trail else []
            self._audit_chain(conn, 'gdpr_export', {'student_id': student,
                                                    'reference': request_reference})
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        export_id = f"GDPR-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        summary = {'readings': len(readings), 'alerts': len(alerts),
                   'escalations': len(escalations), 'activity_records': len(activity)}
        data = {'export_id': export_id, 'student_id': student, 'student_email': student_email,
                'request_reference': request_reference,
                'generated_at': datetime.now().isoformat(), 'generated_by': who.username,
                'data_controller': 'The University (academic integrity)',
                'legal_basis': 'UK GDPR Article 15 - right of access',
                'readings': readings, 'alerts': alerts, 'escalations': escalations,
                'activity_log': activity, 'data_summary': summary}
        path = write_private(os.path.join(export_dir('gdpr', output_dir), f'{export_id}.json'),
                             data)
        self._log_activity('gdpr_export', 'export', student, export_id)
        logger.info(f"GDPR export generated: {export_id}")
        return {'success': True, 'export_id': export_id, 'export_path': path,
                'generated_at': data['generated_at'], 'data_summary': summary}

    # sync_with_plagiarism_checker was removed 2026-10-17: it posted student
    # submissions to made-up vendor endpoints. Similarity checks use the
    # university's own repository (application/integrity/plagiarism_checks).

    def push_to_academic_record(self, student_id: str, submission_id: str,
                                violation_type: str, sanction: str,
                                sanction_details: str = None, notes: str = None,
                                reviewer_id: str = None) -> Dict[str, Any]:
        """Refer the reading behind ``submission_id`` (the detector's
        submission id) as an integrity case, with the proposed sanction for
        the integrity officer. Nothing is put on the student's record until
        the case is decided."""
        conn = self._get_connection()
        try:
            who = self.require_staff(conn)
            ai_result_id, alert = self._reading_of(conn, submission_id=submission_id)
            proposal = f"Proposed outcome: {sanction}" + (f" ({sanction_details})"
                                                         if sanction_details else "")
            note = "; ".join(x for x in (notes, proposal) if x)
            out = self._refer(conn, who, ai_result_id, note, case_type_for(violation_type))
            if out['case_id']:
                conn.execute("INSERT INTO integrity_case_events (case_id, stage, note, actor, at) "
                             "VALUES (?, 'referred', ?, ?, ?)",
                             (out['case_id'], f"From the AI Content Detector. {proposal}",
                              who.username, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            real_student = conn.execute(
                "SELECT s.student_id FROM ai_detector_results r JOIN ai_detector_submissions s "
                "ON s.id = r.submission_id WHERE r.id = ?", (ai_result_id,)).fetchone()[0]
            record_id = f"AR-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
            conn.execute('''
                INSERT INTO ai_detector_academic_records
                (record_id, student_id, submission_id, violation_type, sanction,
                 sanction_details, notes, reviewer_id, status, created_at, ai_result_id, case_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'referred', ?, ?, ?)
            ''', (record_id, real_student, str(submission_id), violation_type, sanction,
                  sanction_details, notes, who.username, datetime.now().isoformat(),
                  ai_result_id, out['case_id']))
            if alert is not None and alert['status'] == 'pending':
                conn.execute("UPDATE ai_detector_alerts SET status = 'referred', case_id = ?, "
                             "reviewed_at = ?, reviewed_by = ? WHERE id = ?",
                             (out['case_id'], datetime.now().isoformat(), who.username,
                              alert['id']))
            self._audit_chain(conn, 'referred_for_sanction',
                              {'ai_result_id': ai_result_id, 'case_id': out['case_id'],
                               'proposed': sanction})
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        _send(out['emails'])
        return {'success': True, 'record_id': record_id, 'case_id': out['case_id'],
                'timestamp': datetime.now().isoformat(),
                'notifications_sent': ['The student (case opened)', 'Integrity officers'],
                'note': 'The integrity officer decides the outcome through the case.'}
