"""Integration Catalog Manager"""

from education_system.post_18.university_system.modules.shared.services.integrations.integration_marketplace_core._imports import Any, Dict, List, get_connection


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
