"""Submission management mixin for AIDetector."""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any

from education_system.systems.university.infrastructure.ai.ai_detector.core.constants import logger, sqlite3
from education_system.systems.university.infrastructure.ai.ai_detector.core.exceptions import DatabaseError


class SubmissionMixin:
    """Mixin providing submission listing, detail retrieval, and statistics."""

    def get_enhanced_statistics(self) -> Dict[str, Any]:
        """
        Enhanced statistics with better error handling
        """
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            # Get basic counts with error handling
            try:
                cursor.execute('SELECT COUNT(*) as total FROM ai_detector_submissions')
                total_submissions = cursor.fetchone()['total']
            except Exception:
                total_submissions = 0

            try:
                cursor.execute('SELECT COUNT(DISTINCT student_id) as total FROM ai_detector_submissions')
                unique_students = cursor.fetchone()['total']
            except Exception:
                unique_students = 0

            try:
                cursor.execute('SELECT AVG(ai_score) as avg FROM ai_detector_results WHERE ai_score IS NOT NULL')
                result = cursor.fetchone()
                avg_score = result['avg'] if result and result['avg'] is not None else 0.0
            except Exception:
                avg_score = 0.0

            # Get recent activity
            try:
                cursor.execute('''
                SELECT COUNT(*) as recent_count
                FROM ai_detector_submissions
                WHERE submission_date >= datetime('now', '-7 days')
                ''')
                recent_submissions = cursor.fetchone()['recent_count']
            except Exception:
                recent_submissions = 0

            # Get high-risk submissions
            try:
                cursor.execute('''
                SELECT COUNT(*) as high_risk_count
                FROM ai_detector_results
                WHERE ai_score >= ?
                ''', (self.detection_threshold,))
                high_risk_submissions = cursor.fetchone()['high_risk_count']
            except Exception:
                high_risk_submissions = 0

            conn.close()

            return {
                'total_submissions': total_submissions,
                'unique_students': unique_students,
                'average_ai_score': round(avg_score, 3),
                'recent_submissions_7_days': recent_submissions,
                'high_risk_submissions': high_risk_submissions,
                'detection_threshold': self.detection_threshold,
                'active_style_profiles': len(getattr(self, 'style_profiles', {})),
                'active_detection_methods': len(getattr(self, 'detection_methods', {})),
                'database_status': 'connected',
                'generated_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting enhanced statistics: {e}")
            return {
                'total_submissions': 0,
                'unique_students': 0,
                'average_ai_score': 0.0,
                'recent_submissions_7_days': 0,
                'high_risk_submissions': 0,
                'detection_threshold': self.detection_threshold,
                'active_style_profiles': 0,
                'active_detection_methods': 0,
                'database_status': 'error',
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }

    def list_submissions(self, student_id: str = None, limit: int = 10,
                        include_text: bool = False) -> Dict[str, Any]:
        """
        Enhanced list_submissions with better error handling
        """
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            # Build flexible query that handles missing columns
            select_fields = [
                's.id',
                's.student_id',
                'COALESCE(s.title, "Untitled") as title',
                's.course_code',
                's.assignment_id',
                's.submission_date',
                'COALESCE(s.word_count, 0) as word_count',
                'COALESCE(s.character_count, 0) as character_count',
                'r.ai_score',
                'r.confidence'
            ]

            if include_text:
                select_fields.append('s.submission_text')

            query = f'''
            SELECT {", ".join(select_fields)}
            FROM ai_detector_submissions s
            LEFT JOIN ai_detector_results r ON s.id = r.submission_id
            '''

            params = []
            if student_id:
                query += " WHERE s.student_id = ?"
                params.append(student_id)

            query += " ORDER BY s.submission_date DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            submissions = []

            for row in cursor.fetchall():
                try:
                    submission = dict(row)
                    # Add computed fields
                    submission['is_ai_generated'] = (submission.get('ai_score') or 0) >= self.detection_threshold
                    submission['risk_level'] = self._calculate_risk_level(submission.get('ai_score', 0))

                    if not include_text and 'submission_text' in submission:
                        # Add preview instead of full text
                        text = submission.pop('submission_text', '')
                        submission['text_preview'] = text[:200] + "..." if len(text) > 200 else text

                    submissions.append(submission)
                except Exception as row_error:
                    logger.warning(f"Error processing submission row: {row_error}")
                    continue

            conn.close()

            return {
                'submissions': submissions,
                'total': len(submissions),
                'student_filter': student_id,
                'limit': limit,
                'include_text': include_text
            }

        except Exception as e:
            logger.error(f"Error listing submissions: {e}")
            return {
                'submissions': [],
                'total': 0,
                'error': str(e),
                'student_filter': student_id,
                'limit': limit
            }

    def _calculate_risk_level(self, ai_score: float) -> str:
        """Calculate risk level based on AI score"""
        if ai_score >= 0.9:
            return 'critical'
        elif ai_score >= 0.7:
            return 'high'
        elif ai_score >= 0.5:
            return 'medium'
        else:
            return 'low'

    def get_submission_details(self, submission_id: int) -> Dict[str, Any]:
        """Get detailed information about a specific submission"""
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT
                s.*,
                r.ai_score,
                r.confidence,
                r.detailed_results,
                r.created_at as analysis_date
            FROM ai_detector_submissions s
            LEFT JOIN ai_detector_results r ON s.id = r.submission_id
            WHERE s.id = ?
            ''', (submission_id,))

            row = cursor.fetchone()
            if not row:
                return {'error': 'Submission not found'}

            submission = dict(row)

            # Parse detailed results if available
            if submission.get('detailed_results'):
                try:
                    submission['detailed_results'] = json.loads(submission['detailed_results'])
                except (ValueError, TypeError):
                    pass

            # Add computed fields
            submission['is_ai_generated'] = (submission.get('ai_score') or 0) >= self.detection_threshold
            submission['risk_level'] = self._calculate_risk_level(submission.get('ai_score', 0))
            submission['word_count'] = submission.get('word_count') or len((submission.get('submission_text') or '').split())
            submission['character_count'] = submission.get('character_count') or len(submission.get('submission_text') or '')

            conn.close()
            return submission

        except Exception as e:
            logger.error(f"Error getting submission details: {e}")
            return {'error': str(e)}

    def patch_ai_detector_class():
        """
        Quick patch function - add these methods directly to your AIDetector class
        """

        # Method 1: Add to __init__
        def add_to_init(self):
            """Add these lines to your __init__ method"""
            # Add missing attributes
            if not hasattr(self, 'detection_methods'):
                self.detection_methods = {
                    'pattern_matching': True,
                    'statistical_analysis': True,
                    'behavioral_analysis': True,
                    'temporal_analysis': True,
                    'citation_verification': True
                }

            if not hasattr(self, 'style_profiles'):
                self.style_profiles = {}

            # Fix database schema on initialization
            try:
                self.fix_database_schema()
            except Exception:
                pass

        # Method 2: Quick fix methods
        def get_statistics(self):
            """Quick fix for missing get_statistics method"""
            return self.get_enhanced_statistics()

        def fix_database_schema(self):
            """Quick fix for database schema issues"""
            try:
                conn = self._safe_db_connect()
                cursor = conn.cursor()

                # Add title column if missing
                try:
                    cursor.execute('ALTER TABLE ai_detector_submissions ADD COLUMN title TEXT')
                except Exception:
                    pass  # Column might already exist


                conn.close()
            except Exception:
                pass
