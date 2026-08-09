"""
Academic Performance Analytics Service

Analyzes and forecasts academic performance trends.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.analytics.models import PredictionResult

logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
    """
    Analyzes academic performance and provides forecasts

    Features:
    - GPA trend analysis
    - Course performance prediction
    - Department performance metrics
    - Graduation timeline prediction
    - Performance intervention recommendations
    """

    def __init__(self):
        """Initialize performance analyzer"""
        pass

    def analyze_gpa_trends(
        self,
        period_days: int = 365
    ) -> Dict[str, Any]:
        """
        Analyze GPA trends across the institution

        Args:
            period_days: Number of days to analyze

        Returns:
            Dictionary with trend analysis
        """
        try:
            with get_connection() as conn:
                # Get GPA trends by department
                cursor = conn.execute('''
                    SELECT
                        s.department,
                        strftime('%Y-%m', g.created_at) as month,
                        AVG(
                            CASE g.final_grade
                                WHEN 'A' THEN 4.0
                                WHEN 'B' THEN 3.0
                                WHEN 'C' THEN 2.0
                                WHEN 'D' THEN 1.0
                                ELSE 0.0
                            END
                        ) as avg_gpa,
                        COUNT(DISTINCT s.student_id) as student_count
                    FROM students s
                    JOIN grades g ON s.student_id = g.student_id
                    WHERE g.created_at >= date('now', '-' || ? || ' days')
                      AND g.final_grade IS NOT NULL
                    GROUP BY s.department, month
                    ORDER BY s.department, month
                ''', (period_days,))

                trends_by_dept = defaultdict(list)
                for row in cursor.fetchall():
                    dept = row[0] or 'Unknown'
                    month = row[1]
                    avg_gpa = round(row[2], 2)
                    student_count = row[3]

                    trends_by_dept[dept].append({
                        'month': month,
                        'avg_gpa': avg_gpa,
                        'student_count': student_count
                    })

                # Calculate overall trend
                cursor = conn.execute('''
                    SELECT
                        strftime('%Y-%m', g.created_at) as month,
                        AVG(
                            CASE g.final_grade
                                WHEN 'A' THEN 4.0
                                WHEN 'B' THEN 3.0
                                WHEN 'C' THEN 2.0
                                WHEN 'D' THEN 1.0
                                ELSE 0.0
                            END
                        ) as avg_gpa
                    FROM grades g
                    WHERE g.created_at >= date('now', '-' || ? || ' days')
                      AND g.final_grade IS NOT NULL
                    GROUP BY month
                    ORDER BY month
                ''', (period_days,))

                overall_trend = []
                for row in cursor.fetchall():
                    overall_trend.append({
                        'month': row[0],
                        'avg_gpa': round(row[1], 2)
                    })

                return {
                    'overall_trend': overall_trend,
                    'trends_by_department': dict(trends_by_dept),
                    'period_days': period_days
                }

        except Exception as e:
            logger.error(f"Error analyzing GPA trends: {e}")
            return {
                'overall_trend': [],
                'trends_by_department': {},
                'period_days': period_days
            }

    def predict_student_performance(
        self,
        student_id: str
    ) -> Optional[PredictionResult]:
        """
        Predict future academic performance for a student

        Args:
            student_id: Student ID

        Returns:
            PredictionResult with performance forecast
        """
        try:
            with get_connection() as conn:
                # Get student's performance history
                cursor = conn.execute('''
                    SELECT
                        AVG(
                            CASE g.final_grade
                                WHEN 'A' THEN 4.0
                                WHEN 'B' THEN 3.0
                                WHEN 'C' THEN 2.0
                                WHEN 'D' THEN 1.0
                                ELSE 0.0
                            END
                        ) as avg_gpa,
                        COUNT(*) as courses_taken,
                        COUNT(CASE WHEN g.final_grade IN ('A', 'B') THEN 1 END) as high_grades,
                        COUNT(CASE WHEN g.final_grade = 'F' THEN 1 END) as failed_courses,
                        MAX(g.created_at) as last_grade_date
                    FROM grades g
                    WHERE g.student_id = ?
                      AND g.final_grade IS NOT NULL
                ''', (student_id,))

                row = cursor.fetchone()

                if not row or row[1] == 0:
                    return None

                avg_gpa = row[0]
                courses_taken = row[1]
                high_grades = row[2]
                failed_courses = row[3]

                # Simple prediction based on trajectory
                success_rate = high_grades / courses_taken if courses_taken > 0 else 0
                failure_rate = failed_courses / courses_taken if courses_taken > 0 else 0

                # Predict probability of strong performance (>= 3.0 GPA)
                probability = (avg_gpa / 4.0) * 0.7 + success_rate * 0.3

                # Determine risk level
                if avg_gpa >= 3.5:
                    risk_level = 'low'  # Excellent performance
                elif avg_gpa >= 3.0:
                    risk_level = 'low'  # Good performance
                elif avg_gpa >= 2.5:
                    risk_level = 'medium'  # Satisfactory performance
                else:
                    risk_level = 'high'  # At-risk performance

                # Contributing factors
                factors = {
                    'current_gpa': avg_gpa,
                    'success_rate': success_rate,
                    'failure_rate': failure_rate
                }

                # Recommendations
                actions = []
                if avg_gpa < 3.0:
                    actions.append("Consider academic tutoring")
                if failure_rate > 0.2:
                    actions.append("Review failed courses and retake if necessary")
                if success_rate > 0.7:
                    actions.append("Maintain current study habits")

                return PredictionResult(
                    student_id=student_id,
                    prediction_type='performance',
                    probability=probability,
                    risk_level=risk_level,
                    contributing_factors=factors,
                    recommended_actions=actions,
                    confidence=0.75
                )

        except Exception as e:
            logger.error(f"Error predicting student performance: {e}")
            return None

    def get_course_performance_metrics(
        self,
        course_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get performance metrics for courses

        Args:
            course_id: Specific course ID (optional)

        Returns:
            Course performance metrics
        """
        try:
            with get_connection() as conn:
                query = '''
                    SELECT
                        c.course_id,
                        c.course_code,
                        c.course_name,
                        COUNT(DISTINCT g.student_id) as students_enrolled,
                        AVG(
                            CASE g.final_grade
                                WHEN 'A' THEN 4.0
                                WHEN 'B' THEN 3.0
                                WHEN 'C' THEN 2.0
                                WHEN 'D' THEN 1.0
                                ELSE 0.0
                            END
                        ) as avg_grade,
                        COUNT(CASE WHEN g.final_grade IN ('A', 'B') THEN 1 END) * 100.0 /
                            NULLIF(COUNT(*), 0) as success_rate,
                        COUNT(CASE WHEN g.final_grade = 'F' THEN 1 END) * 100.0 /
                            NULLIF(COUNT(*), 0) as failure_rate
                    FROM courses c
                    LEFT JOIN grades g ON c.course_id = g.course_id
                        AND g.final_grade IS NOT NULL
                    {where_clause}
                    GROUP BY c.course_id
                    HAVING students_enrolled > 0
                    ORDER BY success_rate DESC
                '''

                if course_id:
                    where_clause = 'WHERE c.course_id = ?'
                    params = (course_id,)
                else:
                    where_clause = ''
                    params = ()

                cursor = conn.execute(query.format(where_clause=where_clause), params)

                courses = []
                for row in cursor.fetchall():
                    courses.append({
                        'course_id': row[0],
                        'course_code': row[1],
                        'course_name': row[2],
                        'students_enrolled': row[3],
                        'avg_grade': round(row[4], 2) if row[4] else 0.0,
                        'success_rate': round(row[5], 2) if row[5] else 0.0,
                        'failure_rate': round(row[6], 2) if row[6] else 0.0
                    })

                return {
                    'courses': courses,
                    'total_courses': len(courses)
                }

        except Exception as e:
            logger.error(f"Error getting course performance metrics: {e}")
            return {
                'courses': [],
                'total_courses': 0
            }

    def get_department_metrics(self) -> Dict[str, Any]:
        """Get performance metrics by department"""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT
                        dp.department,
                        COUNT(DISTINCT s.student_id) as total_students,
                        AVG(sdp.current_gpa) as avg_gpa,
                        COUNT(DISTINCT CASE WHEN s.status = 'Active' THEN s.student_id END) as active_students,
                        COUNT(DISTINCT CASE WHEN s.status = 'Graduated' THEN s.student_id END) as graduated_students
                    FROM students s
                    LEFT JOIN student_degree_progress sdp ON s.student_id = sdp.student_id
                    LEFT JOIN degree_programs dp ON sdp.program_id = dp.program_id
                    WHERE dp.department IS NOT NULL
                    GROUP BY dp.department
                    ORDER BY total_students DESC
                ''')

                departments = []
                for row in cursor.fetchall():
                    departments.append({
                        'department': row[0],
                        'total_students': row[1],
                        'avg_gpa': round(row[2], 2) if row[2] else 0.0,
                        'active_students': row[3],
                        'graduated_students': row[4],
                        'graduation_rate': round((row[4] / row[1] * 100), 2) if row[1] > 0 else 0.0
                    })

                return {
                    'departments': departments,
                    'total_departments': len(departments)
                }

        except Exception as e:
            logger.error(f"Error getting department metrics: {e}")
            return {
                'departments': [],
                'total_departments': 0
            }

    def predict_graduation_timeline(
        self,
        student_id: str
    ) -> Dict[str, Any]:
        """
        Predict when a student will graduate

        Args:
            student_id: Student ID

        Returns:
            Graduation timeline prediction
        """
        try:
            with get_connection() as conn:
                # Get student info and progress
                cursor = conn.execute('''
                    SELECT
                        s.enrollment_status,
                        s.expected_graduation_date,
                        COUNT(DISTINCT g.course_id) as completed_courses,
                        AVG(
                            CASE g.final_grade
                                WHEN 'A' THEN 4.0
                                WHEN 'B' THEN 3.0
                                WHEN 'C' THEN 2.0
                                WHEN 'D' THEN 1.0
                                ELSE 0.0
                            END
                        ) as avg_grade
                    FROM students s
                    LEFT JOIN grades g ON s.student_id = g.student_id
                        AND g.final_grade NOT IN ('F', 'W')
                    WHERE s.student_id = ?
                    GROUP BY s.student_id
                ''', (student_id,))

                row = cursor.fetchone()

                if not row:
                    return {'error': 'Student not found'}

                enrollment_status = row[0]
                expected_grad = row[1]
                completed_courses = row[2]
                avg_grade = row[3]

                # Assume 120 credits needed to graduate (typical bachelor's degree)
                # Assume average course is 3 credits
                total_needed = 40  # courses
                remaining = max(0, total_needed - completed_courses)

                # Estimate semesters needed (assuming 4 courses per semester)
                semesters_needed = (remaining + 3) // 4  # Round up

                # Calculate predicted graduation date
                months_needed = semesters_needed * 4  # 4 months per semester
                predicted_date = datetime.now() + timedelta(days=months_needed * 30)

                return {
                    'student_id': student_id,
                    'enrollment_status': enrollment_status,
                    'expected_graduation_date': expected_grad,
                    'completed_courses': completed_courses,
                    'remaining_courses': remaining,
                    'semesters_needed': semesters_needed,
                    'predicted_graduation_date': predicted_date.strftime('%Y-%m-%d'),
                    'on_track': remaining <= (semesters_needed * 4),
                    'avg_grade': round(avg_grade, 2) if avg_grade else 0.0
                }

        except Exception as e:
            logger.error(f"Error predicting graduation timeline: {e}")
            return {'error': str(e)}


# Singleton instance
_performance_analyzer: Optional[PerformanceAnalyzer] = None


def get_performance_analyzer() -> PerformanceAnalyzer:
    """Get or create performance analyzer singleton"""
    global _performance_analyzer
    if _performance_analyzer is None:
        _performance_analyzer = PerformanceAnalyzer()
    return _performance_analyzer
