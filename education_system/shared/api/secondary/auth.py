"""JWT authentication for the Secondary School API — delegates to shared auth."""

from education_system.shared.api.auth import (
    generate_token,
    decode_token,
    token_required,
    role_required,
    system_required,
    _create_mfa_token,
)
