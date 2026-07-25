"""WebAuthn / Passkey authentication service.

Provides passwordless authentication using the Web Authentication API
(WebAuthn Level 2).  Users can register hardware security keys or platform
authenticators (e.g. fingerprint, Face ID) and use them to log in without
a password.

Requires the ``fido2`` library (``pip install fido2``).

Usage:
    svc = WebAuthnService(db_path)
    # Registration
    options = svc.begin_registration(user_id, username)
    # … client performs navigator.credentials.create() …
    svc.complete_registration(user_id, credential_response, device_name="YubiKey")

    # Authentication
    options = svc.begin_authentication(username)
    # … client performs navigator.credentials.get() …
    user_info = svc.complete_authentication(username, credential_response)
"""

import json
import logging
import os
from base64 import urlsafe_b64decode, urlsafe_b64encode

from education_system.platform.identity.auth.db import connect
from education_system.platform.identity.auth.exceptions import AuthError

logger = logging.getLogger(__name__)

# Relying Party configuration
_RP_ID = os.getenv("WEBAUTHN_RP_ID", "localhost")
_RP_NAME = os.getenv("WEBAUTHN_RP_NAME", "Education System")
_RP_ORIGIN = os.getenv("WEBAUTHN_ORIGIN", "http://localhost:5000")

# In-memory challenge store (short-lived, per-session)
_challenges: dict[str, bytes] = {}


def _check_fido2():
    """Raise ImportError with a helpful message if fido2 is not installed."""
    try:
        import fido2  # noqa: F401
        return True
    except ImportError:
        raise ImportError(
            "WebAuthn support requires the 'fido2' package. "
            "Install it with: pip install fido2"
        )


class WebAuthnService:
    """Manages WebAuthn credential registration and authentication."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def begin_registration(self, user_id: int, username: str) -> dict:
        """Start a WebAuthn registration ceremony.

        Returns a PublicKeyCredentialCreationOptions dict suitable for
        passing to ``navigator.credentials.create()`` on the client.
        """
        _check_fido2()
        from fido2.webauthn import PublicKeyCredentialRpEntity, PublicKeyCredentialUserEntity
        from fido2.server import Fido2Server

        rp = PublicKeyCredentialRpEntity(id=_RP_ID, name=_RP_NAME)
        server = Fido2Server(rp)

        # Gather existing credentials for this user
        existing = self._get_credentials(user_id)
        exclude_credentials = [
            {"type": "public-key", "id": urlsafe_b64decode(c["credential_id"] + "==")}
            for c in existing
        ]

        user_entity = PublicKeyCredentialUserEntity(
            id=str(user_id).encode(),
            name=username,
            display_name=username,
        )

        registration_data, state = server.register_begin(
            user_entity,
            credentials=exclude_credentials,
        )

        # Store challenge for verification
        _challenges[f"reg:{user_id}"] = state

        logger.info("WebAuthn registration started for user_id=%d", user_id)
        return json.loads(json.dumps(registration_data, default=_bytes_encoder))

    def complete_registration(self, user_id: int, credential_response: dict,
                              device_name: str | None = None) -> dict:
        """Complete a WebAuthn registration ceremony.

        Stores the credential in the database.
        """
        _check_fido2()
        from fido2.webauthn import PublicKeyCredentialRpEntity
        from fido2.server import Fido2Server

        rp = PublicKeyCredentialRpEntity(id=_RP_ID, name=_RP_NAME)
        server = Fido2Server(rp)

        state = _challenges.pop(f"reg:{user_id}", None)
        if not state:
            raise AuthError("No pending registration challenge.")

        auth_data = server.register_complete(state, credential_response)

        credential_id = urlsafe_b64encode(auth_data.credential_data.credential_id).rstrip(b"=").decode()
        public_key = auth_data.credential_data.public_key

        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO webauthn_credentials "
                "(user_id, credential_id, public_key, device_name) VALUES (?, ?, ?, ?)",
                (user_id, credential_id, public_key, device_name),
            )
            conn.commit()
            logger.info("WebAuthn credential registered for user_id=%d", user_id)
        finally:
            conn.close()

        return {"credential_id": credential_id, "device_name": device_name}

    def begin_authentication(self, username: str) -> dict:
        """Start a WebAuthn authentication ceremony.

        Returns a PublicKeyCredentialRequestOptions dict for
        ``navigator.credentials.get()``.
        """
        _check_fido2()
        from fido2.webauthn import PublicKeyCredentialRpEntity
        from fido2.server import Fido2Server

        rp = PublicKeyCredentialRpEntity(id=_RP_ID, name=_RP_NAME)
        server = Fido2Server(rp)

        conn = self._conn()
        try:
            user = conn.execute(
                "SELECT id FROM users WHERE username = ? AND is_active = 1",
                (username,),
            ).fetchone()
            if not user:
                raise AuthError("Invalid username.")

            creds = self._get_credentials(user["id"])
            if not creds:
                raise AuthError("No passkeys registered for this account.")

            allow_credentials = [
                {"type": "public-key", "id": urlsafe_b64decode(c["credential_id"] + "==")}
                for c in creds
            ]
        finally:
            conn.close()

        request_options, state = server.authenticate_begin(credentials=allow_credentials)
        _challenges[f"auth:{username}"] = {"state": state, "user_id": user["id"]}

        logger.info("WebAuthn authentication started for '%s'", username)
        return json.loads(json.dumps(request_options, default=_bytes_encoder))

    def complete_authentication(self, username: str, credential_response: dict) -> dict:
        """Complete a WebAuthn authentication ceremony.

        Returns user info on success.
        """
        _check_fido2()
        from fido2.webauthn import PublicKeyCredentialRpEntity
        from fido2.server import Fido2Server

        rp = PublicKeyCredentialRpEntity(id=_RP_ID, name=_RP_NAME)
        server = Fido2Server(rp)

        challenge_data = _challenges.pop(f"auth:{username}", None)
        if not challenge_data:
            raise AuthError("No pending authentication challenge.")

        state = challenge_data["state"]
        user_id = challenge_data["user_id"]

        creds = self._get_credentials(user_id)
        credentials = [
            {"type": "public-key", "id": urlsafe_b64decode(c["credential_id"] + "=="),
             "public_key": c["public_key"]}
            for c in creds
        ]

        auth_data = server.authenticate_complete(state, credentials, credential_response)

        # Update sign count
        cred_id = urlsafe_b64encode(auth_data.credential_id).rstrip(b"=").decode()
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE webauthn_credentials SET sign_count = ? WHERE credential_id = ?",
                (auth_data.new_sign_count, cred_id),
            )

            user = conn.execute(
                "SELECT id, username, display_name, email FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            systems = conn.execute(
                "SELECT system_key, role FROM user_systems WHERE user_id = ?",
                (user_id,),
            ).fetchall()
            conn.commit()
        finally:
            conn.close()

        logger.info("WebAuthn authentication completed for '%s'", username)
        return {
            "user_id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "email": user["email"],
            "systems": [{"system_key": s["system_key"], "role": s["role"]} for s in systems],
        }

    def _get_credentials(self, user_id: int) -> list[dict]:
        """Get all WebAuthn credentials for a user."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT credential_id, public_key, sign_count, device_name "
                "FROM webauthn_credentials WHERE user_id = ?",
                (user_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def list_credentials(self, user_id: int) -> list[dict]:
        """List credentials for display (without raw public keys)."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT id, credential_id, device_name, sign_count, created_at "
                "FROM webauthn_credentials WHERE user_id = ?",
                (user_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def remove_credential(self, user_id: int, credential_db_id: int) -> bool:
        """Remove a WebAuthn credential by its database ID."""
        conn = self._conn()
        try:
            cur = conn.execute(
                "DELETE FROM webauthn_credentials WHERE id = ? AND user_id = ?",
                (credential_db_id, user_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def _bytes_encoder(obj):
    """JSON encoder helper for bytes objects."""
    if isinstance(obj, bytes):
        return urlsafe_b64encode(obj).rstrip(b"=").decode()
    if isinstance(obj, memoryview):
        return urlsafe_b64encode(bytes(obj)).rstrip(b"=").decode()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
