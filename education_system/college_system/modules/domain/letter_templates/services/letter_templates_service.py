"""Letter Templates service for managing templates and generated letters."""

from datetime import datetime

from education_system.college_system.core.exceptions import LetterTemplateError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)

_CATEGORIES = ("general", "admissions", "finance", "academic", "pastoral",
               "disciplinary", "hr", "other")
_RECIPIENT_TYPES = ("student", "parent", "staff", "external")
_SENT_VIA_OPTIONS = ("email", "post", "hand")
_STATUSES = ("draft", "sent", "archived")


class LetterTemplateService:
    """Service for managing letter templates and generated letters."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ── Template methods ──────────────────────────────────────────────

    def create_template(self, template_name: str, body_template: str,
                        **kwargs) -> dict:
        """Create a new letter template."""
        if not template_name or not template_name.strip():
            raise LetterTemplateError("Template name is required.")
        if not body_template or not body_template.strip():
            raise LetterTemplateError("Body template is required.")
        category = kwargs.get("category", "general")
        if category not in _CATEGORIES:
            raise LetterTemplateError(
                f"Category must be one of: {', '.join(_CATEGORIES)}")

        conn = self._conn()
        try:
            now = datetime.now().isoformat()
            cursor = conn.execute(
                """INSERT INTO letter_templates
                   (template_name, body_template, category, subject_line,
                    merge_fields, is_active, created_by, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (template_name.strip(), body_template.strip(), category,
                 kwargs.get("subject_line", ""),
                 kwargs.get("merge_fields", ""),
                 kwargs.get("is_active", 1),
                 kwargs.get("created_by"),
                 now, now),
            )
            conn.commit()
            template_id = cursor.lastrowid
            logger.info("Letter template created: id=%d name=%s",
                        template_id, template_name)
            return self.get_template(template_id)
        except LetterTemplateError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise LetterTemplateError(
                f"Failed to create template: {e}") from e
        finally:
            conn.close()

    def list_templates(self, category: str | None = None,
                       active: int | None = None,
                       search: str | None = None) -> list[dict]:
        """List templates with optional filters."""
        conn = self._conn()
        try:
            conditions: list[str] = []
            params: list = []
            if category:
                conditions.append("category = ?")
                params.append(category)
            if active is not None:
                conditions.append("is_active = ?")
                params.append(active)
            if search:
                conditions.append(
                    "(template_name LIKE ? OR subject_line LIKE ?)")
                params.extend([f"%{search}%", f"%{search}%"])

            sql = "SELECT * FROM letter_templates"
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY created_at DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_template(self, template_id: int) -> dict | None:
        """Get a single template by ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM letter_templates WHERE id = ?",
                (template_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_template(self, template_id: int, **kwargs) -> dict:
        """Update a template's fields."""
        allowed = {"template_name", "body_template", "category",
                    "subject_line", "merge_fields", "is_active"}
        updates = {k: v for k, v in kwargs.items()
                   if k in allowed and v is not None}
        if not updates:
            raise LetterTemplateError("No valid fields to update.")
        if "category" in updates and updates["category"] not in _CATEGORIES:
            raise LetterTemplateError(
                f"Category must be one of: {', '.join(_CATEGORIES)}")

        updates["updated_at"] = datetime.now().isoformat()
        conn = self._conn()
        try:
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [template_id]
            conn.execute(
                f"UPDATE letter_templates SET {sets} WHERE id = ?", vals)
            conn.commit()
            logger.info("Letter template updated: id=%d", template_id)
            return self.get_template(template_id)
        except LetterTemplateError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise LetterTemplateError(
                f"Failed to update template: {e}") from e
        finally:
            conn.close()

    def delete_template(self, template_id: int) -> bool:
        """Delete a template and cascade-delete its generated letters."""
        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM generated_letters WHERE template_id = ?",
                (template_id,))
            conn.execute(
                "DELETE FROM letter_templates WHERE id = ?",
                (template_id,))
            conn.commit()
            logger.info("Letter template deleted (cascade): id=%d",
                        template_id)
            return True
        except Exception as e:
            conn.rollback()
            raise LetterTemplateError(
                f"Failed to delete template: {e}") from e
        finally:
            conn.close()

    def toggle_active(self, template_id: int) -> dict:
        """Toggle a template's is_active flag."""
        tmpl = self.get_template(template_id)
        if not tmpl:
            raise LetterTemplateError(
                f"Template {template_id} not found.")
        new_val = 0 if tmpl["is_active"] else 1
        return self.update_template(template_id, is_active=new_val)

    # ── Generated letter methods ──────────────────────────────────────

    def generate_letter(self, template_id: int, recipient_name: str,
                        body: str, **kwargs) -> dict:
        """Generate a letter from a template."""
        if not recipient_name or not recipient_name.strip():
            raise LetterTemplateError("Recipient name is required.")
        if not body or not body.strip():
            raise LetterTemplateError("Letter body is required.")
        recipient_type = kwargs.get("recipient_type", "student")
        if recipient_type not in _RECIPIENT_TYPES:
            raise LetterTemplateError(
                f"Recipient type must be one of: "
                f"{', '.join(_RECIPIENT_TYPES)}")
        sent_via = kwargs.get("sent_via", "email")
        if sent_via not in _SENT_VIA_OPTIONS:
            raise LetterTemplateError(
                f"Sent-via must be one of: {', '.join(_SENT_VIA_OPTIONS)}")

        conn = self._conn()
        try:
            now = datetime.now().isoformat()
            cursor = conn.execute(
                """INSERT INTO generated_letters
                   (template_id, recipient_type, recipient_id,
                    recipient_name, subject, body, sent_via,
                    status, created_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (template_id, recipient_type,
                 kwargs.get("recipient_id"),
                 recipient_name.strip(),
                 kwargs.get("subject", ""),
                 body.strip(), sent_via, "draft",
                 kwargs.get("created_by"),
                 now),
            )
            conn.commit()
            letter_id = cursor.lastrowid
            logger.info("Letter generated: id=%d template=%d recipient=%s",
                        letter_id, template_id, recipient_name)
            return self.get_letter(letter_id)
        except LetterTemplateError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise LetterTemplateError(
                f"Failed to generate letter: {e}") from e
        finally:
            conn.close()

    def list_letters(self, template_id: int | None = None,
                     status: str | None = None,
                     recipient_type: str | None = None) -> list[dict]:
        """List generated letters with optional filters, joined with
        template name."""
        conn = self._conn()
        try:
            conditions: list[str] = []
            params: list = []
            if template_id is not None:
                conditions.append("gl.template_id = ?")
                params.append(template_id)
            if status:
                conditions.append("gl.status = ?")
                params.append(status)
            if recipient_type:
                conditions.append("gl.recipient_type = ?")
                params.append(recipient_type)

            sql = """SELECT gl.*, lt.template_name
                     FROM generated_letters gl
                     LEFT JOIN letter_templates lt
                       ON gl.template_id = lt.id"""
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY gl.created_at DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_letter(self, letter_id: int) -> dict | None:
        """Get a single generated letter by ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT gl.*, lt.template_name
                   FROM generated_letters gl
                   LEFT JOIN letter_templates lt
                     ON gl.template_id = lt.id
                   WHERE gl.id = ?""",
                (letter_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_letter(self, letter_id: int, **kwargs) -> dict:
        """Update a generated letter's fields."""
        allowed = {"recipient_type", "recipient_id", "recipient_name",
                    "subject", "body", "sent_via", "status"}
        updates = {k: v for k, v in kwargs.items()
                   if k in allowed and v is not None}
        if not updates:
            raise LetterTemplateError("No valid fields to update.")

        conn = self._conn()
        try:
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [letter_id]
            conn.execute(
                f"UPDATE generated_letters SET {sets} WHERE id = ?", vals)
            conn.commit()
            logger.info("Generated letter updated: id=%d", letter_id)
            return self.get_letter(letter_id)
        except LetterTemplateError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise LetterTemplateError(
                f"Failed to update letter: {e}") from e
        finally:
            conn.close()

    def delete_letter(self, letter_id: int) -> bool:
        """Delete a generated letter."""
        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM generated_letters WHERE id = ?",
                (letter_id,))
            conn.commit()
            logger.info("Generated letter deleted: id=%d", letter_id)
            return True
        except Exception as e:
            conn.rollback()
            raise LetterTemplateError(
                f"Failed to delete letter: {e}") from e
        finally:
            conn.close()

    def mark_sent(self, letter_id: int,
                  sent_via: str = "email") -> dict:
        """Mark a letter as sent."""
        if sent_via not in _SENT_VIA_OPTIONS:
            raise LetterTemplateError(
                f"Sent-via must be one of: {', '.join(_SENT_VIA_OPTIONS)}")
        conn = self._conn()
        try:
            now = datetime.now().isoformat()
            conn.execute(
                """UPDATE generated_letters
                   SET status = 'sent', sent_via = ?, sent_at = ?
                   WHERE id = ?""",
                (sent_via, now, letter_id))
            conn.commit()
            logger.info("Letter marked sent: id=%d via=%s",
                        letter_id, sent_via)
            return self.get_letter(letter_id)
        except Exception as e:
            conn.rollback()
            raise LetterTemplateError(
                f"Failed to mark letter sent: {e}") from e
        finally:
            conn.close()

    # ── Statistics ────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get statistics across templates and letters."""
        conn = self._conn()
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM letter_templates").fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM letter_templates "
                "WHERE is_active = 1").fetchone()[0]
            inactive = total - active

            total_letters = conn.execute(
                "SELECT COUNT(*) FROM generated_letters").fetchone()[0]

            by_status_rows = conn.execute(
                "SELECT status, COUNT(*) as cnt "
                "FROM generated_letters GROUP BY status"
            ).fetchall()
            by_status = {r["status"]: r["cnt"] for r in by_status_rows}

            by_category_rows = conn.execute(
                "SELECT category, COUNT(*) as cnt "
                "FROM letter_templates GROUP BY category"
            ).fetchall()
            by_category = {r["category"]: r["cnt"]
                           for r in by_category_rows}

            return {
                "total_templates": total,
                "active_templates": active,
                "inactive_templates": inactive,
                "total_letters": total_letters,
                "by_status": by_status,
                "by_category": by_category,
            }
        finally:
            conn.close()
