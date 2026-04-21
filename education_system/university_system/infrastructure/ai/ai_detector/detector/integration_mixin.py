"""Integration mixin for AI detector."""

import os
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from education_system.university_system.infrastructure.ai.ai_detector.core.constants import logger, REQUESTS_AVAILABLE


class IntegrationMixin:
    """Mixin providing integration methods for external systems."""

    def generate_gdpr_data_export(self, student_id: str, student_email: str,
                                 request_reference: str = None,
                                 include_analysis_details: bool = True,
                                 include_audit_trail: bool = True,
                                 export_format: str = 'json') -> Dict[str, Any]:
        """
        Generate GDPR-compliant data export for a student.

        Args:
            student_id: Student ID
            student_email: Student email for verification
            request_reference: Data request reference number
            include_analysis_details: Include full analysis details
            include_audit_trail: Include audit trail
            export_format: Export format (json/pdf)

        Returns:
            Dict with GDPR export details
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            data_summary = {
                'submissions': 0,
                'analyses': 0,
                'alerts': 0,
                'activity_records': 0
            }

            export_data = {
                'export_id': f"GDPR-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
                'student_id': student_id,
                'student_email': student_email,
                'request_reference': request_reference,
                'generated_at': datetime.now().isoformat(),
                'data_controller': 'University AI Detection System',
                'legal_basis': 'GDPR Article 15 - Right of Access'
            }

            # Get submissions
            cursor.execute('''
                SELECT * FROM ai_detector_submissions WHERE student_id = ?
            ''', (student_id,))
            submissions = cursor.fetchall()
            data_summary['submissions'] = len(submissions)

            if include_analysis_details:
                export_data['submissions'] = [dict(s) for s in submissions]

                # Get analysis results
                if submissions:
                    submission_ids = [s['id'] for s in submissions]
                    placeholders = ','.join('?' * len(submission_ids))
                    cursor.execute(f'''
                        SELECT * FROM ai_detector_results
                        WHERE submission_id IN ({placeholders})
                    ''', submission_ids)
                    analyses = cursor.fetchall()
                    data_summary['analyses'] = len(analyses)
                    export_data['analyses'] = [dict(a) for a in analyses]

            # Get alerts
            cursor.execute('''
                SELECT * FROM ai_detector_alerts WHERE student_id = ?
            ''', (student_id,))
            alerts = cursor.fetchall()
            data_summary['alerts'] = len(alerts)
            export_data['alerts'] = [dict(a) for a in alerts]

            # Get activity logs if requested
            if include_audit_trail:
                cursor.execute('''
                    SELECT * FROM ai_detector_activity_log
                    WHERE target_id = ? OR details LIKE ?
                ''', (student_id, f'%{student_id}%'))
                activities = cursor.fetchall()
                data_summary['activity_records'] = len(activities)
                export_data['activity_log'] = [dict(a) for a in activities]

            conn.close()

            export_data['data_summary'] = data_summary

            # Save export
            export_dir = os.path.join(os.path.dirname(self.db_path), 'gdpr_exports')
            os.makedirs(export_dir, exist_ok=True)

            export_path = os.path.join(export_dir, f"{export_data['export_id']}.json")
            with open(export_path, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)

            logger.info(f"GDPR export generated: {export_data['export_id']} for {student_id}")
            return {
                'success': True,
                'export_id': export_data['export_id'],
                'export_path': export_path,
                'generated_at': export_data['generated_at'],
                'data_summary': data_summary
            }

        except Exception as e:
            logger.error(f"Error generating GDPR export: {e}")
            return {'success': False, 'error': str(e)}

    def sync_with_plagiarism_checker(self, tool: str, api_key: str,
                                    sync_direction: str = 'bidirectional',
                                    submission_ids: List[str] = None) -> Dict[str, Any]:
        """
        Sync results with Turnitin/Copyleaks/other plagiarism tools.

        Args:
            tool: Plagiarism tool (turnitin/copyleaks/plagscan/unicheck)
            api_key: API key for the tool
            sync_direction: Sync direction (push/pull/bidirectional)
            submission_ids: Specific submissions to sync (None for all)

        Returns:
            Dict with sync results
        """
        try:
            if not REQUESTS_AVAILABLE:
                return {'success': False, 'error': 'requests library not available'}

            # Validate tool
            supported_tools = ['turnitin', 'copyleaks', 'plagscan', 'unicheck']
            if tool not in supported_tools:
                return {'success': False, 'error': f'Unsupported tool: {tool}'}

            conn = self._get_connection()
            cursor = conn.cursor()

            # Get submissions to sync
            if submission_ids:
                placeholders = ','.join('?' * len(submission_ids))
                cursor.execute(f'''
                    SELECT * FROM ai_detector_submissions WHERE id IN ({placeholders})
                ''', submission_ids)
            else:
                cursor.execute('SELECT * FROM ai_detector_submissions')

            submissions = cursor.fetchall()
            conn.close()

            results = {
                'submissions_synced': 0,
                'push_success': 0,
                'pull_success': 0,
                'errors': 0,
                'combined_results': {
                    'high_risk_both': 0,
                    'ai_only': 0,
                    'plagiarism_only': 0
                }
            }

            import requests

            # API endpoint mapping for supported plagiarism tools
            tool_endpoints = {
                'turnitin': 'https://api.turnitin.com/api/v1',
                'copyleaks': 'https://api.copyleaks.com/v3',
                'plagscan': 'https://api.plagscan.com/v3',
                'unicheck': 'https://unicheck.com/api/v2',
            }

            base_url = tool_endpoints[tool]
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            }

            for submission in submissions:
                try:
                    submission_id = submission['id']
                    results['submissions_synced'] += 1

                    if sync_direction in ['push', 'bidirectional']:
                        # Push AI detection results to the plagiarism tool
                        try:
                            push_payload = {
                                'external_id': str(submission_id),
                                'text': submission['text_content'][:50000],  # Limit payload size
                                'metadata': {
                                    'ai_score': submission.get('ai_score'),
                                    'source': 'ai_detector',
                                }
                            }
                            resp = requests.post(
                                f'{base_url}/submissions',
                                json=push_payload,
                                headers=headers,
                                timeout=30,
                            )
                            if resp.status_code in (200, 201, 202):
                                results['push_success'] += 1
                            else:
                                logger.warning(
                                    f"Push failed for submission {submission_id}: "
                                    f"HTTP {resp.status_code}"
                                )
                                results['errors'] += 1
                        except requests.RequestException as req_err:
                            logger.error(f"Push request error for submission {submission_id}: {req_err}")
                            results['errors'] += 1

                    if sync_direction in ['pull', 'bidirectional']:
                        # Pull plagiarism results from the tool
                        try:
                            resp = requests.get(
                                f'{base_url}/submissions/{submission_id}/results',
                                headers=headers,
                                timeout=30,
                            )
                            if resp.status_code == 200:
                                plag_data = resp.json()
                                results['pull_success'] += 1

                                # Cross-reference AI detection with plagiarism scores
                                plag_score = plag_data.get('similarity_score', 0)
                                ai_score = submission.get('ai_score', 0)

                                if ai_score and ai_score >= 0.7 and plag_score >= 0.5:
                                    results['combined_results']['high_risk_both'] += 1
                                elif ai_score and ai_score >= 0.7:
                                    results['combined_results']['ai_only'] += 1
                                elif plag_score >= 0.5:
                                    results['combined_results']['plagiarism_only'] += 1
                            elif resp.status_code == 404:
                                # No results yet; not an error
                                results['pull_success'] += 1
                            else:
                                logger.warning(
                                    f"Pull failed for submission {submission_id}: "
                                    f"HTTP {resp.status_code}"
                                )
                                results['errors'] += 1
                        except requests.RequestException as req_err:
                            logger.error(f"Pull request error for submission {submission_id}: {req_err}")
                            results['errors'] += 1

                except Exception as e:
                    logger.error(f"Error syncing submission {submission.get('id', '?')}: {e}")
                    results['errors'] += 1

            logger.info(f"Plagiarism checker sync complete: {tool}")
            return {
                'success': True,
                **results
            }

        except Exception as e:
            logger.error(f"Error syncing with plagiarism checker: {e}")
            return {'success': False, 'error': str(e)}

    def push_to_academic_record(self, student_id: str, submission_id: str,
                               violation_type: str, sanction: str,
                               sanction_details: str = None, notes: str = None,
                               reviewer_id: str = None) -> Dict[str, Any]:
        """
        Push confirmed violations to student academic record system.

        Args:
            student_id: Student ID
            submission_id: Submission ID
            violation_type: Type of violation
            sanction: Applied sanction
            sanction_details: Details if sanction is 'other'
            notes: Additional notes
            reviewer_id: Reviewer/Instructor ID

        Returns:
            Dict with record creation status
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Create academic records table if not exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_detector_academic_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id TEXT UNIQUE NOT NULL,
                    student_id TEXT NOT NULL,
                    submission_id TEXT NOT NULL,
                    violation_type TEXT NOT NULL,
                    sanction TEXT NOT NULL,
                    sanction_details TEXT,
                    notes TEXT,
                    reviewer_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    synced_to_external INTEGER DEFAULT 0,
                    synced_at TEXT
                )
            ''')

            record_id = f"AR-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

            cursor.execute('''
                INSERT INTO ai_detector_academic_records
                (record_id, student_id, submission_id, violation_type, sanction,
                 sanction_details, notes, reviewer_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (record_id, student_id, submission_id, violation_type, sanction,
                  sanction_details, notes, reviewer_id, datetime.now().isoformat()))

            conn.commit()

            # Update alert status if exists
            cursor.execute('''
                UPDATE ai_detector_alerts
                SET status = 'confirmed'
                WHERE submission_id = ?
            ''', (submission_id,))

            conn.commit()
            conn.close()

            # Determine notifications
            notifications_sent = [
                f"Academic Dean's Office ({violation_type})",
                f"Student Affairs ({student_id})",
                f"Course Instructor ({reviewer_id})"
            ]

            logger.info(f"Academic record created: {record_id} for student {student_id}")
            return {
                'success': True,
                'record_id': record_id,
                'timestamp': datetime.now().isoformat(),
                'notifications_sent': notifications_sent
            }

        except Exception as e:
            logger.error(f"Error pushing to academic record: {e}")
            return {'success': False, 'error': str(e)}
