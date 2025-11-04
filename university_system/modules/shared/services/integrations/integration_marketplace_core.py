"""
Integration Marketplace Core Service

Integration catalog, installation management, credentials,
sync logs, data mappings, webhooks, and usage analytics.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from university_system.infrastructure.database.db import get_connection
from university_system.modules.shared.feature_gui_factory import create_gui_launcher


class IntegrationCatalogManager:
    """Manages integration catalog"""

    @staticmethod
    def add_integration(integration_name: str, provider_name: str,
                       integration_type: str, category: str,
                       description: str = "", version: str = "1.0",
                       is_official: bool = False) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO integration_catalog (
                    integration_name, provider_name, integration_type,
                    category, description, version, is_official
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (integration_name, provider_name, integration_type,
                  category, description, version, is_official))
            integration_id = cursor.lastrowid
            conn.commit()
            return integration_id
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error adding integration: {e}")
        finally:
            conn.close()

    @staticmethod
    def get_available_integrations(category: str = "") -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            if category:
                cursor.execute('''
                    SELECT * FROM integration_catalog
                    WHERE category = ? AND is_active = 1
                    ORDER BY rating DESC, install_count DESC
                ''', (category,))
            else:
                cursor.execute('''
                    SELECT * FROM integration_catalog
                    WHERE is_active = 1
                    ORDER BY rating DESC, install_count DESC
                ''')
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()


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


class CredentialManager:
    """Manages integration credentials"""

    @staticmethod
    def store_credentials(install_id: int, credential_type: str,
                         api_key: str = "", api_secret: str = "",
                         oauth_token: str = "", endpoint_url: str = "") -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO integration_credentials (
                    install_id, credential_type, api_key, api_secret,
                    oauth_token, endpoint_url
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (install_id, credential_type, api_key, api_secret,
                  oauth_token, endpoint_url))
            credential_id = cursor.lastrowid
            conn.commit()
            return credential_id
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error storing credentials: {e}")
        finally:
            conn.close()


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


class DataMappingManager:
    """Manages field mappings for integrations"""

    @staticmethod
    def create_mapping(install_id: int, source_field: str, target_field: str,
                      transformation_rule: str = "") -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO integration_data_mappings (
                    install_id, source_field, target_field, transformation_rule
                ) VALUES (?, ?, ?, ?)
            ''', (install_id, source_field, target_field, transformation_rule))
            mapping_id = cursor.lastrowid
            conn.commit()
            return mapping_id
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error creating mapping: {e}")
        finally:
            conn.close()


class WebhookManager:
    """Manages integration webhooks"""

    @staticmethod
    def register_webhook(install_id: int, webhook_url: str, event_type: str,
                        secret_key: str = "") -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO integration_webhooks (
                    install_id, webhook_url, event_type, secret_key
                ) VALUES (?, ?, ?, ?)
            ''', (install_id, webhook_url, event_type, secret_key))
            webhook_id = cursor.lastrowid
            conn.commit()
            return webhook_id
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error registering webhook: {e}")
        finally:
            conn.close()


def display_integration_marketplace_menu(auth):
    """Display the Integration Marketplace CLI menu"""
    print("\n" + "="*50)
    print("      INTEGRATION MARKETPLACE")
    print("="*50)
    print("1. Browse Integration Catalog")
    print("2. Install Integration")
    print("3. Manage Credentials")
    print("4. Sync Logs")
    print("5. Data Mappings")
    print("6. Webhook Configuration")
    print("7. Usage Analytics")
    print("8. Return to Main Menu")
    print("="*50)

    while True:
        try:
            choice = input("\nEnter your choice (1-8): ").strip()
            if choice in ['1', '2', '3', '4', '5', '6', '7']:
                print(f"\n🔌 Feature available via Integration managers")
                print("Use: from university_system.modules.shared.services.integrations import IntegrationCatalogManager")
            elif choice == '8':
                break
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Error: {e}")


# Use factory to create GUI launcher
launch_integration_marketplace_gui = create_gui_launcher(
    title="Integration Marketplace",
    description="""Browse and install third-party integrations.

Features:
• Integration catalog
• Installation management
• Credential management
• Sync logs
• Data mappings
• Webhook configuration""",
    cli_instruction="Use CLI: Integration Marketplace"
)



__all__ = [
    'IntegrationCatalogManager', 'InstallationManager', 'CredentialManager',
    'SyncManager', 'DataMappingManager', 'WebhookManager',
    'display_integration_marketplace_menu',
    'launch_integration_marketplace_gui',
]
