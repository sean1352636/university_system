"""
WebAuthn/FIDO2 Authentication Service

Provides WebAuthn (Web Authentication) support for passwordless and
second-factor authentication using FIDO2 security keys, platform
authenticators (Touch ID, Windows Hello), and other WebAuthn-compatible
devices.

Features:
- Registration (attestation) flow for new credentials
- Authentication (assertion) flow for login
- Credential management (list, rename, revoke)
- Challenge generation and verification with TTL
- Secure storage of public key credentials

Optional Dependency:
    This module requires the ``py_webauthn`` library for full functionality.
    Install with: ``pip install py-webauthn``

    If py_webauthn is not installed, all methods return error dicts
    explaining the missing dependency.

Database Tables:
    - webauthn_credentials: Stores registered credential public keys
    - webauthn_challenges: Stores temporary challenges for registration/auth

Usage:
    from education_system.university_system.infrastructure.auth.webauthn_service import WebAuthnService

    service = WebAuthnService(db_manager=db_manager, rp_id='example.com')
    result = service.begin_registration(user_id='user1', username='john', display_name='John')
    if result['success']:
        options = result['options']
        # Send options to client browser...
"""

from __future__ import annotations

import base64
import json
import logging
import secrets
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from education_system.university_system.infrastructure.database.db import sqlite3

# Import immutable audit logging for compliance
try:
    from education_system.university_system.infrastructure.security.audit_helpers import safe_log_security_event
    from education_system.university_system.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False

# Optional dependency: py_webauthn
try:
    from webauthn import (
        generate_registration_options,
        verify_registration_response,
        generate_authentication_options,
        verify_authentication_response,
        options_to_json,
    )
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria,
        PublicKeyCredentialDescriptor,
        PublicKeyCredentialType,
        ResidentKeyRequirement,
        UserVerificationRequirement,
        AuthenticatorTransport,
        RegistrationCredential,
        AuthenticationCredential,
    )
    from webauthn.helpers import bytes_to_base64url, base64url_to_bytes
    WEBAUTHN_AVAILABLE = True
except ImportError:
    WEBAUTHN_AVAILABLE = False

logger = logging.getLogger(__name__)

# Default challenge TTL in seconds
DEFAULT_CHALLENGE_TTL = 300

# Supported authenticator transports for credential descriptors
SUPPORTED_TRANSPORTS = ['usb', 'ble', 'nfc', 'internal']


class WebAuthnService:
    """WebAuthn/FIDO2 authentication service.

    Handles the full WebAuthn registration and authentication lifecycle,
    including challenge generation, credential storage, and assertion
    verification.

    Parameters
    ----------
    db_manager : DatabaseConnectionManager
        Database connection manager instance providing ``get_connection()``
        context manager.
    rp_id : str, optional
        Relying party identifier (typically the domain name).
        Defaults to ``'localhost'``.
    rp_name : str, optional
        Human-readable relying party name displayed to users.
        Defaults to ``'University System'``.

    Attributes
    ----------
    db_manager : DatabaseConnectionManager
        The database connection manager.
    rp_id : str
        The relying party identifier.
    rp_name : str
        The relying party display name.

    Examples
    --------
    >>> from education_system.university_system.infrastructure.auth.managers import DatabaseConnectionManager
    >>> db_mgr = DatabaseConnectionManager('path/to/db.db')
    >>> webauthn = WebAuthnService(db_manager=db_mgr, rp_id='university.edu')
    >>> reg = webauthn.begin_registration('user1', 'jdoe', 'John Doe')
    >>> if reg['success']:
    ...     print("Send options to browser:", reg['options'])
    """

    def __init__(
        self,
        db_manager,
        rp_id: str = 'localhost',
        rp_name: str = 'University System',
    ):
        self.db_manager = db_manager
        self.rp_id = rp_id
        self.rp_name = rp_name
        self._ensure_tables()

    # =========================================================================
    # Schema Initialization
    # =========================================================================

    def _ensure_tables(self) -> None:
        """Create WebAuthn database tables if they do not exist.

        Creates the ``webauthn_credentials`` and ``webauthn_challenges``
        tables with appropriate schema for storing credential data and
        temporary authentication challenges.
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Credential storage table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS webauthn_credentials (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        credential_id TEXT NOT NULL UNIQUE,
                        user_id TEXT NOT NULL,
                        public_key BLOB NOT NULL,
                        sign_count INTEGER DEFAULT 0,
                        device_name TEXT DEFAULT 'Security Key',
                        transports TEXT DEFAULT '[]',
                        aaguid TEXT,
                        created_at TEXT NOT NULL,
                        last_used_at TEXT,
                        is_active INTEGER DEFAULT 1,
                        attestation_format TEXT,
                        credential_type TEXT DEFAULT 'public-key',
                        backup_eligible INTEGER DEFAULT 0,
                        backup_state INTEGER DEFAULT 0
                    )
                """)

                # Index for faster user lookups
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_webauthn_cred_user_id
                    ON webauthn_credentials(user_id)
                """)

                # Index for credential ID lookups
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_webauthn_cred_credential_id
                    ON webauthn_credentials(credential_id)
                """)

                # Challenge storage table with TTL support
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS webauthn_challenges (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        challenge TEXT NOT NULL,
                        challenge_type TEXT NOT NULL,
                        user_id TEXT,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        consumed INTEGER DEFAULT 0,
                        consumed_at TEXT
                    )
                """)

                # Index for session-based challenge lookups
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_webauthn_challenge_session
                    ON webauthn_challenges(session_id, consumed)
                """)

                conn.commit()
                logger.debug("WebAuthn database tables ensured")

        except sqlite3.Error as e:
            logger.error("Failed to create WebAuthn tables")

    # =========================================================================
    # Registration Flow
    # =========================================================================

    def begin_registration(
        self,
        user_id: str,
        username: str,
        display_name: str,
        session_id: Optional[str] = None,
        authenticator_selection: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Begin the WebAuthn registration (attestation) ceremony.

        Generates registration options that should be sent to the client
        browser for the WebAuthn ``navigator.credentials.create()`` call.

        Parameters
        ----------
        user_id : str
            Unique identifier for the user.
        username : str
            The user's login username.
        display_name : str
            Human-readable display name for the user.
        session_id : str, optional
            Session identifier for challenge binding.
            Generated automatically if not provided.
        authenticator_selection : dict, optional
            Override authenticator selection criteria.

        Returns
        -------
        dict
            On success: ``{'success': True, 'options': ..., 'session_id': ...}``
            On failure: ``{'success': False, 'error': ...}``
        """
        if not WEBAUTHN_AVAILABLE:
            return {
                'success': False,
                'error': 'WebAuthn support requires the py_webauthn library. '
                         'Install with: pip install py-webauthn',
            }

        if not user_id or not username:
            return {
                'success': False,
                'error': 'user_id and username are required',
            }

        if session_id is None:
            session_id = secrets.token_urlsafe(32)

        try:
            # Retrieve existing credentials for exclude list
            existing_credentials = self._get_user_credential_descriptors(user_id)

            # Generate a cryptographic challenge
            challenge = secrets.token_urlsafe(32)

            # Build registration options using py_webauthn
            options = generate_registration_options(
                rp_id=self.rp_id,
                rp_name=self.rp_name,
                user_id=user_id.encode('utf-8'),
                user_name=username,
                user_display_name=display_name,
                exclude_credentials=existing_credentials,
                authenticator_selection=AuthenticatorSelectionCriteria(
                    resident_key=ResidentKeyRequirement.PREFERRED,
                    user_verification=UserVerificationRequirement.PREFERRED,
                ),
                challenge=challenge.encode('utf-8'),
            )

            # Store the challenge for later verification
            self._store_challenge(
                challenge=challenge,
                session_id=session_id,
                challenge_type='registration',
                user_id=user_id,
            )

            # Convert options to JSON-serializable format
            options_json = json.loads(options_to_json(options))

            logger.info(
                "WebAuthn registration started for user '%s' (session: %s)",
                user_id, session_id,
            )

            return {
                'success': True,
                'options': options_json,
                'session_id': session_id,
            }

        except Exception as e:
            logger.error(
                "Failed to begin WebAuthn registration for user '%s': %s",
                user_id, e,
            )
            return {
                'success': False,
                'error': f'Failed to generate registration options: {e}',
            }

    def complete_registration(
        self,
        user_id: str,
        credential_data: Dict[str, Any],
        session_id: str,
        device_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Complete the WebAuthn registration ceremony.

        Validates the attestation response from the client browser and
        stores the new credential in the database.

        Parameters
        ----------
        user_id : str
            Unique identifier for the user.
        credential_data : dict
            The credential response from ``navigator.credentials.create()``,
            typically containing ``id``, ``rawId``, ``response``, and ``type``.
        session_id : str
            The session ID from ``begin_registration``.
        device_name : str, optional
            Human-readable name for the credential device.
            Defaults to ``'Security Key'``.

        Returns
        -------
        dict
            On success: ``{'success': True, 'credential_id': ...}``
            On failure: ``{'success': False, 'error': ...}``
        """
        if not WEBAUTHN_AVAILABLE:
            return {
                'success': False,
                'error': 'WebAuthn support requires the py_webauthn library. '
                         'Install with: pip install py-webauthn',
            }

        if not user_id or not credential_data or not session_id:
            return {
                'success': False,
                'error': 'user_id, credential_data, and session_id are required',
            }

        try:
            # Retrieve and verify the stored challenge
            challenge_record = self._verify_challenge(
                session_id=session_id,
                expected_type='registration',
            )
            if challenge_record is None:
                return {
                    'success': False,
                    'error': 'Challenge not found, expired, or already consumed',
                }

            stored_challenge = challenge_record['challenge']

            # Build the registration credential from client data
            registration_credential = RegistrationCredential.parse_raw(
                json.dumps(credential_data)
            )

            # Verify the registration response
            verification = verify_registration_response(
                credential=registration_credential,
                expected_challenge=stored_challenge.encode('utf-8'),
                expected_rp_id=self.rp_id,
                expected_origin=f"https://{self.rp_id}",
            )

            # Encode credential ID for storage
            credential_id_b64 = base64.urlsafe_b64encode(
                verification.credential_id
            ).decode('utf-8')

            # Store the credential in the database
            now = datetime.utcnow().isoformat()
            if device_name is None:
                device_name = 'Security Key'

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO webauthn_credentials (
                        credential_id, user_id, public_key, sign_count,
                        device_name, aaguid, created_at, is_active,
                        attestation_format, credential_type,
                        backup_eligible, backup_state
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, 'public-key', ?, ?)
                """, (
                    credential_id_b64,
                    user_id,
                    verification.credential_public_key,
                    verification.sign_count,
                    device_name,
                    str(verification.aaguid) if hasattr(verification, 'aaguid') else None,
                    now,
                    verification.fmt if hasattr(verification, 'fmt') else None,
                    int(verification.credential_backed_up) if hasattr(verification, 'credential_backed_up') else 0,
                    int(verification.credential_device_type == 'multi_device') if hasattr(verification, 'credential_device_type') else 0,
                ))
                conn.commit()

            logger.info(
                "WebAuthn credential registered for user '%s': %s",
                user_id, credential_id_b64[:16] + '...',
            )

            # Audit log the registration event
            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    action=AuditAction.MFA_ENABLED,
                    user_id=user_id,
                    resource_type='webauthn_credential',
                    details={
                        'credential_id': credential_id_b64[:16] + '...',
                        'device_name': device_name,
                    },
                )

            return {
                'success': True,
                'credential_id': credential_id_b64,
                'device_name': device_name,
            }

        except Exception as e:
            logger.error(
                "Failed to complete WebAuthn registration for user '%s': %s",
                user_id, e,
            )
            return {
                'success': False,
                'error': f'Registration verification failed: {e}',
            }

    # =========================================================================
    # Authentication Flow
    # =========================================================================

    def begin_authentication(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Begin the WebAuthn authentication (assertion) ceremony.

        Generates authentication options that should be sent to the client
        browser for the WebAuthn ``navigator.credentials.get()`` call.

        Parameters
        ----------
        user_id : str, optional
            If provided, restricts allowed credentials to those belonging
            to this user. If ``None``, allows any registered credential
            (usernameless/discoverable credential flow).
        session_id : str, optional
            Session identifier for challenge binding.
            Generated automatically if not provided.

        Returns
        -------
        dict
            On success: ``{'success': True, 'options': ..., 'session_id': ...}``
            On failure: ``{'success': False, 'error': ...}``
        """
        if not WEBAUTHN_AVAILABLE:
            return {
                'success': False,
                'error': 'WebAuthn support requires the py_webauthn library. '
                         'Install with: pip install py-webauthn',
            }

        if session_id is None:
            session_id = secrets.token_urlsafe(32)

        try:
            # Optionally restrict to a specific user's credentials
            allow_credentials = []
            if user_id is not None:
                allow_credentials = self._get_user_credential_descriptors(user_id)
                if not allow_credentials:
                    return {
                        'success': False,
                        'error': f'No active WebAuthn credentials found for user: {user_id}',
                    }

            # Generate a cryptographic challenge
            challenge = secrets.token_urlsafe(32)

            # Build authentication options
            options = generate_authentication_options(
                rp_id=self.rp_id,
                allow_credentials=allow_credentials if allow_credentials else None,
                user_verification=UserVerificationRequirement.PREFERRED,
                challenge=challenge.encode('utf-8'),
            )

            # Store the challenge for later verification
            self._store_challenge(
                challenge=challenge,
                session_id=session_id,
                challenge_type='authentication',
                user_id=user_id,
            )

            # Convert options to JSON-serializable format
            options_json = json.loads(options_to_json(options))

            logger.info(
                "WebAuthn authentication started (user: %s, session: %s)",
                user_id or 'discoverable', session_id,
            )

            return {
                'success': True,
                'options': options_json,
                'session_id': session_id,
            }

        except Exception as e:
            logger.error("Failed to begin WebAuthn authentication")
            return {
                'success': False,
                'error': f'Failed to generate authentication options: {e}',
            }

    def complete_authentication(
        self,
        assertion_data: Dict[str, Any],
        session_id: str,
    ) -> Dict[str, Any]:
        """Complete the WebAuthn authentication ceremony.

        Validates the assertion response from the client browser and
        returns the authenticated user's identity.

        Parameters
        ----------
        assertion_data : dict
            The credential response from ``navigator.credentials.get()``,
            typically containing ``id``, ``rawId``, ``response``, and ``type``.
        session_id : str
            The session ID from ``begin_authentication``.

        Returns
        -------
        dict
            On success: ``{'success': True, 'user_id': ..., 'credential_id': ...}``
            On failure: ``{'success': False, 'error': ...}``
        """
        if not WEBAUTHN_AVAILABLE:
            return {
                'success': False,
                'error': 'WebAuthn support requires the py_webauthn library. '
                         'Install with: pip install py-webauthn',
            }

        if not assertion_data or not session_id:
            return {
                'success': False,
                'error': 'assertion_data and session_id are required',
            }

        try:
            # Retrieve and verify the stored challenge
            challenge_record = self._verify_challenge(
                session_id=session_id,
                expected_type='authentication',
            )
            if challenge_record is None:
                return {
                    'success': False,
                    'error': 'Challenge not found, expired, or already consumed',
                }

            stored_challenge = challenge_record['challenge']

            # Extract credential ID from assertion data
            assertion_credential_id = assertion_data.get('id', '')

            # Look up the stored credential
            credential = self._get_credential_by_id(assertion_credential_id)
            if credential is None:
                return {
                    'success': False,
                    'error': 'Credential not found or has been revoked',
                }

            # Build the authentication credential from client data
            authentication_credential = AuthenticationCredential.parse_raw(
                json.dumps(assertion_data)
            )

            # Verify the authentication response
            verification = verify_authentication_response(
                credential=authentication_credential,
                expected_challenge=stored_challenge.encode('utf-8'),
                expected_rp_id=self.rp_id,
                expected_origin=f"https://{self.rp_id}",
                credential_public_key=credential['public_key'],
                credential_current_sign_count=credential['sign_count'],
            )

            # Update the sign count and last used timestamp
            now = datetime.utcnow().isoformat()
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE webauthn_credentials
                    SET sign_count = ?, last_used_at = ?
                    WHERE credential_id = ? AND is_active = 1
                """, (
                    verification.new_sign_count,
                    now,
                    credential['credential_id'],
                ))
                conn.commit()

            logger.info(
                "WebAuthn authentication successful for user '%s'",
                credential['user_id'],
            )

            # Audit log the authentication event
            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    action=AuditAction.LOGIN_SUCCESS,
                    user_id=credential['user_id'],
                    resource_type='webauthn_authentication',
                    details={
                        'credential_id': credential['credential_id'][:16] + '...',
                        'sign_count': verification.new_sign_count,
                    },
                )

            return {
                'success': True,
                'user_id': credential['user_id'],
                'credential_id': credential['credential_id'],
                'sign_count': verification.new_sign_count,
            }

        except Exception as e:
            logger.error("Failed to complete WebAuthn authentication")

            # Audit log the failed authentication
            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    action=AuditAction.LOGIN_FAILED,
                    user_id=challenge_record.get('user_id', 'unknown') if challenge_record else 'unknown',
                    resource_type='webauthn_authentication',
                    details={'error': str(e)},
                )

            return {
                'success': False,
                'error': f'Authentication verification failed: {e}',
            }

    # =========================================================================
    # Credential Management
    # =========================================================================

    def list_credentials(self, user_id: str) -> List[Dict[str, Any]]:
        """List all active WebAuthn credentials for a user.

        Parameters
        ----------
        user_id : str
            The user whose credentials to list.

        Returns
        -------
        list of dict
            Each dict contains credential metadata (id, device_name,
            created_at, last_used_at, sign_count). Returns empty list
            on error.
        """
        try:
            with self.db_manager.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT credential_id, device_name, created_at,
                           last_used_at, sign_count, transports,
                           credential_type, backup_eligible, backup_state
                    FROM webauthn_credentials
                    WHERE user_id = ? AND is_active = 1
                    ORDER BY created_at DESC
                """, (user_id,))

                rows = cursor.fetchall()
                credentials = []
                for row in rows:
                    credentials.append({
                        'credential_id': row['credential_id'],
                        'device_name': row['device_name'],
                        'created_at': row['created_at'],
                        'last_used_at': row['last_used_at'],
                        'sign_count': row['sign_count'],
                        'transports': json.loads(row['transports']) if row['transports'] else [],
                        'credential_type': row['credential_type'],
                        'backup_eligible': bool(row['backup_eligible']),
                        'backup_state': bool(row['backup_state']),
                    })

                logger.debug(
                    "Listed %d WebAuthn credentials for user '%s'",
                    len(credentials), user_id,
                )
                return credentials

        except sqlite3.Error as e:
            logger.error(
                "Failed to list WebAuthn credentials for user '%s': %s",
                user_id, e,
            )
            return []

    def revoke_credential(self, credential_id: str) -> Dict[str, Any]:
        """Revoke (deactivate) a WebAuthn credential.

        The credential is soft-deleted by setting ``is_active = 0``.
        It can no longer be used for authentication.

        Parameters
        ----------
        credential_id : str
            The base64url-encoded credential ID to revoke.

        Returns
        -------
        dict
            ``{'success': True}`` on success, ``{'success': False, 'error': ...}``
            on failure.
        """
        if not credential_id:
            return {'success': False, 'error': 'credential_id is required'}

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # First check the credential exists and is active
                cursor.execute("""
                    SELECT user_id, device_name FROM webauthn_credentials
                    WHERE credential_id = ? AND is_active = 1
                """, (credential_id,))
                row = cursor.fetchone()

                if row is None:
                    return {
                        'success': False,
                        'error': 'Credential not found or already revoked',
                    }

                user_id = row[0]
                device_name = row[1]

                # Deactivate the credential
                cursor.execute("""
                    UPDATE webauthn_credentials
                    SET is_active = 0
                    WHERE credential_id = ?
                """, (credential_id,))
                conn.commit()

            logger.info(
                "WebAuthn credential revoked: %s (user: %s, device: %s)",
                credential_id[:16] + '...', user_id, device_name,
            )

            # Audit log the revocation
            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    action=AuditAction.MFA_DISABLED,
                    user_id=user_id,
                    resource_type='webauthn_credential',
                    details={
                        'credential_id': credential_id[:16] + '...',
                        'device_name': device_name,
                    },
                )

            return {'success': True, 'credential_id': credential_id}

        except sqlite3.Error as e:
            logger.error("Failed to revoke WebAuthn credential")
            return {
                'success': False,
                'error': f'Database error while revoking credential: {e}',
            }

    def rename_credential(
        self,
        credential_id: str,
        new_name: str,
    ) -> Dict[str, Any]:
        """Rename a WebAuthn credential.

        Updates the human-readable device name associated with a credential.

        Parameters
        ----------
        credential_id : str
            The base64url-encoded credential ID to rename.
        new_name : str
            The new device name (max 255 characters).

        Returns
        -------
        dict
            ``{'success': True}`` on success, ``{'success': False, 'error': ...}``
            on failure.
        """
        if not credential_id or not new_name:
            return {
                'success': False,
                'error': 'credential_id and new_name are required',
            }

        # Sanitize and limit name length
        new_name = new_name.strip()[:255]
        if not new_name:
            return {'success': False, 'error': 'new_name cannot be empty'}

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE webauthn_credentials
                    SET device_name = ?
                    WHERE credential_id = ? AND is_active = 1
                """, (new_name, credential_id))

                if cursor.rowcount == 0:
                    return {
                        'success': False,
                        'error': 'Credential not found or already revoked',
                    }

                conn.commit()

            logger.info(
                "WebAuthn credential renamed: %s -> '%s'",
                credential_id[:16] + '...', new_name,
            )

            return {
                'success': True,
                'credential_id': credential_id,
                'device_name': new_name,
            }

        except sqlite3.Error as e:
            logger.error("Failed to rename WebAuthn credential")
            return {
                'success': False,
                'error': f'Database error while renaming credential: {e}',
            }

    # =========================================================================
    # Challenge Management
    # =========================================================================

    def _store_challenge(
        self,
        challenge: str,
        session_id: str,
        challenge_type: str,
        user_id: Optional[str] = None,
        ttl_seconds: int = DEFAULT_CHALLENGE_TTL,
    ) -> None:
        """Store a challenge in the database for later verification.

        Challenges are time-limited and single-use. Expired challenges
        are cleaned up periodically.

        Parameters
        ----------
        challenge : str
            The cryptographic challenge string.
        session_id : str
            The session identifier binding this challenge.
        challenge_type : str
            Either ``'registration'`` or ``'authentication'``.
        user_id : str, optional
            The user ID associated with this challenge.
        ttl_seconds : int, optional
            Time-to-live in seconds. Defaults to 300 (5 minutes).
        """
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=ttl_seconds)

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Clean up expired challenges for this session first
                cursor.execute("""
                    DELETE FROM webauthn_challenges
                    WHERE session_id = ? OR expires_at < ?
                """, (session_id, now.isoformat()))

                # Insert the new challenge
                cursor.execute("""
                    INSERT INTO webauthn_challenges (
                        session_id, challenge, challenge_type,
                        user_id, created_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    challenge,
                    challenge_type,
                    user_id,
                    now.isoformat(),
                    expires_at.isoformat(),
                ))
                conn.commit()

            logger.debug(
                "WebAuthn challenge stored (session: %s, type: %s, TTL: %ds)",
                session_id, challenge_type, ttl_seconds,
            )

        except sqlite3.Error as e:
            logger.error("Failed to store WebAuthn challenge")
            raise

    def _verify_challenge(
        self,
        session_id: str,
        expected_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Verify and consume a stored challenge.

        Retrieves the challenge for the given session, checks that it
        has not expired or been consumed, marks it as consumed, and
        returns the challenge data.

        Parameters
        ----------
        session_id : str
            The session identifier to look up.
        expected_type : str, optional
            If provided, verify the challenge type matches.

        Returns
        -------
        dict or None
            The challenge record dict if valid, or ``None`` if the
            challenge was not found, expired, already consumed, or
            type mismatch.
        """
        now = datetime.utcnow().isoformat()

        try:
            with self.db_manager.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Find the most recent unconsumed, unexpired challenge
                cursor.execute("""
                    SELECT id, challenge, challenge_type, user_id,
                           created_at, expires_at
                    FROM webauthn_challenges
                    WHERE session_id = ?
                      AND consumed = 0
                      AND expires_at > ?
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (session_id, now))

                row = cursor.fetchone()
                if row is None:
                    logger.warning(
                        "No valid WebAuthn challenge found for session: %s",
                        session_id,
                    )
                    return None

                # Check challenge type if expected
                if expected_type and row['challenge_type'] != expected_type:
                    logger.warning(
                        "WebAuthn challenge type mismatch: expected '%s', got '%s'",
                        expected_type, row['challenge_type'],
                    )
                    return None

                # Mark the challenge as consumed (single-use)
                cursor.execute("""
                    UPDATE webauthn_challenges
                    SET consumed = 1, consumed_at = ?
                    WHERE id = ?
                """, (now, row['id']))
                conn.commit()

                challenge_data = {
                    'challenge': row['challenge'],
                    'challenge_type': row['challenge_type'],
                    'user_id': row['user_id'],
                    'created_at': row['created_at'],
                }

                logger.debug(
                    "WebAuthn challenge verified and consumed (session: %s)",
                    session_id,
                )
                return challenge_data

        except sqlite3.Error as e:
            logger.error("Failed to verify WebAuthn challenge")
            return None

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _get_user_credential_descriptors(
        self,
        user_id: str,
    ) -> List:
        """Get PublicKeyCredentialDescriptor list for a user's active credentials.

        Used for the ``excludeCredentials`` (registration) and
        ``allowCredentials`` (authentication) fields in WebAuthn options.

        Parameters
        ----------
        user_id : str
            The user whose credential descriptors to retrieve.

        Returns
        -------
        list
            List of PublicKeyCredentialDescriptor objects if py_webauthn
            is available, otherwise empty list.
        """
        if not WEBAUTHN_AVAILABLE:
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT credential_id, transports
                    FROM webauthn_credentials
                    WHERE user_id = ? AND is_active = 1
                """, (user_id,))

                descriptors = []
                for row in cursor.fetchall():
                    cred_id_bytes = base64.urlsafe_b64decode(row[0] + '==')
                    transports_list = json.loads(row[1]) if row[1] else []

                    # Map transport strings to enum values
                    transport_enums = []
                    for t in transports_list:
                        t_lower = t.lower()
                        if t_lower in SUPPORTED_TRANSPORTS:
                            try:
                                transport_enums.append(AuthenticatorTransport(t_lower))
                            except (ValueError, KeyError):
                                pass

                    descriptors.append(
                        PublicKeyCredentialDescriptor(
                            type=PublicKeyCredentialType.PUBLIC_KEY,
                            id=cred_id_bytes,
                            transports=transport_enums if transport_enums else None,
                        )
                    )

                return descriptors

        except sqlite3.Error as e:
            logger.error(
                "Failed to get credential descriptors for user '%s': %s",
                user_id, e,
            )
            return []

    def _get_credential_by_id(
        self,
        credential_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a stored credential by its ID.

        Parameters
        ----------
        credential_id : str
            The base64url-encoded credential ID.

        Returns
        -------
        dict or None
            The credential record, or ``None`` if not found or inactive.
        """
        try:
            with self.db_manager.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT credential_id, user_id, public_key, sign_count,
                           device_name, transports, aaguid, created_at,
                           last_used_at
                    FROM webauthn_credentials
                    WHERE credential_id = ? AND is_active = 1
                """, (credential_id,))

                row = cursor.fetchone()
                if row is None:
                    return None

                return {
                    'credential_id': row['credential_id'],
                    'user_id': row['user_id'],
                    'public_key': row['public_key'],
                    'sign_count': row['sign_count'],
                    'device_name': row['device_name'],
                    'transports': json.loads(row['transports']) if row['transports'] else [],
                    'aaguid': row['aaguid'],
                    'created_at': row['created_at'],
                    'last_used_at': row['last_used_at'],
                }

        except sqlite3.Error as e:
            logger.error(
                "Failed to retrieve WebAuthn credential '%s': %s",
                credential_id[:16] + '...' if credential_id else 'None', e,
            )
            return None

    def get_credential_count(self, user_id: str) -> int:
        """Get the number of active WebAuthn credentials for a user.

        Parameters
        ----------
        user_id : str
            The user whose credentials to count.

        Returns
        -------
        int
            Number of active credentials, or 0 on error.
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM webauthn_credentials
                    WHERE user_id = ? AND is_active = 1
                """, (user_id,))
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            logger.error(
                "Failed to count credentials for user '%s': %s",
                user_id, e,
            )
            return 0

    def cleanup_expired_challenges(self) -> int:
        """Remove expired and consumed challenges from the database.

        This should be called periodically (e.g., via a background task)
        to prevent the challenges table from growing unboundedly.

        Returns
        -------
        int
            Number of deleted challenge records, or 0 on error.
        """
        now = datetime.utcnow().isoformat()

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM webauthn_challenges
                    WHERE expires_at < ? OR consumed = 1
                """, (now,))
                deleted = cursor.rowcount
                conn.commit()

            if deleted > 0:
                logger.info(
                    "Cleaned up %d expired/consumed WebAuthn challenges",
                    deleted,
                )
            return deleted

        except sqlite3.Error as e:
            logger.error("Failed to clean up WebAuthn challenges")
            return 0

    def is_available(self) -> bool:
        """Check if the WebAuthn service is operational.

        Returns
        -------
        bool
            ``True`` if py_webauthn is installed and the database tables
            are accessible.
        """
        if not WEBAUTHN_AVAILABLE:
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) FROM webauthn_credentials WHERE 1=0"
                )
                return True
        except sqlite3.Error:
            return False


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    'WebAuthnService',
    'WEBAUTHN_AVAILABLE',
]
