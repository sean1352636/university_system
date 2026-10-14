"""Compatibility shim — moved to :mod:`..security.principals`.

128 modules across the university domains import from this path (roughly
269 call sites), so it stays until those are migrated. The implementation
is now ``security/principals.py``; the decorator surface is re-exported
from ``security/decorators.py``.

Import from the new locations in new code.
"""

from education_system.platform.delivery.api.security.principals import *  # noqa: F401,F403
from education_system.platform.delivery.api.security.principals import (  # noqa: E402
    __dict__ as _moved,
)

# Private helpers (``_api_config``, ``_normalise_principal``,
# ``_extract_bearer_token``) are imported by callers and tests.
globals().update({k: v for k, v in _moved.items() if not k.startswith("__")})
