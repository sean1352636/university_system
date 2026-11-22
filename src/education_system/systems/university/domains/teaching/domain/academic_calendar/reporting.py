import logging
from datetime import datetime
from collections import defaultdict
from typing import Dict, Tuple, Any
from education_system.systems.university.infrastructure.logging.log_config import configure_logging
from education_system.systems.university.domains.teaching.domain.academic_calendar.exceptions import PermissionError
from education_system.systems.university.domains.teaching.domain.academic_calendar.database import DatabaseManager
from education_system.systems.university.domains.teaching.domain.academic_calendar.auth import AuthenticationManager

logger = configure_logging(name=__name__)

#: Attendance statuses that count as the student being there.
ATTENDED_STATUSES = ('present', 'late', 'attended')

#: Utilisation is expressed against a working year of 40-hour weeks.
WORKING_HOURS_PER_WEEK = 40
WEEKS_IN_YEAR = 52

_DATETIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                     "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M")


def _parse_datetime(value):
    text = str(value or '').strip().split('.')[0]
    if not text:
        return None
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _booking_hours(start, finish):
    """Length of a booking in hours; 0 when either end is missing or unreadable."""
    begin, end = _parse_datetime(start), _parse_datetime(finish)
    if not begin or not end or end <= begin:
        return 0.0
    return (end - begin).total_seconds() / 3600


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
            FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar') e
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

    def _optional_query(self, query, params=()):
        """Run *query*, treating a table or column this database lacks as no rows."""
        try:
            return self.db_manager.execute_query(query, params)
        except Exception as e:
            message = str(e).lower()
            if 'no such table' in message or 'no such column' in message:
                logger.debug(f"Skipping optional report source: {e}")
                return []
            raise

    def attendance_by_course(self) -> Dict[str, Any]:
        """Attendance for every course, including courses with none recorded.

        generate_attendance_report() reaches attendance through calendar
        events (course_events -> course_event_attendance). Nothing records
        attendance there, and it only lists courses that have a linked event,
        so the chart showed a handful of courses with no figures. Marks are
        taken per module in attendance_records, and a module's course is
        modules.course, so this starts from the courses table and counts what
        was recorded against each course's modules.

        Each row: course_code, course_name, sessions (distinct module + date),
        marks, attended, attendance_rate (None when nothing is recorded) and
        linked_events (calendar events tied to the course). Marks whose module
        belongs to no course are reported as a final "not linked" row.
        """
        if not self.auth_manager.check_permission('view_reports'):
            raise PermissionError("Insufficient permissions to generate reports")

        try:
            courses = self.db_manager.execute_query(
                "SELECT id, code, COALESCE(NULLIF(name, ''), course_name, code) AS name "
                "FROM courses WHERE COALESCE(code, '') <> '' ORDER BY code")
            marks = self._optional_query('''
                SELECT (SELECT m.course FROM modules m
                         WHERE m.module_code = ar.module_code
                           AND COALESCE(m.course, '') <> '' LIMIT 1) AS course_code,
                       ar.module_code, ar.date,
                       LOWER(TRIM(COALESCE(ar.status, ''))) AS status
                  FROM attendance_records ar
            ''')
            linked = self._optional_query(
                "SELECT course_id, COUNT(*) AS n FROM course_events GROUP BY course_id")
        except Exception as e:
            logger.error(f"Failed to build attendance by course: {e}")
            return {'success': False, 'error': str(e)}

        per_course = {}
        for row in marks:
            entry = per_course.setdefault(row['course_code'] or '',
                                          {'sessions': set(), 'marks': 0, 'attended': 0})
            entry['sessions'].add((row['module_code'], row['date']))
            entry['marks'] += 1
            if row['status'] in ATTENDED_STATUSES:
                entry['attended'] += 1
        linked_by = {str(row['course_id']): row['n'] for row in linked}

        def _row(code, name, entry, events):
            entry = entry or {'sessions': set(), 'marks': 0, 'attended': 0}
            return {
                'course_code': code,
                'course_name': name,
                'sessions': len(entry['sessions']),
                'marks': entry['marks'],
                'attended': entry['attended'],
                'attendance_rate': (round(entry['attended'] / entry['marks'] * 100, 1)
                                    if entry['marks'] else None),
                'linked_events': events,
            }

        rows, known = [], set()
        for course in courses:
            code, course_id = course['code'], str(course['id'])
            known.add(code)
            events = linked_by.get(code, 0) + (linked_by.get(course_id, 0) if course_id != code else 0)
            rows.append(_row(code, course['name'], per_course.get(code), events))
        # A module tagged with a course code the courses table doesn't hold.
        for code in sorted(c for c in per_course if c and c not in known):
            rows.append(_row(code, code, per_course[code], linked_by.get(code, 0)))
        if per_course.get('', {}).get('marks'):
            rows.append(_row('—', 'Module not linked to a course', per_course[''], 0))

        return {
            'success': True,
            'courses': rows,
            'generated_at': datetime.now().isoformat(),
        }

    def generate_utilization_report(self, resource_type: str = None) -> Dict[str, Any]:
        """Generate resource utilization reports.

        Bookings are spread over three tables: resource_bookings (the
        calendar's own), room_bookings (exams and classes) and
        facility_bookings (study and seminar rooms). Reading only the first
        showed nothing while the others held confirmed bookings. The old query
        also reported julianday differences — days — as hours, and filtered
        its LEFT JOIN in WHERE.

        *resource_type* matches the type column case-insensitively: a
        resource's own type, or 'Room' / 'Facility' for the other two tables.
        """
        if not self.auth_manager.check_permission('view_reports'):
            raise PermissionError("Insufficient permissions to generate reports")

        try:
            bookings = []
            for row in self._optional_query('''
                SELECT r.name AS name, COALESCE(NULLIF(r.type, ''), 'Resource') AS kind,
                       rb.start_time AS start, rb.end_time AS finish
                  FROM resource_bookings rb
                  JOIN resources r ON r.id = rb.resource_id
                 WHERE LOWER(COALESCE(rb.status, 'confirmed')) IN ('confirmed', 'approved')
            '''):
                bookings.append((row['name'] or 'Resource', row['kind'], row['start'], row['finish']))

            for row in self._optional_query('''
                SELECT rb.room_id, r.room_name, r.room_number, r.building,
                       rb.start_datetime AS start, rb.end_datetime AS finish
                  FROM room_bookings rb
                  LEFT JOIN rooms r ON r.id = rb.room_id
                 WHERE LOWER(COALESCE(rb.booking_status, 'confirmed')) IN ('confirmed', 'approved')
            '''):
                label = (row['room_name']
                         or (f"Room {row['room_number']}" if row['room_number'] else f"Room {row['room_id']}"))
                if row['building'] and row['building'] != label:
                    label = f"{label} ({row['building']})"
                bookings.append((label, 'Room', row['start'], row['finish']))

            for row in self._optional_query('''
                SELECT facility_name AS name,
                       booking_date || ' ' || start_time AS start,
                       booking_date || ' ' || end_time AS finish
                  FROM facility_bookings
                 WHERE LOWER(COALESCE(status, 'confirmed')) IN ('confirmed', 'approved')
            '''):
                bookings.append((row['name'] or 'Facility', 'Facility', row['start'], row['finish']))

        except Exception as e:
            logger.error(f"Failed to generate utilization report: {e}")
            return {'success': False, 'error': str(e)}

        if resource_type:
            wanted = resource_type.strip().lower()
            bookings = [b for b in bookings if str(b[1]).lower() == wanted]

        totals = {}
        for name, kind, start, finish in bookings:
            entry = totals.setdefault((name, kind), {'bookings': 0, 'hours': 0.0})
            entry['bookings'] += 1
            entry['hours'] += _booking_hours(start, finish)

        available_hours = WORKING_HOURS_PER_WEEK * WEEKS_IN_YEAR
        utilization_data = []
        for (name, kind), entry in sorted(totals.items(),
                                          key=lambda kv: (-kv[1]['bookings'], -kv[1]['hours'], kv[0][0])):
            utilization_data.append({
                'resource_name': name,
                'resource_type': kind,
                'total_bookings': entry['bookings'],
                'total_hours': round(entry['hours'], 2),
                'avg_duration': round(entry['hours'] / entry['bookings'], 2),
                'utilization_percentage': round(entry['hours'] / available_hours * 100, 2),
            })

        return {
            'success': True,
            'resources': utilization_data,
            'total_resources': len(utilization_data),
            'generated_at': datetime.now().isoformat()
        }

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
            FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar') e
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
