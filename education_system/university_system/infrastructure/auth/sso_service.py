"""
Single Sign-On (SSO) Orchestration Service

Coordinates SSO login flows using pluggable provider implementations
(SAML 2.0, OpenID Connect). Manages provider registration, identity
linking, user provisioning, and SSO session lifecycle.

Architecture:
    SSOService (this file)
        ├── SAMLProvider (sso_providers.py) - SAML 2.0 integration
        ├── OIDCProvider (sso_providers.py) - OpenID Connect integration
        ├── DatabaseManager  - SSO table operations
        └── ActivityLogger   - Audit trail for SSO events

Database Tables:
    sso_providers    - Registered identity provider configurations
    sso_identities   - Links between local users and external SSO identities
    sso_sessions     - Active SSO sessions with token metadata

Features:
    - Multi-provider support (SAML, OIDC)
    - Automatic user provisioning on first SSO login
    - Identity linking/unlinking for existing accounts
    - Secure token storage (hashed access tokens)
    - Comprehensive audit logging for compliance
    - Graceful degradation when provider libraries are unavailable
"""

import hashlib
import json
import logging
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.infrastructure.exceptions import (
    AuthenticationError,
    ConfigurationError,
    DatabaseError,
    ValidationError,
)

# Conditionally import SSO provider implementations
try:
    from education_system.university_system.infrastructure.auth.sso_providers import SAMLProvider
    SAML_AVAILABLE = True
except ImportError:
    SAMLProvider = None
    SAML_AVAILABLE = False

try:
    from education_system.university_system.infrastructure.auth.sso_providers import OIDCProvider
    OIDC_AVAILABLE = True
except ImportError:
    OIDCProvider = None
    OIDC_AVAILABLE = False

# Import immutable audit logging for compliance
try:
    from education_system.university_system.infrastructure.security.audit_helpers import safe_log_security_event
    from education_system.university_system.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False

__all__ = ['SSOService']

logger = logging.getLogger(__name__)

# Supported provider types and their availability
PROVIDER_TYPES = {
    'saml': {
        'label': 'SAML 2.0',
        'available': SAML_AVAILABLE,
        'class': SAMLProvider,
    },
    'oidc': {
        'label': 'OpenID Connect',
        'available': OIDC_AVAILABLE,
        'class': OIDCProvider,
    },
}

# Schema definitions for SSO tables
SSO_PROVIDERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS sso_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id TEXT UNIQUE NOT NULL,
    provider_type TEXT NOT NULL,
    display_name TEXT NOT NULL,
    config_json TEXT NOT NULL DEFAULT '{}',
    is_enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

SSO_IDENTITIES_SCHEMA = """
CREATE TABLE IF NOT EXISTS sso_identities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    provider_id TEXT NOT NULL,
    external_id TEXT NOT NULL,
    external_email TEXT,
    attributes_json TEXT DEFAULT '{}',
    last_login_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(provider_id, external_id)
)
"""

SSO_SESSIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS sso_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    provider_id TEXT NOT NULL,
    session_index TEXT,
    access_token_hash TEXT,
    token_expires_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


class SSOService:
    """
    SSO orchestration service that coordinates login flows across
    multiple identity providers.

    This service manages the full SSO lifecycle: provider registration,
    authentication initiation, callback handling, user provisioning,
    and identity linking. It delegates protocol-specific work to
    pluggable provider implementations (SAMLProvider, OIDCProvider).

    Attributes
    ----------
    db_manager : DatabaseConnectionManager
        Database manager instance for connection pooling.
    activity_logger : callable
        Callable with signature (username, action, details, user_id)
        used to record audit trail entries.
    _provider_cache : dict
        In-memory cache of instantiated provider objects keyed by provider_id.

    Examples
    --------
    >>> sso = SSOService(db_manager, activity_logger)
    >>> sso.register_provider('azure-ad', 'oidc', 'Azure AD', {
    ...     'client_id': '...',
    ...     'client_secret': '...',
    ...     'discovery_url': 'https://login.microsoftonline.com/...'
    ... })
    >>> result = sso.initiate_sso_login('azure-ad')
    >>> print(result['auth_url'])
    """

    def __init__(self, db_manager, activity_logger):
        """
        Initialize the SSO service.

        Parameters
        ----------
        db_manager : DatabaseConnectionManager
            Database connection manager that provides get_connection()
            context manager for thread-safe database access.
        activity_logger : callable
            Logging callable with signature
            (username: str, action: str, details: str, user_id: int).

        Raises
        ------
        ValueError
            If db_manager or activity_logger is None.
        """
        if db_manager is None:
            raise ValueError("db_manager is required for SSOService")
        if activity_logger is None:
            raise ValueError("activity_logger is required for SSOService")

        self.db_manager = db_manager
        self.activity_logger = activity_logger
        self._provider_cache: Dict[str, Any] = {}

        # Ensure SSO database tables exist
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Schema initialization
    # ------------------------------------------------------------------

    def _ensure_schema(self):
        """
        Create SSO database tables if they do not already exist.

        This method is called once during initialization. It creates the
        sso_providers, sso_identities, and sso_sessions tables using
        CREATE TABLE IF NOT EXISTS, making it safe to call repeatedly.
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(SSO_PROVIDERS_SCHEMA)
                cursor.execute(SSO_IDENTITIES_SCHEMA)
                cursor.execute(SSO_SESSIONS_SCHEMA)
                conn.commit()
                logger.debug("SSO schema ensured successfully")
        except sqlite3.Error as e:
            logger.error(f"Failed to ensure SSO schema: {e}")
            raise DatabaseError(f"SSO schema initialization failed: {e}")

    # ------------------------------------------------------------------
    # Provider management
    # ------------------------------------------------------------------

    def register_provider(self, provider_id, provider_type, display_name, config):
        """
        Register a new SSO identity provider.

        Validates the provider type, stores the configuration in the database,
        and logs the registration event for audit purposes.

        Parameters
        ----------
        provider_id : str
            Unique identifier for the provider (e.g. 'azure-ad', 'okta').
        provider_type : str
            Provider protocol type. Must be one of: 'saml', 'oidc'.
        display_name : str
            Human-readable name shown in the login UI.
        config : dict
            Provider-specific configuration (client_id, endpoints, etc.).
            Stored as JSON in the database.

        Returns
        -------
        dict
            Result dictionary with keys:
            - 'success' (bool): Whether registration succeeded.
            - 'provider_id' (str): The registered provider ID.
            - 'message' (str): Human-readable status message.

        Raises
        ------
        ValidationError
            If provider_id, display_name, or config is empty/invalid.
        ConfigurationError
            If the provider_type is not supported or its library is unavailable.
        DatabaseError
            If a database operation fails.
        """
        # Input validation
        if not provider_id or not isinstance(provider_id, str):
            raise ValidationError("provider_id must be a non-empty string")
        if not display_name or not isinstance(display_name, str):
            raise ValidationError("display_name must be a non-empty string")
        if not isinstance(config, dict):
            raise ValidationError("config must be a dictionary")

        provider_id = provider_id.strip().lower()
        provider_type = str(provider_type).strip().lower()

        # Validate provider type
        if provider_type not in PROVIDER_TYPES:
            supported = ', '.join(PROVIDER_TYPES.keys())
            raise ConfigurationError(
                f"Unsupported provider type '{provider_type}'. "
                f"Supported types: {supported}"
            )

        provider_info = PROVIDER_TYPES[provider_type]
        if not provider_info['available']:
            raise ConfigurationError(
                f"Provider type '{provider_type}' ({provider_info['label']}) "
                f"is not available. Required library is not installed."
            )

        config_json = json.dumps(config)
        now = datetime.now().isoformat()

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Check if provider already exists
                cursor.execute(
                    "SELECT id FROM sso_providers WHERE provider_id = ?",
                    (provider_id,)
                )
                existing = cursor.fetchone()

                if existing:
                    # Update existing provider
                    cursor.execute(
                        """UPDATE sso_providers
                           SET provider_type = ?, display_name = ?,
                               config_json = ?, updated_at = ?
                           WHERE provider_id = ?""",
                        (provider_type, display_name, config_json, now, provider_id)
                    )
                    conn.commit()
                    action_detail = "updated"
                else:
                    # Insert new provider
                    cursor.execute(
                        """INSERT INTO sso_providers
                           (provider_id, provider_type, display_name, config_json,
                            is_enabled, created_at, updated_at)
                           VALUES (?, ?, ?, ?, 1, ?, ?)""",
                        (provider_id, provider_type, display_name,
                         config_json, now, now)
                    )
                    conn.commit()
                    action_detail = "registered"

            # Clear provider cache so next use picks up new config
            self._provider_cache.pop(provider_id, None)

            self.activity_logger(
                'system',
                f'SSO provider {action_detail}: {provider_id}',
                f'Type: {provider_type}, Name: {display_name}',
                None
            )

            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    AuditAction.CONFIG_CHANGE,
                    f"SSO provider {action_detail}: {provider_id} ({provider_type})",
                    username='system'
                )

            logger.info(f"SSO provider {action_detail}: {provider_id} ({provider_type})")

            return {
                'success': True,
                'provider_id': provider_id,
                'message': f"Provider '{display_name}' {action_detail} successfully",
            }

        except sqlite3.IntegrityError as e:
            logger.error(f"Integrity error registering SSO provider: {e}")
            raise DatabaseError(f"Failed to register SSO provider: {e}")
        except sqlite3.Error as e:
            logger.error(f"Database error registering SSO provider: {e}")
            raise DatabaseError(f"Failed to register SSO provider: {e}")

    def get_provider(self, provider_id):
        """
        Retrieve a provider's configuration from the database.

        Parameters
        ----------
        provider_id : str
            Unique identifier of the provider.

        Returns
        -------
        dict or None
            Provider configuration dict with keys: id, provider_id,
            provider_type, display_name, config, is_enabled, created_at,
            updated_at. Returns None if the provider does not exist.
        """
        if not provider_id:
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT id, provider_id, provider_type, display_name,
                              config_json, is_enabled, created_at, updated_at
                       FROM sso_providers
                       WHERE provider_id = ?""",
                    (provider_id,)
                )
                row = cursor.fetchone()

                if not row:
                    return None

                return {
                    'id': row[0],
                    'provider_id': row[1],
                    'provider_type': row[2],
                    'display_name': row[3],
                    'config': json.loads(row[4]) if row[4] else {},
                    'is_enabled': bool(row[5]),
                    'created_at': row[6],
                    'updated_at': row[7],
                }

        except sqlite3.Error as e:
            logger.error(f"Database error fetching SSO provider '{provider_id}': {e}")
            return None

    def list_providers(self, enabled_only=True):
        """
        List all configured SSO providers.

        Parameters
        ----------
        enabled_only : bool, optional
            If True (default), only return enabled providers.
            If False, return all providers including disabled ones.

        Returns
        -------
        list of dict
            List of provider configuration dictionaries. Each dict contains:
            id, provider_id, provider_type, display_name, config,
            is_enabled, created_at, updated_at.
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                if enabled_only:
                    cursor.execute(
                        """SELECT id, provider_id, provider_type, display_name,
                                  config_json, is_enabled, created_at, updated_at
                           FROM sso_providers
                           WHERE is_enabled = 1
                           ORDER BY display_name""",
                    )
                else:
                    cursor.execute(
                        """SELECT id, provider_id, provider_type, display_name,
                                  config_json, is_enabled, created_at, updated_at
                           FROM sso_providers
                           ORDER BY display_name""",
                    )

                rows = cursor.fetchall()
                providers = []
                for row in rows:
                    providers.append({
                        'id': row[0],
                        'provider_id': row[1],
                        'provider_type': row[2],
                        'display_name': row[3],
                        'config': json.loads(row[4]) if row[4] else {},
                        'is_enabled': bool(row[5]),
                        'created_at': row[6],
                        'updated_at': row[7],
                    })

                return providers

        except sqlite3.Error as e:
            logger.error(f"Database error listing SSO providers: {e}")
            return []

    # ------------------------------------------------------------------
    # SSO login flow
    # ------------------------------------------------------------------

    def _get_provider_instance(self, provider_id):
        """
        Get or create a provider protocol handler instance.

        Looks up the provider configuration in the database, determines
        the correct protocol handler class, and returns an instantiated
        handler. Results are cached in memory for reuse.

        Parameters
        ----------
        provider_id : str
            Unique identifier of the provider.

        Returns
        -------
        object
            An instantiated provider handler (SAMLProvider or OIDCProvider).

        Raises
        ------
        AuthenticationError
            If the provider is not found, not enabled, or its type is
            unsupported / unavailable.
        """
        # Return cached instance if available
        if provider_id in self._provider_cache:
            return self._provider_cache[provider_id]

        provider_data = self.get_provider(provider_id)
        if not provider_data:
            raise AuthenticationError(
                f"SSO provider '{provider_id}' not found"
            )

        if not provider_data['is_enabled']:
            raise AuthenticationError(
                f"SSO provider '{provider_id}' is currently disabled"
            )

        provider_type = provider_data['provider_type']
        type_info = PROVIDER_TYPES.get(provider_type)

        if not type_info:
            raise AuthenticationError(
                f"Unknown provider type '{provider_type}' for provider '{provider_id}'"
            )

        if not type_info['available']:
            raise AuthenticationError(
                f"Provider type '{provider_type}' ({type_info['label']}) "
                f"library is not installed"
            )

        provider_class = type_info['class']
        config = provider_data['config']

        try:
            instance = provider_class(provider_id, config)
            self._provider_cache[provider_id] = instance
            return instance
        except Exception as e:
            logger.error(
                f"Failed to instantiate provider '{provider_id}' "
                f"({provider_type}): {e}"
            )
            raise AuthenticationError(
                f"Failed to initialize SSO provider '{provider_id}': {e}"
            )

    def initiate_sso_login(self, provider_id):
        """
        Start the SSO login flow for a given provider.

        Generates a unique state parameter for CSRF protection, constructs
        the authorization URL via the provider handler, and returns the
        URL for the client to redirect the user to the identity provider.

        For CLI usage, a localhost temporary HTTP server would receive the
        OAuth callback. For now, this method returns the authorization URL
        for the caller to handle redirection.

        Parameters
        ----------
        provider_id : str
            Unique identifier of the provider to authenticate against.

        Returns
        -------
        dict
            Result dictionary with keys:
            - 'success' (bool): Whether URL generation succeeded.
            - 'auth_url' (str): The authorization URL to redirect the user to.
            - 'state' (str): The CSRF state token to validate on callback.
            - 'provider_id' (str): Echo of the provider identifier.

        Raises
        ------
        AuthenticationError
            If the provider is not found, disabled, or URL generation fails.
        """
        if not provider_id:
            raise AuthenticationError("provider_id is required")

        provider_instance = self._get_provider_instance(provider_id)

        # Generate CSRF state token
        state = secrets.token_urlsafe(32)

        try:
            auth_url = provider_instance.get_authorization_url(state=state)
        except Exception as e:
            logger.error(
                f"Failed to generate auth URL for provider '{provider_id}': {e}"
            )
            raise AuthenticationError(
                f"Failed to initiate SSO login with '{provider_id}': {e}"
            )

        self.activity_logger(
            'system',
            f'SSO login initiated: {provider_id}',
            f'State token generated',
            None
        )

        logger.info(f"SSO login initiated for provider '{provider_id}'")

        return {
            'success': True,
            'auth_url': auth_url,
            'state': state,
            'provider_id': provider_id,
        }

    def handle_sso_callback(self, provider_id, callback_data):
        """
        Process the SSO callback after the user authenticates with the IdP.

        Validates the callback response (state, authorization code, SAML
        assertion), exchanges it for user identity attributes, and stores
        an SSO session record.

        Parameters
        ----------
        provider_id : str
            Unique identifier of the provider.
        callback_data : dict
            Data received from the IdP callback. Expected keys vary by
            provider type but typically include:
            - 'code' (str): Authorization code (OIDC).
            - 'state' (str): CSRF state token for validation.
            - 'SAMLResponse' (str): Base64-encoded SAML assertion (SAML).

        Returns
        -------
        dict
            Result dictionary with keys:
            - 'success' (bool): Whether callback handling succeeded.
            - 'external_id' (str): User identifier from the IdP.
            - 'email' (str): User email from the IdP.
            - 'display_name' (str): User display name from the IdP.
            - 'attributes' (dict): All user attributes from the IdP.
            - 'provider_id' (str): Echo of the provider identifier.

        Raises
        ------
        AuthenticationError
            If callback validation fails or user attributes cannot be
            extracted.
        ValidationError
            If callback_data is missing or malformed.
        """
        if not provider_id:
            raise AuthenticationError("provider_id is required")
        if not callback_data or not isinstance(callback_data, dict):
            raise ValidationError("callback_data must be a non-empty dictionary")

        provider_instance = self._get_provider_instance(provider_id)

        try:
            # Delegate to provider-specific callback handling
            identity = provider_instance.handle_callback(callback_data)
        except Exception as e:
            logger.error(
                f"SSO callback handling failed for provider '{provider_id}': {e}"
            )
            self.activity_logger(
                'system',
                f'SSO callback failed: {provider_id}',
                f'Error: {str(e)[:200]}',
                None
            )
            raise AuthenticationError(
                f"SSO authentication failed for provider '{provider_id}': {e}"
            )

        # Validate required identity fields
        external_id = identity.get('external_id') or identity.get('sub') or identity.get('name_id')
        email = identity.get('email', '')
        display_name = identity.get('display_name') or identity.get('name', '')
        attributes = identity.get('attributes', {})

        if not external_id:
            logger.error(
                f"SSO callback for '{provider_id}' returned no external_id"
            )
            raise AuthenticationError(
                f"Identity provider '{provider_id}' did not return a user identifier"
            )

        # Store SSO session record with hashed access token
        access_token = identity.get('access_token', '')
        session_index = identity.get('session_index', '')
        token_expires_at = identity.get('token_expires_at', '')

        self._store_sso_session(
            provider_id=provider_id,
            external_id=external_id,
            access_token=access_token,
            session_index=session_index,
            token_expires_at=token_expires_at,
        )

        self.activity_logger(
            'system',
            f'SSO callback processed: {provider_id}',
            f'External ID: {external_id[:50]}, Email: {email[:50]}',
            None
        )

        if IMMUTABLE_AUDIT_AVAILABLE:
            safe_log_security_event(
                AuditAction.USER_LOGIN,
                f"SSO callback success: provider={provider_id}, "
                f"external_id={external_id[:50]}",
                username='system'
            )

        logger.info(
            f"SSO callback processed for provider '{provider_id}', "
            f"external_id='{external_id[:50]}'"
        )

        return {
            'success': True,
            'external_id': external_id,
            'email': email,
            'display_name': display_name,
            'attributes': attributes,
            'provider_id': provider_id,
        }

    def _store_sso_session(self, provider_id, external_id, access_token='',
                           session_index='', token_expires_at=''):
        """
        Store an SSO session record in the database.

        Access tokens are stored as SHA-256 hashes for security. The
        original token is never persisted.

        Parameters
        ----------
        provider_id : str
            Provider identifier.
        external_id : str
            External user identifier (used to look up user_id).
        access_token : str, optional
            Raw access token to hash and store.
        session_index : str, optional
            SAML session index or OIDC session identifier.
        token_expires_at : str, optional
            ISO-format expiration timestamp for the token.
        """
        access_token_hash = ''
        if access_token:
            access_token_hash = hashlib.sha256(
                access_token.encode('utf-8')
            ).hexdigest()

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Look up local user_id from sso_identities
                cursor.execute(
                    """SELECT user_id FROM sso_identities
                       WHERE provider_id = ? AND external_id = ?""",
                    (provider_id, external_id)
                )
                row = cursor.fetchone()
                user_id = row[0] if row else 0

                cursor.execute(
                    """INSERT INTO sso_sessions
                       (user_id, provider_id, session_index,
                        access_token_hash, token_expires_at, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (user_id, provider_id, session_index,
                     access_token_hash, token_expires_at,
                     datetime.now().isoformat())
                )
                conn.commit()

        except sqlite3.Error as e:
            # Session storage failure is non-fatal; log and continue
            logger.warning(f"Failed to store SSO session for '{provider_id}'")

    # ------------------------------------------------------------------
    # User provisioning and identity linking
    # ------------------------------------------------------------------

    def find_or_provision_user(self, provider_id, sso_identity):
        """
        Find an existing local user by SSO identity or email match,
        or create (provision) a new user account.

        The lookup order is:
        1. Match by (provider_id, external_id) in sso_identities.
        2. Match by email in user_accounts.
        3. Provision a new user account.

        When a new user is provisioned, a corresponding sso_identities
        record is also created to link the accounts.

        Parameters
        ----------
        provider_id : str
            Unique identifier of the SSO provider.
        sso_identity : dict
            Identity attributes from the IdP callback, expected keys:
            - 'external_id' (str): Required. User ID from the IdP.
            - 'email' (str): User email address.
            - 'display_name' (str): User display name.
            - 'attributes' (dict): Additional IdP attributes.

        Returns
        -------
        dict
            Result dictionary with keys:
            - 'success' (bool): Whether the operation succeeded.
            - 'user_id' (int): Local user ID.
            - 'username' (str): Local username.
            - 'is_new_user' (bool): True if a new account was created.
            - 'message' (str): Human-readable status message.

        Raises
        ------
        ValidationError
            If sso_identity is missing required fields.
        DatabaseError
            If a database operation fails.
        """
        if not sso_identity or not isinstance(sso_identity, dict):
            raise ValidationError("sso_identity must be a non-empty dictionary")

        external_id = sso_identity.get('external_id', '')
        email = sso_identity.get('email', '')
        display_name = sso_identity.get('display_name', '')
        attributes = sso_identity.get('attributes', {})

        if not external_id:
            raise ValidationError("sso_identity must contain 'external_id'")

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Step 1: Check for existing SSO identity link
                cursor.execute(
                    """SELECT user_id FROM sso_identities
                       WHERE provider_id = ? AND external_id = ?""",
                    (provider_id, external_id)
                )
                row = cursor.fetchone()

                if row:
                    user_id = row[0]
                    # Update last login timestamp
                    cursor.execute(
                        """UPDATE sso_identities
                           SET last_login_at = ?
                           WHERE provider_id = ? AND external_id = ?""",
                        (datetime.now().isoformat(), provider_id, external_id)
                    )
                    conn.commit()

                    # Fetch username
                    cursor.execute(
                        "SELECT username FROM user_accounts WHERE user_id = ?",
                        (user_id,)
                    )
                    user_row = cursor.fetchone()
                    username = user_row[0] if user_row else f'sso_{external_id[:20]}'

                    self.activity_logger(
                        username,
                        f'SSO login (existing identity): {provider_id}',
                        f'External ID: {external_id[:50]}',
                        user_id
                    )

                    return {
                        'success': True,
                        'user_id': user_id,
                        'username': username,
                        'is_new_user': False,
                        'message': 'Existing SSO identity matched',
                    }

                # Step 2: Check for email match in user_accounts
                if email:
                    cursor.execute(
                        "SELECT user_id, username FROM user_accounts WHERE email = ?",
                        (email,)
                    )
                    user_row = cursor.fetchone()

                    if user_row:
                        user_id = user_row[0]
                        username = user_row[1]

                        # Link SSO identity to existing account
                        self._create_identity_link(
                            conn, user_id, provider_id, external_id,
                            email, attributes
                        )
                        conn.commit()

                        self.activity_logger(
                            username,
                            f'SSO identity linked by email: {provider_id}',
                            f'External ID: {external_id[:50]}, Email: {email}',
                            user_id
                        )

                        return {
                            'success': True,
                            'user_id': user_id,
                            'username': username,
                            'is_new_user': False,
                            'message': 'Existing user matched by email, SSO identity linked',
                        }

                # Step 3: Provision a new user
                username = self._generate_sso_username(cursor, email, external_id)
                now = datetime.now().isoformat()

                cursor.execute(
                    """INSERT INTO user_accounts
                       (username, email, role, is_active, created_at)
                       VALUES (?, ?, 'student', 1, ?)""",
                    (username, email, now)
                )
                user_id = cursor.lastrowid

                # Link SSO identity to new account
                self._create_identity_link(
                    conn, user_id, provider_id, external_id,
                    email, attributes
                )
                conn.commit()

                self.activity_logger(
                    username,
                    f'SSO user provisioned: {provider_id}',
                    f'External ID: {external_id[:50]}, Email: {email}',
                    user_id
                )

                if IMMUTABLE_AUDIT_AVAILABLE:
                    safe_log_security_event(
                        AuditAction.USER_CREATE,
                        f"SSO user provisioned: {username} via {provider_id}",
                        username='system'
                    )

                logger.info(
                    f"New user provisioned via SSO: {username} "
                    f"(provider={provider_id})"
                )

                return {
                    'success': True,
                    'user_id': user_id,
                    'username': username,
                    'is_new_user': True,
                    'message': f'New user account created: {username}',
                }

        except sqlite3.Error as e:
            logger.error(f"Database error in find_or_provision_user: {e}")
            raise DatabaseError(f"Failed to find or provision SSO user: {e}")

    def _generate_sso_username(self, cursor, email, external_id):
        """
        Generate a unique username for an SSO-provisioned user.

        Attempts to derive the username from the email local part. Falls
        back to the external_id prefix. Appends numeric suffixes to
        resolve collisions.

        Parameters
        ----------
        cursor : sqlite3.Cursor
            Active database cursor for uniqueness checks.
        email : str
            User email address (may be empty).
        external_id : str
            External user identifier.

        Returns
        -------
        str
            A unique username string.
        """
        # Derive base username from email or external_id
        if email and '@' in email:
            base = email.split('@')[0].lower()
        else:
            base = f"sso_{external_id[:20].lower()}"

        # Sanitize: keep only alphanumeric and underscores
        sanitized = ''.join(c if c.isalnum() or c == '_' else '_' for c in base)
        if not sanitized:
            sanitized = 'sso_user'

        # Check uniqueness and append suffix if needed
        candidate = sanitized
        suffix = 1
        while True:
            cursor.execute(
                "SELECT COUNT(*) FROM user_accounts WHERE username = ?",
                (candidate,)
            )
            count = cursor.fetchone()[0]
            if count == 0:
                return candidate
            candidate = f"{sanitized}_{suffix}"
            suffix += 1
            if suffix > 9999:
                # Fallback to random suffix
                return f"{sanitized}_{secrets.token_hex(4)}"

    def _create_identity_link(self, conn, user_id, provider_id, external_id,
                              email, attributes):
        """
        Create an sso_identities record linking a local user to an external
        identity.

        Parameters
        ----------
        conn : sqlite3.Connection
            Active database connection (caller manages commit).
        user_id : int
            Local user ID.
        provider_id : str
            SSO provider identifier.
        external_id : str
            External user identifier from the IdP.
        email : str
            External email address.
        attributes : dict
            Additional IdP attributes to store.
        """
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO sso_identities
               (user_id, provider_id, external_id, external_email,
                attributes_json, last_login_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, provider_id, external_id, email,
             json.dumps(attributes) if attributes else '{}',
             datetime.now().isoformat(),
             datetime.now().isoformat())
        )

    # ------------------------------------------------------------------
    # Identity linking / unlinking
    # ------------------------------------------------------------------

    def link_sso_identity(self, user_id, provider_id, external_id,
                          external_email, attributes=None):
        """
        Link an SSO identity to an existing local user account.

        This allows a user to add SSO login capability to their existing
        account without going through the full provisioning flow.

        Parameters
        ----------
        user_id : int
            Local user ID to link the identity to.
        provider_id : str
            SSO provider identifier.
        external_id : str
            External user identifier from the IdP.
        external_email : str
            Email address associated with the external identity.
        attributes : dict, optional
            Additional IdP attributes to store.

        Returns
        -------
        dict
            Result dictionary with keys:
            - 'success' (bool): Whether linking succeeded.
            - 'identity_id' (int): ID of the new sso_identities record.
            - 'message' (str): Human-readable status message.

        Raises
        ------
        ValidationError
            If required parameters are missing.
        DatabaseError
            If the identity already exists or a database operation fails.
        """
        if not user_id:
            raise ValidationError("user_id is required")
        if not provider_id:
            raise ValidationError("provider_id is required")
        if not external_id:
            raise ValidationError("external_id is required")

        attributes = attributes or {}

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Check for existing link
                cursor.execute(
                    """SELECT id FROM sso_identities
                       WHERE provider_id = ? AND external_id = ?""",
                    (provider_id, external_id)
                )
                existing = cursor.fetchone()
                if existing:
                    raise DatabaseError(
                        f"External ID '{external_id}' is already linked to a user "
                        f"for provider '{provider_id}'"
                    )

                # Check that user exists
                cursor.execute(
                    "SELECT username FROM user_accounts WHERE user_id = ?",
                    (user_id,)
                )
                user_row = cursor.fetchone()
                if not user_row:
                    raise ValidationError(f"User with ID {user_id} not found")

                username = user_row[0]

                cursor.execute(
                    """INSERT INTO sso_identities
                       (user_id, provider_id, external_id, external_email,
                        attributes_json, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (user_id, provider_id, external_id, external_email,
                     json.dumps(attributes),
                     datetime.now().isoformat())
                )
                identity_id = cursor.lastrowid
                conn.commit()

            self.activity_logger(
                username,
                f'SSO identity linked: {provider_id}',
                f'External ID: {external_id[:50]}, Email: {external_email}',
                user_id
            )

            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    AuditAction.CONFIG_CHANGE,
                    f"SSO identity linked: user={username}, provider={provider_id}",
                    username=username
                )

            logger.info(
                f"SSO identity linked: user_id={user_id}, "
                f"provider={provider_id}, external_id={external_id[:50]}"
            )

            return {
                'success': True,
                'identity_id': identity_id,
                'message': f"SSO identity linked to user '{username}' successfully",
            }

        except (DatabaseError, ValidationError):
            raise
        except sqlite3.IntegrityError as e:
            logger.error(f"Integrity error linking SSO identity: {e}")
            raise DatabaseError(f"Failed to link SSO identity: {e}")
        except sqlite3.Error as e:
            logger.error(f"Database error linking SSO identity: {e}")
            raise DatabaseError(f"Failed to link SSO identity: {e}")

    def unlink_sso_identity(self, identity_id):
        """
        Remove an SSO identity link.

        Deletes the sso_identities record, preventing future SSO logins
        via that external identity. Does not delete the local user account
        or any SSO session records.

        Parameters
        ----------
        identity_id : int
            Primary key of the sso_identities record to remove.

        Returns
        -------
        dict
            Result dictionary with keys:
            - 'success' (bool): Whether unlinking succeeded.
            - 'message' (str): Human-readable status message.

        Raises
        ------
        ValidationError
            If identity_id is missing or the identity does not exist.
        DatabaseError
            If a database operation fails.
        """
        if not identity_id:
            raise ValidationError("identity_id is required")

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Fetch identity details for logging
                cursor.execute(
                    """SELECT si.user_id, si.provider_id, si.external_id,
                              ua.username
                       FROM sso_identities si
                       LEFT JOIN user_accounts ua ON si.user_id = ua.user_id
                       WHERE si.id = ?""",
                    (identity_id,)
                )
                row = cursor.fetchone()

                if not row:
                    raise ValidationError(
                        f"SSO identity with ID {identity_id} not found"
                    )

                user_id = row[0]
                provider_id = row[1]
                external_id = row[2]
                username = row[3] or 'unknown'

                cursor.execute(
                    "DELETE FROM sso_identities WHERE id = ?",
                    (identity_id,)
                )
                conn.commit()

            self.activity_logger(
                username,
                f'SSO identity unlinked: {provider_id}',
                f'External ID: {external_id[:50]}',
                user_id
            )

            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    AuditAction.CONFIG_CHANGE,
                    f"SSO identity unlinked: user={username}, "
                    f"provider={provider_id}",
                    username=username
                )

            logger.info(
                f"SSO identity unlinked: identity_id={identity_id}, "
                f"user={username}, provider={provider_id}"
            )

            return {
                'success': True,
                'message': (
                    f"SSO identity for provider '{provider_id}' "
                    f"unlinked from user '{username}'"
                ),
            }

        except (ValidationError, DatabaseError):
            raise
        except sqlite3.Error as e:
            logger.error(f"Database error unlinking SSO identity: {e}")
            raise DatabaseError(f"Failed to unlink SSO identity: {e}")

    # ------------------------------------------------------------------
    # Identity queries
    # ------------------------------------------------------------------

    def get_user_sso_identities(self, user_id):
        """
        Retrieve all SSO identities linked to a local user.

        Parameters
        ----------
        user_id : int
            Local user ID to look up.

        Returns
        -------
        list of dict
            List of identity dictionaries. Each dict contains: id, user_id,
            provider_id, external_id, external_email, attributes,
            last_login_at, created_at, provider_display_name.
            Returns an empty list if the user has no linked SSO identities
            or if user_id is invalid.
        """
        if not user_id:
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT si.id, si.user_id, si.provider_id, si.external_id,
                              si.external_email, si.attributes_json,
                              si.last_login_at, si.created_at,
                              sp.display_name
                       FROM sso_identities si
                       LEFT JOIN sso_providers sp
                           ON si.provider_id = sp.provider_id
                       WHERE si.user_id = ?
                       ORDER BY si.created_at""",
                    (user_id,)
                )
                rows = cursor.fetchall()

                identities = []
                for row in rows:
                    identities.append({
                        'id': row[0],
                        'user_id': row[1],
                        'provider_id': row[2],
                        'external_id': row[3],
                        'external_email': row[4],
                        'attributes': json.loads(row[5]) if row[5] else {},
                        'last_login_at': row[6],
                        'created_at': row[7],
                        'provider_display_name': row[8] or row[2],
                    })

                return identities

        except sqlite3.Error as e:
            logger.error(
                f"Database error fetching SSO identities for user {user_id}: {e}"
            )
            return []
