"""Sync Manager"""

from education_system.post_18.university_system.modules.shared.services.integrations.integration_marketplace_core._imports import datetime, get_connection


class SyncManager:
    """Manages integration synchronization"""

    @staticmethod
    def start_sync(install_id: int) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO integration_sync_logs (
                    install_id, sync_status
                ) VALUES (?, 'running')
            ''', (install_id,))
            log_id = cursor.lastrowid
            conn.commit()
            return log_id
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error starting sync: {e}")
        finally:
            conn.close()

    @staticmethod
    def complete_sync(log_id: int, sync_status: str, records_synced: int = 0,
                     errors_encountered: int = 0, error_details: str = "") -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE integration_sync_logs
                SET sync_end_time = ?, sync_status = ?,
                    records_synced = ?, errors_encountered = ?, error_details = ?
                WHERE log_id = ?
            ''', (datetime.now().isoformat(), sync_status, records_synced,
                  errors_encountered, error_details, log_id))

            # Update last sync date
            cursor.execute('''
                UPDATE installed_integrations
                SET last_sync_date = ?
                WHERE install_id = (
                    SELECT install_id FROM integration_sync_logs WHERE log_id = ?
                )
            ''', (datetime.now().isoformat(), log_id))

            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error completing sync: {e}")
        finally:
            conn.close()
