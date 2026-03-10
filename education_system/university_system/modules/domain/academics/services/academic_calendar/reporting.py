import logging
from datetime import datetime
from collections import defaultdict
from typing import Dict, Tuple, Any
from education_system.university_system.utils.logging.log_config import configure_logging
from .exceptions import PermissionError
from .database import DatabaseManager
from .auth import AuthenticationManager

logger = configure_logging(name=__name__)


class AdvancedReportingManager:
    """Comprehensive reporting and analytics system"""

    def __init__(self, db_manager: DatabaseManager, auth_manager: AuthenticationManager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager

    def generate_attendance_report(self, course_id: str = None,
                                 date_range: Tuple[str, str] = None) -> Dict[str, Any]:
        """Generate comprehensive attendance reports"""
        if not self.auth_manager.check_permission('view_reports'):
            raise PermissionError("Insufficient permissions to generate reports")

        try:
            query = '''
            SELECT e.name as event_name, e.date as event_date, e.event_type,
                   COUNT(DISTINCT cea.student_id) as attendees,
                   ce.course_id, c.name as course_name
            FROM academic_calendar_events e
            LEFT JOIN course_events ce ON e.id = ce.event_id
            LEFT JOIN courses c ON ce.course_id = c.id
            LEFT JOIN course_event_attendance cea ON e.id = cea.event_id
            WHERE 1=1
            '''
            params = []

            if course_id:
                query += " AND ce.course_id = ?"
                params.append(course_id)

            if date_range:
                query += " AND e.date BETWEEN ? AND ?"
                params.extend(date_range)

            query += " GROUP BY e.id ORDER BY e.date DESC"

            rows = self.db_manager.execute_query(query, tuple(params))

            # Calculate statistics
            total_events = len(rows)
            avg_attendance = sum(row['attendees'] for row in rows) / total_events if total_events > 0 else 0

            # Group by course
            course_stats = defaultdict(lambda: {'events': 0, 'total_attendance': 0})
            for row in rows:
                course_name = row['course_name'] or 'Unassigned'
                course_stats[course_name]['events'] += 1
                course_stats[course_name]['total_attendance'] += row['attendees']

            return {
                'success': True,
                'total_events': total_events,
                'average_attendance': round(avg_attendance, 2),
                'events': [dict(row) for row in rows],
                'course_statistics': dict(course_stats),
                'generated_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to generate attendance report: {e}")
            return {'success': False, 'error': str(e)}

    def generate_utilization_report(self, resource_type: str = None) -> Dict[str, Any]:
        """Generate resource utilization reports"""
        if not self.auth_manager.check_permission('view_reports'):
            raise PermissionError("Insufficient permissions to generate reports")

        try:
            query = '''
            SELECT r.name as resource_name, r.type as resource_type,
                   COUNT(rb.id) as total_bookings,
                   SUM(julianday(rb.end_time) - julianday(rb.start_time)) as total_hours,
                   AVG(julianday(rb.end_time) - julianday(rb.start_time)) as avg_booking_duration
            FROM resources r
            LEFT JOIN resource_bookings rb ON r.id = rb.resource_id
            WHERE rb.status = 'confirmed'
            '''
            params = []

            if resource_type:
                query += " AND r.type = ?"
                params.append(resource_type)

            query += " GROUP BY r.id ORDER BY total_bookings DESC"

            rows = self.db_manager.execute_query(query, tuple(params))

            # Calculate utilization percentages (assuming 8 hours/day, 5 days/week)
            working_hours_per_week = 40
            weeks_in_period = 52  # Adjust based on actual period

            utilization_data = []
            for row in rows:
                total_available_hours = working_hours_per_week * weeks_in_period
                utilization_percentage = (row['total_hours'] / total_available_hours) * 100 if total_available_hours > 0 else 0

                utilization_data.append({
                    'resource_name': row['resource_name'],
                    'resource_type': row['resource_type'],
                    'total_bookings': row['total_bookings'],
                    'total_hours': round(row['total_hours'], 2),
                    'avg_duration': round(row['avg_booking_duration'], 2),
                    'utilization_percentage': round(utilization_percentage, 2)
                })

            return {
                'success': True,
                'resources': utilization_data,
                'total_resources': len(utilization_data),
                'generated_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to generate utilization report: {e}")
            return {'success': False, 'error': str(e)}

    def generate_academic_year_summary(self, academic_year_id: str) -> Dict[str, Any]:
        """Generate comprehensive academic year summary"""
        if not self.auth_manager.check_permission('view_reports'):
            raise PermissionError("Insufficient permissions to generate reports")

        try:
            # Get academic year info
            year_rows = self.db_manager.execute_query(
                "SELECT * FROM academic_years WHERE id = ?", (academic_year_id,)
            )
            if not year_rows:
                return {'success': False, 'error': 'Academic year not found'}

            year_info = dict(year_rows[0])

            # Get events for this academic year
            event_query = '''
            SELECT e.*, s.name as semester_name
            FROM academic_calendar_events e
            LEFT JOIN semesters s ON (e.date BETWEEN s.start_date AND s.end_date)
            WHERE s.academic_year_id = ?
            ORDER BY e.date
            '''
            event_rows = self.db_manager.execute_query(event_query, (academic_year_id,))

            # Categorize events
            event_stats = defaultdict(int)
            monthly_distribution = defaultdict(int)

            for event in event_rows:
                event_stats[event['event_type']] += 1
                if event['date']:
                    month = datetime.strptime(event['date'], "%Y-%m-%d").strftime("%Y-%m")
                    monthly_distribution[month] += 1

            # Get semester info
            semester_rows = self.db_manager.execute_query(
                "SELECT * FROM semesters WHERE academic_year_id = ? ORDER BY start_date",
                (academic_year_id,)
            )

            return {
                'success': True,
                'academic_year': year_info,
                'semesters': [dict(row) for row in semester_rows],
                'total_events': len(event_rows),
                'event_statistics': dict(event_stats),
                'monthly_distribution': dict(monthly_distribution),
                'events': [dict(row) for row in event_rows],
                'generated_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to generate academic year summary: {e}")
            return {'success': False, 'error': str(e)}
