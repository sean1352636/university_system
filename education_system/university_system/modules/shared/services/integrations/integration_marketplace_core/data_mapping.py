"""Data Mapping Manager"""

from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core._imports import get_connection


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
