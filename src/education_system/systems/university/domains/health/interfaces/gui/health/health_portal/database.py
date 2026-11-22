
from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.domains.health.interfaces.gui.health._dialogs import messagebox

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system import paths


class DatabaseMixin:
    """Mixin for database schema initialization."""

    def init_database(self):
        """The health tables, once per database file (``infrastructure/health/
        health_schema``, also applied by migration ``a0d2f4b6c8e1``). This
        window used to declare 22 tables on every open."""
        from education_system.systems.university.domains.health.infrastructure.health import (
            health_schema,
        )
        try:
            conn = self.get_connection()
            try:
                health_schema.apply_to_connection(conn)
            finally:
                conn.close()

        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.health.health_portal.database.dialogs.database_error', default="Database Error"), f"Error initializing database: {e}")
