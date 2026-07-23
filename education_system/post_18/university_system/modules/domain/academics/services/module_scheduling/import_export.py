from education_system.post_18.university_system.infrastructure.database.db import get_connection
from datetime import datetime, timedelta
from education_system.post_18.university_system.modules.domain.academics.services.module_scheduling.constants import DAYS_OF_WEEK
import os
try:
    from icalendar import Calendar, Event
    ICALENDAR_AVAILABLE = True
except Exception:
    ICALENDAR_AVAILABLE = False


class ImportExportMixin:
    def import_schedules_from_csv(self, csv_file_path):
        """Import schedules from CSV file"""
        import pandas as pd
        try:
            df = pd.read_csv(csv_file_path)
            required_columns = ['module_code', 'day_of_week', 'start_time', 'end_time',
                              'room_id', 'instructor_id', 'session_type']

            if not all(col in df.columns for col in required_columns):
                print(f"CSV must contain columns: {', '.join(required_columns)}")
                return False

            success_count = 0
            error_count = 0

            for index, row in df.iterrows():
                try:
                    result = self.add_module_schedule(
                        row['module_code'], row['day_of_week'], row['start_time'],
                        row['end_time'], int(row['room_id']), int(row['instructor_id']),
                        row['session_type']
                    )
                    if result:
                        success_count += 1
                    else:
                        error_count += 1
                except Exception as e:
                    print(f"Error importing row {index + 1}: {e}")
                    error_count += 1

            print(f"Import completed: {success_count} successful, {error_count} errors")

            # Log the import
            self._log_system_action('bulk_import', f"Imported {success_count} schedules from {csv_file_path}")

            return True

        except Exception as e:
            print(f"Error reading CSV file: {e}")
            return False

    def export_all_schedules_to_csv(self):
        """Export all schedules to CSV"""
        import pandas as pd
        with get_connection(self.db_path, row_factory=False) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            query = '''
        SELECT ms.module_code, ms.day_of_week, ms.start_time, ms.end_time,
               ms.room_id, ms.instructor_id, ms.session_type,
               r.building, r.room_number, i.first_name, i.last_name
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        LEFT JOIN instructors i ON ms.instructor_id = i.id
        ORDER BY ms.module_code, ms.day_of_week, ms.start_time
        '''

            df = pd.read_sql_query(query, conn)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Ensure directory exists
        from education_system.post_18.university_system.core import paths
        timetable_reports_dir = paths.REPORTS_DIR / 'timetable_reports'
        os.makedirs(str(timetable_reports_dir), exist_ok=True)

        filename = os.path.join(str(timetable_reports_dir), f"all_schedules_export_{timestamp}.csv")
        df.to_csv(filename, index=False)
        print(f"All schedules exported to: {filename}")

        return filename

    def export_to_ical(self, entity_type, entity_id, filename=None):
        """Export schedule to iCal format"""
        if not ICALENDAR_AVAILABLE:
            raise ImportError("icalendar library not available. Install with: pip install icalendar")
        cal = Calendar()
        cal.add('prodid', '-//University Schedule//EN')
        cal.add('version', '2.0')

        # Get schedule data
        if entity_type == 'student':
            schedules = self._get_student_schedule_data(entity_id)
            cal.add('x-wr-calname', f'Student {entity_id} Schedule')
        elif entity_type == 'instructor':
            schedules = self._get_instructor_schedule_data(entity_id)
            cal.add('x-wr-calname', f'Instructor {entity_id} Schedule')
        else:
            print("Invalid entity type")
            return None

        # Add events
        for schedule in schedules:
            event = Event()
            event.add('summary', f"{schedule['module_code']} - {schedule['session_type']}")
            event.add('description', f"Module: {schedule['module_name']}\nRoom: {schedule['room']}\nInstructor: {schedule['instructor']}")

            # Calculate event times (recurring weekly)
            start_time = datetime.strptime(schedule['start_time'], "%H:%M").time()
            end_time = datetime.strptime(schedule['end_time'], "%H:%M").time()

            # Get day index (Monday = 0)
            day_index = DAYS_OF_WEEK.index(schedule['day'])

            # Find next occurrence of this day
            today = datetime.now().date()
            days_ahead = day_index - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7

            event_date = today + timedelta(days=days_ahead)
            event_start = datetime.combine(event_date, start_time)
            event_end = datetime.combine(event_date, end_time)

            event.add('dtstart', event_start)
            event.add('dtend', event_end)
            event.add('location', schedule['room'])

            # Add recurrence rule (weekly for the semester)
            event.add('rrule', {'freq': 'weekly', 'count': 15})  # 15 weeks typical semester

            cal.add_component(event)

        # Save to file
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"timetable_reports/{entity_type}_{entity_id}_schedule_{timestamp}.ics"

        # Ensure directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        with open(filename, 'wb') as f:
            f.write(cal.to_ical())

        print(f"iCal file exported: {filename}")
        return filename

    def _get_student_schedule_data(self, student_id):
        """Get schedule data for a student"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        cursor.execute('SELECT module_code FROM student_modules WHERE student_id = ?', (student_id,))
        modules = [row[0] for row in cursor.fetchall()]

        if not modules:
            conn.close()
            return []

        placeholders = ','.join(['?'] * len(modules))
        query = f'''
        SELECT ms.module_code, m.module_name, ms.day_of_week, ms.start_time, ms.end_time,
               r.building, r.room_number, i.first_name, i.last_name, ms.session_type
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        LEFT JOIN instructors i ON ms.instructor_id = i.id
        LEFT JOIN modules m ON ms.module_code = m.module_code
        WHERE ms.module_code IN ({placeholders})
        ORDER BY ms.day_of_week, ms.start_time
        '''

        cursor.execute(query, modules)
        schedules = cursor.fetchall()
        conn.close()

        schedule_data = []
        for schedule in schedules:
            module_code, module_name, day, start, end, building, room, first_name, last_name, session_type = schedule
            schedule_data.append({
                'module_code': module_code,
                'module_name': module_name or "Unknown",
                'day': day,
                'start_time': start,
                'end_time': end,
                'room': f"{building}-{room}" if building and room else "TBA",
                'instructor': f"{first_name} {last_name}" if first_name and last_name else "TBA",
                'session_type': session_type
            })

        return schedule_data

    def _get_instructor_schedule_data(self, instructor_id):
        """Get schedule data for an instructor"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        query = '''
        SELECT ms.module_code, m.module_name, ms.day_of_week, ms.start_time, ms.end_time,
               r.building, r.room_number, i.first_name, i.last_name, ms.session_type
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        LEFT JOIN instructors i ON ms.instructor_id = i.id
        LEFT JOIN modules m ON ms.module_code = m.module_code
        WHERE ms.instructor_id = ?
        ORDER BY ms.day_of_week, ms.start_time
        '''

        cursor.execute(query, (instructor_id,))
        schedules = cursor.fetchall()
        conn.close()

        schedule_data = []
        for schedule in schedules:
            module_code, module_name, day, start, end, building, room, first_name, last_name, session_type = schedule
            schedule_data.append({
                'module_code': module_code,
                'module_name': module_name or "Unknown",
                'day': day,
                'start_time': start,
                'end_time': end,
                'room': f"{building}-{room}" if building and room else "TBA",
                'instructor': f"{first_name} {last_name}" if first_name and last_name else "TBA",
                'session_type': session_type
            })

        return schedule_data
