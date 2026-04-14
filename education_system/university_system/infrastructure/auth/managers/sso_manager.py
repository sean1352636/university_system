"""
Single Sign-On (SSO) Manager Module

This module bridges the SSOService with the authentication system, handling
SSO provider configuration, management, and lifecycle operations.

Classes:
    SSOManager: Manages SSO provider configuration and operations
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from education_system.university_system.infrastructure.database.db import sqlite3

logger = logging.getLogger(__name__)

__all__ = ['SSOManager']


class SSOManager:
    """
    Manager for Single Sign-On provider operations.

    This class handles SSO provider configuration, updates, deletion, and
    enable/disable toggling. It bridges the SSOService with the core
    authentication system and provides audit logging for all operations.

    Attributes:
        db_manager: Database manager instance for data operations
        activity_logger: Activity logger for audit trails
        get_current_user: Callable that returns the current user dict
    """

    # Supported SSO provider types
    SUPPORTED_PROVIDER_TYPES = [
        'saml2',
        'oidc',
        'oauth2',
        'ldap',
        'cas',
        'shibboleth',
    ]

    def __init__(self, db_manager, activity_logger, current_user_getter):
        """
        Initialize the SSOManager.

        Parameters:
            db_manager: Database manager instance
            activity_logger: Activity logger callable with signature
                             (username, action, details, user_id)
            current_user_getter: Callable that returns the current user dict
        """
        self.db_manager = db_manager
        self.activity_logger = activity_logger
        self.get_current_user = current_user_getter

    def _check_permission(self, permission: str = 'manage_sso_providers') -> Optional[Dict]:
        """
        Check if the current user has the required permission.

        Parameters:
            permission: Permission name to check (default: 'manage_sso_providers')

        Returns:
            dict: Current user dict if authorized, None otherwise
        """
        current_user = self.get_current_user()
        if not current_user:
            logger.warning("SSO operation attempted without authenticated user")
            return None
        if permission not in current_user.get('permissions', []):
            logger.warning(
                f"User '{current_user.get('username')}' lacks '{permission}' permission"
            )
            return None
        return current_user

    def _serialize_config(self, config: Dict) -> str:
        """
        Serialize provider configuration to JSON string.

        Parameters:
            config: Configuration dictionary to serialize

        Returns:
            str: JSON string representation of the config
        """
        return json.dumps(config, default=str)

    def _deserialize_config(self, config_str: Optional[str]) -> Dict:
        """
        Deserialize provider configuration from JSON string.

        Parameters:
            config_str: JSON string to deserialize

        Returns:
            dict: Deserialized configuration dictionary
        """
        if not config_str:
            return {}
        try:
            return json.loads(config_str)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to deserialize SSO provider config")
            return {}

    def configure_provider(
        self,
        provider_id: str,
        provider_type: str,
        display_name: str,
        config: Dict,
    ) -> Dict[str, Any]:
        """
        Configure a new SSO provider.

        Creates a new SSO provider entry in the database with the specified
        type, display name, and configuration. Requires 'manage_sso_providers'
        permission.

        Parameters:
            provider_id: Unique identifier for the provider (e.g. 'azure-ad')
            provider_type: Type of SSO protocol (saml2, oidc, oauth2, ldap, cas, shibboleth)
            display_name: Human-readable name for the provider
            config: Provider-specific configuration dictionary

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether operation succeeded
                  - provider_id: str - Provider ID (if successful)
                  - message: str - Result message
        """
        current_user = self._check_permission()
        if not current_user:
            return {
                'success': False,
                'message': 'Permission denied. Requires manage_sso_providers permission.',
            }

        if not provider_id or not provider_id.strip():
            return {'success': False, 'message': 'Provider ID is required.'}

        if not display_name or not display_name.strip():
            return {'success': False, 'message': 'Display name is required.'}

        if provider_type not in self.SUPPORTED_PROVIDER_TYPES:
            return {
                'success': False,
                'message': (
                    f"Unsupported provider type '{provider_type}'. "
                    f"Supported types: {', '.join(self.SUPPORTED_PROVIDER_TYPES)}"
                ),
            }

        if not isinstance(config, dict):
            return {'success': False, 'message': 'Configuration must be a dictionary.'}

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Check if provider already exists
                cursor.execute(
                    'SELECT provider_id FROM sso_providers WHERE provider_id = ?',
                    (provider_id,),
                )
                if cursor.fetchone():
                    return {
                        'success': False,
                        'message': f"SSO provider '{provider_id}' already exists.",
                    }

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                config_json = self._serialize_config(config)

                cursor.execute(
                    '''INSERT INTO sso_providers
                       (provider_id, provider_type, display_name, config_json, is_enabled, created_at, updated_at)
                       VALUES (?, ?, ?, ?, 1, ?, ?)''',
                    (provider_id, provider_type, display_name, config_json, timestamp, timestamp),
                )
                conn.commit()

            self.activity_logger(
                current_user['username'],
                f'SSO provider configured: {provider_id}',
                f'Type: {provider_type}, Display: {display_name}',
                current_user['id'],
            )

            logger.info(f"SSO provider '{provider_id}' configured by {current_user['username']}")

            return {
                'success': True,
                'provider_id': provider_id,
                'message': f"SSO provider '{display_name}' configured successfully.",
            }

        except sqlite3.IntegrityError as e:
            logger.error(f"Integrity error configuring SSO provider: {e}")
            return {
                'success': False,
                'message': f"SSO provider '{provider_id}' already exists.",
            }
        except sqlite3.Error as e:
            logger.error(f"Database error configuring SSO provider: {e}")
            return {'success': False, 'message': 'Failed to configure SSO provider.'}
        except Exception as e:
            logger.error(f"Unexpected error configuring SSO provider: {e}")
            return {'success': False, 'message': 'An unexpected error occurred.'}

    def list_providers(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        """
        List all configured SSO providers.

        Parameters:
            enabled_only: If True, only return enabled providers (default True)

        Returns:
            list: List of provider dictionaries, each containing:
                  - provider_id: str
                  - provider_type: str
                  - display_name: str
                  - enabled: bool
                  - created_at: str
                  - updated_at: str
                  Returns empty list on error.
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                if enabled_only:
                    cursor.execute(
                        '''SELECT provider_id, provider_type, display_name, is_enabled,
                                  created_at, updated_at
                           FROM sso_providers WHERE is_enabled = 1
                           ORDER BY display_name''',
                    )
                else:
                    cursor.execute(
                        '''SELECT provider_id, provider_type, display_name, is_enabled,
                                  created_at, updated_at
                           FROM sso_providers
                           ORDER BY display_name''',
                    )

                rows = cursor.fetchall()
                providers = []
                for row in rows:
                    providers.append({
                        'provider_id': row[0],
                        'provider_type': row[1],
                        'display_name': row[2],
                        'enabled': bool(row[3]),
                        'created_at': row[4],
                        'updated_at': row[5],
                    })

                return providers

        except sqlite3.Error as e:
            logger.error(f"Database error listing SSO providers: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing SSO providers: {e}")
            return []

    def get_provider_config(self, provider_id: str) -> Dict[str, Any]:
        """
        Get the full configuration for an SSO provider.

        Parameters:
            provider_id: Unique identifier of the provider

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether operation succeeded
                  - provider: dict - Full provider info including config (if successful)
                  - message: str - Result message (if failed)
        """
        current_user = self._check_permission()
        if not current_user:
            return {
                'success': False,
                'message': 'Permission denied. Requires manage_sso_providers permission.',
            }

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    '''SELECT provider_id, provider_type, display_name, config_json,
                              is_enabled, created_at, updated_at
                       FROM sso_providers WHERE provider_id = ?''',
                    (provider_id,),
                )
                row = cursor.fetchone()

                if not row:
                    return {
                        'success': False,
                        'message': f"SSO provider '{provider_id}' not found.",
                    }

                provider = {
                    'provider_id': row[0],
                    'provider_type': row[1],
                    'display_name': row[2],
                    'config': self._deserialize_config(row[3]),
                    'enabled': bool(row[4]),
                    'created_at': row[5],
                    'updated_at': row[6],
                }

                return {'success': True, 'provider': provider}

        except sqlite3.Error as e:
            logger.error(f"Database error getting SSO provider config: {e}")
            return {'success': False, 'message': 'Failed to retrieve SSO provider configuration.'}
        except Exception as e:
            logger.error(f"Unexpected error getting SSO provider config: {e}")
            return {'success': False, 'message': 'An unexpected error occurred.'}

    def update_provider(self, provider_id: str, **kwargs) -> Dict[str, Any]:
        """
        Update an SSO provider's settings.

        Parameters:
            provider_id: Unique identifier of the provider to update
            **kwargs: Fields to update. Supported fields:
                      - display_name: str - New display name
                      - provider_type: str - New provider type
                      - config: dict - New configuration (replaces existing)

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether operation succeeded
                  - message: str - Result message
        """
        current_user = self._check_permission()
        if not current_user:
            return {
                'success': False,
                'message': 'Permission denied. Requires manage_sso_providers permission.',
            }

        if not kwargs:
            return {'success': False, 'message': 'No fields to update.'}

        # Validate provider_type if provided
        if 'provider_type' in kwargs:
            if kwargs['provider_type'] not in self.SUPPORTED_PROVIDER_TYPES:
                return {
                    'success': False,
                    'message': (
                        f"Unsupported provider type '{kwargs['provider_type']}'. "
                        f"Supported types: {', '.join(self.SUPPORTED_PROVIDER_TYPES)}"
                    ),
                }

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Check provider exists
                cursor.execute(
                    'SELECT provider_id, display_name FROM sso_providers WHERE provider_id = ?',
                    (provider_id,),
                )
                existing = cursor.fetchone()
                if not existing:
                    return {
                        'success': False,
                        'message': f"SSO provider '{provider_id}' not found.",
                    }

                display_name = existing[1]
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                update_fields = []
                update_values = []

                allowed_fields = {'display_name', 'provider_type', 'config'}
                for key, value in kwargs.items():
                    if key not in allowed_fields:
                        continue
                    if key == 'config':
                        if not isinstance(value, dict):
                            return {
                                'success': False,
                                'message': 'Configuration must be a dictionary.',
                            }
                        update_fields.append('config_json = ?')
                        update_values.append(self._serialize_config(value))
                    else:
                        update_fields.append(f'{key} = ?')
                        update_values.append(value)

                if not update_fields:
                    return {'success': False, 'message': 'No valid fields to update.'}

                update_fields.append('updated_at = ?')
                update_values.append(timestamp)
                update_values.append(provider_id)

                cursor.execute(
                    f"UPDATE sso_providers SET {', '.join(update_fields)} WHERE provider_id = ?",
                    update_values,
                )
                conn.commit()

            updated_fields = [k for k in kwargs.keys() if k in allowed_fields]
            self.activity_logger(
                current_user['username'],
                f'SSO provider updated: {provider_id}',
                f'Fields updated: {", ".join(updated_fields)}',
                current_user['id'],
            )

            logger.info(f"SSO provider '{provider_id}' updated by {current_user['username']}")

            return {
                'success': True,
                'message': f"SSO provider '{display_name}' updated successfully.",
            }

        except sqlite3.Error as e:
            logger.error(f"Database error updating SSO provider: {e}")
            return {'success': False, 'message': 'Failed to update SSO provider.'}
        except Exception as e:
            logger.error(f"Unexpected error updating SSO provider: {e}")
            return {'success': False, 'message': 'An unexpected error occurred.'}

    def delete_provider(self, provider_id: str) -> Dict[str, Any]:
        """
        Delete an SSO provider.

        Permanently removes the SSO provider and its configuration from the
        database. This action cannot be undone.

        Parameters:
            provider_id: Unique identifier of the provider to delete

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether operation succeeded
                  - message: str - Result message
        """
        current_user = self._check_permission()
        if not current_user:
            return {
                'success': False,
                'message': 'Permission denied. Requires manage_sso_providers permission.',
            }

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Check provider exists
                cursor.execute(
                    'SELECT provider_id, display_name FROM sso_providers WHERE provider_id = ?',
                    (provider_id,),
                )
                existing = cursor.fetchone()
                if not existing:
                    return {
                        'success': False,
                        'message': f"SSO provider '{provider_id}' not found.",
                    }

                display_name = existing[1]

                cursor.execute(
                    'DELETE FROM sso_providers WHERE provider_id = ?',
                    (provider_id,),
                )
                conn.commit()

            self.activity_logger(
                current_user['username'],
                f'SSO provider deleted: {provider_id}',
                f'Display name: {display_name}',
                current_user['id'],
            )

            logger.info(f"SSO provider '{provider_id}' deleted by {current_user['username']}")

            return {
                'success': True,
                'message': f"SSO provider '{display_name}' has been deleted.",
            }

        except sqlite3.Error as e:
            logger.error(f"Database error deleting SSO provider: {e}")
            return {'success': False, 'message': 'Failed to delete SSO provider.'}
        except Exception as e:
            logger.error(f"Unexpected error deleting SSO provider: {e}")
            return {'success': False, 'message': 'An unexpected error occurred.'}

    def enable_provider(self, provider_id: str) -> Dict[str, Any]:
        """
        Enable an SSO provider.

        Sets the provider's enabled flag to True, making it available for
        user authentication.

        Parameters:
            provider_id: Unique identifier of the provider to enable

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether operation succeeded
                  - message: str - Result message
        """
        return self._toggle_provider(provider_id, enabled=True)

    def disable_provider(self, provider_id: str) -> Dict[str, Any]:
        """
        Disable an SSO provider.

        Sets the provider's enabled flag to False, preventing it from being
        used for user authentication.

        Parameters:
            provider_id: Unique identifier of the provider to disable

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether operation succeeded
                  - message: str - Result message
        """
        return self._toggle_provider(provider_id, enabled=False)

    def _toggle_provider(self, provider_id: str, enabled: bool) -> Dict[str, Any]:
        """
        Toggle the enabled state of an SSO provider.

        Parameters:
            provider_id: Unique identifier of the provider
            enabled: Whether to enable (True) or disable (False)

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether operation succeeded
                  - message: str - Result message
        """
        current_user = self._check_permission()
        if not current_user:
            return {
                'success': False,
                'message': 'Permission denied. Requires manage_sso_providers permission.',
            }

        action = 'enable' if enabled else 'disable'

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Check provider exists
                cursor.execute(
                    'SELECT provider_id, display_name, is_enabled FROM sso_providers WHERE provider_id = ?',
                    (provider_id,),
                )
                existing = cursor.fetchone()
                if not existing:
                    return {
                        'success': False,
                        'message': f"SSO provider '{provider_id}' not found.",
                    }

                display_name = existing[1]
                current_state = bool(existing[2])

                if current_state == enabled:
                    state_str = 'enabled' if enabled else 'disabled'
                    return {
                        'success': True,
                        'message': f"SSO provider '{display_name}' is already {state_str}.",
                    }

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    'UPDATE sso_providers SET is_enabled = ?, updated_at = ? WHERE provider_id = ?',
                    (1 if enabled else 0, timestamp, provider_id),
                )
                conn.commit()

            state_str = 'enabled' if enabled else 'disabled'
            self.activity_logger(
                current_user['username'],
                f'SSO provider {state_str}: {provider_id}',
                f'Display name: {display_name}',
                current_user['id'],
            )

            logger.info(
                f"SSO provider '{provider_id}' {state_str} by {current_user['username']}"
            )

            return {
                'success': True,
                'message': f"SSO provider '{display_name}' has been {state_str}.",
            }

        except sqlite3.Error as e:
            logger.error(f"Database error toggling SSO provider: {e}")
            return {'success': False, 'message': f'Failed to {action} SSO provider.'}
        except Exception as e:
            logger.error(f"Unexpected error toggling SSO provider: {e}")
            return {'success': False, 'message': 'An unexpected error occurred.'}
