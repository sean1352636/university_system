from education_system.systems.university.domain.operations.commerce.cafe import *  # noqa: F401,F403
from .schema import get_db_connection

def create_reservation(customer_name: str, student_id: str, reservation_date: str, reservation_time: str, party_size: int, notes: str = "") -> Optional[int]:
    """Create a new reservation. Returns reservation_id or None."""
    try:
        conn = get_db_connection()
        if not conn:
            return None
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO cafe_reservations (customer_name, student_id, reservation_date, reservation_time, party_size, status, notes) VALUES (?, ?, ?, ?, ?, 'confirmed', ?)",
            (customer_name, student_id or None, reservation_date, reservation_time, party_size, notes or None)
        )
        conn.commit()
        reservation_id = cursor.lastrowid
        conn.close()
        if ACTIVITY_LOGGER_AVAILABLE:
            log_create('cafe_reservation', customer=customer_name, date=reservation_date)
        return reservation_id
    except sqlite3.Error as e:
        logger.error(f"Error creating reservation: {e}")
        return None

def get_all_reservations(filter_type: str = "all") -> List[Tuple]:
    """Get reservations with optional date filter."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor()

    date_filter = ""
    if filter_type == "today":
        date_filter = "AND reservation_date = DATE('now')"
    elif filter_type == "upcoming":
        date_filter = "AND reservation_date >= DATE('now')"
    elif filter_type == "past":
        date_filter = "AND reservation_date < DATE('now')"

    cursor.execute(f'''
        SELECT reservation_id, customer_name, student_id, reservation_date, reservation_time, party_size, status, notes
        FROM cafe_reservations
        WHERE 1=1 {date_filter}
        ORDER BY reservation_date DESC, reservation_time DESC
    ''')
    results = cursor.fetchall()
    conn.close()
    return results

def get_reservation(reservation_id: int) -> Optional[Tuple]:
    """Get a single reservation by ID."""
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()
    cursor.execute(
        "SELECT reservation_id, customer_name, student_id, reservation_date, reservation_time, party_size, status, notes FROM cafe_reservations WHERE reservation_id = ?",
        (reservation_id,)
    )
    result = cursor.fetchone()
    conn.close()
    return result

def update_reservation_details(reservation_id: int, customer_name: str, reservation_date: str, reservation_time: str, party_size: int, notes: str) -> bool:
    """Update a reservation."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE cafe_reservations SET customer_name = ?, reservation_date = ?, reservation_time = ?, party_size = ?, notes = ? WHERE reservation_id = ?",
            (customer_name, reservation_date, reservation_time, party_size, notes, reservation_id)
        )
        conn.commit()
        conn.close()
        if ACTIVITY_LOGGER_AVAILABLE:
            log_update('cafe_reservation', reservation_id=reservation_id)
        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating reservation: {e}")
        return False

def cancel_reservation(reservation_id: int) -> bool:
    """Cancel a reservation by setting status to cancelled."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE cafe_reservations SET status = 'cancelled' WHERE reservation_id = ?",
            (reservation_id,)
        )
        conn.commit()
        conn.close()
        if ACTIVITY_LOGGER_AVAILABLE:
            log_update('cafe_reservation', reservation_id=reservation_id, action='cancelled')
        return True
    except sqlite3.Error as e:
        logger.error(f"Error cancelling reservation: {e}")
        return False
