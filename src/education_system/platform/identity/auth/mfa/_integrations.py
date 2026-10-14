"""Optional side-integrations for the shared MFA service.

The MFA service wants three things that are not its job: an audit sink, an
SMS sender and an email sender. Each is optional — MFA still works without
them, it just logs less or reports a delivery failure.

This module resolves each one in the same order:

1. an implementation a system registered at start-up (``register_*``)
2. the platform's own implementation
3. a no-op that degrades safely

The registration hooks exist so the university can keep writing to its
*immutable* audit log without the platform importing university code —
``platform`` must never import from ``systems``.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "AuditAction",
    "get_recovery_format_hint",
    "register_email_sender",
    "register_recovery_format_hint",
    "register_security_logger",
    "register_sms_sender",
    "safe_log_security_event",
    "send_email_otp",
    "send_sms_otp",
]

#: Shown next to the recovery-code box so users know what shape to type.
DEFAULT_RECOVERY_FORMAT_HINT = "8 digits with hyphen in middle"


class AuditAction:
    """Audit action names used by the MFA service.

    Plain strings rather than an ``Enum`` so a registered logger that
    expects its own action type can accept them unchanged.
    """

    MFA_ENABLED = "MFA_ENABLED"
    MFA_DISABLED = "MFA_DISABLED"
    MFA_CHALLENGE = "MFA_CHALLENGE"


_security_logger: Optional[Callable[..., Any]] = None
_sms_sender: Optional[Callable[..., Any]] = None
_email_sender: Optional[Callable[..., Any]] = None
_recovery_format_hint: Optional[Callable[[], str]] = None


def register_recovery_format_hint(func: Callable[[], str] | None) -> None:
    """Let a system describe its own recovery-code format — ``func() -> str``."""
    global _recovery_format_hint
    _recovery_format_hint = func


def get_recovery_format_hint() -> str:
    """The configured recovery-code format hint, or the default."""
    if _recovery_format_hint is not None:
        try:
            return _recovery_format_hint()
        except Exception:
            logger.debug("Recovery format hint provider failed", exc_info=True)
    return DEFAULT_RECOVERY_FORMAT_HINT


def register_security_logger(func: Callable[..., Any] | None) -> None:
    """Route MFA security events to *func*.

    *func* must accept the keyword arguments used by
    :func:`safe_log_security_event`.
    """
    global _security_logger
    _security_logger = func


def register_sms_sender(func: Callable[..., Any] | None) -> None:
    """Route MFA SMS OTPs to *func* — ``func(phone_number, code)``."""
    global _sms_sender
    _sms_sender = func


def register_email_sender(func: Callable[..., Any] | None) -> None:
    """Route MFA email OTPs to *func* — ``func(email, code, username)``."""
    global _email_sender
    _email_sender = func


def safe_log_security_event(
    action: str,
    user_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    session_id: Optional[str] = None,
    *,
    required: bool = False,
) -> bool:
    """Record an MFA security event. Never raises.

    Signature matches the university's ``audit_helpers`` original so the
    service's call sites are unchanged.
    """
    payload = dict(
        action=action,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
        session_id=session_id,
    )

    if _security_logger is not None:
        try:
            _security_logger(required=required, **payload)
            return True
        except Exception:
            logger.warning("Registered MFA security logger failed", exc_info=True)

    try:
        from education_system.platform.governance.audit.audit_service import AuditService

        try:
            numeric_user_id = int(user_id) if user_id is not None else None
        except (TypeError, ValueError):
            numeric_user_id = None
        AuditService().log_security(
            action,
            user_id=numeric_user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
        )
        return True
    except Exception:
        # An audit sink that is merely absent must not break enrolment.
        logger.debug("MFA security event not persisted: %s", payload, exc_info=True)
        return False


def send_sms_otp(phone_number: str, code: str) -> Dict[str, Any]:
    """Send an SMS OTP. Returns ``{"success": bool, ...}``."""
    if _sms_sender is not None:
        return _sms_sender(phone_number, code)
    from education_system.platform.identity.auth.sms_provider import send_otp

    return send_otp(phone_number, code)


def send_email_otp(email: str, code: str, username: str | None = None) -> Dict[str, Any]:
    """Send an email OTP. Returns ``{"success": bool, ...}``."""
    if _email_sender is not None:
        return _email_sender(email, code, username)
    from education_system.platform.integrations.email.otp_sender import send_otp

    return send_otp(email, code, username)
