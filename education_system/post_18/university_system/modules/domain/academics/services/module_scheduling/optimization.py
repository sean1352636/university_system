from education_system.post_18.university_system.core.sql_safety import escape_like
from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.post_18.university_system.modules.domain.academics.services.module_scheduling.constants import DAYS_OF_WEEK, TIME_SLOTS


class OptimizationMixin:
    def suggest_optimal_time_slot(self, module_code, session_type, duration_minutes=60):
        """Suggest optimal time slots for a new schedule"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        # Get module information
        cursor.execute('SELECT module_code FROM modules WHERE module_code = ?', (module_code,))
        if not cursor.fetchone():
            print(f"Module {module_code} does not exist.")
            conn.close()
            return []

        suggestions = []

        for day in DAYS_OF_WEEK:
            for time_slot in TIME_SLOTS:
                # Calculate end time
                start_hour, start_min = map(int, time_slot.split(':'))
                end_time = datetime.strptime(time_slot, "%H:%M") + timedelta(minutes=duration_minutes)
                end_time_str = end_time.strftime("%H:%M")

                # Check availability
                score = self._calculate_slot_score(day, time_slot, end_time_str, session_type)

                if score > 0:  # Only suggest available slots
                    suggestions.append({
                        'day': day,
                        'start_time': time_slot,
                        'end_time': end_time_str,
                        'score': score,
                        'reasons': self._get_score_reasons(day, time_slot, session_type)
                    })

        conn.close()

        # Sort by score (highest first)
        suggestions.sort(key=lambda x: x['score'], reverse=True)

        return suggestions[:10]  # Return top 10 suggestions

    def _calculate_slot_score(self, day, start_time, end_time, session_type):
        """Calculate a score for a time slot based on various factors"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        score = 100  # Start with base score

        # Check for conflicts
        cursor.execute('''
        SELECT COUNT(*) FROM module_schedule
        WHERE day_of_week = ? AND (
            (start_time < ? AND end_time > ?) OR
            (start_time < ? AND end_time > ?) OR
            (start_time >= ? AND end_time <= ?)
        )
        ''', (day, end_time, start_time, end_time, start_time, start_time, end_time))

        conflicts = cursor.fetchone()[0]
        if conflicts > 0:
            score = 0  # No score for conflicting slots
            conn.close()
            return score

        # Bonus for popular time slots (but not too crowded)
        cursor.execute('''
        SELECT COUNT(*) FROM module_schedule
        WHERE day_of_week = ? AND start_time = ?
        ''', (day, start_time))

        same_time_count = cursor.fetchone()[0]
        if 1 <= same_time_count <= 3:  # Sweet spot
            score += 10
        elif same_time_count > 5:  # Too crowded
            score -= 20

        # Preference bonuses
        if session_type == 'Lecture' and start_time in ['09:00', '10:00', '11:00']:
            score += 15  # Morning lectures preferred
        elif session_type == 'Lab' and start_time in ['14:00', '15:00', '16:00']:
            score += 10  # Afternoon labs preferred

        # Day preferences
        if day in ['Tuesday', 'Wednesday', 'Thursday']:
            score += 5  # Mid-week preferred

        conn.close()
        return score

    def _get_score_reasons(self, day, start_time, session_type):
        """Get human-readable reasons for the score"""
        reasons = []

        if session_type == 'Lecture' and start_time in ['09:00', '10:00', '11:00']:
            reasons.append("Good time for lectures")
        elif session_type == 'Lab' and start_time in ['14:00', '15:00', '16:00']:
            reasons.append("Preferred afternoon lab time")

        if day in ['Tuesday', 'Wednesday', 'Thursday']:
            reasons.append("Mid-week scheduling preferred")

        if start_time in ['09:00', '10:00']:
            reasons.append("Popular morning slot")

        return reasons

    def find_alternative_slots(self, day, start_time, end_time, room_type=None):
        """Find alternative time slots when conflicts occur"""
        alternatives = []

        # Try same day, different times
        for time_slot in TIME_SLOTS:
            if time_slot != start_time:
                duration = self._calculate_duration(start_time, end_time)
                alt_end = self._add_minutes_to_time(time_slot, duration)

                if self._is_slot_available(day, time_slot, alt_end):
                    alternatives.append({
                        'day': day,
                        'start_time': time_slot,
                        'end_time': alt_end,
                        'type': 'same_day'
                    })

        # Try same time, different days
        for alt_day in DAYS_OF_WEEK:
            if alt_day != day and self._is_slot_available(alt_day, start_time, end_time):
                alternatives.append({
                    'day': alt_day,
                    'start_time': start_time,
                    'end_time': end_time,
                    'type': 'same_time'
                })

        return alternatives

    def _calculate_duration(self, start_time, end_time):
        """Calculate duration in minutes between two times"""
        start = datetime.strptime(start_time, "%H:%M")
        end = datetime.strptime(end_time, "%H:%M")
        return int((end - start).total_seconds() / 60)

    def _add_minutes_to_time(self, time_str, minutes):
        """Add minutes to a time string"""
        time_obj = datetime.strptime(time_str, "%H:%M")
        new_time = time_obj + timedelta(minutes=minutes)
        return new_time.strftime("%H:%M")

    def _is_slot_available(self, day, start_time, end_time):
        """Check if a time slot is available"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        cursor.execute('''
        SELECT COUNT(*) FROM module_schedule
        WHERE day_of_week = ? AND (
            (start_time < ? AND end_time > ?) OR
            (start_time < ? AND end_time > ?) OR
            (start_time >= ? AND end_time <= ?)
        )
        ''', (day, end_time, start_time, end_time, start_time, start_time, end_time))

        conflicts = cursor.fetchone()[0]
        conn.close()

        return conflicts == 0

    def advanced_schedule_search(self, filters=None):
        """Advanced search with multiple criteria"""
        if filters is None:
            filters = {}

        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        # Build dynamic query
        base_query = '''
        SELECT ms.id, ms.module_code, m.module_name, ms.day_of_week,
               ms.start_time, ms.end_time, r.building, r.room_number,
               i.first_name, i.last_name, ms.session_type
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        LEFT JOIN instructors i ON ms.instructor_id = i.id
        LEFT JOIN modules m ON ms.module_code = m.module_code
        WHERE 1=1
        '''

        params = []

        # Add filters
        if 'module_code' in filters and filters['module_code']:
            base_query += " AND ms.module_code LIKE ?"
            params.append(f"%{escape_like(filters['module_code'])}%")

        if 'day' in filters and filters['day']:
            base_query += " AND ms.day_of_week = ?"
            params.append(filters['day'])

        if 'time_from' in filters and filters['time_from']:
            base_query += " AND ms.start_time >= ?"
            params.append(filters['time_from'])

        if 'time_to' in filters and filters['time_to']:
            base_query += " AND ms.end_time <= ?"
            params.append(filters['time_to'])

        if 'session_type' in filters and filters['session_type']:
            base_query += " AND ms.session_type = ?"
            params.append(filters['session_type'])

        if 'instructor' in filters and filters['instructor']:
            base_query += " AND (i.first_name LIKE ? OR i.last_name LIKE ?)"
            params.extend([f"%{escape_like(filters['instructor'])}%", f"%{escape_like(filters['instructor'])}%"])

        if 'building' in filters and filters['building']:
            base_query += " AND r.building LIKE ?"
            params.append(f"%{escape_like(filters['building'])}%")

        if 'room_type' in filters and filters['room_type']:
            base_query += " AND r.room_type = ?"
            params.append(filters['room_type'])

        base_query += " ORDER BY ms.day_of_week, ms.start_time"

        cursor.execute(base_query, params)
        results = cursor.fetchall()
        conn.close()

        return results

    def find_free_rooms(self, day, start_time, end_time, min_capacity=0, room_type=None):
        """Find available rooms for a specific time slot"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        # Base query for rooms
        query = '''
        SELECT r.id, r.room_number, r.building, r.capacity, r.room_type, r.equipment
        FROM rooms r
        WHERE r.is_active = 1 AND r.capacity >= ?
        '''
        params = [min_capacity]

        if room_type:
            query += " AND r.room_type = ?"
            params.append(room_type)

        # Exclude rooms that are scheduled during this time
        query += '''
        AND r.id NOT IN (
            SELECT ms.room_id FROM module_schedule ms
            WHERE ms.day_of_week = ? AND (
                (ms.start_time < ? AND ms.end_time > ?) OR
                (ms.start_time < ? AND ms.end_time > ?) OR
                (ms.start_time >= ? AND ms.end_time <= ?)
            )
        )
        '''
        params.extend([day, end_time, start_time, end_time, start_time, start_time, end_time])

        query += " ORDER BY r.building, r.room_number"

        cursor.execute(query, params)
        free_rooms = cursor.fetchall()
        conn.close()

        return free_rooms

    def find_schedule_gaps(self, entity_type, entity_id):
        """Find free periods in student or instructor schedules"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        if entity_type == 'student':
            # Get student's enrolled modules
            cursor.execute('SELECT module_code FROM student_modules WHERE student_id = ?', (entity_id,))
            modules = [row[0] for row in cursor.fetchall()]

            if not modules:
                conn.close()
                return "Student not enrolled in any modules"

            # Get schedule for these modules
            placeholders = ','.join(['?'] * len(modules))
            query = f'''
            SELECT day_of_week, start_time, end_time
            FROM module_schedule
            WHERE module_code IN ({placeholders})
            ORDER BY day_of_week, start_time
            '''
            cursor.execute(query, modules)

        elif entity_type == 'instructor':
            query = '''
            SELECT day_of_week, start_time, end_time
            FROM module_schedule
            WHERE instructor_id = ?
            ORDER BY day_of_week, start_time
            '''
            cursor.execute(query, (entity_id,))

        schedules = cursor.fetchall()
        conn.close()

        # Find gaps
        gaps = {}
        for day in DAYS_OF_WEEK:
            day_schedules = [s for s in schedules if s[0] == day]
            gaps[day] = self._find_daily_gaps(day_schedules)

        return gaps

    def _find_daily_gaps(self, day_schedules):
        """Find gaps in a single day's schedule"""
        if not day_schedules:
            return [{'start': '09:00', 'end': '17:00', 'duration': 480}]

        # Sort by start time
        day_schedules.sort(key=lambda x: x[1])

        gaps = []

        # Gap before first class
        first_start = day_schedules[0][1]
        if first_start > '09:00':
            duration = self._calculate_duration('09:00', first_start)
            gaps.append({'start': '09:00', 'end': first_start, 'duration': duration})

        # Gaps between classes
        for i in range(len(day_schedules) - 1):
            current_end = day_schedules[i][2]
            next_start = day_schedules[i + 1][1]

            if current_end < next_start:
                duration = self._calculate_duration(current_end, next_start)
                if duration >= 30:  # Only count gaps of 30+ minutes
                    gaps.append({'start': current_end, 'end': next_start, 'duration': duration})

        # Gap after last class
        last_end = day_schedules[-1][2]
        if last_end < '17:00':
            duration = self._calculate_duration(last_end, '17:00')
            gaps.append({'start': last_end, 'end': '17:00', 'duration': duration})

        return gaps
