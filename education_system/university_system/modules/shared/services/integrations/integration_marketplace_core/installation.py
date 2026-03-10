"""Installation Manager"""

from ._imports import get_connection


class InstallationManager:
    """Manages integration installations"""

    @staticmethod
    def install_integration(integration_id: int, installed_by: str,
                           configuration: str = "") -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            # Get version
            cursor.execute('''
                SELECT version FROM integration_catalog
                WHERE integration_id = ?
            ''', (integration_id,))
            version = cursor.fetchone()['version']

            cursor.execute('''
                INSERT INTO installed_integrations (
                    integration_id, installed_by, version_installed, configuration
                ) VALUES (?, ?, ?, ?)
            ''', (integration_id, installed_by, version, configuration))
            install_id = cursor.lastrowid

            # Update install count
            cursor.execute('''
                UPDATE integration_catalog
                SET install_count = install_count + 1
                WHERE integration_id = ?
            ''', (integration_id,))

            conn.commit()
            return install_id
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error installing integration: {e}")
        finally:
            conn.close()

    @staticmethod
    def uninstall_integration(install_id: int) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE installed_integrations
                SET status = 'uninstalled', is_enabled = 0
                WHERE install_id = ?
            ''', (install_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error uninstalling integration: {e}")
        finally:
            conn.close()
