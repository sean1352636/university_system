"""Shared multi-method MFA.

``MFAService`` here is the full implementation — TOTP, SMS OTP, email OTP,
recovery codes, device trust, enforcement policies — promoted out of the
university system so every system uses one MFA rather than four.

Not to be confused with ``platform.identity.auth.mfa_service``, the small
TOTP-only service that the *login* path in ``auth/core.py`` depends on.
That one is deliberately left alone: it is fail-closed (a read failure
denies the login), so it changes on its own schedule.
"""

from education_system.platform.identity.auth.mfa._integrations import (
    AuditAction,
    get_recovery_format_hint,
    register_email_sender,
    register_recovery_format_hint,
    register_security_logger,
    register_sms_sender,
)
from education_system.platform.identity.auth.mfa.service import (
    MFAService,
    generate_sms_otp,
    setup_totp,
    verify_sms_otp,
    verify_totp,
)

__all__ = [
    "AuditAction",
    "MFAService",
    "generate_sms_otp",
    "setup_totp",
    "verify_sms_otp",
    "verify_totp",
    "get_recovery_format_hint",
    "register_email_sender",
    "register_recovery_format_hint",
    "register_security_logger",
    "register_sms_sender",
]
