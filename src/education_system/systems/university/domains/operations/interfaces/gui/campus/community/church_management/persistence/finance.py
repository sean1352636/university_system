"""Extracted ChurchManagementSystem behaviour."""
from .. import *

class ChurchPersistenceFinanceMixin:
    def _db_save_expense(self, expense):
        """Save an expense to the database."""
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO church_expenses (description, amount, category, date, vendor, approved_by)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (expense.get('description'), expense.get('amount'), expense.get('category'),
                      expense.get('date'), expense.get('vendor'), expense.get('approved_by')))
                expense['id'] = cursor.lastrowid
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save expense: {e}")
            return False
