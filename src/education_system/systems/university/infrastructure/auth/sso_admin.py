"""Admin-side helpers around :class:`SSOService` for the CLI/GUI screens.

The service itself is constructed exactly as the auth facade would build it
(a ``DatabaseConnectionManager`` on the university DB plus the activity
logger), so the admin screens read and write the same ``sso_providers``
rows a future login integration would. Nothing here is on a login path.

SAML fails closed: ``python3-saml`` is not installed, so a SAML provider can
be listed but neither enabled nor tested from here.
"""
from __future__ import annotations

import logging
from typing import Any

from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH
from education_system.systems.university.infrastructure.auth.managers.database_manager import (
    DatabaseConnectionManager,
)
from education_system.systems.university.infrastructure.auth.sso_providers import saml_provider
from education_system.systems.university.infrastructure.auth.sso_service import (
    PROVIDER_TYPES,
    SSOService,
)
from education_system.systems.university.infrastructure.exceptions import (
    AuthenticationError,
    ConfigurationError,
    DatabaseError,
    ValidationError,
)

logger = logging.getLogger(__name__)

SSO_ERRORS = (AuthenticationError, ConfigurationError, DatabaseError, ValidationError)

#: Config keys an OIDC provider must carry before ``initiate_sso_login`` can work.
OIDC_REQUIRED_KEYS = (
    "client_id", "client_secret", "authorization_endpoint", "token_endpoint", "redirect_uri",
)


def saml_available() -> bool:
    """True only when the signature-verifying SAML library is importable."""
    return bool(getattr(saml_provider, "PYTHON3_SAML_AVAILABLE", False))


def provider_type_status() -> list[dict[str, Any]]:
    """Availability of each protocol, with SAML reflecting the real library."""
    rows = []
    for key, info in PROVIDER_TYPES.items():
        available = saml_available() if key == "saml" else bool(info["available"])
        rows.append({"type": key, "label": info["label"], "available": available})
    return rows


def _activity_logger(username: str, action: str, details: str = "", user_id: Any = None) -> None:
    try:
        from education_system.systems.university.infrastructure.utils import activity_logger
        activity_logger.log_activity(str(UNIVERSITY_DEFAULT_DB_PATH), username, action, details, user_id)
    except Exception:
        logger.debug("activity_logger unavailable for SSO admin event", exc_info=True)


def build_sso_service(db_path: str | None = None) -> SSOService:
    """The service wired the way the auth facade wires it."""
    manager = DatabaseConnectionManager(str(db_path or UNIVERSITY_DEFAULT_DB_PATH))
    return SSOService(manager, _activity_logger)


def is_admin(user: dict[str, Any] | None) -> bool:
    return bool(user) and str(user.get("role", "")).lower() in ("admin", "administrator")


def can_enable(provider: dict[str, Any]) -> tuple[bool, str]:
    """Whether a provider may be switched on; SAML is refused while unavailable."""
    if provider.get("provider_type") == "saml" and not saml_available():
        return False, "SAML is unavailable (python3-saml not installed); refusing to enable."
    return True, ""


def test_provider(service: SSOService, provider: dict[str, Any]) -> dict[str, Any]:
    """Dry-run a provider: build its authorization URL without any login.

    Returns ``{'ok': bool, 'message': str, 'auth_url': str}``. SAML fails
    closed; a disabled or misconfigured provider reports the service's error.
    """
    provider_id = provider.get("provider_id", "")
    if provider.get("provider_type") == "saml" and not saml_available():
        return {"ok": False, "auth_url": "",
                "message": "SAML unavailable: python3-saml is not installed, test refused."}
    if provider.get("provider_type") == "oidc":
        missing = [k for k in OIDC_REQUIRED_KEYS if not (provider.get("config") or {}).get(k)]
        if missing:
            return {"ok": False, "auth_url": "",
                    "message": "OIDC config incomplete; missing: " + ", ".join(missing)}
    try:
        result = service.initiate_sso_login(provider_id)
    except SSO_ERRORS as exc:
        return {"ok": False, "auth_url": "", "message": str(exc)}
    except Exception as exc:  # provider libraries raise their own types
        logger.debug("SSO provider test failed", exc_info=True)
        return {"ok": False, "auth_url": "", "message": f"Provider test failed: {exc}"}
    return {"ok": True, "auth_url": result.get("auth_url", ""),
            "message": "Authorization URL generated; provider configuration is usable."}


__all__ = [
    "OIDC_REQUIRED_KEYS", "SSO_ERRORS", "build_sso_service", "can_enable", "is_admin",
    "provider_type_status", "saml_available", "test_provider",
]
