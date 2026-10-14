"""SMS OTP provider for shared MFA.

Minimal port of the university SMS provider — keeps Twilio + Mock since
those are the two providers actually exercised by the platform. AWS SNS
and email-to-SMS were trimmed for Phase 1; add them back here if needed.

Public surface:

    send_otp(phone_number, code, system_name="Education System") -> dict

Returns ``{"success": True, "provider": ..., ...}`` on success or
``{"success": False, "error": "..."}`` on failure.

Configuration is read from ``shared/data/sms_config.json`` (same dir as
the email config) or environment variables. With no config the mock
provider logs the code to stdout — handy in dev, never in production.
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict

logger = logging.getLogger(__name__)


#: ``APP_ENV`` values in which the mock provider may run at all. An unset
#: ``APP_ENV`` reads as production, so the refusal is the default and a
#: deployment that forgot to configure SMS fails closed.
_MOCK_PROVIDER_ENVIRONMENTS = frozenset({"development", "dev", "local", "test", "testing"})


def _mock_delivery_allowed() -> bool:
    """True when logging an OTP locally instead of sending it is safe.

    Read at call time so a process that sets ``APP_ENV`` after import still
    gets the right answer.
    """
    return os.getenv("APP_ENV", "production").strip().lower() in _MOCK_PROVIDER_ENVIRONMENTS


# Runtime state lives under var/, not inside the package (ADR 0018).
from education_system.paths import (
    PLATFORM_DATA_DIR as _SHARED_DATA_DIR,
    PLATFORM_SMS_CONFIG_PATH as _SMS_CONFIG_PATH,
)


def _redact_phone(phone_number: str) -> str:
    """Last two digits only — enough to correlate, not to contact."""
    return f"****{phone_number[-2:]}" if len(phone_number) > 2 else "****"


# ── Providers ────────────────────────────────────────────────────────

class SMSProvider(ABC):
    @abstractmethod
    def send_otp(self, phone_number: str, code: str,
                 system_name: str = "Education System") -> Dict:
        ...


class MockSMSProvider(SMSProvider):
    """Logs the code instead of sending. Development and test only."""

    def send_otp(self, phone_number, code, system_name="Education System"):
        if not _mock_delivery_allowed():
            # Reporting success for an SMS nobody received is worse than
            # failing: the account holder is locked out while the code sits
            # in a log. Fail so the MFA service fails closed.
            logger.error(
                "SMS OTP fell back to the mock provider outside development; "
                "refusing to emit a verification code. Configure an SMS provider."
            )
            return {"success": False, "provider": "mock",
                    "error": "SMS OTP delivery is not configured"}

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # The code goes to stdout only — that is the point of the dev mock.
        # It must not reach ``logger``: application logs are shipped, kept and
        # read by people who are not the account holder, so a full OTP (and
        # the number it was for) does not belong in them.
        print(f"📱 [{ts}] MOCK SMS to {phone_number}: code={code} ({system_name})")
        logger.info("Mock SMS OTP emitted for %s (code withheld from logs)",
                    _redact_phone(phone_number))
        return {"success": True, "provider": "mock", "code": code}


class TwilioSMSProvider(SMSProvider):
    """Twilio. Requires the ``twilio`` package + account SID / auth token /
    sender number — provided via the SMS config file or environment."""

    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number

    def send_otp(self, phone_number, code, system_name="Education System"):
        try:
            from twilio.rest import Client  # type: ignore[import-not-found]
        except ImportError:
            return {
                "success": False,
                "error": "twilio package not installed (pip install twilio)",
            }
        try:
            client = Client(self.account_sid, self.auth_token)
            body = (
                f"Your {system_name} verification code is {code}. "
                f"It expires in 10 minutes."
            )
            client.messages.create(
                body=body, from_=self.from_number, to=phone_number,
            )
            return {"success": True, "provider": "twilio"}
        except Exception as e:
            logger.warning("Twilio send failed for %s: %s", phone_number, e)  # lgtm[py/clear-text-logging-sensitive-data]
            return {"success": False, "error": f"Twilio error: {e}"}


# ── Config loading + dispatch ────────────────────────────────────────

def _load_sms_config() -> Dict:
    if _SMS_CONFIG_PATH.exists():
        try:
            with open(_SMS_CONFIG_PATH, "r") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to load SMS config: %s", e)

    return {
        "primary_provider": os.getenv("SMS_PRIMARY_PROVIDER", "mock"),
        "twilio": {
            "account_sid": os.getenv("TWILIO_ACCOUNT_SID", ""),
            "auth_token":  os.getenv("TWILIO_AUTH_TOKEN", ""),
            "from_number": os.getenv("TWILIO_FROM_NUMBER", ""),
        },
    }


def _build_provider(name: str, cfg: Dict) -> SMSProvider:
    name = (name or "mock").lower()
    if name == "twilio":
        tw = cfg.get("twilio", {}) or {}
        sid = tw.get("account_sid") or ""
        tok = tw.get("auth_token") or ""
        num = tw.get("from_number") or ""
        if not all([sid, tok, num]):
            logger.warning("Twilio not fully configured — falling back to mock.")
            return MockSMSProvider()
        return TwilioSMSProvider(sid, tok, num)
    return MockSMSProvider()


_default_provider: SMSProvider | None = None


def _get_default_provider() -> SMSProvider:
    global _default_provider
    if _default_provider is None:
        cfg = _load_sms_config()
        _default_provider = _build_provider(cfg.get("primary_provider", "mock"), cfg)
    return _default_provider


def send_otp(phone_number: str, code: str,
             system_name: str = "Education System") -> Dict:
    """Send an OTP via the configured SMS provider.

    Mirrors the signature of ``shared/email/otp_sender.send_otp`` so the
    MFA service can dispatch by method type without per-method branching.
    """
    if not phone_number or not str(phone_number).strip():
        return {"success": False, "error": "Phone number is required."}
    return _get_default_provider().send_otp(
        str(phone_number).strip(), code, system_name,
    )
