"""Credential Manager"""

from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core._imports import get_connection


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
