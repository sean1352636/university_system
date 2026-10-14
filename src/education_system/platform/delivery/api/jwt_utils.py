"""Compatibility shim — this module moved to :mod:`education_system.platform.delivery.api.security.jwt`.

Kept because existing imports across the codebase and tests still point
here. Import from the new location in new code; this file can be deleted
once nothing references ``education_system.platform.delivery.api.jwt_utils``.
"""

from education_system.platform.delivery.api.security.jwt import *  # noqa: F401,F403
from education_system.platform.delivery.api.security.jwt import __dict__ as _moved  # noqa: E402

# ``import *`` skips names starting with an underscore, and several of
# these modules keep their state and helpers private (``_rate_limiter``,
# ``_extract_subdomain``, ``_JWT_SECRET``). Callers and tests reach for
# those, so re-export everything the target defines.
globals().update({k: v for k, v in _moved.items() if not k.startswith("__")})
