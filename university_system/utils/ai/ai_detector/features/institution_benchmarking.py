"""Benchmarking across institutions."""

from datetime import datetime, timedelta
from typing import Any, Dict

from university_system.utils.ai.ai_detector.core.constants import logger


class InstitutionBenchmarking:
    """Provides benchmarking across institutions"""

    def __init__(self, detector_instance):
        self.detector = detector_instance

    def generate_benchmark_report(self, institution_id: str, comparison_period: str = '1_month') -> Dict[str, Any]:
        """Generate benchmarking report comparing institution to others"""
        try:
            # Calculate period dates
            if comparison_period == '1_month':
                start_date = datetime.now() - timedelta(days=30)
            elif comparison_period == '3_months':
                start_date = datetime.now() - timedelta(days=90)
            elif comparison_period == '1_year':
                start_date = datetime.now() - timedelta(days=365)
            else:
                start_date = datetime.now() - timedelta(days=30)

            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()

            # Get institution metrics
            cursor.execute('''
            SELECT
                COUNT(*) as total_submissions,
                AVG(r.ai_score) as avg_ai_score,
                COUNT(CASE WHEN r.ai_score >= 0.7 THEN 1 END) as flagged_submissions,
                COUNT(DISTINCT s.student_id) as unique_students
            FROM ai_detector_submissions s
            JOIN ai_detector_results r ON s.id = r.submission_id
            WHERE s.institution_id = ? AND s.submission_date >= ?
            ''', (institution_id, start_date.isoformat()))

            institution_stats = cursor.fetchone()

            # Get global benchmarks (anonymized)
            cursor.execute('''
            SELECT
                AVG(total_submissions) as avg_submissions_per_institution,
                AVG(avg_ai_score) as global_avg_ai_score,
                AVG(flagged_rate) as global_flagged_rate
            FROM (
                SELECT
                    s.institution_id,
                    COUNT(*) as total_submissions,
                    AVG(r.ai_score) as avg_ai_score,
                    CAST(COUNT(CASE WHEN r.ai_score >= 0.7 THEN 1 END) AS FLOAT) / COUNT(*) as flagged_rate
                FROM ai_detector_submissions s
                JOIN ai_detector_results r ON s.id = r.submission_id
                WHERE s.submission_date >= ?
                GROUP BY s.institution_id
            ) institution_metrics
            ''', (start_date.isoformat(),))

            global_stats = cursor.fetchone()
            conn.close()

            # Calculate percentiles
            institution_flagged_rate = (institution_stats['flagged_submissions'] /
                                     max(1, institution_stats['total_submissions']))

            report = {
                'institution_id': institution_id,
                'period': comparison_period,
                'institution_metrics': {
                    'total_submissions': institution_stats['total_submissions'],
                    'avg_ai_score': round(institution_stats['avg_ai_score'] or 0, 3),
                    'flagged_rate': round(institution_flagged_rate, 3),
                    'unique_students': institution_stats['unique_students']
                },
                'benchmarks': {
                    'avg_submissions_per_institution': round(global_stats['avg_submissions_per_institution'] or 0, 1),
                    'global_avg_ai_score': round(global_stats['global_avg_ai_score'] or 0, 3),
                    'global_flagged_rate': round(global_stats['global_flagged_rate'] or 0, 3)
                },
                'performance_indicators': {}
            }

            # Calculate performance indicators
            if global_stats['global_flagged_rate']:
                flagged_rate_ratio = institution_flagged_rate / global_stats['global_flagged_rate']
                if flagged_rate_ratio > 1.5:
                    report['performance_indicators']['flagged_rate'] = 'above_average'
                elif flagged_rate_ratio < 0.5:
                    report['performance_indicators']['flagged_rate'] = 'below_average'
                else:
                    report['performance_indicators']['flagged_rate'] = 'average'

            return report

        except Exception as e:
            logger.error(f"Error generating benchmark report: {e}")
            return {'error': str(e)}
