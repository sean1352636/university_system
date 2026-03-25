"""Helpdesk ticket management service."""

from datetime import datetime

from education_system.college_system.core.exceptions import HelpdeskError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)

_CATEGORIES = ("general", "it", "facilities", "academic", "finance", "other")
_PRIORITIES = ("low", "medium", "high", "urgent")
_STATUSES = ("open", "in_progress", "resolved", "closed")


class HelpdeskService:
    """Service for managing helpdesk tickets and responses."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_ticket(self, user_id: int, subject: str, description: str,
                      category: str = "general",
                      priority: str = "medium") -> dict:
        """Create a new helpdesk ticket."""
        if not subject or not subject.strip():
            raise HelpdeskError("Subject is required.")
        if not description or not description.strip():
            raise HelpdeskError("Description is required.")
        if category not in _CATEGORIES:
            raise HelpdeskError(f"Category must be one of: {', '.join(_CATEGORIES)}")
        if priority not in _PRIORITIES:
            raise HelpdeskError(f"Priority must be one of: {', '.join(_PRIORITIES)}")

        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO helpdesk_tickets
                   (user_id, subject, description, category, priority)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, subject.strip(), description.strip(), category, priority),
            )
            conn.commit()
            ticket_id = cursor.lastrowid
            logger.info("Helpdesk ticket created: id=%d user=%d", ticket_id, user_id)
            return self.get_ticket(ticket_id)
        except HelpdeskError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HelpdeskError(f"Failed to create ticket: {e}") from e
        finally:
            conn.close()

    def list_tickets(self, user_id: int | None = None,
                     status: str | None = None,
                     limit: int = 50) -> list[dict]:
        """List tickets. If user_id given, show their tickets; otherwise all."""
        conn = self._conn()
        try:
            conditions = []
            params: list = []
            if user_id is not None:
                conditions.append("t.user_id = ?")
                params.append(user_id)
            if status:
                conditions.append("t.status = ?")
                params.append(status)

            sql = """SELECT t.*, u.username as created_by_name
                     FROM helpdesk_tickets t
                     JOIN users u ON t.user_id = u.id"""
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY t.created_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_ticket(self, ticket_id: int) -> dict:
        """Get a ticket with its responses."""
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT t.*, u.username as created_by_name
                   FROM helpdesk_tickets t
                   JOIN users u ON t.user_id = u.id
                   WHERE t.id = ?""",
                (ticket_id,),
            ).fetchone()
            if not row:
                raise HelpdeskError("Ticket not found.")

            ticket = dict(row)

            # Fetch responses
            responses = conn.execute(
                """SELECT r.*, u.username
                   FROM helpdesk_responses r
                   JOIN users u ON r.user_id = u.id
                   WHERE r.ticket_id = ?
                   ORDER BY r.created_at""",
                (ticket_id,),
            ).fetchall()
            ticket["responses"] = [dict(r) for r in responses]

            return ticket
        finally:
            conn.close()

    def update_ticket(self, ticket_id: int, **kwargs) -> dict:
        """Update ticket status, priority, or assigned_to."""
        allowed = {"status", "priority", "assigned_to"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            raise HelpdeskError("No valid fields to update.")
        if "status" in updates and updates["status"] not in _STATUSES:
            raise HelpdeskError(f"Status must be one of: {', '.join(_STATUSES)}")
        if "priority" in updates and updates["priority"] not in _PRIORITIES:
            raise HelpdeskError(f"Priority must be one of: {', '.join(_PRIORITIES)}")

        conn = self._conn()
        try:
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values())
            vals.extend([datetime.now().isoformat(), ticket_id])
            conn.execute(
                f"UPDATE helpdesk_tickets SET {sets}, updated_at = ? WHERE id = ?",
                vals,
            )
            conn.commit()
            logger.info("Helpdesk ticket updated: id=%d", ticket_id)
            return self.get_ticket(ticket_id)
        except HelpdeskError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HelpdeskError(f"Failed to update ticket: {e}") from e
        finally:
            conn.close()

    def add_response(self, ticket_id: int, user_id: int, message: str) -> dict:
        """Add a response to a ticket."""
        if not message or not message.strip():
            raise HelpdeskError("Message is required.")

        conn = self._conn()
        try:
            # Verify ticket exists
            ticket = conn.execute("SELECT id FROM helpdesk_tickets WHERE id = ?",
                                  (ticket_id,)).fetchone()
            if not ticket:
                raise HelpdeskError("Ticket not found.")

            conn.execute(
                """INSERT INTO helpdesk_responses (ticket_id, user_id, message)
                   VALUES (?, ?, ?)""",
                (ticket_id, user_id, message.strip()),
            )
            conn.commit()
            logger.info("Response added to ticket %d by user %d", ticket_id, user_id)
            return self.get_ticket(ticket_id)
        except HelpdeskError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HelpdeskError(f"Failed to add response: {e}") from e
        finally:
            conn.close()

    def delete_ticket(self, ticket_id: int) -> bool:
        """Delete a helpdesk ticket and its responses by ID."""
        conn = self._conn()
        try:
            # Delete associated responses first
            conn.execute(
                "DELETE FROM helpdesk_responses WHERE ticket_id = ?", (ticket_id,)
            )
            result = conn.execute(
                "DELETE FROM helpdesk_tickets WHERE id = ?", (ticket_id,)
            )
            conn.commit()
            if result.rowcount == 0:
                raise HelpdeskError(f"Ticket {ticket_id} not found.")
            logger.info("Helpdesk ticket deleted: id=%d", ticket_id)
            return True
        except HelpdeskError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HelpdeskError(f"Failed to delete ticket: {e}") from e
        finally:
            conn.close()

    def assign_ticket(self, ticket_id: int, assigned_to: int) -> dict:
        """Assign a ticket to a user."""
        return self.update_ticket(ticket_id, assigned_to=assigned_to)
