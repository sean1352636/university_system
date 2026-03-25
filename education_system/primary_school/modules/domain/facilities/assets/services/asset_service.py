"""Asset service for the Primary School Management System."""

import logging

from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import AssetError
from education_system.primary_school.core.sql_safety import validate_identifier
import traceback

logger = logging.getLogger(__name__)


class AssetService:
    """CRUD operations for school assets."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_asset(self, asset_name, asset_type=None, serial_number=None,
                     location=None, assigned_to=None, purchase_date=None,
                     purchase_cost=None, condition="Good", notes=None):
        """Create a new asset record."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO assets (
                    asset_name, asset_type, serial_number, location,
                    assigned_to, purchase_date, purchase_cost,
                    condition, notes, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'In Use',
                          datetime('now'))""",
                (asset_name, asset_type, serial_number, location,
                 assigned_to, purchase_date, purchase_cost,
                 condition, notes),
            )
            conn.commit()
            asset_id = cursor.lastrowid
            logger.info("Created asset %s: %s", asset_id, asset_name)
            return {"id": asset_id, "asset_name": asset_name,
                    "asset_type": asset_type}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise AssetError(f"Failed to create asset: {e}") from e
        finally:
            conn.close()

    def get_asset(self, asset_id):
        """Get a single asset by ID."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM assets WHERE id = ?", (asset_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_assets(self, asset_type=None, location=None, status="In Use"):
        """List assets with optional filters."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM assets WHERE 1=1"
            params = []
            if asset_type:
                sql += " AND asset_type = ?"
                params.append(asset_type)
            if location:
                sql += " AND location = ?"
                params.append(location)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY asset_name"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_asset(self, asset_id, **kwargs):
        """Update an asset record."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {
                "asset_name", "asset_type", "serial_number", "location",
                "assigned_to", "purchase_date", "purchase_cost",
                "condition", "notes", "status",
            }
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values())
            values.append(asset_id)
            cursor.execute(
                f"UPDATE assets SET {set_clause}, "
                "updated_at = datetime('now') WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated asset %s", asset_id)
            return self.get_asset(asset_id)
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise AssetError(f"Failed to update asset: {e}") from e
        finally:
            conn.close()

    def delete_asset(self, asset_id):
        """Delete an asset record."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM assets WHERE id = ?", (asset_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info("Deleted asset %s", asset_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise AssetError(f"Failed to delete asset: {e}") from e
        finally:
            conn.close()
