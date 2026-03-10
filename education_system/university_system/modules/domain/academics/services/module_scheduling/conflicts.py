from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
import json


class ConflictsMixin:
    def display_student_conflicts(self, student_id):
        """Display scheduling conflicts for a student"""
        conflicts = self.check_student_conflicts(student_id)

        if not conflicts:
            print(f"No scheduling conflicts found for student {student_id}.")
            return

        print(f"\nScheduling Conflicts for Student {student_id}:")
        print("="*100)

        for i, conflict in enumerate(conflicts, 1):
            module1 = conflict['module1']
            module2 = conflict['module2']

            print(f"Conflict #{i}:")
            print(f"Module 1: {module1['code']} - {module1['name']}")
            print(f"          {module1['day']} {module1['time']} in {module1['room']}")
            print(f"Module 2: {module2['code']} - {module2['name']}")
            print(f"          {module2['day']} {module2['time']} in {module2['room']}")
            print("-"*100)

        print("="*100)

    def check_student_conflicts(self, student_id):
        """Check for scheduling conflicts in a student's timetable"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        # Check if student exists
        cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
        student = cursor.fetchone()

        if not student:
            print(f"Student ID {student_id} does not exist.")
            conn.close()
            return []

        # Get modules the student is enrolled in
        cursor.execute('''
        SELECT module_code FROM student_modules WHERE student_id = ?
        ''', (student_id,))

        enrolled_modules = [row[0] for row in cursor.fetchall()]

        if not enrolled_modules:
            print(f"Student {student_id} is not enrolled in any modules.")
            conn.close()
            return []

        # Get schedule for the enrolled modules
        placeholders = ','.join(['?'] * len(enrolled_modules))
        query = f'''
        SELECT ms.id, ms.module_code, m.module_name, ms.day_of_week, ms.start_time, ms.end_time,
               r.building, r.room_number
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        LEFT JOIN modules m ON ms.module_code = m.module_code
        WHERE ms.module_code IN ({placeholders})
        ORDER BY ms.day_of_week, ms.start_time
        '''

        cursor.execute(query, enrolled_modules)
        schedules = cursor.fetchall()

        # Check for conflicts
        conflicts = []

        for i, schedule1 in enumerate(schedules):
            id1, code1, name1, day1, start1, end1, building1, room1 = schedule1
            room1_str = f"{building1}-{room1}" if building1 and room1 else "TBA"

            for j, schedule2 in enumerate(schedules):
                if i >= j:  # Skip comparing the same schedule or already compared pairs
                    continue

                id2, code2, name2, day2, start2, end2, building2, room2 = schedule2
                room2_str = f"{building2}-{room2}" if building2 and room2 else "TBA"

                # Check if days match and times overlap
                if day1 == day2 and (
                    (start1 <= start2 < end1) or
                    (start1 < end2 <= end1) or
                    (start2 <= start1 < end2) or
                    (start2 < end1 <= end2)
                ):
                    conflicts.append({
                        'module1': {
                            'code': code1,
                            'name': name1,
                            'day': day1,
                            'time': f"{start1}-{end1}",
                            'room': room1_str
                        },
                        'module2': {
                            'code': code2,
                            'name': name2,
                            'day': day2,
                            'time': f"{start2}-{end2}",
                            'room': room2_str
                        }
                    })

        conn.close()
        return conflicts

    def _check_student_conflicts(self, student_id, day_of_week, start_time, end_time, except_module=None):
        """Check if a student has conflicting classes for the given time slot"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        # Get modules the student is enrolled in
        cursor.execute('''
        SELECT module_code FROM student_modules WHERE student_id = ?
        ''', (student_id,))

        enrolled_modules = [row[0] for row in cursor.fetchall()]

        if not enrolled_modules:
            conn.close()
            return []

        # Build query to check for conflicts
        query = '''
        SELECT ms.id, ms.module_code, ms.start_time, ms.end_time
        FROM module_schedule ms
        WHERE ms.module_code IN ({}) AND ms.day_of_week = ? AND
        ((ms.start_time < ? AND ms.end_time > ?) OR
        (ms.start_time < ? AND ms.end_time > ?) OR
        (ms.start_time >= ? AND ms.end_time <= ?))
        '''.format(','.join(['?'] * len(enrolled_modules)))

        params = enrolled_modules + [day_of_week, end_time, start_time,
                                    end_time, start_time, start_time, end_time]

        # Exclude a specific module if needed (for updates)
        if except_module:
            query += " AND ms.module_code != ?"
            params.append(except_module)

        cursor.execute(query, params)
        conflicts = cursor.fetchall()
        conn.close()

        return conflicts

    def _check_room_conflicts(self, room_id, day_of_week, start_time, end_time):
        """Check if a room is already scheduled for the given time slot"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        cursor.execute('''
        SELECT id, module_code, start_time, end_time
        FROM module_schedule
        WHERE room_id = ? AND day_of_week = ? AND
        ((start_time < ? AND end_time > ?) OR
        (start_time < ? AND end_time > ?) OR
        (start_time >= ? AND end_time <= ?))
        ''', (room_id, day_of_week, end_time, start_time,
              end_time, start_time, start_time, end_time))

        conflicts = cursor.fetchall()
        conn.close()

        return conflicts

    def _check_instructor_conflicts(self, instructor_id, day_of_week, start_time, end_time):
        """Check if an instructor is already scheduled for the given time slot"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        cursor.execute('''
        SELECT id, module_code, start_time, end_time
        FROM module_schedule
        WHERE instructor_id = ? AND day_of_week = ? AND
        ((start_time < ? AND end_time > ?) OR
        (start_time < ? AND end_time > ?) OR
        (start_time >= ? AND end_time <= ?))
        ''', (instructor_id, day_of_week, end_time, start_time,
              end_time, start_time, start_time, end_time))

        conflicts = cursor.fetchall()
        conn.close()

        return conflicts

    def detect_all_conflicts(self):
        """Detect all types of scheduling conflicts"""
        conflicts = []

        # Room conflicts
        room_conflicts = self._detect_room_conflicts()
        conflicts.extend(room_conflicts)

        # Instructor conflicts
        instructor_conflicts = self._detect_instructor_conflicts()
        conflicts.extend(instructor_conflicts)

        # Student conflicts
        student_conflicts = self._detect_student_conflicts()
        conflicts.extend(student_conflicts)

        # Save conflicts to database
        self._save_conflicts_to_db(conflicts)

        return conflicts

    def _detect_room_conflicts(self):
        """Detect room scheduling conflicts"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        cursor.execute('''
        SELECT ms1.id, ms1.module_code, ms1.day_of_week, ms1.start_time, ms1.end_time,
               ms2.id, ms2.module_code, ms2.day_of_week, ms2.start_time, ms2.end_time,
               r.building, r.room_number
        FROM module_schedule ms1
        JOIN module_schedule ms2 ON ms1.room_id = ms2.room_id AND ms1.id < ms2.id
        JOIN rooms r ON ms1.room_id = r.id
        WHERE ms1.day_of_week = ms2.day_of_week
        AND ((ms1.start_time < ms2.end_time AND ms1.end_time > ms2.start_time))
        ''')

        conflicts = []
        for row in cursor.fetchall():
            conflicts.append({
                'type': 'room_conflict',
                'description': f"Room {row[10]}-{row[11]} double-booked on {row[2]} between {row[8]} modules {row[1]} and {row[6]}",
                'affected_schedules': [row[0], row[5]],
                'severity': 'high'
            })

        conn.close()
        return conflicts

    def _detect_instructor_conflicts(self):
        """Detect instructor scheduling conflicts"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        cursor.execute('''
        SELECT ms1.id, ms1.module_code, ms1.day_of_week, ms1.start_time, ms1.end_time,
               ms2.id, ms2.module_code, ms2.day_of_week, ms2.start_time, ms2.end_time,
               i.first_name, i.last_name
        FROM module_schedule ms1
        JOIN module_schedule ms2 ON ms1.instructor_id = ms2.instructor_id AND ms1.id < ms2.id
        JOIN instructors i ON ms1.instructor_id = i.id
        WHERE ms1.day_of_week = ms2.day_of_week
        AND ((ms1.start_time < ms2.end_time AND ms1.end_time > ms2.start_time))
        ''')

        conflicts = []
        for row in cursor.fetchall():
            conflicts.append({
                'type': 'instructor_conflict',
                'description': f"Instructor {row[10]} {row[11]} double-booked on {row[2]} between modules {row[1]} and {row[6]}",
                'affected_schedules': [row[0], row[5]],
                'severity': 'high'
            })

        conn.close()
        return conflicts

    def _detect_student_conflicts(self):
        """Detect student scheduling conflicts"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        # Get all students and their enrolled modules
        cursor.execute('SELECT DISTINCT student_id FROM student_modules')
        students = [row[0] for row in cursor.fetchall()]

        conflicts = []
        for student_id in students:
            student_conflicts = self.check_student_conflicts(student_id)
            for conflict in student_conflicts:
                conflicts.append({
                    'type': 'student_conflict',
                    'description': f"Student {student_id} has overlapping classes: {conflict['module1']['code']} and {conflict['module2']['code']} on {conflict['module1']['day']}",
                    'affected_schedules': [],  # Would need schedule IDs
                    'severity': 'medium',
                    'student_id': student_id
                })

        conn.close()
        return conflicts

    def _save_conflicts_to_db(self, conflicts):
        """Save detected conflicts to database"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        # Clear existing unresolved conflicts
        cursor.execute('DELETE FROM schedule_conflicts WHERE resolved = 0')

        for conflict in conflicts:
            cursor.execute('''
            INSERT INTO schedule_conflicts
            (conflict_type, description, affected_schedules, resolved)
            VALUES (?, ?, ?, 0)
            ''', (conflict['type'], conflict['description'],
                  json.dumps(conflict['affected_schedules'])))

        conn.commit()
        conn.close()

    def resolve_conflict(self, conflict_id, resolution_notes=""):
        """Mark a conflict as resolved"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        cursor.execute('''
        UPDATE schedule_conflicts
        SET resolved = 1, resolution_notes = ?, resolved_date = CURRENT_TIMESTAMP
        WHERE id = ?
        ''', (resolution_notes, conflict_id))

        conn.commit()
        conn.close()

        print(f"Conflict {conflict_id} marked as resolved.")

    def _get_all_conflicts(self):
        """Get all conflicts from database"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        cursor.execute('''
        SELECT id, conflict_type, description, resolved, detected_date, resolution_notes
        FROM schedule_conflicts
        ORDER BY detected_date DESC
        ''')

        conflicts = []
        for row in cursor.fetchall():
            conflicts.append({
                'id': row[0],
                'type': row[1],
                'description': row[2],
                'resolved': bool(row[3]),
                'detected_date': row[4],
                'resolution_notes': row[5]
            })

        conn.close()
        return conflicts
