"""Extracted function implementation."""
import logging

logger = logging.getLogger(__name__)

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _load_integration_status(self):
    """Load integration status into treeview"""
    try:
        for item in self.integration_tree.get_children():
            self.integration_tree.delete(item)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='ai_integration_config'
            ''')

            if cursor.fetchone():
                cursor.execute('''
                    SELECT service_name,
                           CASE WHEN enabled = 1 THEN 'Active' ELSE 'Inactive' END,
                           datetime(last_sync),
                           0
                    FROM ai_integration_config
                ''')
                integrations = cursor.fetchall()

                for integration in integrations:
                    self.integration_tree.insert('', 'end', values=integration)

        finally:
            conn.close()
    except Exception:
        logger.debug("Suppressed exception", exc_info=True)
