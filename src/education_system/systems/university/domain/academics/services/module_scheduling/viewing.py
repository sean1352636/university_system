from education_system.systems.university.infrastructure.database.db import get_connection


class ViewingMixin:
    def view_module_schedule(self, module_code=None):
        """View the schedule for a specific module or all modules"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        if module_code:
            # Check if module exists
            cursor.execute('SELECT module_code FROM modules WHERE module_code = ?', (module_code,))
            if not cursor.fetchone():
                known_modules = self._get_known_modules()
                if module_code not in known_modules:
                    print(f"Module {module_code} does not exist.")
                    conn.close()
                    return

            query = '''
            SELECT ms.module_code, m.module_name, ms.day_of_week, ms.start_time, ms.end_time,
                   r.building, r.room_number,
                   i.first_name, i.last_name,
                   ms.session_type
            FROM module_schedule ms
            LEFT JOIN rooms r ON ms.room_id = r.id
            LEFT JOIN instructors i ON ms.instructor_id = i.id
            LEFT JOIN modules m ON ms.module_code = m.module_code
            WHERE ms.module_code = ?
            ORDER BY ms.day_of_week, ms.start_time
            '''
            cursor.execute(query, (module_code,))
        else:
            query = '''
            SELECT ms.module_code, m.module_name, ms.day_of_week, ms.start_time, ms.end_time,
                   r.building, r.room_number,
                   i.first_name, i.last_name,
                   ms.session_type
            FROM module_schedule ms
            LEFT JOIN rooms r ON ms.room_id = r.id
            LEFT JOIN instructors i ON ms.instructor_id = i.id
            LEFT JOIN modules m ON ms.module_code = m.module_code
            ORDER BY ms.day_of_week, ms.start_time
            '''
            cursor.execute(query)

        schedules = cursor.fetchall()
        conn.close()

        if not schedules:
            print("No schedules found.")
            return

        # Display schedules
        print("\n" + "="*100)
        print(f"{'Module':<10} {'Name':<30} {'Day':<10} {'Time':<15} {'Room':<15} {'Instructor':<20} {'Type':<10}")
        print("-"*100)

        for schedule in schedules:
            module_code, module_name, day, start, end, building, room, first_name, last_name, session_type = schedule
            module_name = module_name or "Unknown"  # Handle None values
            time_slot = f"{start}-{end}"
            room_str = f"{building}-{room}" if building and room else "TBA"
            instructor = f"{first_name} {last_name}" if first_name and last_name else "TBA"

            print(f"{module_code:<10} {module_name[:28]:<30} {day:<10} {time_slot:<15} {room_str:<15} {instructor:<20} {session_type:<10}")

        print("="*100)

    def view_room_schedule(self, room_id=None):
        """View the schedule for a specific room or all rooms"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        if room_id:
            # Check if room exists
            cursor.execute('SELECT id FROM rooms WHERE id = ?', (room_id,))
            if not cursor.fetchone():
                print(f"Room ID {room_id} does not exist.")
                conn.close()
                return

            # Get room details
            cursor.execute('SELECT room_number, building FROM rooms WHERE id = ?', (room_id,))
            room_info = cursor.fetchone()
            room_number, building = room_info

            print(f"\nSchedule for Room {building}-{room_number}:")
            print("="*100)

            query = '''
            SELECT ms.day_of_week, ms.start_time, ms.end_time,
                   ms.module_code, m.module_name,
                   i.first_name, i.last_name,
                   ms.session_type
            FROM module_schedule ms
            LEFT JOIN modules m ON ms.module_code = m.module_code
            LEFT JOIN instructors i ON ms.instructor_id = i.id
            WHERE ms.room_id = ?
            ORDER BY ms.day_of_week, ms.start_time
            '''
            cursor.execute(query, (room_id,))
        else:
            # List all rooms with schedules
            print("\nRoom Schedules:")
            print("="*100)

            query = '''
            SELECT r.id, r.building, r.room_number, r.capacity, r.room_type,
                   COUNT(ms.id) as schedule_count
            FROM rooms r
            LEFT JOIN module_schedule ms ON r.id = ms.room_id
            GROUP BY r.id
            ORDER BY r.building, r.room_number
            '''
            cursor.execute(query)

            rooms = cursor.fetchall()
            if not rooms:
                print("No rooms found.")
                conn.close()
                return

            print(f"{'ID':<5} {'Building':<15} {'Room':<10} {'Capacity':<10} {'Type':<15} {'# Classes':<10}")
            print("-"*100)

            for room in rooms:
                room_id, building, room_number, capacity, room_type, schedule_count = room
                print(f"{room_id:<5} {building:<15} {room_number:<10} {capacity:<10} {room_type:<15} {schedule_count:<10}")

            print("="*100)

            # Ask if user wants to view a specific room
            view_specific = input("\nView schedule for a specific room? (Enter room ID or 'n' to skip): ")
            if view_specific.lower() == 'n':
                conn.close()
                return

            try:
                room_id = int(view_specific)
                cursor.execute('SELECT room_number, building FROM rooms WHERE id = ?', (room_id,))
                room_info = cursor.fetchone()

                if not room_info:
                    print(f"Room ID {room_id} does not exist.")
                    conn.close()
                    return

                room_number, building = room_info
                print(f"\nSchedule for Room {building}-{room_number}:")
                print("="*100)

                query = '''
                SELECT ms.day_of_week, ms.start_time, ms.end_time,
                       ms.module_code, m.module_name,
                       i.first_name, i.last_name,
                       ms.session_type
                FROM module_schedule ms
                LEFT JOIN modules m ON ms.module_code = m.module_code
                LEFT JOIN instructors i ON ms.instructor_id = i.id
                WHERE ms.room_id = ?
                ORDER BY ms.day_of_week, ms.start_time
                '''
                cursor.execute(query, (room_id,))
            except ValueError:
                print("Invalid room ID.")
                conn.close()
                return

        # Display room schedule
        schedules = cursor.fetchall()

        if not schedules:
            print("No schedules found for this room.")
            conn.close()
            return

        print(f"{'Day':<10} {'Time':<15} {'Module':<10} {'Module Name':<30} {'Instructor':<20} {'Type':<10}")
        print("-"*100)

        for schedule in schedules:
            day, start, end, module_code, module_name, first_name, last_name, session_type = schedule
            module_name = module_name or "Unknown"  # Handle None values
            time_slot = f"{start}-{end}"
            instructor = f"{first_name} {last_name}" if first_name and last_name else "TBA"

            print(f"{day:<10} {time_slot:<15} {module_code:<10} {module_name[:28]:<30} {instructor:<20} {session_type:<10}")

        conn.close()
        print("="*100)

    def view_instructor_schedule(self, instructor_id=None):
        """View the schedule for a specific instructor or all instructors"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        if instructor_id:
            # Check if instructor exists
            cursor.execute('SELECT id FROM instructors WHERE id = ?', (instructor_id,))
            if not cursor.fetchone():
                print(f"Instructor ID {instructor_id} does not exist.")
                conn.close()
                return

            # Get instructor details
            cursor.execute('SELECT first_name, last_name FROM instructors WHERE id = ?', (instructor_id,))
            instructor_info = cursor.fetchone()
            first_name, last_name = instructor_info

            print(f"\nSchedule for {first_name} {last_name}:")
            print("="*100)

            query = '''
            SELECT ms.day_of_week, ms.start_time, ms.end_time,
                   ms.module_code, m.module_name,
                   r.building, r.room_number,
                   ms.session_type
            FROM module_schedule ms
            LEFT JOIN modules m ON ms.module_code = m.module_code
            LEFT JOIN rooms r ON ms.room_id = r.id
            WHERE ms.instructor_id = ?
            ORDER BY ms.day_of_week, ms.start_time
            '''
            cursor.execute(query, (instructor_id,))
        else:
            # List all instructors with schedules
            print("\nInstructor Schedules:")
            print("="*100)

            query = '''
            SELECT i.id, i.first_name, i.last_name, i.department,
                   COUNT(ms.id) as schedule_count
            FROM instructors i
            LEFT JOIN module_schedule ms ON i.id = ms.instructor_id
            GROUP BY i.id
            ORDER BY i.last_name, i.first_name
            '''
            cursor.execute(query)

            instructors = cursor.fetchall()
            if not instructors:
                print("No instructors found.")
                conn.close()
                return

            print(f"{'ID':<5} {'Name':<30} {'Department':<20} {'# Classes':<10}")
            print("-"*100)

            for instructor in instructors:
                instr_id, first_name, last_name, department, schedule_count = instructor
                full_name = f"{first_name} {last_name}"
                print(f"{instr_id:<5} {full_name:<30} {department:<20} {schedule_count:<10}")

            print("="*100)

            # Ask if user wants to view a specific instructor
            view_specific = input("\nView schedule for a specific instructor? (Enter instructor ID or 'n' to skip): ")
            if view_specific.lower() == 'n':
                conn.close()
                return

            try:
                instructor_id = int(view_specific)
                cursor.execute('SELECT first_name, last_name FROM instructors WHERE id = ?', (instructor_id,))
                instructor_info = cursor.fetchone()

                if not instructor_info:
                    print(f"Instructor ID {instructor_id} does not exist.")
                    conn.close()
                    return

                first_name, last_name = instructor_info
                print(f"\nSchedule for {first_name} {last_name}:")
                print("="*100)

                query = '''
                SELECT ms.day_of_week, ms.start_time, ms.end_time,
                       ms.module_code, m.module_name,
                       r.building, r.room_number,
                       ms.session_type
                FROM module_schedule ms
                LEFT JOIN modules m ON ms.module_code = m.module_code
                LEFT JOIN rooms r ON ms.room_id = r.id
                WHERE ms.instructor_id = ?
                ORDER BY ms.day_of_week, ms.start_time
                '''
                cursor.execute(query, (instructor_id,))
            except ValueError:
                print("Invalid instructor ID.")
                conn.close()
                return

        # Display instructor schedule
        schedules = cursor.fetchall()

        if not schedules:
            print("No schedules found for this instructor.")
            conn.close()
            return

        print(f"{'Day':<10} {'Time':<15} {'Module':<10} {'Module Name':<30} {'Room':<15} {'Type':<10}")
        print("-"*100)

        for schedule in schedules:
            day, start, end, module_code, module_name, building, room, session_type = schedule
            module_name = module_name or "Unknown"  # Handle None values
            time_slot = f"{start}-{end}"
            room_str = f"{building}-{room}" if building and room else "TBA"

            print(f"{day:<10} {time_slot:<15} {module_code:<10} {module_name[:28]:<30} {room_str:<15} {session_type:<10}")

        conn.close()
        print("="*100)
