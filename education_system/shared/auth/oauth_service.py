"""OAuth2 / social login service.

Supports linking external identity providers (Google, Microsoft) to
Education System user accounts.  Users can log in via an OAuth2 provider
and be automatically mapped to their existing account (by email match)
or create a new linked account.

Configuration via environment variables:
    OAUTH_GOOGLE_CLIENT_ID / OAUTH_GOOGLE_CLIENT_SECRET
    OAUTH_MICROSOFT_CLIENT_ID / OAUTH_MICROSOFT_CLIENT_SECRET
    APP_BASE_URL  — used to build redirect URIs

Usage:
    svc = OAuthService(db_path)
    url = svc.get_authorization_url("google")
    # … user completes OAuth flow in browser …
    user_info = svc.handle_callback("google", code, state)
"""

import hashlib
import json
import logging
import os
import secrets
from datetime import datetime

from education_system.shared.auth.db import connect
from education_system.shared.auth.exceptions import AuthError

logger = logging.getLogger(__name__)

# In-memory state store (short-lived, per-session)
_oauth_states: dict[str, dict] = {}

_PROVIDERS = {
    "google": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
        "scopes": ["openid", "email", "profile"],
        "client_id_env": "OAUTH_GOOGLE_CLIENT_ID",
        "client_secret_env": "OAUTH_GOOGLE_CLIENT_SECRET",
    },
    "microsoft": {
        "authorize_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "userinfo_url": "https://graph.microsoft.com/v1.0/me",
        "scopes": ["openid", "email", "profile", "User.Read"],
        "client_id_env": "OAUTH_MICROSOFT_CLIENT_ID",
        "client_secret_env": "OAUTH_MICROSOFT_CLIENT_SECRET",
    },
}


class OAuthService:
    """Manages OAuth2 provider linking and authentication."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    @staticmethod
    def list_providers() -> list[dict]:
        """List configured OAuth providers with their status."""
        result = []
        for name, cfg in _PROVIDERS.items():
            client_id = os.getenv(cfg["client_id_env"], "")
            result.append({
                "provider": name,
                "configured": bool(client_id),
            })
        return result

    def get_authorization_url(self, provider: str) -> str:
        """Generate an OAuth2 authorization URL for the given provider.

        Returns the URL the client should redirect the user to.
        """
        if provider not in _PROVIDERS:
            raise AuthError(f"Unknown OAuth provider: {provider}")

        cfg = _PROVIDERS[provider]
        client_id = os.getenv(cfg["client_id_env"], "")
        if not client_id:
            raise AuthError(f"OAuth provider '{provider}' is not configured.")

        state = secrets.token_urlsafe(32)
        base_url = os.getenv("APP_BASE_URL", "http://localhost:5000")
        redirect_uri = f"{base_url}/api/v1/auth/oauth/{provider}/callback"

        _oauth_states[state] = {"provider": provider, "redirect_uri": redirect_uri}

        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(cfg["scopes"]),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        query = "&".join(f"{k}={_url_encode(v)}" for k, v in params.items())
        return f"{cfg['authorize_url']}?{query}"

    def handle_callback(self, provider: str, code: str, state: str) -> dict:
        """Exchange the authorization code for tokens and user info.

        Returns user info dict with the linked Education System account.
        If no linked account exists and an account with a matching email
        is found, links them automatically.  Otherwise raises AuthError.
        """
        if provider not in _PROVIDERS:
            raise AuthError(f"Unknown OAuth provider: {provider}")

        state_data = _oauth_states.pop(state, None)
        if not state_data or state_data["provider"] != provider:
            raise AuthError("Invalid or expired OAuth state.")

        cfg = _PROVIDERS[provider]
        client_id = os.getenv(cfg["client_id_env"], "")
        client_secret = os.getenv(cfg["client_secret_env"], "")
        redirect_uri = state_data["redirect_uri"]

        # Exchange code for tokens
        token_data = self._exchange_code(cfg["token_url"], code, client_id, client_secret, redirect_uri)
        access_token = token_data.get("access_token")
        if not access_token:
            raise AuthError("Failed to obtain access token from provider.")

        # Fetch user info from provider
        provider_user = self._fetch_userinfo(cfg["userinfo_url"], access_token, provider)

        # Look up or link account
        return self._link_or_find_account(provider, provider_user)

    def link_account(self, user_id: int, provider: str,
                     provider_user_id: str, email: str | None = None,
                     display_name: str | None = None):
        """Manually link an OAuth account to an existing user."""
        conn = self._conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO oauth_accounts "
                "(user_id, provider, provider_user_id, email, display_name, updated_at) "
                "VALUES (?, ?, ?, ?, ?, datetime('now'))",
                (user_id, provider, provider_user_id, email, display_name),
            )
            conn.commit()
            logger.info("Linked %s account to user_id=%d", provider, user_id)
        finally:
            conn.close()

    def unlink_account(self, user_id: int, provider: str) -> bool:
        """Remove an OAuth link from a user account."""
        conn = self._conn()
        try:
            cur = conn.execute(
                "DELETE FROM oauth_accounts WHERE user_id = ? AND provider = ?",
                (user_id, provider),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def get_linked_providers(self, user_id: int) -> list[dict]:
        """List OAuth providers linked to a user account."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT provider, email, display_name, created_at "
                "FROM oauth_accounts WHERE user_id = ?",
                (user_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _link_or_find_account(self, provider: str, provider_user: dict) -> dict:
        """Find an existing linked account or auto-link by email match."""
        provider_user_id = provider_user["id"]
        email = provider_user.get("email", "")

        conn = self._conn()
        try:
            # Check for existing link
            row = conn.execute(
                "SELECT user_id FROM oauth_accounts WHERE provider = ? AND provider_user_id = ?",
                (provider, provider_user_id),
            ).fetchone()

            if row:
                user_id = row["user_id"]
            elif email:
                # Try to auto-link by email
                user = conn.execute(
                    "SELECT id FROM users WHERE email = ? AND is_active = 1",
                    (email.lower(),),
                ).fetchone()
                if not user:
                    raise AuthError(
                        f"No Education System account found for {email}. "
                        f"Ask an administrator to create your account first."
                    )
                user_id = user["id"]
                conn.execute(
                    "INSERT INTO oauth_accounts (user_id, provider, provider_user_id, email, display_name) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (user_id, provider, provider_user_id, email, provider_user.get("name")),
                )
                conn.commit()
                logger.info("Auto-linked %s account for %s to user_id=%d", provider, email, user_id)
            else:
                raise AuthError("Cannot link account: no email provided by OAuth provider.")

            # Fetch full user info
            user = conn.execute(
                "SELECT id, username, display_name, email FROM users WHERE id = ? AND is_active = 1",
                (user_id,),
            ).fetchone()
            if not user:
                raise AuthError("Linked account is inactive.")

            systems = conn.execute(
                "SELECT system_key, role FROM user_systems WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        finally:
            conn.close()

        return {
            "user_id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "email": user["email"],
            "oauth_provider": provider,
            "systems": [{"system_key": s["system_key"], "role": s["role"]} for s in systems],
        }

    @staticmethod
    def _exchange_code(token_url: str, code: str, client_id: str,
                       client_secret: str, redirect_uri: str) -> dict:
        """Exchange an authorization code for tokens via HTTP POST."""
        import urllib.request
        import urllib.parse

        data = urllib.parse.urlencode({
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        }).encode()

        req = urllib.request.Request(token_url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("Accept", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
                return json.loads(resp.read().decode())
        except Exception as exc:
            logger.error("OAuth token exchange failed: %s", exc)
            raise AuthError("Failed to exchange OAuth code for tokens.") from exc

    @staticmethod
    def _fetch_userinfo(userinfo_url: str, access_token: str, provider: str) -> dict:
        """Fetch user info from the OAuth provider."""
        import urllib.request

        req = urllib.request.Request(userinfo_url)
        req.add_header("Authorization", f"Bearer {access_token}")
        req.add_header("Accept", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
                data = json.loads(resp.read().decode())
        except Exception as exc:
            logger.error("OAuth userinfo fetch failed: %s", exc)
            raise AuthError("Failed to fetch user info from provider.") from exc

        # Normalise across providers
        if provider == "google":
            return {"id": data.get("sub"), "email": data.get("email"), "name": data.get("name")}
        elif provider == "microsoft":
            return {
                "id": data.get("id"),
                "email": data.get("mail") or data.get("userPrincipalName"),
                "name": data.get("displayName"),
            }
        return {"id": data.get("id") or data.get("sub"), "email": data.get("email"), "name": data.get("name")}


def _url_encode(value: str) -> str:
    """URL-encode a string value."""
    import urllib.parse
    return urllib.parse.quote(value, safe="")
