import logging
from typing import Dict, Any, Optional, List
from .database import DatabaseManager
from .utils import convert_to_user_error

gui_logger = logging.getLogger(__name__)

class ReportingEngine:
    """
    Advanced reporting and analytics engine

    Features:
    - Attendance tracking and reporting
    - Resource utilization analysis
    - Academic year summaries
    - Custom report generation
    - Export to multiple formats
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize reporting engine

        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager
        gui_logger.info("ReportingEngine initialized")

    def generate_attendance_report(self, start_date: str, end_date: str,
                                  event_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate attendance report for date range

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            event_type: Optional event type filter

        Returns:
            Dict: Attendance statistics and details

        Example:
            report = reporting.generate_attendance_report(
                "2025-09-01",
                "2025-12-31",
                event_type="lecture"
            )
        """
        try:
            query = """
                SELECT
                    e.id,
                    e.title,
                    e.date,
                    e.event_type,
                    COUNT(DISTINCT a.student_id) as attendee_count,
                    e.capacity,
                    CASE
                        WHEN e.capacity > 0
                        THEN ROUND(COUNT(DISTINCT a.student_id) * 100.0 / e.capacity, 2)
                        ELSE 0
                    END as attendance_percentage
                FROM calendar_events e
                LEFT JOIN event_attendance a ON e.id = a.event_id
                WHERE e.date BETWEEN ? AND ?
            """

            params = [start_date, end_date]

            if event_type:
                query += " AND e.event_type = ?"
                params.append(event_type)

            query += " GROUP BY e.id ORDER BY e.date"

            events = self.db.execute_query(query, tuple(params))

            # Calculate summary statistics
            total_events = len(events)
            total_attendees = sum(e['attendee_count'] for e in events)
            avg_attendance = (
                sum(e['attendance_percentage'] for e in events) / total_events
                if total_events > 0 else 0
            )

            return {
                'period': {'start': start_date, 'end': end_date},
                'event_type': event_type or 'all',
                'summary': {
                    'total_events': total_events,
                    'total_attendees': total_attendees,
                    'average_attendance_percentage': round(avg_attendance, 2)
                },
                'events': events
            }

        except Exception as e:
            raise convert_to_user_error(e, {'operation': 'generate_attendance_report'})

    def generate_utilization_report(self, resource_type: str = 'room') -> Dict[str, Any]:
        """
        Generate resource utilization report

        Args:
            resource_type: Type of resource ('room', 'equipment', etc.)

        Returns:
            Dict: Utilization statistics

        Example:
            report = reporting.generate_utilization_report(resource_type='room')
        """
        try:
            query = """
                SELECT
                    location as resource_name,
                    COUNT(*) as total_bookings,
                    COUNT(DISTINCT date) as days_used,
                    SUM(CASE
                        WHEN date >= date('now')
                        THEN 1 ELSE 0
                    END) as upcoming_bookings
                FROM calendar_events
                WHERE location IS NOT NULL AND location != ''
                GROUP BY location
                ORDER BY total_bookings DESC
            """

            resources = self.db.execute_query(query)

            # Calculate overall utilization
            total_bookings = sum(r['total_bookings'] for r in resources)
            total_resources = len(resources)

            return {
                'resource_type': resource_type,
                'summary': {
                    'total_resources': total_resources,
                    'total_bookings': total_bookings,
                    'average_bookings_per_resource': (
                        round(total_bookings / total_resources, 2)
                        if total_resources > 0 else 0
                    )
                },
                'resources': resources
            }

        except Exception as e:
            raise convert_to_user_error(e, {'operation': 'generate_utilization_report'})

    def generate_academic_year_summary(self, academic_year: str) -> Dict[str, Any]:
        """
        Generate comprehensive academic year summary

        Args:
            academic_year: Academic year (e.g., "2025-2026")

        Returns:
            Dict: Academic year statistics and breakdown

        Example:
            report = reporting.generate_academic_year_summary("2025-2026")
        """
        try:
            # Parse academic year
            start_year = int(academic_year.split('-')[0])
            start_date = f"{start_year}-09-01"
            end_date = f"{start_year + 1}-08-31"

            # Get event breakdown by type
            event_breakdown = self.db.execute_query("""
                SELECT
                    event_type,
                    COUNT(*) as count,
                    COUNT(DISTINCT date) as unique_dates
                FROM calendar_events
                WHERE date BETWEEN ? AND ?
                GROUP BY event_type
            """, (start_date, end_date))

            # Get monthly distribution
            monthly_distribution = self.db.execute_query("""
                SELECT
                    strftime('%Y-%m', date) as month,
                    COUNT(*) as event_count
                FROM calendar_events
                WHERE date BETWEEN ? AND ?
                GROUP BY month
                ORDER BY month
            """, (start_date, end_date))

            total_events = sum(e['count'] for e in event_breakdown)

            return {
                'academic_year': academic_year,
                'period': {'start': start_date, 'end': end_date},
                'summary': {
                    'total_events': total_events,
                    'event_types': len(event_breakdown)
                },
                'event_breakdown': event_breakdown,
                'monthly_distribution': monthly_distribution
            }

        except Exception as e:
            raise convert_to_user_error(e, {'operation': 'generate_academic_year_summary'})


