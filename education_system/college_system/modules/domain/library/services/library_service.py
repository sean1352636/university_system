"""Library service for managing library items and loans."""

from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.exceptions import LibraryError


class LibraryService:
    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # --- Library Items ---

    def add_item(self, title: str, author: str = None, isbn: str = None,
                  category: str = "textbook",
                  location: str = None, total_copies: int = 1) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO library_items
                   (title, author, isbn, category, location,
                    total_copies, available_copies)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (title, author, isbn, category, location,
                 total_copies, total_copies),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM library_items WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise LibraryError(f"Failed to add item: {e}")
        finally:
            conn.close()

    def list_items(self, search: str = None, category: str = None,
                    available_only: bool = False) -> list[dict]:
        conn = self._conn()
        try:
            query = "SELECT * FROM library_items WHERE 1=1"
            params = []
            if search:
                query += " AND (title LIKE ? OR author LIKE ? OR isbn LIKE ?)"
                term = f"%{search}%"
                params.extend([term, term, term])
            if category:
                query += " AND category = ?"
                params.append(category)
            if available_only:
                query += " AND available_copies > 0"
            query += " ORDER BY title"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_item(self, item_id: int) -> dict:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM library_items WHERE id = ?", (item_id,)
            ).fetchone()
            if not row:
                raise LibraryError(f"Item {item_id} not found")
            return dict(row)
        finally:
            conn.close()

    def update_item(self, item_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {"title", "author", "isbn", "category",
                        "location", "total_copies", "available_copies"}
            parts, params = [], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if not parts:
                raise LibraryError("No valid fields to update")
            params.append(item_id)
            conn.execute(f"UPDATE library_items SET {', '.join(parts)} WHERE id = ?", params)
            conn.commit()
            return self.get_item(item_id)
        except LibraryError:
            raise
        except Exception as e:
            raise LibraryError(f"Failed to update item: {e}")
        finally:
            conn.close()

    # --- Loans ---

    def checkout(self, item_id: int, student_id: int,
                  due_date: str = None) -> dict:
        conn = self._conn()
        try:
            item = conn.execute(
                "SELECT available_copies FROM library_items WHERE id = ?", (item_id,)
            ).fetchone()
            if not item:
                raise LibraryError(f"Item {item_id} not found")
            if item["available_copies"] <= 0:
                raise LibraryError("No copies available")

            if due_date:
                conn.execute(
                    """INSERT INTO library_loans
                       (item_id, student_id, due_date)
                       VALUES (?, ?, ?)""",
                    (item_id, student_id, due_date),
                )
            else:
                conn.execute(
                    """INSERT INTO library_loans
                       (item_id, student_id, due_date)
                       VALUES (?, ?, date('now', '+14 days'))""",
                    (item_id, student_id),
                )
            conn.execute(
                "UPDATE library_items SET available_copies = available_copies - 1 WHERE id = ?",
                (item_id,),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM library_loans WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except LibraryError:
            raise
        except Exception as e:
            raise LibraryError(f"Failed to checkout: {e}")
        finally:
            conn.close()

    def return_item(self, loan_id: int) -> dict:
        conn = self._conn()
        try:
            loan = conn.execute(
                "SELECT * FROM library_loans WHERE id = ?", (loan_id,)
            ).fetchone()
            if not loan:
                raise LibraryError(f"Loan {loan_id} not found")
            if loan["status"] == "returned":
                raise LibraryError("Item already returned")

            conn.execute(
                """UPDATE library_loans
                   SET status = 'returned', returned_date = date('now')
                   WHERE id = ?""",
                (loan_id,),
            )
            conn.execute(
                "UPDATE library_items SET available_copies = available_copies + 1 WHERE id = ?",
                (loan["item_id"],),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM library_loans WHERE id = ?", (loan_id,)
            ).fetchone()
            return dict(row)
        except LibraryError:
            raise
        except Exception as e:
            raise LibraryError(f"Failed to return item: {e}")
        finally:
            conn.close()

    def list_loans(self, student_id: int = None, status: str = None) -> list[dict]:
        conn = self._conn()
        try:
            query = """SELECT ll.*, li.title, li.author FROM library_loans ll
                       LEFT JOIN library_items li ON ll.item_id = li.id WHERE 1=1"""
            params = []
            if student_id:
                query += " AND ll.student_id = ?"
                params.append(student_id)
            if status:
                query += " AND ll.status = ?"
                params.append(status)
            query += " ORDER BY ll.loaned_date DESC"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def renew_loan(self, loan_id: int, extra_days: int = 14) -> dict:
        conn = self._conn()
        try:
            loan = conn.execute(
                "SELECT * FROM library_loans WHERE id = ?", (loan_id,)
            ).fetchone()
            if not loan:
                raise LibraryError(f"Loan {loan_id} not found")
            if loan["status"] != "on_loan":
                raise LibraryError("Only active loans can be renewed")
            conn.execute(
                f"""UPDATE library_loans
                    SET due_date = date(due_date, '+{extra_days} days')
                    WHERE id = ?""",
                (loan_id,),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM library_loans WHERE id = ?", (loan_id,)
            ).fetchone()
            return dict(row)
        except LibraryError:
            raise
        except Exception as e:
            raise LibraryError(f"Failed to renew: {e}")
        finally:
            conn.close()

    def get_overdue(self) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT ll.*, li.title, li.author FROM library_loans ll
                   LEFT JOIN library_items li ON ll.item_id = li.id
                   WHERE ll.status = 'on_loan' AND ll.due_date < date('now')
                   ORDER BY ll.due_date"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
