"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def display_room_menu(scheduler):
    """Display the room management menu"""
    while True:
        print("\nRoom Management Menu:")
        print("=====================")
        print("1. Add New Room")
        print("2. View All Rooms")
        print("3. Update Room Details")
        print("4. Deactivate Room")
        print("5. Return to Previous Menu")

        choice = input("\nEnter your choice (1-5): ")

        if choice == '1':
            room_number = input("Enter room number: ")
            building = input("Enter building name: ")

            try:
                capacity = int(input("Enter room capacity: "))
            except ValueError:
                print("Invalid capacity. Must be a number.")
                continue

            print(f"\nRoom Types: {', '.join(ROOM_TYPES)}")
            room_type = input("Enter room type: ")
            if room_type not in ROOM_TYPES:
                room_type = "Other"

            equipment = input("Enter equipment/facilities (optional): ")
            notes = input("Enter notes (optional): ")

            scheduler.add_room(room_number, building, capacity, room_type, equipment, notes)

        elif choice == '2':
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT id, room_number, building, capacity, room_type, equipment, is_active
            FROM rooms
            ORDER BY building, room_number
            ''')

            rooms = cursor.fetchall()
            conn.close()

            if not rooms:
                print("No rooms found.")
                continue

            print("\nAll Rooms:")
            print("=" * 100)
            print(f"{'ID':<5} {'Building':<15} {'Room':<10} {'Capacity':<10} {'Type':<15} {'Equipment':<20} {'Status':<8}")
            print("-" * 100)

            for room in rooms:
                room_id, room_number, building, capacity, room_type, equipment, is_active = room
                status = "Active" if is_active else "Inactive"
                equipment = equipment or "N/A"
                print(f"{room_id:<5} {building:<15} {room_number:<10} {capacity:<10} "
                      f"{room_type:<15} {equipment[:18]:<20} {status:<8}")

            print("=" * 100)

        elif choice == '3':
            # Update room details
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()

            try:
                room_id = int(input("Enter room ID to update: "))

                cursor.execute('SELECT * FROM rooms WHERE id = ?', (room_id,))
                room = cursor.fetchone()

                if not room:
                    print("Room not found.")
                    conn.close()
                    continue

                print(f"Current details: {room[2]}-{room[1]} (Capacity: {room[3]}, Type: {room[4]})")

                # Get new values
                new_capacity = input(f"New capacity (current: {room[3]}): ").strip()
                new_equipment = input(f"New equipment (current: {room[5] or 'N/A'}): ").strip()
                new_notes = input(f"New notes (current: {room[6] or 'N/A'}): ").strip()

                # Update only if values provided
                if new_capacity:
                    cursor.execute('UPDATE rooms SET capacity = ? WHERE id = ?', (int(new_capacity), room_id))
                if new_equipment:
                    cursor.execute('UPDATE rooms SET equipment = ? WHERE id = ?', (new_equipment, room_id))
                if new_notes:
                    cursor.execute('UPDATE rooms SET notes = ? WHERE id = ?', (new_notes, room_id))

                conn.commit()
                print("Room updated successfully.")

            except ValueError:
                print("Invalid room ID.")
            except Exception as e:
                print(f"Error updating room: {e}")
            finally:
                conn.close()

        elif choice == '4':
            # Deactivate room
            try:
                room_id = int(input("Enter room ID to deactivate: "))

                conn = get_connection(scheduler.db_path, row_factory=False)
                cursor = conn.cursor()

                cursor.execute('UPDATE rooms SET is_active = 0 WHERE id = ?', (room_id,))

                if cursor.rowcount > 0:
                    conn.commit()
                    print("Room deactivated successfully.")
                else:
                    print("Room not found.")

                conn.close()

            except ValueError:
                print("Invalid room ID.")
            except Exception as e:
                print(f"Error deactivating room: {e}")

        elif choice == '5':
            break
        else:
            print("Invalid choice. Please try again.")
