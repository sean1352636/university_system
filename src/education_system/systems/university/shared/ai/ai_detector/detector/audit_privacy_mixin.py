"""Security, audit, and privacy mixin for AI detector.

* The activity log and anonymised extracts are for integrity officers.
* A chain-of-custody record covers one reading: when the text arrived, its
  SHA-256, the reading, the alert and its review, the integrity case it
  became, and whether the detector's audit chain still verifies.
* Files go to a path the officer chooses or under
  ``var/data/university/exports/ai_detector/`` — never beside the database —
  and are readable by their owner only. An anonymised extract never contains
  the real student numbers; the key that maps them back is written to a
  separate file.
"""

import os
import re
import json
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from education_system.systems.university.shared.ai.ai_detector.core.constants import logger

_EMAIL = re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.-]+\b')
_STUDENT_NUMBER = re.compile(r'\b\d{6,9}\b')


def export_dir(name, chosen=None) -> str:
    """``chosen`` or ``exports/ai_detector/<name>``, created owner-only."""
    if chosen:
        folder = str(chosen)
    else:
        from education_system.paths import UNIVERSITY_EXPORTS_DIR
        folder = str(UNIVERSITY_EXPORTS_DIR / "ai_detector" / name)
    os.makedirs(folder, exist_ok=True)
    os.chmod(folder, 0o700)
    return folder


def write_private(path, data) -> str:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, indent=2, default=str)
    return path


class AuditPrivacyMixin:
    """Mixin providing security/audit and privacy methods."""

    def view_user_activity_log(self, user_id: str = None, action_type: str = None,
                               days: int = 7) -> Dict[str, Any]:
        """Who did what in the detector (integrity officers)."""
        conn = self._get_connection()
        try:
            self.require_officer(conn)
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            query = 'SELECT * FROM ai_detector_activity_log WHERE timestamp >= ?'
            params: list = [cutoff]
            if user_id:
                query += ' AND user_id = ?'
                params.append(user_id)
            if action_type:
                query += ' AND action_type = ?'
                params.append(action_type)
            activities = [dict(r) for r in conn.execute(
                query + ' ORDER BY timestamp DESC LIMIT 500', params)]
            summary_row = conn.execute(
                'SELECT COUNT(*) AS total, COUNT(DISTINCT user_id) AS unique_users '
                'FROM ai_detector_activity_log WHERE timestamp >= ?', (cutoff,)).fetchone()
            most_active_row = conn.execute(
                'SELECT user_id, COUNT(*) AS count FROM ai_detector_activity_log WHERE '
                'timestamp >= ? GROUP BY user_id ORDER BY count DESC LIMIT 1',
                (cutoff,)).fetchone()
        finally:
            conn.close()
        return {'activities': activities,
                'summary': {'total': summary_row['total'] if summary_row else 0,
                            'unique_users': summary_row['unique_users'] if summary_row else 0,
                            'most_active_user': most_active_row['user_id']
                            if most_active_row else 'N/A'}}

    def _log_activity(self, action: str, action_type: str = None, target_id: str = None,
                      details: str = None):
        """Record an action in the activity log (a failure is logged, not
        raised: the action itself has already happened)."""
        conn = self._get_connection()
        try:
            conn.execute('''
                INSERT INTO ai_detector_activity_log
                (user_id, action, action_type, target_id, details, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (self._username(), action, action_type, target_id, details,
                  datetime.now().isoformat()))
            conn.commit()
        except Exception:
            conn.rollback()
            logger.exception("Could not record AI detector activity %s", action)
        finally:
            conn.close()

    def export_chain_of_custody(self, submission_id: str, student_id: str = None,
                                case_reference: str = None,
                                include_all_analyses: bool = True,
                                include_reviewer_actions: bool = True,
                                export_format: str = 'json',
                                output_dir: str = None) -> Dict[str, Any]:
        """The custody record of one reading (``submission_id`` is the
        detector's submission id): for the reviewing staff or an officer."""
        from education_system.systems.university.application.integrity import (
            access as integrity_access,
        )
        conn = self._get_connection()
        try:
            who = self.require_staff(conn)
            sub = conn.execute('SELECT * FROM ai_detector_submissions WHERE id = ?',
                               (submission_id,)).fetchone()
            if sub is None:
                raise ValueError(f"No reading for submission {submission_id}")
            if not (integrity_access.is_officer(conn, who)
                    or integrity_access.can_review(conn, who, sub['course_code'])):
                raise PermissionError("You do not review this module")
            text = sub['submission_text'] or ''
            entries: List[Dict[str, Any]] = [{
                'type': 'submission', 'timestamp': sub['submission_date'],
                'details': f"Text received: {sub['title'] or 'untitled'} "
                           f"({sub['word_count'] or 0} words), read by "
                           f"{sub['checked_by'] or 'unknown'}",
                'evidence_hash': hashlib.sha256(text.encode('utf-8')).hexdigest()
                if text else 'text removed under the retention policy'}]
            results = conn.execute('SELECT * FROM ai_detector_results WHERE submission_id = ?',
                                   (submission_id,)).fetchall()
            if include_all_analyses:
                for r in results:
                    entries.append({'type': 'analysis', 'timestamp': r['created_at'],
                                    'details': f"Reading {r['id']}: {r['level'] or 'score'} "
                                               f"(strength {r['ai_score']}, method "
                                               f"{r['method'] or 'retired detector'})"})
            result_ids = [r['id'] for r in results] or [-1]
            marks = ','.join('?' * len(result_ids))
            if include_reviewer_actions:
                for alert in conn.execute(f'SELECT * FROM ai_detector_alerts WHERE '  # nosec B608
                                          f'ai_result_id IN ({marks}) OR submission_id = ?',
                                          (*result_ids, str(submission_id))).fetchall():
                    entries.append({'type': 'alert', 'timestamp': alert['created_at'],
                                    'details': f"Alert ({alert['risk_level']}), status "
                                               f"{alert['status']}"})
                for review in conn.execute(f'SELECT * FROM integrity_ai_reviews WHERE '  # nosec B608
                                           f'ai_result_id IN ({marks})', result_ids).fetchall():
                    entries.append({'type': 'review', 'timestamp': review['reviewed_at'],
                                    'details': f"Reviewed by {review['reviewed_by']}: "
                                               f"{review['decision']} — {review['note']}",
                                    'reviewer': review['reviewed_by'],
                                    'case_id': review['case_id']})
                    if review['case_id']:
                        for event in conn.execute(
                                'SELECT * FROM integrity_case_events WHERE case_id = ? ORDER BY '
                                'event_id', (review['case_id'],)).fetchall():
                            entries.append({'type': 'case', 'timestamp': event['at'],
                                            'details': f"Case {review['case_id']} "
                                                       f"{event['stage']}: {event['note'] or ''}",
                                            'actor': event['actor']})
            chain = self._chain_status(conn)
            self._audit_chain(conn, 'custody_exported', {'submission_id': submission_id})
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        entries.sort(key=lambda x: x.get('timestamp') or '')
        time_span = (f"{entries[0].get('timestamp')} to {entries[-1].get('timestamp')}"
                     if entries else 'N/A')
        document_id = f"COC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        document = {'document_id': document_id, 'case_reference': case_reference,
                    'student_id': sub['student_id'], 'submission_id': submission_id,
                    'custody_entries': entries, 'time_span': time_span,
                    'audit_chain': chain, 'generated_at': datetime.now().isoformat(),
                    'generated_by': who.username}
        document['integrity_hash'] = hashlib.sha256(
            json.dumps(document, sort_keys=True, default=str).encode()).hexdigest()
        path = write_private(os.path.join(export_dir('chain_of_custody', output_dir),
                                          f'{document_id}.json'), document)
        self._log_activity('chain_of_custody_exported', 'export', str(submission_id), document_id)
        return {'success': True, 'document_id': document_id, 'export_path': path,
                'generated_at': document['generated_at'], 'custody_entries': len(entries),
                'time_span': time_span, 'hash': document['integrity_hash']}

    @staticmethod
    def _chain_status(conn) -> Optional[Dict[str, Any]]:
        try:
            from education_system.systems.university.shared.ai.ai_detector.features import (
                blockchain_audit,
            )
        except ImportError:
            return None
        verify = getattr(blockchain_audit, 'verify', None)
        return verify(conn) if verify is not None else None

    def anonymize_student_data(self, scope: Dict[str, Any], preserve_patterns: bool = True,
                               preserve_temporal: bool = True,
                               output_path: str = None) -> Dict[str, Any]:
        """An anonymised extract of readings for research (integrity
        officers). Student numbers become ``ANON_00001``…, e-mail addresses
        and student numbers in the text are masked; the key mapping them back
        goes to its own owner-only file, never into the extract."""
        conn = self._get_connection()
        try:
            self.require_officer(conn)
            scope_type = scope.get('type', 'all')
            query = ('SELECT s.id, s.student_id, s.title, s.course_code, s.assignment_id, '
                     's.submission_date, s.word_count, s.submission_text, r.ai_score, r.level, '
                     'r.method FROM ai_detector_submissions s LEFT JOIN ai_detector_results r '
                     'ON r.submission_id = s.id WHERE COALESCE(s.purged, 0) = 0')
            params: list = []
            if scope_type == 'student':
                query += ' AND s.student_id = ?'
                params.append(scope.get('student_id'))
            elif scope_type == 'course':
                query += ' AND s.course_code = ?'
                params.append(scope.get('course_code'))
            elif scope_type == 'department':
                query += ' AND s.course_code LIKE ?'
                params.append(f"{scope.get('department')}%")
            records = conn.execute(query, params).fetchall()
            self._audit_chain(conn, 'anonymised_extract', {'scope': scope,
                                                           'records': len(records)})
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        if not records:
            return {'success': False, 'error': 'No records found for specified scope'}
        student_map: Dict[str, str] = {}
        anonymized = []
        for record in records:
            row = dict(record)
            original = row.pop('student_id') or ''
            student_map.setdefault(original, f"ANON_{len(student_map) + 1:05d}")
            row['student'] = student_map[original]
            text = row.pop('submission_text') or ''
            if preserve_patterns:
                text = _STUDENT_NUMBER.sub('[NUMBER]', _EMAIL.sub('[EMAIL]', text))
                row['text'] = text
            else:
                row['course_code'] = 'COURSE_ANON'
            if not preserve_temporal:
                row['submission_date'] = None
            anonymized.append(row)
        folder = export_dir('anonymised', output_path)
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        data_path = write_private(os.path.join(folder, f'anonymised_data_{stamp}.json'),
                                  anonymized)
        key_path = write_private(os.path.join(folder, f'anonymisation_key_{stamp}.json'),
                                 {v: k for k, v in student_map.items()})
        self._log_activity('data_anonymised', 'export', scope_type,
                           f"{len(records)} records → {data_path}")
        return {'success': True, 'records_processed': len(records), 'output_path': data_path,
                'key_file': key_path,
                'note': 'Keep the key file apart from the extract; share only the extract.'}
