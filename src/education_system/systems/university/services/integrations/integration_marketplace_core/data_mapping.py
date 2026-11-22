"""Data Mapping Manager"""

from education_system.systems.university.services.integrations.integration_marketplace_core._imports import get_connection


class DataMappingManager:
    """Manages field mappings for integrations"""

    @staticmethod
    def update_mapping(mapping_id: int, install_id: int, source_field: str, target_field: str,
                       transformation_rule: str = "", is_active: int = 1) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE integration_data_mappings
                SET install_id = ?, source_field = ?, target_field = ?,
                    transformation_rule = ?, is_active = ?
                WHERE mapping_id = ?
            ''', (install_id, source_field, target_field, transformation_rule,
                  is_active, mapping_id))
            updated = cursor.rowcount > 0
            conn.commit()
            return updated
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error updating mapping: {e}")
        finally:
            conn.close()

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
