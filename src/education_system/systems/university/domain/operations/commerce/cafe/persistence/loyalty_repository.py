from education_system.systems.university.domain.operations.commerce.cafe import *  # noqa: F401,F403
from .schema import get_db_connection

def get_or_create_loyalty_account(student_id: str, customer_name: str) -> Optional[Tuple]:
    """Get or create a loyalty account. Returns (loyalty_id, student_id, customer_name, points)."""
    try:
        conn = get_db_connection()
        if not conn:
            return None
        cursor = conn.cursor()
        cursor.execute("SELECT loyalty_id, student_id, customer_name, points FROM cafe_loyalty WHERE student_id = ?", (student_id,))
        result = cursor.fetchone()
        if result:
            conn.close()
            return result
        # Create new account
        cursor.execute(
            "INSERT INTO cafe_loyalty (student_id, customer_name, points) VALUES (?, ?, 0)",
            (student_id, customer_name)
        )
        conn.commit()
        loyalty_id = cursor.lastrowid
        conn.close()
        return (loyalty_id, student_id, customer_name, 0)
    except sqlite3.Error as e:
        logger.error(f"Error with loyalty account: {e}")
        return None

def get_loyalty_account(student_id: str) -> Optional[Tuple]:
    """Get loyalty account by student ID."""
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()
    cursor.execute("SELECT loyalty_id, student_id, customer_name, points FROM cafe_loyalty WHERE student_id = ?", (student_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def get_all_loyalty_accounts() -> List[Tuple]:
    """Get all loyalty accounts."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor()
    cursor.execute("SELECT loyalty_id, student_id, customer_name, points FROM cafe_loyalty ORDER BY points DESC")
    results = cursor.fetchall()
    conn.close()
    return results

def add_loyalty_points(student_id: str, points: int, reason: str = "") -> bool:
    """Add loyalty points to an account."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        cursor.execute("UPDATE cafe_loyalty SET points = points + ? WHERE student_id = ?", (points, student_id))
        cursor.execute(
            "INSERT INTO cafe_loyalty_log (student_id, points_change, transaction_type, reason) VALUES (?, ?, 'added', ?)",
            (student_id, points, reason or 'Manual addition')
        )
        conn.commit()
        conn.close()
        if ACTIVITY_LOGGER_AVAILABLE:
            log_activity('loyalty', 'cafe_loyalty_add', student_id=student_id, points=points)
        return True
    except sqlite3.Error as e:
        logger.error(f"Error adding loyalty points: {e}")
        return False

def redeem_loyalty_points(student_id: str, points: int, reason: str = "") -> bool:
    """Redeem loyalty points from an account."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        # Check sufficient points
        cursor.execute("SELECT points FROM cafe_loyalty WHERE student_id = ?", (student_id,))
        row = cursor.fetchone()
        if not row or row[0] < points:
            conn.close()
            return False
        cursor.execute("UPDATE cafe_loyalty SET points = points - ? WHERE student_id = ?", (points, student_id))
        cursor.execute(
            "INSERT INTO cafe_loyalty_log (student_id, points_change, transaction_type, reason) VALUES (?, ?, 'redeemed', ?)",
            (student_id, -points, reason or 'Manual redemption')
        )
        conn.commit()
        conn.close()
        if ACTIVITY_LOGGER_AVAILABLE:
            log_activity('loyalty', 'cafe_loyalty_redeem', student_id=student_id, points=points)
        return True
    except sqlite3.Error as e:
        logger.error(f"Error redeeming loyalty points: {e}")
        return False

def get_loyalty_log(student_id: str, limit: int = 50) -> List[Tuple]:
    """Get loyalty points transaction log for a student."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor()
    cursor.execute(
        "SELECT log_id, points_change, transaction_type, reason, created_at FROM cafe_loyalty_log WHERE student_id = ? ORDER BY created_at DESC LIMIT ?",
        (student_id, limit)
    )
    results = cursor.fetchall()
    conn.close()
    return results
