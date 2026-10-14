"""University MFA — moved to the platform.

The implementation now lives at
``education_system.platform.identity.auth.mfa.service``. It was the richest
of the four MFA implementations in the tree, so it became the shared one
rather than being replaced by a weaker version; the university keeps using
exactly the same code, from its new home.

This module stays as a re-export so existing university imports keep
resolving, and it is where the university re-attaches the two integrations
the platform cannot import upward:

* the **immutable** audit log (``security.audit_helpers``), so university
  MFA events keep landing in the compliance sink rather than the general
  platform audit table
* the university's own SMS and email OTP senders

Registration happens on import, which is the moment any university caller
first reaches the service.
"""

from __future__ import annotations

import logging

from education_system.platform.identity.auth.mfa import (  # noqa: F401
    AuditAction,
    MFAService,
    generate_sms_otp,
    register_email_sender,
    register_security_logger,
    register_sms_sender,
    setup_totp,
    verify_sms_otp,
    verify_totp,
)

logger = logging.getLogger(__name__)

# ``infrastructure/auth/__init__.py`` imports these four module-level
# helpers alongside MFAService, in a try/except that sets MFAService = None
# and MFA_AVAILABLE = False on ImportError. Omitting them from this shim
# disabled university MFA silently rather than raising — so keep them
# re-exported.
__all__ = [
    "AuditAction",
    "MFAService",
    "generate_sms_otp",
    "setup_totp",
    "shared_mfa_identity",
    "verify_sms_otp",
    "verify_totp",
]


def shared_mfa_identity(current_user) -> tuple[MFAService, int | None]:
    """Return ``(service, shared_auth_user_id)`` for a university session.

    MFA is stored once, in the shared ``auth.db``. The university's own ids
    are a **different id space** — ``admin`` is 1 here and 19 there — so a
    local id must never be handed to the shared store; it would land on
    whichever account happens to hold that number.

    Resolution order: the ``shared_auth_id`` the login already put in the
    session, else a lookup by username. Returns ``None`` for the id when
    the account has no shared-auth counterpart, and callers must refuse
    rather than fall back to the local id.
    """
    service = MFAService.for_shared_auth()
    session = current_user if isinstance(current_user, dict) else {}
    shared_id = session.get("shared_auth_id")
    if shared_id:
        return service, int(shared_id)
    resolved = MFAService.resolve_shared_user_id(
        session.get("id") or session.get("user_id"),
        session.get("username"),
    )
    return service, resolved


def _register_university_integrations() -> None:
    """Point the shared MFA service back at the university's own sinks.

    Each hook is optional: if a module is missing the platform default is
    kept, which is exactly what the previous ``try/except ImportError``
    probes in this file did.
    """
    try:
        from education_system.systems.university.infrastructure.security.audit_helpers import (
            safe_log_security_event,
        )
    except ImportError:
        logger.debug("University immutable audit log unavailable; using platform audit")
    else:
        register_security_logger(safe_log_security_event)

    try:
        from education_system.systems.university.infrastructure.auth.sms_provider import (
            send_otp as send_sms,
        )
    except ImportError:
        logger.debug("University SMS provider unavailable; using platform provider")
    else:
        register_sms_sender(lambda phone, code: send_sms(phone, code))

    try:
        from education_system.systems.university.infrastructure.auth.email_otp_service import (
            send_otp as send_email,
        )
    except ImportError:
        logger.debug("University email OTP service unavailable; using platform sender")
    else:
        register_email_sender(
            lambda email, code, username=None: send_email(email, code, username)
        )


_register_university_integrations()
