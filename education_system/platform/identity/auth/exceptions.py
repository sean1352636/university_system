"""Shared authentication exceptions."""


class AuthError(Exception):
    """Raised for authentication or authorisation failures."""


class ValidationError(Exception):
    """Raised for input validation errors (e.g. weak passwords)."""


class MFAError(Exception):
    """Raised for multi-factor authentication failures."""
