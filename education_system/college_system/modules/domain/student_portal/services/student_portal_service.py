"""Student Portal service for managing portal pages and quick links."""

from education_system.college_system.core.exceptions import StudentPortalError
from education_system.college_system.infrastructure.database.db import connect

from education_system.college_system.core.sql_safety import escape_like
import logging

logger = logging.getLogger(__name__)


class StudentPortalService:
    """Student Portal service for pages and links management."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ── Portal Pages ──

    def create_page(self, page_title: str, page_slug: str, **kwargs) -> dict:
        conn = self._conn()
        try:
            content = kwargs.get("content")
            category = kwargs.get("category", "general")
            is_published = kwargs.get("is_published", 1)
            sort_order = kwargs.get("sort_order", 0)
            created_by = kwargs.get("created_by")
            conn.execute(
                """INSERT INTO portal_pages
                   (page_title, page_slug, content, category, is_published,
                    sort_order, created_by, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
                (page_title, page_slug, content, category, is_published,
                 sort_order, created_by),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM portal_pages WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            conn.rollback()
            raise StudentPortalError(f"Failed to create page: {e}") from e
        finally:
            conn.close()

    def list_pages(self, category: str = None, published: bool = None,
                   search: str = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM portal_pages WHERE 1=1"
            params: list = []
            if category:
                sql += " AND category = ?"
                params.append(category)
            if published is not None:
                sql += " AND is_published = ?"
                params.append(1 if published else 0)
            if search:
                sql += " AND (page_title LIKE ? OR page_slug LIKE ? OR content LIKE ?)"
                escaped = escape_like(search)
                term = f"%{escaped}%"
                params.extend([term, term, term])
            sql += " ORDER BY sort_order, page_title"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_page(self, page_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM portal_pages WHERE id = ?", (page_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_page_by_slug(self, slug: str) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM portal_pages WHERE page_slug = ?", (slug,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_page(self, page_id: int, **kwargs) -> dict:
        allowed = {"page_title", "page_slug", "content", "category",
                    "is_published", "sort_order", "created_by"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise StudentPortalError("No valid fields to update.")
        conn = self._conn()
        try:
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [page_id]
            conn.execute(
                f"UPDATE portal_pages SET {sets}, updated_at = datetime('now') WHERE id = ?",
                vals,
            )
            conn.commit()
            return self.get_page(page_id)
        except Exception as e:
            conn.rollback()
            raise StudentPortalError(f"Failed to update page: {e}") from e
        finally:
            conn.close()

    def delete_page(self, page_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM portal_pages WHERE id = ?", (page_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise StudentPortalError(f"Failed to delete page: {e}") from e
        finally:
            conn.close()

    def toggle_publish(self, page_id: int) -> dict:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT is_published FROM portal_pages WHERE id = ?", (page_id,)
            ).fetchone()
            if not row:
                raise StudentPortalError(f"Page {page_id} not found.")
            new_val = 0 if row["is_published"] else 1
            conn.execute(
                "UPDATE portal_pages SET is_published = ?, updated_at = datetime('now') WHERE id = ?",
                (new_val, page_id),
            )
            conn.commit()
            return self.get_page(page_id)
        except StudentPortalError:
            raise
        except Exception as e:
            conn.rollback()
            raise StudentPortalError(f"Failed to toggle publish: {e}") from e
        finally:
            conn.close()

    # ── Portal Links ──

    def create_link(self, link_title: str, url: str, **kwargs) -> dict:
        conn = self._conn()
        try:
            category = kwargs.get("category", "useful_links")
            description = kwargs.get("description")
            icon = kwargs.get("icon")
            sort_order = kwargs.get("sort_order", 0)
            is_active = kwargs.get("is_active", 1)
            conn.execute(
                """INSERT INTO portal_links
                   (link_title, url, category, description, icon,
                    sort_order, is_active, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (link_title, url, category, description, icon,
                 sort_order, is_active),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM portal_links WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            conn.rollback()
            raise StudentPortalError(f"Failed to create link: {e}") from e
        finally:
            conn.close()

    def list_links(self, category: str = None, active: bool = None,
                   search: str = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM portal_links WHERE 1=1"
            params: list = []
            if category:
                sql += " AND category = ?"
                params.append(category)
            if active is not None:
                sql += " AND is_active = ?"
                params.append(1 if active else 0)
            if search:
                sql += " AND (link_title LIKE ? OR url LIKE ? OR description LIKE ?)"
                escaped = escape_like(search)
                term = f"%{escaped}%"
                params.extend([term, term, term])
            sql += " ORDER BY sort_order, link_title"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_link(self, link_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM portal_links WHERE id = ?", (link_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_link(self, link_id: int, **kwargs) -> dict:
        allowed = {"link_title", "url", "category", "description",
                    "icon", "sort_order", "is_active"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise StudentPortalError("No valid fields to update.")
        conn = self._conn()
        try:
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [link_id]
            conn.execute(
                f"UPDATE portal_links SET {sets} WHERE id = ?", vals,
            )
            conn.commit()
            return self.get_link(link_id)
        except Exception as e:
            conn.rollback()
            raise StudentPortalError(f"Failed to update link: {e}") from e
        finally:
            conn.close()

    def delete_link(self, link_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM portal_links WHERE id = ?", (link_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise StudentPortalError(f"Failed to delete link: {e}") from e
        finally:
            conn.close()

    def toggle_active(self, link_id: int) -> dict:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT is_active FROM portal_links WHERE id = ?", (link_id,)
            ).fetchone()
            if not row:
                raise StudentPortalError(f"Link {link_id} not found.")
            new_val = 0 if row["is_active"] else 1
            conn.execute(
                "UPDATE portal_links SET is_active = ? WHERE id = ?",
                (new_val, link_id),
            )
            conn.commit()
            return self.get_link(link_id)
        except StudentPortalError:
            raise
        except Exception as e:
            conn.rollback()
            raise StudentPortalError(f"Failed to toggle active: {e}") from e
        finally:
            conn.close()

    # ── Statistics ──

    def get_stats(self) -> dict:
        conn = self._conn()
        try:
            # Page stats
            total_pages = conn.execute(
                "SELECT COUNT(*) FROM portal_pages"
            ).fetchone()[0]
            published = conn.execute(
                "SELECT COUNT(*) FROM portal_pages WHERE is_published = 1"
            ).fetchone()[0]
            draft = total_pages - published

            pages_by_cat = {}
            rows = conn.execute(
                "SELECT category, COUNT(*) as cnt FROM portal_pages GROUP BY category"
            ).fetchall()
            for r in rows:
                pages_by_cat[r["category"] or "general"] = r["cnt"]

            # Link stats
            total_links = conn.execute(
                "SELECT COUNT(*) FROM portal_links"
            ).fetchone()[0]
            active_links = conn.execute(
                "SELECT COUNT(*) FROM portal_links WHERE is_active = 1"
            ).fetchone()[0]
            inactive_links = total_links - active_links

            links_by_cat = {}
            rows = conn.execute(
                "SELECT category, COUNT(*) as cnt FROM portal_links GROUP BY category"
            ).fetchall()
            for r in rows:
                links_by_cat[r["category"] or "useful_links"] = r["cnt"]

            return {
                "total_pages": total_pages,
                "published": published,
                "draft": draft,
                "total_links": total_links,
                "active_links": active_links,
                "inactive_links": inactive_links,
                "pages_by_category": pages_by_cat,
                "links_by_category": links_by_cat,
            }
        finally:
            conn.close()
