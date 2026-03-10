"""Secondary school password management - delegates to shared auth module."""

from education_system.shared.auth.password_manager import (  # noqa: F401
    hash_password,
    verify_password,
    validate_password_strength,
)
