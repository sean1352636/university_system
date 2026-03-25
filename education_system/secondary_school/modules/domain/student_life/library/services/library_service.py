"""Library management service."""

import logging
from education_system.secondary_school.core.sql_safety import validate_identifier, escape_like
from datetime import datetime, timedelta
from education_system.secondary_school.core.exceptions import LibraryError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

CATEGORIES = ("fiction", "non-fiction", "textbook", "reference", "graphic_novel", "poetry", "drama", "other")


class LibraryService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # --- Books ---

    def add_book(self, title, author=None, isbn=None, category=None,
                 location=None, copies=1):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO library_books (title, author, isbn, category, location,
                   copies_total, copies_available) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (title, author, isbn, category, location, copies, copies))
            conn.commit()
            row = conn.execute("SELECT * FROM library_books WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise LibraryError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_books(self, category=None, search=None):
        conn = self._conn()
        try:
            sql = "SELECT * FROM library_books WHERE 1=1"
            params = []
            if category:
                sql += " AND category = ?"
                params.append(category)
            if search:
                sql += " AND (title LIKE ? OR author LIKE ? OR isbn LIKE ?)"
                escaped = escape_like(search)
                q = f"%{escaped}%"
                params.extend([q, q, q])
            sql += " ORDER BY title"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def update_book(self, book_id, **kwargs):
        conn = self._conn()
        try:
            allowed = {"title", "author", "isbn", "category", "location", "copies_total", "copies_available"}
            updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
            if not updates:
                return
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            conn.execute(f"UPDATE library_books SET {set_clause} WHERE id = ?",
                         list(updates.values()) + [book_id])
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise LibraryError(f"Failed: {e}") from e
        finally:
            conn.close()

    def delete_book(self, book_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM library_books WHERE id = ?", (book_id,))
            conn.commit()
        finally:
            conn.close()

    # --- Loans ---

    def issue_loan(self, book_id, student_id, loan_days=14):
        conn = self._conn()
        try:
            book = conn.execute("SELECT * FROM library_books WHERE id = ?", (book_id,)).fetchone()
            if not book:
                raise LibraryError("Book not found.")
            if book["copies_available"] < 1:
                raise LibraryError("No copies available.")
            due = (datetime.now() + timedelta(days=loan_days)).strftime("%Y-%m-%d")
            conn.execute(
                "INSERT INTO library_loans (book_id, student_id, due_date) VALUES (?, ?, ?)",
                (book_id, student_id, due))
            conn.execute(
                "UPDATE library_books SET copies_available = copies_available - 1 WHERE id = ?",
                (book_id,))
            conn.commit()
        except LibraryError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise LibraryError(f"Failed: {e}") from e
        finally:
            conn.close()

    def return_book(self, loan_id):
        conn = self._conn()
        try:
            loan = conn.execute("SELECT * FROM library_loans WHERE id = ?", (loan_id,)).fetchone()
            if not loan or loan["status"] == "returned":
                return
            conn.execute(
                "UPDATE library_loans SET status = 'returned', returned_at = datetime('now') WHERE id = ?",
                (loan_id,))
            conn.execute(
                "UPDATE library_books SET copies_available = copies_available + 1 WHERE id = ?",
                (loan["book_id"],))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise LibraryError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_loans(self, status=None, student_id=None):
        conn = self._conn()
        try:
            sql = """SELECT ll.*, lb.title as book_title, lb.author,
                     s.first_name, s.last_name, s.student_id as stu_code
                     FROM library_loans ll
                     JOIN library_books lb ON ll.book_id = lb.id
                     JOIN students s ON ll.student_id = s.id
                     WHERE 1=1"""
            params = []
            if status:
                sql += " AND ll.status = ?"
                params.append(status)
            if student_id:
                sql += " AND ll.student_id = ?"
                params.append(student_id)
            sql += " ORDER BY ll.borrowed_at DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def overdue_loans(self):
        conn = self._conn()
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            sql = """SELECT ll.*, lb.title as book_title, lb.author,
                     s.first_name, s.last_name, s.student_id as stu_code
                     FROM library_loans ll
                     JOIN library_books lb ON ll.book_id = lb.id
                     JOIN students s ON ll.student_id = s.id
                     WHERE ll.status = 'borrowed' AND ll.due_date < ?
                     ORDER BY ll.due_date"""
            return [dict(r) for r in conn.execute(sql, (today,)).fetchall()]
        finally:
            conn.close()
