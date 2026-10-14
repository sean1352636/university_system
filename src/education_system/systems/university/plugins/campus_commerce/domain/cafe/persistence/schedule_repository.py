from education_system.systems.university.plugins.campus_commerce.domain.cafe import *  # noqa: F401,F403
from .schema import get_db_connection

def add_staff_schedule(staff_name: str, position: str, day_of_week: str, start_time: str, end_time: str, notes: str = "") -> bool:
    """Add a staff schedule entry."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO cafe_staff_schedules (staff_name, position, day_of_week, start_time, end_time, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (staff_name, position, day_of_week, start_time, end_time, notes or None)
        )
        conn.commit()
        conn.close()
        if ACTIVITY_LOGGER_AVAILABLE:
            log_create('cafe_staff_schedule', staff_name=staff_name, day=day_of_week)
        return True
    except sqlite3.Error as e:
        logger.error(f"Error adding staff schedule: {e}")
        return False

def get_all_staff_schedules() -> List[Tuple]:
    """Get all staff schedules."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor()
    cursor.execute('''
        SELECT schedule_id, staff_name, position, day_of_week, start_time, end_time, notes
        FROM cafe_staff_schedules
        ORDER BY
            CASE day_of_week
                WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6
                WHEN 'Sunday' THEN 7 ELSE 8
            END,
            start_time
    ''')
    results = cursor.fetchall()
    conn.close()
    return results

def get_staff_schedule_by_name(staff_name: str) -> List[Tuple]:
    """Get schedules for a specific staff member."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor()
    cursor.execute(
        "SELECT schedule_id, staff_name, position, day_of_week, start_time, end_time, notes FROM cafe_staff_schedules WHERE LOWER(staff_name) LIKE ? ORDER BY CASE day_of_week WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6 WHEN 'Sunday' THEN 7 ELSE 8 END",
        (f"%{staff_name.lower()}%",)
    )
    results = cursor.fetchall()
    conn.close()
    return results

def update_staff_schedule_entry(schedule_id: int, day_of_week: str, start_time: str, end_time: str, notes: str) -> bool:
    """Update a staff schedule entry."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE cafe_staff_schedules SET day_of_week = ?, start_time = ?, end_time = ?, notes = ? WHERE schedule_id = ?",
            (day_of_week, start_time, end_time, notes, schedule_id)
        )
        conn.commit()
        conn.close()
        if ACTIVITY_LOGGER_AVAILABLE:
            log_update('cafe_staff_schedule', schedule_id=schedule_id)
        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating staff schedule: {e}")
        return False

def delete_staff_schedule_entry(schedule_id: int) -> bool:
    """Delete a staff schedule entry."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cafe_staff_schedules WHERE schedule_id = ?", (schedule_id,))
        conn.commit()
        conn.close()
        if ACTIVITY_LOGGER_AVAILABLE:
            log_delete('cafe_staff_schedule', schedule_id=schedule_id)
        return True
    except sqlite3.Error as e:
        logger.error(f"Error deleting staff schedule: {e}")
        return False

def get_unique_staff_names() -> List[str]:
    """Get unique staff names from schedules."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT staff_name FROM cafe_staff_schedules ORDER BY staff_name")
    results = [row[0] for row in cursor.fetchall()]
    conn.close()
    return results
