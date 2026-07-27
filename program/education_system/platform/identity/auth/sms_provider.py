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

# Runtime state lives under var/, not inside the package (ADR 0018).
from education_system.platform.paths import DATA_DIR as _SHARED_DATA_DIR, SMS_CONFIG_PATH as _SMS_CONFIG_PATH


# ── Providers ────────────────────────────────────────────────────────

class SMSProvider(ABC):
    @abstractmethod
    def send_otp(self, phone_number: str, code: str,
                 system_name: str = "Education System") -> Dict:
        ...


class MockSMSProvider(SMSProvider):
    """Logs the code instead of sending. Default in dev."""

    def send_otp(self, phone_number, code, system_name="Education System"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"[{ts}] MOCK SMS to {phone_number}: code={code} ({system_name})"
        # Stdout so devs see it; logger so it's also captured.
        print(f"📱 {msg}")
        logger.info(msg)
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
