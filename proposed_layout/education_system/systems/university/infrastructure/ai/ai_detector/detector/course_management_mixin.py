"""Course and assignment management mixin for AI detector."""

import os
import re
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from education_system.systems.university.infrastructure.ai.ai_detector.core.constants import logger


class CourseManagementMixin:
    """Mixin providing course and assignment management methods."""

    def create_assignment_profile(self, course_code: str, assignment_name: str,
                                 assignment_type: str = 'essay',
                                 word_count_min: int = None, word_count_max: int = None,
                                 references_required: int = 0,
                                 technical_terms: List[str] = None,
                                 allow_collaboration: bool = False) -> Dict[str, Any]:
        """
        Define expected characteristics for an assignment.

        Args:
            course_code: Course code
            assignment_name: Name of the assignment
            assignment_type: Type of assignment
            word_count_min: Minimum word count
            word_count_max: Maximum word count
            references_required: Number of required references
            technical_terms: Expected technical terminology
            allow_collaboration: Whether collaboration is allowed

        Returns:
            Dict with profile creation status
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Create assignment profiles table if not exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_detector_assignment_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id TEXT UNIQUE NOT NULL,
                    course_code TEXT NOT NULL,
                    assignment_name TEXT NOT NULL,
                    assignment_type TEXT NOT NULL,
                    word_count_min INTEGER,
                    word_count_max INTEGER,
                    references_required INTEGER DEFAULT 0,
                    technical_terms TEXT,
                    allow_collaboration INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    created_by TEXT,
                    baseline_set INTEGER DEFAULT 0
                )
            ''')

            profile_id = f"PROF-{course_code}-{uuid.uuid4().hex[:8].upper()}"

            cursor.execute('''
                INSERT INTO ai_detector_assignment_profiles
                (profile_id, course_code, assignment_name, assignment_type,
                 word_count_min, word_count_max, references_required,
                 technical_terms, allow_collaboration, created_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (profile_id, course_code, assignment_name, assignment_type,
                  word_count_min, word_count_max, references_required,
                  ','.join(technical_terms) if technical_terms else None,
                  1 if allow_collaboration else 0,
                  datetime.now().isoformat(),
                  self.current_user.get('username') if self.current_user else None))

            conn.commit()
            conn.close()

            logger.info(f"Assignment profile created: {profile_id}")
            return {
                'success': True,
                'profile_id': profile_id,
                'course_code': course_code,
                'assignment_name': assignment_name
            }

        except Exception as e:
            logger.error(f"Error creating assignment profile: {e}")
            return {'success': False, 'error': str(e)}

    def set_assignment_baseline(self, profile_id: str, source: str = 'samples',
                               sample_path: str = None, previous_course: str = None,
                               previous_assignment: str = None,
                               avg_sentence_length: float = None,
                               vocabulary_complexity: float = None) -> Dict[str, Any]:
        """
        Establish baseline metrics for a specific assignment.

        Args:
            profile_id: Assignment profile ID
            source: Baseline source (samples/previous/manual)
            sample_path: Path to sample submissions
            previous_course: Previous course code for baseline
            previous_assignment: Previous assignment name
            avg_sentence_length: Manual average sentence length
            vocabulary_complexity: Manual vocabulary complexity

        Returns:
            Dict with baseline metrics
        """
        try:
            baseline = {}
            samples_analyzed = 0

            if source == 'samples' and sample_path:
                # Analyze sample submissions
                if os.path.isdir(sample_path):
                    sentence_lengths = []
                    vocab_scores = []
                    word_counts = []

                    for f in os.listdir(sample_path):
                        file_path = os.path.join(sample_path, f)
                        content = self._read_file_content(file_path)
                        if content:
                            samples_analyzed += 1
                            metrics = self._calculate_text_metrics(content)
                            sentence_lengths.append(metrics.get('avg_sentence_length', 0))
                            vocab_scores.append(metrics.get('vocabulary_complexity', 0))
                            word_counts.append(metrics.get('word_count', 0))

                    if samples_analyzed > 0:
                        baseline = {
                            'avg_sentence_length': round(sum(sentence_lengths) / len(sentence_lengths), 2),
                            'vocabulary_complexity': round(sum(vocab_scores) / len(vocab_scores), 2),
                            'avg_word_count': round(sum(word_counts) / len(word_counts), 0)
                        }

            elif source == 'previous' and previous_course:
                # Use previous semester data
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT AVG(word_count) as avg_wc,
                           AVG(sentence_length) as avg_sl,
                           AVG(vocabulary_score) as avg_vocab
                    FROM ai_detector_submissions
                    WHERE course_code = ? AND assignment_id = ?
                ''', (previous_course, previous_assignment))
                row = cursor.fetchone()
                conn.close()

                if row and row['avg_wc']:
                    baseline = {
                        'avg_sentence_length': round(row['avg_sl'] or 15, 2),
                        'vocabulary_complexity': round(row['avg_vocab'] or 5, 2),
                        'avg_word_count': round(row['avg_wc'] or 500, 0)
                    }
                    samples_analyzed = -1  # Indicates from database

            elif source == 'manual':
                baseline = {
                    'avg_sentence_length': avg_sentence_length or 15,
                    'vocabulary_complexity': vocabulary_complexity or 5,
                    'avg_word_count': None
                }

            if not baseline:
                return {'success': False, 'error': 'Could not establish baseline'}

            # Save baseline to database
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_detector_baselines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id TEXT UNIQUE NOT NULL,
                    avg_sentence_length REAL,
                    vocabulary_complexity REAL,
                    avg_word_count REAL,
                    samples_analyzed INTEGER,
                    created_at TEXT NOT NULL
                )
            ''')

            cursor.execute('''
                INSERT OR REPLACE INTO ai_detector_baselines
                (profile_id, avg_sentence_length, vocabulary_complexity,
                 avg_word_count, samples_analyzed, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (profile_id, baseline.get('avg_sentence_length'),
                  baseline.get('vocabulary_complexity'),
                  baseline.get('avg_word_count'),
                  samples_analyzed, datetime.now().isoformat()))

            # Update profile to indicate baseline is set
            cursor.execute('''
                UPDATE ai_detector_assignment_profiles
                SET baseline_set = 1
                WHERE profile_id = ?
            ''', (profile_id,))

            conn.commit()
            conn.close()

            return {
                'success': True,
                'baseline': baseline,
                'samples_analyzed': samples_analyzed
            }

        except Exception as e:
            logger.error(f"Error setting assignment baseline: {e}")
            return {'success': False, 'error': str(e)}

    def _calculate_text_metrics(self, text: str) -> Dict[str, Any]:
        """Calculate various text metrics"""
        words = text.split()
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        word_count = len(words)
        sentence_count = len(sentences) if sentences else 1
        avg_sentence_length = word_count / sentence_count

        # Calculate vocabulary complexity (unique words ratio * avg word length)
        unique_words = set(w.lower() for w in words if w.isalpha())
        unique_ratio = len(unique_words) / len(words) if words else 0
        avg_word_length = sum(len(w) for w in words) / len(words) if words else 0
        vocabulary_complexity = unique_ratio * avg_word_length

        return {
            'word_count': word_count,
            'sentence_count': sentence_count,
            'avg_sentence_length': avg_sentence_length,
            'vocabulary_complexity': vocabulary_complexity,
            'unique_words': len(unique_words)
        }

    def compare_against_assignment_baseline(self, profile_id: str, text: str,
                                           student_id: str = None) -> Dict[str, Any]:
        """
        Compare submission against assignment expectations.

        Args:
            profile_id: Assignment profile ID
            text: Submission text
            student_id: Optional student ID

        Returns:
            Dict with comparison results and deviation score
        """
        try:
            # Get baseline
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM ai_detector_baselines WHERE profile_id = ?
            ''', (profile_id,))
            baseline_row = cursor.fetchone()
            conn.close()

            if not baseline_row:
                return {'success': False, 'error': 'Baseline not found for this profile'}

            baseline = {
                'avg_sentence_length': baseline_row['avg_sentence_length'],
                'vocabulary_complexity': baseline_row['vocabulary_complexity'],
                'avg_word_count': baseline_row['avg_word_count']
            }

            # Calculate submission metrics
            submission_metrics = self._calculate_text_metrics(text)

            # Calculate deviations
            deviations = {}
            flags = []

            if baseline['avg_sentence_length']:
                sl_dev = abs(submission_metrics['avg_sentence_length'] - baseline['avg_sentence_length']) / baseline['avg_sentence_length']
                deviations['sentence_length_deviation'] = round(sl_dev, 3)
                if sl_dev > 0.5:
                    flags.append(f"Sentence length differs significantly ({sl_dev:.1%} deviation)")

            if baseline['vocabulary_complexity']:
                vc_dev = abs(submission_metrics['vocabulary_complexity'] - baseline['vocabulary_complexity']) / baseline['vocabulary_complexity']
                deviations['vocabulary_deviation'] = round(vc_dev, 3)
                if vc_dev > 0.5:
                    flags.append(f"Vocabulary complexity differs significantly ({vc_dev:.1%} deviation)")

            if baseline['avg_word_count']:
                wc_dev = abs(submission_metrics['word_count'] - baseline['avg_word_count']) / baseline['avg_word_count']
                deviations['word_count_deviation'] = round(wc_dev, 3)
                if wc_dev > 0.5:
                    flags.append(f"Word count differs significantly ({wc_dev:.1%} deviation)")

            # Calculate overall deviation score
            deviation_values = list(deviations.values())
            overall_deviation = sum(deviation_values) / len(deviation_values) if deviation_values else 0

            return {
                'success': True,
                'deviation_score': round(overall_deviation, 3),
                'metrics': deviations,
                'submission_metrics': submission_metrics,
                'baseline': baseline,
                'flags': flags
            }

        except Exception as e:
            logger.error(f"Error comparing against baseline: {e}")
            return {'success': False, 'error': str(e)}

    def view_course_integrity_dashboard(self, course_code: str,
                                       semester: str = None) -> Dict[str, Any]:
        """
        Course-level integrity metrics dashboard.

        Args:
            course_code: Course code
            semester: Optional semester filter

        Returns:
            Dict with course integrity metrics
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Get submission statistics
            query = '''
                SELECT COUNT(*) as total,
                       COUNT(DISTINCT student_id) as students,
                       AVG(ai_score) as avg_score,
                       SUM(CASE WHEN ai_score >= 0.9 THEN 1 ELSE 0 END) as critical,
                       SUM(CASE WHEN ai_score >= 0.7 AND ai_score < 0.9 THEN 1 ELSE 0 END) as high,
                       SUM(CASE WHEN ai_score >= 0.5 AND ai_score < 0.7 THEN 1 ELSE 0 END) as medium,
                       SUM(CASE WHEN ai_score < 0.5 THEN 1 ELSE 0 END) as low
                FROM ai_detector_submissions
                WHERE course_code = ?
            '''
            params = [course_code]

            cursor.execute(query, params)
            stats_row = cursor.fetchone()

            # Get flagged students
            cursor.execute('''
                SELECT student_id, COUNT(*) as flag_count
                FROM ai_detector_alerts
                WHERE submission_id IN (
                    SELECT id FROM ai_detector_submissions WHERE course_code = ?
                )
                GROUP BY student_id
                ORDER BY flag_count DESC
                LIMIT 10
            ''', (course_code,))
            flagged_rows = cursor.fetchall()

            conn.close()

            statistics = {
                'total_submissions': stats_row['total'] or 0,
                'analyzed': stats_row['total'] or 0,
                'avg_ai_score': stats_row['avg_score'] or 0
            }

            risk_distribution = {
                'critical': stats_row['critical'] or 0,
                'high': stats_row['high'] or 0,
                'medium': stats_row['medium'] or 0,
                'low': stats_row['low'] or 0
            }

            flagged_students = [
                {'student_id': row['student_id'], 'flag_count': row['flag_count']}
                for row in flagged_rows
            ]

            return {
                'course_code': course_code,
                'semester': semester or 'Current',
                'statistics': statistics,
                'risk_distribution': risk_distribution,
                'flagged_students': flagged_students,
                'trends': {
                    'wow_change': 0,
                    'assignment_trend': 'stable'
                }
            }

        except Exception as e:
            logger.error(f"Error viewing course integrity dashboard: {e}")
            return {'error': str(e)}

    def generate_course_end_report(self, course_code: str, semester: str,
                                  include_student_details: bool = False,
                                  include_recommendations: bool = True,
                                  export_format: str = 'pdf') -> Dict[str, Any]:
        """
        End-of-semester academic integrity summary.

        Args:
            course_code: Course code
            semester: Semester identifier
            include_student_details: Whether to include individual student details
            include_recommendations: Whether to include recommendations
            export_format: Export format (pdf/csv/html)

        Returns:
            Dict with report summary and path
        """
        try:
            # Get course dashboard data
            dashboard = self.view_course_integrity_dashboard(course_code, semester)

            if dashboard.get('error'):
                return {'success': False, 'error': dashboard['error']}

            # Calculate integrity score (100 - weighted average of risk)
            risk = dashboard.get('risk_distribution', {})
            total = sum(risk.values()) if risk else 1
            if total > 0:
                weighted_risk = (
                    (risk.get('critical', 0) * 100 +
                     risk.get('high', 0) * 70 +
                     risk.get('medium', 0) * 40 +
                     risk.get('low', 0) * 10) / total
                )
                integrity_score = max(0, 100 - weighted_risk)
            else:
                integrity_score = 100

            # Get confirmed violations count
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) as count FROM ai_detector_alerts
                WHERE status = 'confirmed' AND submission_id IN (
                    SELECT id FROM ai_detector_submissions WHERE course_code = ?
                )
            ''', (course_code,))
            violations_row = cursor.fetchone()
            confirmed_violations = violations_row['count'] if violations_row else 0
            conn.close()

            summary = {
                'total_students': dashboard['statistics'].get('analyzed', 0),
                'total_submissions': dashboard['statistics'].get('total_submissions', 0),
                'avg_ai_score': dashboard['statistics'].get('avg_ai_score', 0),
                'flagged_count': len(dashboard.get('flagged_students', [])),
                'confirmed_violations': confirmed_violations
            }

            # Generate report file
            report_dir = os.path.join(os.path.dirname(self.db_path), 'reports')
            os.makedirs(report_dir, exist_ok=True)

            report_filename = f"course_report_{course_code}_{semester}_{datetime.now().strftime('%Y%m%d')}.{export_format}"
            report_path = os.path.join(report_dir, report_filename)

            # For simplicity, create a JSON report
            report_data = {
                'course_code': course_code,
                'semester': semester,
                'summary': summary,
                'integrity_score': integrity_score,
                'risk_distribution': risk,
                'generated_at': datetime.now().isoformat()
            }

            if include_recommendations:
                recommendations = []
                if integrity_score < 60:
                    recommendations.append("Consider implementing more rigorous AI detection policies")
                if risk.get('critical', 0) > 5:
                    recommendations.append("Review critical cases urgently")
                if not recommendations:
                    recommendations.append("Course integrity metrics are within acceptable range")
                report_data['recommendations'] = recommendations

            with open(report_path.replace(f'.{export_format}', '.json'), 'w') as f:
                json.dump(report_data, f, indent=2)

            return {
                'success': True,
                'summary': summary,
                'integrity_score': integrity_score,
                'report_path': report_path.replace(f'.{export_format}', '.json')
            }

        except Exception as e:
            logger.error(f"Error generating course end report: {e}")
            return {'success': False, 'error': str(e)}
