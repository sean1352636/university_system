"""Library management service for the Primary School Management System."""

import logging
from datetime import date, timedelta
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import LibraryError
from education_system.primary_school.core.sql_safety import validate_identifier
import traceback

logger = logging.getLogger(__name__)


class LibraryService:
    """CRUD operations for library books and loans."""

    DEFAULT_LOAN_DAYS = 14

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ── Books ────────────────────────────────────────────────────────────

    def add_book(self, title, author=None, isbn=None, category=None,
                 reading_level=None, location=None, copies=1):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO library_books (
                    title, author, isbn, category, reading_level, location, copies
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (title, author, isbn, category, reading_level, location, copies),
            )
            conn.commit()
            book_id = cursor.lastrowid
            logger.info("Added book: %s (id=%s)", title, book_id)
            return {"id": book_id, "title": title, "copies": copies}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise LibraryError(f"Failed to add book: {e}") from e
        finally:
            conn.close()

    def get_book(self, book_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM library_books WHERE id = ?", (book_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_books(self, category=None, available=None, search=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM library_books WHERE 1=1"
            params = []
            if category:
                sql += " AND category = ?"
                params.append(category)
            if available is not None:
                if available:
                    sql += " AND available_copies > 0"
                else:
                    sql += " AND available_copies = 0"
            if search:
                sql += " AND (title LIKE ? OR author LIKE ? OR isbn LIKE ?)"
                escaped = escape_like(search)
                term = f"%{escaped}%"
                params.extend([term, term, term])
            sql += " ORDER BY title"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_book(self, book_id, **kwargs):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {
                "title", "author", "isbn", "category", "reading_level",
                "location", "copies", "available_copies",
            }
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values())
            values.append(book_id)
            cursor.execute(
                f"UPDATE library_books SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated book id=%s", book_id)
            return self.get_book(book_id)
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise LibraryError(f"Failed to update book: {e}") from e
        finally:
            conn.close()

    def delete_book(self, book_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM library_books WHERE id = ?", (book_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted book id=%s", book_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise LibraryError(f"Failed to delete book: {e}") from e
        finally:
            conn.close()

    # ── Loans ────────────────────────────────────────────────────────────

    def loan_book(self, book_id, pupil_id, due_date=None):
        if due_date is None:
            due_date = (date.today() + timedelta(days=self.DEFAULT_LOAN_DAYS)).isoformat()
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO library_loans (book_id, pupil_id, due_date)
                VALUES (?, ?, ?)""",
                (book_id, pupil_id, due_date),
            )
            cursor.execute(
                "UPDATE library_books SET available_copies = available_copies - 1 WHERE id = ? AND available_copies > 0",
                (book_id,),
            )
            conn.commit()
            loan_id = cursor.lastrowid
            logger.info(
                "Loaned book id=%s to pupil %s (loan id=%s)",
                book_id, pupil_id, loan_id,
            )
            return {"id": loan_id, "book_id": book_id, "pupil_id": pupil_id, "due_date": due_date}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise LibraryError(f"Failed to loan book: {e}") from e
        finally:
            conn.close()

    def return_book(self, loan_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT book_id FROM library_loans WHERE id = ? AND status = 'On Loan'",
                (loan_id,),
            )
            row = cursor.fetchone()
            if not row:
                return False
            book_id = row["book_id"]
            cursor.execute(
                "UPDATE library_loans SET status = 'Returned', returned_date = date('now') WHERE id = ?",
                (loan_id,),
            )
            cursor.execute(
                "UPDATE library_books SET available_copies = available_copies + 1 WHERE id = ?",
                (book_id,),
            )
            conn.commit()
            logger.info("Returned loan id=%s (book id=%s)", loan_id, book_id)
            return True
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise LibraryError(f"Failed to return book: {e}") from e
        finally:
            conn.close()

    def get_loans(self, pupil_id=None, status="On Loan"):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = """SELECT ll.*, lb.title, lb.author
                FROM library_loans ll
                JOIN library_books lb ON lb.id = ll.book_id
                WHERE 1=1"""
            params = []
            if pupil_id:
                sql += " AND ll.pupil_id = ?"
                params.append(pupil_id)
            if status:
                sql += " AND ll.status = ?"
                params.append(status)
            sql += " ORDER BY ll.due_date"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def get_overdue_loans(self):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT ll.*, lb.title, lb.author, p.first_name, p.last_name, p.class_name
                FROM library_loans ll
                JOIN library_books lb ON lb.id = ll.book_id
                JOIN pupils p ON p.pupil_id = ll.pupil_id
                WHERE ll.status = 'On Loan' AND ll.due_date < date('now')
                ORDER BY ll.due_date""",
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()
