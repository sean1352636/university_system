"""Compatibility shim — shared authentication was split.

The implementation moved to:

    security/authentication.py   state, helpers, decorators, ``auth_bp``
    routes/auth_routes.py        the route handlers

Importing this module still yields everything the old
``delivery.api.auth`` exposed, including ``auth_bp`` with its routes
attached — importing ``auth_routes`` is what registers them, so it is
imported here for its side effects, not just its names.

New code should import from the split modules directly.
"""

from education_system.platform.delivery.api.security.authentication import *  # noqa: F401,F403
from education_system.platform.delivery.api.security.authentication import (  # noqa: E402
    __dict__ as _auth_ns,
)

# Registers the handlers on auth_bp. Without this import the blueprint
# exists but serves nothing, which is how /auth/logout could 404 while
# appearing in the source.
from education_system.platform.delivery.api.routes import auth_routes as _auth_routes  # noqa: E402,F401

# Private helpers (``_get_jwt_secret``, ``_revoke_refresh_jti``,
# ``_rate_limiter``) are used by callers and tests; ``import *`` skips
# them, so re-export the whole namespace.
globals().update({k: v for k, v in _auth_ns.items() if not k.startswith("__")})
globals().update({k: v for k, v in _auth_routes.__dict__.items()
                  if not k.startswith("__") and k not in globals()})
