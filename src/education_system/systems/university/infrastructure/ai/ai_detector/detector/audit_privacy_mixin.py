"""Security, audit, and privacy mixin for AI detector."""

import os
import re
import json
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from education_system.systems.university.infrastructure.ai.ai_detector.core.constants import logger


class AuditPrivacyMixin:
    """Mixin providing security/audit and privacy methods."""

    def view_user_activity_log(self, user_id: str = None, action_type: str = None,
                              days: int = 7) -> Dict[str, Any]:
        """
        View detailed log of user actions in the system.

        Args:
            user_id: Filter by user ID
            action_type: Filter by action type
            days: Number of days to look back

        Returns:
            Dict with activity log entries
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Create activity log table if not exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_detector_activity_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    action_type TEXT,
                    target_id TEXT,
                    details TEXT,
                    ip_address TEXT,
                    timestamp TEXT NOT NULL
                )
            ''')

            # Build query
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            query = 'SELECT * FROM ai_detector_activity_log WHERE timestamp >= ?'
            params = [cutoff]

            if user_id:
                query += ' AND user_id = ?'
                params.append(user_id)

            if action_type:
                query += ' AND action_type = ?'
                params.append(action_type)

            query += ' ORDER BY timestamp DESC LIMIT 500'

            cursor.execute(query, params)
            rows = cursor.fetchall()

            activities = [dict(row) for row in rows]

            # Get summary
            cursor.execute('''
                SELECT COUNT(*) as total, COUNT(DISTINCT user_id) as unique_users
                FROM ai_detector_activity_log
                WHERE timestamp >= ?
            ''', (cutoff,))
            summary_row = cursor.fetchone()

            cursor.execute('''
                SELECT user_id, COUNT(*) as count
                FROM ai_detector_activity_log
                WHERE timestamp >= ?
                GROUP BY user_id
                ORDER BY count DESC
                LIMIT 1
            ''', (cutoff,))
            most_active_row = cursor.fetchone()

            conn.close()

            summary = {
                'total': summary_row['total'] if summary_row else 0,
                'unique_users': summary_row['unique_users'] if summary_row else 0,
                'most_active_user': most_active_row['user_id'] if most_active_row else 'N/A'
            }

            return {
                'activities': activities,
                'summary': summary
            }

        except Exception as e:
            logger.error(f"Error viewing activity log: {e}")
            return {'error': str(e)}

    def _log_activity(self, action: str, action_type: str = None, target_id: str = None,
                     details: str = None):
        """Internal method to log user activity"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO ai_detector_activity_log
                (user_id, action, action_type, target_id, details, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                self.current_user.get('username') if self.current_user else 'system',
                action,
                action_type,
                target_id,
                details,
                datetime.now().isoformat()
            ))

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error logging activity: {e}")

    def export_chain_of_custody(self, submission_id: str, student_id: str,
                               case_reference: str = None,
                               include_all_analyses: bool = True,
                               include_reviewer_actions: bool = True,
                               export_format: str = 'pdf') -> Dict[str, Any]:
        """
        Export complete chain of custody for legal proceedings.

        Args:
            submission_id: Submission ID
            student_id: Student ID
            case_reference: Optional case reference number
            include_all_analyses: Include all historical analyses
            include_reviewer_actions: Include reviewer actions
            export_format: Export format (pdf/json)

        Returns:
            Dict with chain of custody document details
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            custody_entries = []

            # Get submission details
            cursor.execute('''
                SELECT * FROM ai_detector_submissions
                WHERE id = ? OR student_id = ?
            ''', (submission_id, student_id))
            submissions = cursor.fetchall()

            for sub in submissions:
                custody_entries.append({
                    'type': 'submission',
                    'timestamp': sub['submission_date'],
                    'details': f"Submission received: {sub['title']}",
                    'evidence_hash': hashlib.sha256(
                        (sub['text_content'] or '').encode()
                    ).hexdigest()[:16]
                })

            # Get all analysis results
            if include_all_analyses:
                cursor.execute('''
                    SELECT * FROM ai_detector_results
                    WHERE submission_id IN (
                        SELECT id FROM ai_detector_submissions
                        WHERE id = ? OR student_id = ?
                    )
                ''', (submission_id, student_id))
                results = cursor.fetchall()

                for result in results:
                    custody_entries.append({
                        'type': 'analysis',
                        'timestamp': result.get('analyzed_at', ''),
                        'details': f"AI analysis performed - Score: {result.get('ai_score', 'N/A')}",
                        'analyzer': result.get('analyzed_by', 'system')
                    })

            # Get reviewer actions
            if include_reviewer_actions:
                cursor.execute('''
                    SELECT * FROM ai_detector_alerts
                    WHERE submission_id = ?
                ''', (submission_id,))
                alerts = cursor.fetchall()

                for alert in alerts:
                    custody_entries.append({
                        'type': 'alert',
                        'timestamp': alert['created_at'],
                        'details': f"Alert created - Risk: {alert['risk_level']}",
                        'status': alert['status']
                    })

                    if alert['reviewed_at']:
                        custody_entries.append({
                            'type': 'review',
                            'timestamp': alert['reviewed_at'],
                            'details': f"Reviewed by {alert['reviewed_by']} - {alert['status']}",
                            'reviewer': alert['reviewed_by']
                        })

            conn.close()

            # Sort by timestamp
            custody_entries.sort(key=lambda x: x.get('timestamp', ''))

            # Calculate time span
            if custody_entries:
                first = custody_entries[0].get('timestamp', '')
                last = custody_entries[-1].get('timestamp', '')
                time_span = f"{first} to {last}"
            else:
                time_span = 'N/A'

            # Generate document
            document_id = f"COC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

            export_dir = os.path.join(os.path.dirname(self.db_path), 'chain_of_custody')
            os.makedirs(export_dir, exist_ok=True)

            document = {
                'document_id': document_id,
                'case_reference': case_reference,
                'student_id': student_id,
                'submission_id': submission_id,
                'custody_entries': custody_entries,
                'time_span': time_span,
                'generated_at': datetime.now().isoformat(),
                'generated_by': self.current_user.get('username') if self.current_user else 'system'
            }

            # Calculate document hash
            doc_hash = hashlib.sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()
            document['integrity_hash'] = doc_hash

            export_path = os.path.join(export_dir, f'{document_id}.json')
            with open(export_path, 'w') as f:
                json.dump(document, f, indent=2)

            logger.info(f"Chain of custody exported: {document_id}")
            return {
                'success': True,
                'document_id': document_id,
                'export_path': export_path,
                'generated_at': document['generated_at'],
                'custody_entries': len(custody_entries),
                'time_span': time_span,
                'hash': doc_hash
            }

        except Exception as e:
            logger.error(f"Error exporting chain of custody: {e}")
            return {'success': False, 'error': str(e)}

    def anonymize_student_data(self, scope: Dict[str, Any], preserve_patterns: bool = True,
                              preserve_temporal: bool = True,
                              output_path: str = None) -> Dict[str, Any]:
        """
        Anonymize student data for research/sharing.

        Args:
            scope: Scope of anonymization (type: student/course/department/all)
            preserve_patterns: Preserve writing patterns while anonymizing
            preserve_temporal: Preserve temporal relationships
            output_path: Output directory for anonymized data

        Returns:
            Dict with anonymization results
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Build query based on scope
            scope_type = scope.get('type', 'all')
            query = 'SELECT * FROM ai_detector_submissions WHERE 1=1'
            params = []

            if scope_type == 'student':
                query += ' AND student_id = ?'
                params.append(scope.get('student_id'))
            elif scope_type == 'course':
                query += ' AND course_code = ?'
                params.append(scope.get('course_code'))
            elif scope_type == 'department':
                # Assuming department is prefix of course_code
                query += ' AND course_code LIKE ?'
                params.append(f"{scope.get('department')}%")

            cursor.execute(query, params)
            records = cursor.fetchall()
            conn.close()

            if not records:
                return {'success': False, 'error': 'No records found for specified scope'}

            # Generate anonymization mapping
            student_map = {}
            anonymized_records = []

            for record in records:
                record_dict = dict(record)

                # Anonymize student ID
                original_student = record_dict.get('student_id', '')
                if original_student not in student_map:
                    student_map[original_student] = f"ANON_{len(student_map):05d}"

                record_dict['original_student_id'] = original_student
                record_dict['student_id'] = student_map[original_student]

                # Anonymize course code if needed
                if not preserve_patterns:
                    record_dict['course_code'] = 'COURSE_ANON'

                # Remove or hash text content
                if record_dict.get('text_content'):
                    if preserve_patterns:
                        # Keep text but remove identifying info
                        text = record_dict['text_content']
                        # Simple anonymization - replace names, emails
                        text = re.sub(r'\b[A-Za-z]+@[A-Za-z]+\.[A-Za-z]+\b', '[EMAIL]', text)
                        record_dict['text_content'] = text
                    else:
                        record_dict['text_content'] = '[REDACTED]'

                # Handle timestamps
                if not preserve_temporal:
                    record_dict['submission_date'] = 'REDACTED'

                anonymized_records.append(record_dict)

            # Save anonymized data
            if output_path is None:
                output_path = os.path.join(os.path.dirname(self.db_path), 'anonymized_data')
            os.makedirs(output_path, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_path = os.path.join(output_path, f'anonymized_data_{timestamp}.json')
            key_path = os.path.join(output_path, f'anonymization_key_{timestamp}.json')

            with open(data_path, 'w') as f:
                json.dump(anonymized_records, f, indent=2, default=str)

            # Save mapping key (for potential de-anonymization)
            with open(key_path, 'w') as f:
                json.dump(student_map, f, indent=2)

            logger.info(f"Data anonymized: {len(records)} records")
            return {
                'success': True,
                'records_processed': len(records),
                'output_path': data_path,
                'key_file': key_path
            }

        except Exception as e:
            logger.error(f"Error anonymizing data: {e}")
            return {'success': False, 'error': str(e)}
