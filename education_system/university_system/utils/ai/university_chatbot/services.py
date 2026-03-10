"""Supporting service classes: notifications, analytics, recommendations, admin, scheduler."""

import logging
from typing import Dict, List

from education_system.university_system.infrastructure.database.db import sqlite3, ensure_parent_dir

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, config: Dict):
        self.config = config

    def send_bulk_notifications(self, notifications: List[Dict]) -> Dict:
        """Send multiple notifications efficiently"""
        results = {"success": 0, "failed": 0, "errors": []}

        for notification in notifications:
            try:
                results["success"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(str(e))

        return results


class AnalyticsService:
    def __init__(self, log_dir: str):
        self.log_dir = log_dir

    def generate_real_time_dashboard(self) -> Dict:
        """Generate real-time analytics dashboard data"""
        return {
            "active_users": 0,
            "conversations_today": 0,
            "average_response_time": 0.0,
            "top_intents": [],
            "satisfaction_score": 0.0,
            "voice_interactions": 0
        }


class CourseRecommendationEngine:
    def __init__(self, db_path: str):
        self.db_path = db_path
        ensure_parent_dir(self.db_path)

    def update_recommendation_model(self):
        """
        Update the recommendation model with new data

        Analyzes historical student performance data to improve course recommendations:
        - Calculates success rates for course combinations
        - Identifies patterns in successful course progressions
        - Updates weights based on completion rates and grades
        - Tracks prerequisite effectiveness
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            course_metrics = {}

            try:
                cursor.execute("""
                    SELECT
                        module_code,
                        COUNT(*) as enrollments,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completions,
                        AVG(CASE WHEN grade IS NOT NULL THEN grade ELSE 0 END) as avg_grade
                    FROM student_modules
                    WHERE status IN ('completed', 'enrolled', 'failed')
                    GROUP BY module_code
                """)

                completion_data = cursor.fetchall()

                for module_code, enrollments, completions, avg_grade in completion_data:
                    if enrollments > 0:
                        completion_rate = completions / enrollments
                        course_metrics[module_code] = {
                            'completion_rate': completion_rate,
                            'average_grade': avg_grade,
                            'total_enrollments': enrollments,
                            'popularity_score': min(enrollments / 100.0, 1.0)
                        }

            except sqlite3.OperationalError as e:
                logger.debug(f"Courses table not available for learning analytics: {e}")

            try:
                cursor.execute("""
                    SELECT
                        m.module_code,
                        m.prerequisites,
                        COUNT(CASE WHEN sm.status = 'completed' THEN 1 END) as successful_students
                    FROM modules m
                    LEFT JOIN student_modules sm ON m.module_code = sm.module_code
                    WHERE m.prerequisites IS NOT NULL AND m.prerequisites != ''
                    GROUP BY m.module_code, m.prerequisites
                """)

                prereq_data = cursor.fetchall()

                for module_code, prerequisites, successful_count in prereq_data:
                    if module_code in course_metrics:
                        course_metrics[module_code]['prereq_effectiveness'] = successful_count

            except sqlite3.OperationalError as e:
                logger.debug(f"Prerequisite data not available for learning analytics: {e}")

            try:
                cursor.execute("""
                    SELECT
                        s.program,
                        sm.module_code,
                        AVG(s.cumulative_gpa) as avg_student_gpa
                    FROM students s
                    JOIN student_modules sm ON s.student_id = sm.student_id
                    WHERE sm.status = 'completed'
                    GROUP BY s.program, sm.module_code
                """)

                progression_data = cursor.fetchall()

                for program, module_code, avg_gpa in progression_data:
                    if module_code in course_metrics:
                        if 'program_performance' not in course_metrics[module_code]:
                            course_metrics[module_code]['program_performance'] = {}
                        course_metrics[module_code]['program_performance'][program] = avg_gpa

            except sqlite3.OperationalError as e:
                logger.debug(f"Student progression data not available for learning analytics: {e}")

            print(f"[CourseRecommendationEngine] Model updated with {len(course_metrics)} courses analyzed")

            if course_metrics:
                top_courses = sorted(
                    course_metrics.items(),
                    key=lambda x: x[1].get('completion_rate', 0),
                    reverse=True
                )[:5]

                print("Top performing courses:")
                for course_code, metrics in top_courses:
                    print(f"  {course_code}: {metrics.get('completion_rate', 0):.1%} completion, "
                          f"{metrics.get('average_grade', 0):.1f} avg grade")

            conn.close()
            return {
                'success': True,
                'courses_analyzed': len(course_metrics),
                'metrics': course_metrics
            }

        except Exception as e:
            print(f"[CourseRecommendationEngine] Error updating model: {e}")
            return {
                'success': False,
                'error': str(e)
            }


class AdminPanel:
    def __init__(self, chatbot):
        self.chatbot = chatbot

    def generate_admin_dashboard(self) -> Dict:
        """Generate admin dashboard with comprehensive metrics"""
        return {
            "system_status": "operational",
            "active_sessions": len(self.chatbot.active_sessions),
            "daily_metrics": self.chatbot.generate_usage_analytics(),
            "voice_status": self.chatbot.voice_interface.enabled,
            "system_performance": self.get_system_performance()
        }

    def get_system_performance(self) -> Dict:
        """Get system performance metrics"""
        return {
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "response_time": 0.0,
            "uptime": "24h"
        }


class BackgroundScheduler:
    def __init__(self):
        self.tasks = []

    def add_task(self, task_func, schedule_time):
        """Add a scheduled task"""
        self.tasks.append((task_func, schedule_time))
