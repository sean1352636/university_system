"""Batch operations mixin for AI detector."""

import os
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from education_system.systems.university.shared.ai.ai_detector.core.constants import logger


class BatchOperationsMixin:
    """Mixin providing batch analysis and job management methods."""

    def batch_analyze_folder(self, folder_path: str, file_types: List[str] = None,
                            recursive: bool = False, course_code: str = None,
                            assignment_id: str = None) -> Dict[str, Any]:
        """
        Analyze all documents in a selected folder.

        Args:
            folder_path: Path to folder containing documents
            file_types: List of file extensions to include
            recursive: Whether to include subdirectories
            course_code: The module the work belongs to (required)
            assignment_id: The assignment, if known

        Each file's student is taken from its name (a student number in it,
        e.g. ``Smith_5853694_essay.docx``); a file without one is skipped and
        listed, never read against an unknown student.

        Returns:
            Dict with analysis results and summary
        """
        try:
            if not os.path.isdir(folder_path):
                return {'success': False, 'error': f'Directory not found: {folder_path}'}

            if not course_code:
                return {'success': False, 'error': 'Choose the module the work belongs to'}
            if file_types is None:
                file_types = ['txt', 'docx', 'pdf']
            skipped = []

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

                    name = os.path.basename(file_path)
                    student = self._extract_student_id_from_filename(name)
                    if student == 'unknown':
                        skipped.append({'file': name, 'reason': 'no student number in the name'})
                        files_failed += 1
                        continue
                    result = self.analyze_text(text=content, title=name, student_id=student,
                                               course_code=course_code,
                                               assignment_id=assignment_id)
                    if result.get('skipped'):
                        return {'success': False, 'error': result['reason']}

                    files_analyzed += 1
                    risk_level = result.get('risk_level', 'low')
                    risk_counts[risk_level] = risk_counts.get(risk_level, 0) + 1
                    results.append({'file': name, 'student_id': student,
                                    'result_id': result.get('result_id'),
                                    'ai_score': result.get('ai_score', 0),
                                    'level': result.get('level'),
                                    'needs_review': result.get('needs_review'),
                                    'risk_level': risk_level})

                except PermissionError:
                    raise
                except Exception as e:
                    logger.error(f"Error analyzing {file_path}: {e}")
                    skipped.append({'file': os.path.basename(file_path), 'reason': str(e)})
                    files_failed += 1

            total_time = time.time() - start_time

            from education_system.systems.university.shared.ai.ai_detector.detector.audit_privacy_mixin import (
                export_dir, write_private,
            )
            report_path = write_private(os.path.join(
                export_dir('batch'), f'batch_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'),
                {'module': course_code, 'results': results, 'skipped': skipped,
                 'summary': risk_counts})

            return {
                'success': True,
                'files_analyzed': files_analyzed,
                'files_failed': files_failed,
                'skipped': skipped,
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

            if not course_code:
                return {'success': False, 'error': 'Choose the module the work belongs to'}
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

                    if result.get('skipped'):
                        return {'success': False, 'error': result['reason']}
                    submissions_analyzed += 1
                    ai_score = result.get('ai_score', 0)
                    risk_level = result.get('risk_level', 'low')
                    risk_counts[risk_level] = risk_counts.get(risk_level, 0) + 1

                    if result.get('needs_review'):
                        flagged_students.append({
                            'student_id': result.get('student_id'),
                            'result_id': result.get('result_id'),
                            'risk_level': risk_level,
                            'level': result.get('level'),
                            'ai_score': ai_score
                        })

                except PermissionError:
                    raise
                except Exception as e:
                    logger.error(f"Error analyzing LMS submission: {e}")
                    parse_errors += 1

            from education_system.systems.university.shared.ai.ai_detector.detector.audit_privacy_mixin import (
                export_dir, write_private,
            )
            report_path = write_private(os.path.join(
                export_dir('batch'), f'lms_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'),
                {'module': course_code, 'summary': risk_counts,
                 'flagged_students': flagged_students})

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
        import re as _re
        for part in _re.split(r'[^A-Za-z0-9]+', filename):
            if part.isdigit() and len(part) >= 6:
                return part
        return 'unknown'

    def schedule_batch_job(self, job_type: str, target_path: str,
                           scheduled_time: str = "02:00",
                           notify_email: str = None, course_code: str = None,
                           assignment_id: str = None) -> Dict[str, Any]:
        """Run a batch reading at the next ``scheduled_time`` (HH:MM) — for a
        folder (``job_type='folder'``) or an LMS export (``'lms'``) of work on
        ``course_code``. :meth:`run_due_batch_jobs` runs it, as the person who
        scheduled it."""
        if job_type not in ('folder', 'lms'):
            return {'success': False, 'error': "job_type must be 'folder' or 'lms'"}
        if not course_code:
            return {'success': False, 'error': 'Choose the module the work belongs to'}
        try:
            datetime.strptime(scheduled_time, '%H:%M')
        except ValueError:
            return {'success': False, 'error': 'Give the time as HH:MM'}
        if not os.path.exists(target_path):
            return {'success': False, 'error': f'Path not found: {target_path}'}
        from education_system.systems.university.application.integrity import (
            access as integrity_access,
        )
        conn = self._get_connection()
        try:
            who = self.require_staff(conn)
            if not integrity_access.can_review(conn, who, course_code):
                raise PermissionError(f"You do not review {course_code}")
            job_id = f"BATCH-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
            conn.execute('''
                INSERT INTO ai_detector_batch_jobs
                (job_id, job_type, target_path, scheduled_time, notify_email, created_at,
                 course_code, assignment_id, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (job_id, job_type, target_path, scheduled_time, notify_email,
                  datetime.now().isoformat(), course_code,
                  None if assignment_id is None else str(assignment_id), who.username))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return {'success': True, 'job_id': job_id, 'status': 'queued',
                'scheduled_time': scheduled_time, 'next_run': self._next_run(
                    datetime.now().isoformat(), scheduled_time).isoformat()}

    @staticmethod
    def _next_run(created_at: str, scheduled_time: str) -> datetime:
        created = datetime.fromisoformat(str(created_at)[:19])
        hour, minute = (int(x) for x in scheduled_time.split(':'))
        run = created.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return run if run > created else run + timedelta(days=1)

    def run_due_batch_jobs(self, now: datetime = None) -> Dict[str, Any]:
        """Run every queued job whose time has come, each as the person who
        scheduled it. Returns what ran."""
        now = now or datetime.now()
        conn = self._get_connection()
        try:
            jobs = [dict(r) for r in conn.execute(
                "SELECT * FROM ai_detector_batch_jobs WHERE status = 'queued' ORDER BY created_at")]
        finally:
            conn.close()
        ran = []
        signed_in = self.current_user
        for job in jobs:
            if self._next_run(job['created_at'], job['scheduled_time']) > now:
                continue
            ran.append(self._run_job(job))
        self.current_user = signed_in
        return {'ran': len(ran), 'jobs': ran}

    def _run_job(self, job) -> Dict[str, Any]:
        self._set_job(job['job_id'], status='running', started_at=datetime.now().isoformat())
        self.current_user = {'username': job.get('created_by')} if job.get('created_by') else None
        try:
            if job['job_type'] == 'folder':
                result = self.batch_analyze_folder(job['target_path'],
                                                   course_code=job.get('course_code'),
                                                   assignment_id=job.get('assignment_id'))
            else:
                result = self.batch_analyze_lms_export(job['target_path'],
                                                       course_code=job.get('course_code'),
                                                       assignment_name=job.get('assignment_id'))
            status = 'completed' if result.get('success') else 'failed'
            error = None if result.get('success') else result.get('error')
        except Exception as exc:
            logger.exception("Batch job %s failed", job['job_id'])
            result, status, error = {}, 'failed', str(exc)
        self._set_job(job['job_id'], status=status, progress=100 if status == 'completed' else 0,
                      completed_at=datetime.now().isoformat(),
                      result=json.dumps(result, default=str), error=error)
        if job.get('notify_email'):
            from education_system.systems.university.shared.ai.ai_detector.detector.alerts_mixin import (
                _send,
            )
            _send([(job['notify_email'], f"AI-writing batch {job['job_id']}: {status}",
                    f"The batch reading of {job['target_path']} ({job.get('course_code')}) "
                    f"{status}." + (f" {error}" if error else
                                    f" {result.get('files_analyzed', result.get('submissions_analyzed', 0))} read."))])
        return {'job_id': job['job_id'], 'status': status, 'error': error}

    def _set_job(self, job_id, **fields):
        conn = self._get_connection()
        try:
            sets = ", ".join(f'"{k}" = ?' for k in fields)
            conn.execute(f"UPDATE ai_detector_batch_jobs SET {sets} WHERE job_id = ?",  # nosec B608
                         (*fields.values(), job_id))
            conn.commit()
        finally:
            conn.close()

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
        """Batch jobs that failed (a reading that fails is never stored, so
        failures are counted by job)."""
        conn = self._get_connection()
        try:
            sql = "SELECT COUNT(*) FROM ai_detector_batch_jobs WHERE status = 'failed'"
            params = []
            if job_id:
                sql += " AND job_id = ?"
                params.append(job_id)
            return {'count': conn.execute(sql, params).fetchone()[0]}
        finally:
            conn.close()

    def retry_failed_analyses(self, job_id: str = None, max_retries: int = 3) -> Dict[str, Any]:
        """Queue failed batch jobs again (up to ``max_retries`` times each);
        :meth:`run_due_batch_jobs` runs them."""
        conn = self._get_connection()
        try:
            self.require_staff(conn)
            sql = ("UPDATE ai_detector_batch_jobs SET status = 'queued', error = NULL, "
                   "retries = COALESCE(retries, 0) + 1, scheduled_time = ? WHERE status = 'failed' "
                   "AND COALESCE(retries, 0) < ?")
            params = [datetime.now().strftime('%H:%M'), int(max_retries)]
            if job_id:
                sql += " AND job_id = ?"
                params.append(job_id)
            requeued = conn.execute(sql, params).rowcount
            conn.commit()
        finally:
            conn.close()
        return {'success': True, 'retried': requeued, 'successful': None, 'still_failed': None,
                'note': 'Queued again; they run with the next batch run.'}
