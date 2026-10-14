"""Error handling.

Merged surface over ``delivery/api/errors.py`` and
``delivery/api/university/errors.py``. RFC 7807 payload construction
lives in :mod:`.problems`; this module keeps the handler registration
and the exception types the route layers raise.
"""

from education_system.platform.delivery.api.errors import *  # noqa: F401,F403
from education_system.platform.delivery.api.errors import __dict__ as _platform_ns
from education_system.platform.delivery.api.university.errors import (  # noqa: E402
    __dict__ as _university_ns,
)

# Platform names win on a collision: it is the layer that registers the
# app-wide handlers, and a university-specific override reaching every
# system would be a behaviour change, not a merge.
globals().update({k: v for k, v in _university_ns.items()
                  if not k.startswith("__") and k not in globals()})
globals().update({k: v for k, v in _platform_ns.items()
                  if not k.startswith("__")})
