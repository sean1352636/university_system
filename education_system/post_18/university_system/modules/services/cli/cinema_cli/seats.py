"""Cinema CLI seat selection and management functions."""

import logging
from typing import List, Dict

from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction

logger = logging.getLogger(__name__)


def initialize_seats_for_screening(screening_id: int, conn):
    """Initialize seat map for a screening if not exists"""
    try:
        # Check if seats already exist
        cursor = conn.execute('''
            SELECT COUNT(*) FROM cinema_seats WHERE screening_id = ?
        ''', (screening_id,))

        if cursor.fetchone()[0] > 0:
            return True  # Seats already initialized

        # Create seat map (10 rows x 10 seats = 100 seats)
        rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']
        seats_per_row = 10

        for row in rows:
            for seat_num in range(1, seats_per_row + 1):
                seat_type = 'premium' if row in ['E', 'F'] else 'standard'
                conn.execute('''
                    INSERT INTO cinema_seats (screening_id, row_letter, seat_number, seat_type, status)
                    VALUES (?, ?, ?, ?, 'available')
                ''', (screening_id, row, seat_num, seat_type))

        return True
    except Exception as e:
        logger.error(f"Error initializing seats: {e}")
        return False


def display_seat_map(screening_id: int) -> List[Dict]:
    """Display visual seat map and return seat data"""
    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT row_letter, seat_number, status, seat_type
                FROM cinema_seats
                WHERE screening_id = ?
                ORDER BY row_letter, seat_number
            ''', (screening_id,))
            seats = cursor.fetchall()

            if not seats:
                return []

            print("\n🎬 SCREEN")
            print("=" * 42)
            print("\n   1  2  3  4  5  6  7  8  9  10")

            current_row = None
            seat_data = []

            for seat in seats:
                row, num, status, seat_type = seat
                seat_data.append({
                    'row': row,
                    'number': num,
                    'status': status,
                    'type': seat_type
                })

                if row != current_row:
                    if current_row is not None:
                        print()
                    current_row = row
                    print(f"{row} ", end='')

                # Display seat status
                if status == 'available':
                    if seat_type == 'premium':
                        print(" ♦️ ", end='')
                    else:
                        print(" ⬜", end='')
                else:
                    print(" ⬛", end='')

            print("\n\n⬜ Available  ⬛ Taken  ♦️  Premium")
            print("=" * 42)

            return seat_data

    except Exception as e:
        logger.error(f"Error displaying seat map: {e}")
        return []


def select_seats(screening_id: int, num_tickets: int) -> List[str]:
    """Interactive seat selection"""
    try:
        with transaction() as conn:
            # Initialize seats if needed
            initialize_seats_for_screening(screening_id, conn)

        selected_seats = []

        while len(selected_seats) < num_tickets:
            seats_data = display_seat_map(screening_id)

            if not seats_data:
                print("❌ Error loading seat map")
                return []

            remaining = num_tickets - len(selected_seats)
            print(f"\n🎟️  Select {remaining} more seat(s)")

            if selected_seats:
                print(f"Selected: {', '.join(selected_seats)}")

            row = input("\nEnter row (A-J) or 'auto' for automatic selection: ").strip().upper()

            if row == 'AUTO':
                # Auto-select best available seats
                auto_seats = auto_select_seats(screening_id, num_tickets - len(selected_seats))
                if auto_seats:
                    selected_seats.extend(auto_seats)
                    print(f"✅ Auto-selected: {', '.join(auto_seats)}")
                    break
                else:
                    print("❌ Could not find enough consecutive seats")
                    continue

            if row not in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
                print("❌ Invalid row. Please enter A-J")
                continue

            seat_num = input("Enter seat number (1-10): ").strip()

            if not seat_num.isdigit() or int(seat_num) < 1 or int(seat_num) > 10:
                print("❌ Invalid seat number. Please enter 1-10")
                continue

            seat_id = f"{row}{seat_num}"

            # Check if seat is available
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT status FROM cinema_seats
                    WHERE screening_id = ? AND row_letter = ? AND seat_number = ?
                ''', (screening_id, row, int(seat_num)))
                result = cursor.fetchone()

                if not result:
                    print("❌ Seat not found")
                    continue

                if result[0] != 'available':
                    print("❌ Seat already taken")
                    continue

                if seat_id in selected_seats:
                    print("❌ Seat already selected")
                    continue

            selected_seats.append(seat_id)
            print(f"✅ Added seat {seat_id}")

        return selected_seats

    except Exception as e:
        logger.error(f"Error in seat selection: {e}")
        return []


def auto_select_seats(screening_id: int, num_seats: int) -> List[str]:
    """Automatically select best available consecutive seats"""
    try:
        with get_connection() as conn:
            # Try to find consecutive seats in middle rows first
            preferred_rows = ['E', 'F', 'D', 'G', 'C', 'H', 'B', 'I', 'A', 'J']

            for row in preferred_rows:
                cursor = conn.execute('''
                    SELECT seat_number FROM cinema_seats
                    WHERE screening_id = ? AND row_letter = ? AND status = 'available'
                    ORDER BY seat_number
                ''', (screening_id, row))
                available = [r[0] for r in cursor.fetchall()]

                # Find consecutive seats
                for i in range(len(available) - num_seats + 1):
                    consecutive = available[i:i+num_seats]
                    if len(consecutive) == num_seats and consecutive[-1] - consecutive[0] == num_seats - 1:
                        return [f"{row}{num}" for num in consecutive]

        # If no consecutive seats, just pick any available
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT row_letter, seat_number FROM cinema_seats
                WHERE screening_id = ? AND status = 'available'
                ORDER BY row_letter, seat_number
                LIMIT ?
            ''', (screening_id, num_seats))
            seats = cursor.fetchall()
            return [f"{row}{num}" for row, num in seats]

    except Exception as e:
        logger.error(f"Error auto-selecting seats: {e}")
        return []


def mark_seats_as_booked(screening_id: int, seats: List[str], booking_ref: str):
    """Mark selected seats as booked"""
    try:
        with transaction() as conn:
            for seat_id in seats:
                row = seat_id[0]
                num = int(seat_id[1:])
                conn.execute('''
                    UPDATE cinema_seats
                    SET status = 'booked', booking_ref = ?
                    WHERE screening_id = ? AND row_letter = ? AND seat_number = ?
                ''', (booking_ref, screening_id, row, num))
        return True
    except Exception as e:
        logger.error(f"Error marking seats as booked: {e}")
        return False
