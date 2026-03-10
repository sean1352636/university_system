"""Asset management service."""

import logging
from education_system.secondary_school.core.exceptions import AssetError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

ASSET_CATEGORIES = ("IT", "furniture", "textbooks", "science_equipment", "sports_equipment",
                    "audio_visual", "musical_instruments", "vehicles", "other")
CONDITIONS = ("new", "good", "fair", "poor", "damaged", "write_off")
STATUSES = ("in_use", "available", "in_repair", "disposed", "lost")


class AssetService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def add_asset(self, asset_tag, name, category="IT", description=None,
                  serial_number=None, location=None, assigned_to=None,
                  department=None, purchase_date=None, purchase_cost=None,
                  warranty_expiry=None, condition="good", notes=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO assets
                   (asset_tag, name, category, description, serial_number, location,
                    assigned_to, department, purchase_date, purchase_cost, warranty_expiry,
                    condition, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (asset_tag, name, category, description, serial_number, location,
                 assigned_to, department, purchase_date, purchase_cost, warranty_expiry,
                 condition, notes))
            conn.commit()
            return dict(conn.execute("SELECT * FROM assets WHERE id = ?", (cursor.lastrowid,)).fetchone())
        except Exception as e:
            conn.rollback()
            raise AssetError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_assets(self, category=None, status=None, search=None):
        conn = self._conn()
        try:
            sql = "SELECT * FROM assets WHERE 1=1"
            params = []
            if category:
                sql += " AND category = ?"
                params.append(category)
            if status:
                sql += " AND status = ?"
                params.append(status)
            if search:
                sql += " AND (name LIKE ? OR asset_tag LIKE ? OR serial_number LIKE ?)"
                q = f"%{search}%"
                params.extend([q, q, q])
            sql += " ORDER BY name"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def update_asset(self, asset_id, **kwargs):
        conn = self._conn()
        try:
            allowed = {"name", "category", "description", "serial_number", "location",
                       "assigned_to", "department", "condition", "status", "notes"}
            updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
            if not updates:
                return
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(f"UPDATE assets SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                         list(updates.values()) + [asset_id])
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise AssetError(f"Failed: {e}") from e
        finally:
            conn.close()

    def delete_asset(self, asset_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
            conn.commit()
        finally:
            conn.close()

    def asset_summary(self):
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT category, COUNT(*) as cnt, SUM(COALESCE(purchase_cost, 0)) as total_value FROM assets GROUP BY category ORDER BY cnt DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
