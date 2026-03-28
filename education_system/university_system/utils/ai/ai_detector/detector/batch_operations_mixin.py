"""Batch operations mixin for AI detector."""

import os
import json
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from education_system.university_system.utils.ai.ai_detector.core.constants import logger


class BatchOperationsMixin:
    """Mixin providing batch analysis and job management methods."""

    def batch_analyze_folder(self, folder_path: str, file_types: List[str] = None,
                            recursive: bool = False) -> Dict[str, Any]:
        """
        Analyze all documents in a selected folder.

        Args:
            folder_path: Path to folder containing documents
            file_types: List of file extensions to include
            recursive: Whether to include subdirectories

        Returns:
            Dict with analysis results and summary
        """
        try:
            if not os.path.isdir(folder_path):
                return {'success': False, 'error': f'Directory not found: {folder_path}'}

            if file_types is None:
                file_types = ['txt', 'docx', 'pdf']

            start_time = time.time()
            files_analyzed = 0
            files_failed = 0
            results = []
            risk_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}

            # Collect files
            files_to_analyze = []
            if recursive:
                for root, dirs, files in os.walk(folder_path):
                    for f in files:
                        if any(f.lower().endswith(f'.{ext}') for ext in file_types):
                            files_to_analyze.append(os.path.join(root, f))
            else:
                for f in os.listdir(folder_path):
                    if any(f.lower().endswith(f'.{ext}') for ext in file_types):
                        files_to_analyze.append(os.path.join(folder_path, f))

            # Analyze each file
            for file_path in files_to_analyze:
                try:
                    # Read file content
                    content = self._read_file_content(file_path)
                    if not content:
                        files_failed += 1
                        continue

                    # Analyze
                    result = self.analyze_text(
                        text=content,
                        title=os.path.basename(file_path)
                    )

                    files_analyzed += 1

                    # Categorize risk
                    ai_score = result.get('ai_score', 0)
                    if ai_score >= 0.9:
                        risk_level = 'critical'
                    elif ai_score >= 0.7:
                        risk_level = 'high'
                    elif ai_score >= 0.5:
                        risk_level = 'medium'
                    else:
                        risk_level = 'low'

                    risk_counts[risk_level] += 1

                    results.append({
                        'file': os.path.basename(file_path),
                        'ai_score': ai_score,
                        'risk_level': risk_level
                    })

                except Exception as e:
                    logger.error(f"Error analyzing {file_path}: {e}")
                    files_failed += 1

            total_time = time.time() - start_time

            # Save report
            report_path = os.path.join(folder_path, f'batch_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
            with open(report_path, 'w') as f:
                json.dump({'results': results, 'summary': risk_counts}, f, indent=2)

            return {
                'success': True,
                'files_analyzed': files_analyzed,
                'files_failed': files_failed,
                'total_time': total_time,
                'summary': risk_counts,
                'report_path': report_path
            }

        except Exception as e:
            logger.error(f"Error in batch folder analysis: {e}")
            return {'success': False, 'error': str(e)}

    def _read_file_content(self, file_path: str) -> Optional[str]:
        """Read content from various file types"""
        try:
            ext = os.path.splitext(file_path)[1].lower()

            if ext == '.txt':
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
            elif ext == '.md':
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
            elif ext == '.docx':
                try:
                    import docx
                    doc = docx.Document(file_path)
                    return '\n'.join([para.text for para in doc.paragraphs])
                except ImportError:
                    logger.warning("python-docx not installed, skipping .docx files")
                    return None
            elif ext == '.pdf':
                try:
                    import pypdf
                    with open(file_path, 'rb') as f:
                        reader = pypdf.PdfReader(f)
                        text = ''
                        for page in reader.pages:
                            text += page.extract_text() or ''
                        return text
                except ImportError:
                    logger.warning("pypdf not installed, skipping .pdf files")
                    return None
            else:
                return None

        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return None

    def batch_analyze_lms_export(self, export_path: str, lms_format: str = 'auto',
                                course_code: str = None, assignment_name: str = None) -> Dict[str, Any]:
        """
        Process exported assignments from Canvas/Blackboard/Moodle.

        Args:
            export_path: Path to LMS export file/folder
            lms_format: LMS format (canvas/blackboard/moodle/auto)
            course_code: Optional course code for tracking
            assignment_name: Optional assignment name

        Returns:
            Dict with analysis results
        """
        try:
            if not os.path.exists(export_path):
                return {'success': False, 'error': f'Path not found: {export_path}'}

            # Detect LMS format if auto
            if lms_format == 'auto':
                lms_format = self._detect_lms_format(export_path)

            submissions_found = 0
            submissions_analyzed = 0
            parse_errors = 0
            risk_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
            flagged_students = []

            # Parse LMS export based on format
            submissions = self._parse_lms_export(export_path, lms_format)
            submissions_found = len(submissions)

            for submission in submissions:
                try:
                    result = self.analyze_text(
                        text=submission.get('content', ''),
                        title=submission.get('title', 'LMS Submission'),
                        student_id=submission.get('student_id'),
                        course_code=course_code,
                        assignment_id=assignment_name
                    )

                    submissions_analyzed += 1
                    ai_score = result.get('ai_score', 0)

                    # Categorize risk
                    if ai_score >= 0.9:
                        risk_level = 'critical'
                    elif ai_score >= 0.7:
                        risk_level = 'high'
                    elif ai_score >= 0.5:
                        risk_level = 'medium'
                    else:
                        risk_level = 'low'

                    risk_counts[risk_level] += 1

                    if risk_level in ['high', 'critical']:
                        flagged_students.append({
                            'student_id': submission.get('student_id'),
                            'risk_level': risk_level,
                            'ai_score': ai_score
                        })

                except Exception as e:
                    logger.error(f"Error analyzing LMS submission: {e}")
                    parse_errors += 1

            # Save report
            report_dir = os.path.dirname(export_path) if os.path.isfile(export_path) else export_path
            report_path = os.path.join(report_dir, f'lms_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')

            with open(report_path, 'w') as f:
                json.dump({
                    'summary': risk_counts,
                    'flagged_students': flagged_students
                }, f, indent=2)

            return {
                'success': True,
                'submissions_found': submissions_found,
                'submissions_analyzed': submissions_analyzed,
                'parse_errors': parse_errors,
                'summary': risk_counts,
                'flagged_students': flagged_students,
                'report_path': report_path
            }

        except Exception as e:
            logger.error(f"Error in LMS export analysis: {e}")
            return {'success': False, 'error': str(e)}

    def _detect_lms_format(self, export_path: str) -> str:
        """Detect LMS format from export structure"""
        # Simple heuristic detection
        if os.path.isdir(export_path):
            files = os.listdir(export_path)
            if any('canvas' in f.lower() for f in files):
                return 'canvas'
            elif any('blackboard' in f.lower() for f in files):
                return 'blackboard'
            elif any('moodle' in f.lower() for f in files):
                return 'moodle'
        return 'generic'

    def _parse_lms_export(self, export_path: str, lms_format: str) -> List[Dict]:
        """Parse LMS export and return list of submissions"""
        submissions = []

        if os.path.isdir(export_path):
            # Treat each file/folder as a submission
            for item in os.listdir(export_path):
                item_path = os.path.join(export_path, item)
                if os.path.isfile(item_path):
                    content = self._read_file_content(item_path)
                    if content:
                        # Extract student ID from filename if possible
                        student_id = self._extract_student_id_from_filename(item)
                        submissions.append({
                            'student_id': student_id,
                            'title': item,
                            'content': content
                        })

        return submissions

    def _extract_student_id_from_filename(self, filename: str) -> str:
        """Extract student ID from filename using common patterns"""
        # Try to extract ID from patterns like "StudentName_12345_submission.txt"
        parts = filename.replace('.', '_').split('_')
        for part in parts:
            if part.isdigit() and len(part) >= 4:
                return part
        return filename.split('_')[0] if '_' in filename else 'unknown'

    def schedule_batch_job(self, job_type: str, target_path: str,
                          scheduled_time: str = "02:00",
                          notify_email: str = None) -> Dict[str, Any]:
        """
        Schedule batch analysis for off-peak hours.

        Args:
            job_type: Type of batch job
            target_path: Path to analyze
            scheduled_time: Time to run (HH:MM format)
            notify_email: Email for notifications

        Returns:
            Dict with job scheduling details
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Create batch jobs table if not exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_detector_batch_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT UNIQUE NOT NULL,
                    job_type TEXT NOT NULL,
                    target_path TEXT NOT NULL,
                    scheduled_time TEXT NOT NULL,
                    notify_email TEXT,
                    status TEXT NOT NULL DEFAULT 'queued',
                    progress INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    result TEXT,
                    error TEXT
                )
            ''')

            job_id = f"BATCH-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

            cursor.execute('''
                INSERT INTO ai_detector_batch_jobs
                (job_id, job_type, target_path, scheduled_time, notify_email, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (job_id, job_type, target_path, scheduled_time, notify_email,
                  datetime.now().isoformat()))

            conn.commit()
            conn.close()

            logger.info(f"Batch job scheduled: {job_id}")
            return {
                'success': True,
                'job_id': job_id,
                'scheduled_time': scheduled_time,
                'status': 'queued'
            }

        except Exception as e:
            logger.error(f"Error scheduling batch job: {e}")
            return {'success': False, 'error': str(e)}

    def view_batch_job_status(self, job_id: str = None) -> Dict[str, Any]:
        """
        Monitor progress of running batch jobs.

        Args:
            job_id: Optional specific job ID to check

        Returns:
            Dict with job status information
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            if job_id:
                cursor.execute('''
                    SELECT * FROM ai_detector_batch_jobs WHERE job_id = ?
                ''', (job_id,))
            else:
                cursor.execute('''
                    SELECT * FROM ai_detector_batch_jobs ORDER BY created_at DESC LIMIT 50
                ''')

            rows = cursor.fetchall()
            jobs = []
            status_counts = {'running': 0, 'queued': 0, 'completed': 0, 'failed': 0}

            for row in rows:
                job = dict(row)
                jobs.append(job)
                status = job.get('status', 'unknown')
                if status in status_counts:
                    status_counts[status] += 1

            conn.close()

            return {
                'jobs': jobs,
                'summary': status_counts
            }

        except Exception as e:
            logger.error(f"Error viewing batch job status: {e}")
            return {'error': str(e)}

    def cancel_batch_job(self, job_id: str) -> Dict[str, Any]:
        """
        Cancel a running or queued batch job.

        Args:
            job_id: ID of the job to cancel

        Returns:
            Dict with cancellation status
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT status FROM ai_detector_batch_jobs WHERE job_id = ?', (job_id,))
            row = cursor.fetchone()

            if not row:
                conn.close()
                return {'success': False, 'error': 'Job not found'}

            previous_status = row['status']
            if previous_status in ['completed', 'cancelled']:
                conn.close()
                return {'success': False, 'error': f'Job already {previous_status}'}

            cursor.execute('''
                UPDATE ai_detector_batch_jobs
                SET status = 'cancelled', completed_at = ?
                WHERE job_id = ?
            ''', (datetime.now().isoformat(), job_id))

            conn.commit()
            conn.close()

            logger.info(f"Batch job cancelled: {job_id}")
            return {
                'success': True,
                'job_id': job_id,
                'previous_status': previous_status,
                'cancelled_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error cancelling batch job: {e}")
            return {'success': False, 'error': str(e)}

    def get_failed_analyses_count(self, job_id: str = None) -> Dict[str, Any]:
        """Get count of failed analyses for retry"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            if job_id:
                cursor.execute('''
                    SELECT COUNT(*) as count FROM ai_detector_submissions
                    WHERE batch_job_id = ? AND status = 'failed'
                ''', (job_id,))
            else:
                cursor.execute('''
                    SELECT COUNT(*) as count FROM ai_detector_submissions
                    WHERE status = 'failed'
                ''')

            row = cursor.fetchone()
            conn.close()

            return {'count': row['count'] if row else 0}

        except Exception as e:
            logger.error(f"Error getting failed analyses count: {e}")
            return {'count': 0, 'error': str(e)}

    def retry_failed_analyses(self, job_id: str = None, max_retries: int = 3) -> Dict[str, Any]:
        """
        Retry all failed analyses from a batch.

        Args:
            job_id: Optional specific batch job ID
            max_retries: Maximum retry attempts per analysis

        Returns:
            Dict with retry results
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Get failed submissions
            if job_id:
                cursor.execute('''
                    SELECT id, text_content, title, student_id, retry_count
                    FROM ai_detector_submissions
                    WHERE batch_job_id = ? AND status = 'failed' AND retry_count < ?
                ''', (job_id, max_retries))
            else:
                cursor.execute('''
                    SELECT id, text_content, title, student_id, retry_count
                    FROM ai_detector_submissions
                    WHERE status = 'failed' AND retry_count < ?
                ''', (max_retries,))

            failed = cursor.fetchall()
            retried = 0
            successful = 0
            still_failed = 0

            for submission in failed:
                try:
                    # Increment retry count
                    cursor.execute('''
                        UPDATE ai_detector_submissions
                        SET retry_count = retry_count + 1
                        WHERE id = ?
                    ''', (submission['id'],))

                    # Retry analysis
                    result = self.analyze_text(
                        text=submission['text_content'],
                        title=submission['title'],
                        student_id=submission['student_id']
                    )

                    retried += 1
                    if result.get('ai_score') is not None:
                        successful += 1
                        cursor.execute('''
                            UPDATE ai_detector_submissions
                            SET status = 'completed'
                            WHERE id = ?
                        ''', (submission['id'],))
                    else:
                        still_failed += 1

                except Exception as e:
                    logger.error(f"Retry failed for submission {submission['id']}: {e}")
                    still_failed += 1

            conn.commit()
            conn.close()

            return {
                'success': True,
                'retried': retried,
                'successful': successful,
                'still_failed': still_failed
            }

        except Exception as e:
            logger.error(f"Error retrying failed analyses: {e}")
            return {'success': False, 'error': str(e)}
