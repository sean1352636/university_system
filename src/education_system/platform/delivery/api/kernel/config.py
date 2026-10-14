"""API configuration.

Merged from ``delivery/api/base_config.py`` (the lazy Flask ``SECRET_KEY``
holder) and ``delivery/api/university/config.py`` (the JSON-file config
loader and JWT secret resolution). They solved adjacent problems and both
fail closed in production, so they belong together.

Both halves are re-exported unchanged; nothing about how a secret is
resolved has been altered, because the resolution order is load-bearing:
``JWT_SECRET_KEY`` before ``API_SECRET_KEY``, and a hard refusal in
production rather than a generated placeholder that would let every
worker sign tokens with a different key.
"""

from education_system.platform.delivery.api.base_config import (  # noqa: F401
    BaseAPIConfig,
    _LazySecretKey,
    _secret_key,
)
from education_system.platform.delivery.api.university.config import (  # noqa: F401
    load_config,
    _deep_merge,
    _resolve_jwt_secret,
    _DEFAULTS,
    _DEFAULT_CONFIG_PATH,
)

__all__ = ["BaseAPIConfig", "load_config"]
