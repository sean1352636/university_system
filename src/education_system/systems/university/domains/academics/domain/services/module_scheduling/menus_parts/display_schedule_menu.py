"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def display_schedule_menu(scheduler):
    """Display the schedule management menu"""
    while True:
        print("\nModule Schedule Management Menu:")
        print("===============================")
        print("1. Add New Module Schedule")
        print("2. Update Existing Schedule")
        print("3. Delete Schedule")
        print("4. Return to Previous Menu")

        choice = input("\nEnter your choice (1-4): ")

        if choice == '1':
            # Display all modules
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT module_code, module_name FROM modules
            ORDER BY module_code
            ''')

            modules = cursor.fetchall()

            if not modules:
                known_modules = scheduler._get_known_modules()
                if not known_modules:
                    print("No modules found in the system.")
                    conn.close()
                    continue

                print("\nModules:")
                print("=" * 60)
                print(f"{'Code':<10} {'Name':<50}")
                print("-" * 60)

                for code, name in known_modules.items():
                    print(f"{code:<10} {name:<50}")
            else:
                print("\nModules:")
                print("=" * 60)
                print(f"{'Code':<10} {'Name':<50}")
                print("-" * 60)

                for module in modules:
                    code, name = module
                    print(f"{code:<10} {name:<50}")

            print("=" * 60)

            # Get module code
            while True:
                module_code = input("Enter module code: ")
                if module_code:
                    break
                print("Module code cannot be empty.")

            # Display days of week
            print("\nDays of Week:")
            for i, day in enumerate(DAYS_OF_WEEK, 1):
                print(f"{i}. {day}")

            while True:
                day_choice = input("Enter day of week (1-5): ")
                try:
                    day_index = int(day_choice) - 1
                    if 0 <= day_index < len(DAYS_OF_WEEK):
                        day_of_week = DAYS_OF_WEEK[day_index]
                        break
                    else:
                        print(f"Invalid choice. Must be between 1 and {len(DAYS_OF_WEEK)}.")
                except ValueError:
                    print("Invalid choice. Please enter a number.")

            while True:
                start_time = input("Enter start time (HH:MM, 24-hour format): ")
                end_time = input("Enter end time (HH:MM, 24-hour format): ")

                try:
                    datetime.strptime(start_time, "%H:%M")
                    datetime.strptime(end_time, "%H:%M")

                    if start_time >= end_time:
                        print("Start time must be before end time.")
                        continue

                    break
                except ValueError:
                    print("Invalid time format. Use HH:MM format (24-hour).")

            # Display rooms
            cursor.execute('''
            SELECT id, room_number, building, capacity, room_type FROM rooms
            ORDER BY building, room_number
            ''')

            rooms = cursor.fetchall()

            if not rooms:
                print("No rooms found. Please add a room first.")
                conn.close()
                continue

            print("\nRooms:")
            print("=" * 80)
            print(f"{'ID':<5} {'Building':<20} {'Room':<10} {'Capacity':<10} {'Type':<20}")
            print("-" * 80)

            for room in rooms:
                room_id, room_number, building, capacity, room_type = room
                print(f"{room_id:<5} {building:<20} {room_number:<10} {capacity:<10} {room_type:<20}")

            print("=" * 80)

            while True:
                try:
                    room_id = int(input("Enter room ID: "))
                    cursor.execute('SELECT id FROM rooms WHERE id = ?', (room_id,))
                    if cursor.fetchone():
                        break
                    else:
                        print(f"Room ID {room_id} does not exist.")
                except ValueError:
                    print("Invalid room ID. Please enter a number.")

            # Display instructors
            cursor.execute('''
            SELECT id, first_name, last_name, department FROM instructors
            ORDER BY last_name, first_name
            ''')

            instructors = cursor.fetchall()

            if not instructors:
                print("No instructors found. Please add an instructor first.")
                conn.close()
                continue

            print("\nInstructors:")
            print("=" * 80)
            print(f"{'ID':<5} {'Name':<30} {'Department':<30}")
            print("-" * 80)

            for instructor in instructors:
                instructor_id, first_name, last_name, department = instructor
                full_name = f"{first_name} {last_name}"
                print(f"{instructor_id:<5} {full_name:<30} {department:<30}")

            print("=" * 80)

            while True:
                try:
                    instructor_id = int(input("Enter instructor ID: "))
                    cursor.execute('SELECT id FROM instructors WHERE id = ?', (instructor_id,))
                    if cursor.fetchone():
                        break
                    else:
                        print(f"Instructor ID {instructor_id} does not exist.")
                except ValueError:
                    print("Invalid instructor ID. Please enter a number.")

            # Display session types
            print("\nSession Types:")
            for i, session_type in enumerate(SESSION_TYPES, 1):
                print(f"{i}. {session_type}")

            while True:
                session_choice = input(f"Enter session type (1-{len(SESSION_TYPES)}): ")
                try:
                    session_index = int(session_choice) - 1
                    if 0 <= session_index < len(SESSION_TYPES):
                        session_type = SESSION_TYPES[session_index]
                        break
                    else:
                        print(f"Invalid choice. Must be between 1 and {len(SESSION_TYPES)}.")
                except ValueError:
                    print("Invalid choice. Please enter a number.")

            conn.close()

            scheduler.add_module_schedule(
                module_code, day_of_week, start_time, end_time,
                room_id, instructor_id, session_type
            )

        elif choice == '2':
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT ms.id, ms.module_code, m.module_name, ms.day_of_week, ms.start_time, ms.end_time,
                   r.building, r.room_number, i.first_name, i.last_name, ms.session_type
            FROM module_schedule ms
            LEFT JOIN rooms r ON ms.room_id = r.id
            LEFT JOIN instructors i ON ms.instructor_id = i.id
            LEFT JOIN modules m ON ms.module_code = m.module_code
            ORDER BY ms.module_code, ms.day_of_week, ms.start_time
            ''')

            schedules = cursor.fetchall()

            if not schedules:
                print("No schedules found.")
                conn.close()
                continue

            print("\nAll Module Schedules:")
            print("=" * 120)
            print(f"{'ID':<5} {'Module':<10} {'Name':<25} {'Day':<10} {'Time':<15} {'Room':<15} {'Instructor':<20} {'Type':<10}")
            print("-" * 120)

            for schedule in schedules:
                id, code, name, day, start, end, building, room, first_name, last_name, session_type = schedule
                name = name or "Unknown"
                time_slot = f"{start}-{end}"
                room_str = f"{building}-{room}" if building and room else "TBA"
                instructor = f"{first_name} {last_name}" if first_name and last_name else "TBA"

                print(f"{id:<5} {code:<10} {name[:23]:<25} {day:<10} {time_slot:<15} "
                      f"{room_str:<15} {instructor[:18]:<20} {session_type:<10}")

            print("=" * 120)

            while True:
                try:
                    schedule_id = int(input("Enter schedule ID to update: "))
                    cursor.execute('SELECT id FROM module_schedule WHERE id = ?', (schedule_id,))
                    if cursor.fetchone():
                        break
                    else:
                        print(f"Schedule ID {schedule_id} does not exist.")
                except ValueError:
                    print("Invalid schedule ID. Please enter a number.")

            print("\nWhat would you like to update?")
            print("1. Day of Week")
            print("2. Time")
            print("3. Room")
            print("4. Instructor")
            print("5. Session Type")

            update_choice = input("Enter your choice (1-5): ")

            if update_choice == '1':
                print("\nDays of Week:")
                for i, day in enumerate(DAYS_OF_WEEK, 1):
                    print(f"{i}. {day}")

                while True:
                    day_choice = input("Enter new day of week (1-5): ")
                    try:
                        day_index = int(day_choice) - 1
                        if 0 <= day_index < len(DAYS_OF_WEEK):
                            day_of_week = DAYS_OF_WEEK[day_index]
                            break
                        else:
                            print(f"Invalid choice. Must be between 1 and {len(DAYS_OF_WEEK)}.")
                    except ValueError:
                        print("Invalid choice. Please enter a number.")

                scheduler.update_module_schedule(schedule_id, day_of_week=day_of_week)

            elif update_choice == '2':
                while True:
                    start_time = input("Enter new start time (HH:MM, 24-hour format): ")
                    end_time = input("Enter new end time (HH:MM, 24-hour format): ")

                    try:
                        datetime.strptime(start_time, "%H:%M")
                        datetime.strptime(end_time, "%H:%M")

                        if start_time >= end_time:
                            print("Start time must be before end time.")
                            continue

                        break
                    except ValueError:
                        print("Invalid time format. Use HH:MM format (24-hour).")

                scheduler.update_module_schedule(schedule_id, start_time=start_time, end_time=end_time)

            elif update_choice == '3':
                cursor.execute('''
                SELECT id, room_number, building, capacity, room_type FROM rooms
                ORDER BY building, room_number
                ''')

                rooms = cursor.fetchall()

                if not rooms:
                    print("No rooms found.")
                    conn.close()
                    continue

                print("\nRooms:")
                print("=" * 80)
                print(f"{'ID':<5} {'Building':<20} {'Room':<10} {'Capacity':<10} {'Type':<20}")
                print("-" * 80)

                for room in rooms:
                    room_id, room_number, building, capacity, room_type = room
                    print(f"{room_id:<5} {building:<20} {room_number:<10} {capacity:<10} {room_type:<20}")

                print("=" * 80)

                while True:
                    try:
                        room_id = int(input("Enter new room ID: "))
                        cursor.execute('SELECT id FROM rooms WHERE id = ?', (room_id,))
                        if cursor.fetchone():
                            break
                        else:
                            print(f"Room ID {room_id} does not exist.")
                    except ValueError:
                        print("Invalid room ID. Please enter a number.")

                scheduler.update_module_schedule(schedule_id, room_id=room_id)

            elif update_choice == '4':
                cursor.execute('''
                SELECT id, first_name, last_name, department FROM instructors
                ORDER BY last_name, first_name
                ''')

                instructors = cursor.fetchall()

                if not instructors:
                    print("No instructors found.")
                    conn.close()
                    continue

                print("\nInstructors:")
                print("=" * 80)
                print(f"{'ID':<5} {'Name':<30} {'Department':<30}")
                print("-" * 80)

                for instructor in instructors:
                    instructor_id, first_name, last_name, department = instructor
                    full_name = f"{first_name} {last_name}"
                    print(f"{instructor_id:<5} {full_name:<30} {department:<30}")

                print("=" * 80)

                while True:
                    try:
                        instructor_id = int(input("Enter new instructor ID: "))
                        cursor.execute('SELECT id FROM instructors WHERE id = ?', (instructor_id,))
                        if cursor.fetchone():
                            break
                        else:
                            print(f"Instructor ID {instructor_id} does not exist.")
                    except ValueError:
                        print("Invalid instructor ID. Please enter a number.")

                scheduler.update_module_schedule(schedule_id, instructor_id=instructor_id)

            elif update_choice == '5':
                print("\nSession Types:")
                for i, session_type in enumerate(SESSION_TYPES, 1):
                    print(f"{i}. {session_type}")

                while True:
                    session_choice = input(f"Enter new session type (1-{len(SESSION_TYPES)}): ")
                    try:
                        session_index = int(session_choice) - 1
                        if 0 <= session_index < len(SESSION_TYPES):
                            session_type = SESSION_TYPES[session_index]
                            break
                        else:
                            print(f"Invalid choice. Must be between 1 and {len(SESSION_TYPES)}.")
                    except ValueError:
                        print("Invalid choice. Please enter a number.")

                scheduler.update_module_schedule(schedule_id, session_type=session_type)

            else:
                print("Invalid choice.")

            conn.close()

        elif choice == '3':
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT ms.id, ms.module_code, m.module_name, ms.day_of_week, ms.start_time, ms.end_time,
                   r.building, r.room_number, i.first_name, i.last_name, ms.session_type
            FROM module_schedule ms
            LEFT JOIN rooms r ON ms.room_id = r.id
            LEFT JOIN instructors i ON ms.instructor_id = i.id
            LEFT JOIN modules m ON ms.module_code = m.module_code
            ORDER BY ms.module_code, ms.day_of_week, ms.start_time
            ''')

            schedules = cursor.fetchall()

            if not schedules:
                print("No schedules found.")
                conn.close()
                continue

            print("\nAll Module Schedules:")
            print("=" * 120)
            print(f"{'ID':<5} {'Module':<10} {'Name':<25} {'Day':<10} {'Time':<15} {'Room':<15} {'Instructor':<20} {'Type':<10}")
            print("-" * 120)

            for schedule in schedules:
                id, code, name, day, start, end, building, room, first_name, last_name, session_type = schedule
                name = name or "Unknown"
                time_slot = f"{start}-{end}"
                room_str = f"{building}-{room}" if building and room else "TBA"
                instructor = f"{first_name} {last_name}" if first_name and last_name else "TBA"

                print(f"{id:<5} {code:<10} {name[:23]:<25} {day:<10} {time_slot:<15} "
                      f"{room_str:<15} {instructor[:18]:<20} {session_type:<10}")

            print("=" * 120)

            while True:
                try:
                    schedule_id = int(input("Enter schedule ID to delete: "))
                    cursor.execute('SELECT id FROM module_schedule WHERE id = ?', (schedule_id,))
                    if cursor.fetchone():
                        break
                    else:
                        print(f"Schedule ID {schedule_id} does not exist.")
                except ValueError:
                    print("Invalid schedule ID. Please enter a number.")

            conn.close()

            scheduler.delete_module_schedule(schedule_id)

        elif choice == '4':
            break
        else:
            print("Invalid choice. Please try again.")
