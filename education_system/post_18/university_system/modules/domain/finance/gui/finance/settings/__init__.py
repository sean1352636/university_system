"""Settings sub-package – drop-in replacement for the former settings.py module."""

from education_system.post_18.university_system.modules.domain.finance.gui.finance.settings._base import (
    SettingsManager,
    PAYMENT_GATEWAYS,
    SUPPORTED_CURRENCIES,
    EXCHANGE_API_KEY,
    ENCRYPTION_KEY,
    cipher_suite,
    auth,
    logger,
)

from education_system.post_18.university_system.infrastructure.auth import get_global_auth

__all__ = [
    "SettingsManager",
    "PAYMENT_GATEWAYS",
    "SUPPORTED_CURRENCIES",
    "EXCHANGE_API_KEY",
    "ENCRYPTION_KEY",
    "cipher_suite",
    "auth",
    "logger",
    "get_global_auth",
]
