"""Compatibility shim — moved to ``platform.delivery.web.portal.pwa``."""

from education_system.platform.delivery.web.portal.pwa import *  # noqa: F401,F403
from education_system.platform.delivery.web.portal.pwa import (  # noqa: E402,F401
    __dict__ as _moved,
)

globals().update({k: v for k, v in _moved.items() if not k.startswith("__")})
