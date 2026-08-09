"""Extracted function implementation."""

from .. import finance_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def process_scanned_barcode(barcode):
    """Process scanned barcode and return item info"""
    try:
        conn = get_db_connection()
        if not conn:
            return None

        cursor = conn.cursor()

        # Try to find book by barcode
        cursor.execute('''
        SELECT book_id, title, author, status, barcode
        FROM books
        WHERE barcode = ?
        ''', (barcode,))

        result = cursor.fetchone()
        if result:
            book_id, title, author, status, barcode_val = result
            conn.close()
            return {
                'type': 'book',
                'id': book_id,
                'title': title,
                'author': author,
                'status': status,
                'barcode': barcode_val
            }

        # Try to find user by barcode (if user barcode system exists)
        cursor.execute('''
        SELECT student_id, first_name, last_name
        FROM students
        WHERE student_id = ?
        ''', (barcode,))

        result = cursor.fetchone()
        conn.close()

        if result:
            student_id, first_name, last_name = result
            return {
                'type': 'user',
                'id': student_id,
                'name': f"{first_name} {last_name}",
                'barcode': barcode
            }

        return None

    except (sqlite3.Error, DatabaseError) as e:
        print(f"Error processing barcode: {e}")
        return None
