"""Compatibility shim — moved to ``platform.delivery.web.portal.routes``."""

from education_system.platform.delivery.web.portal.routes import *  # noqa: F401,F403
from education_system.platform.delivery.web.portal.routes import (  # noqa: E402,F401
    web_bp,
    __dict__ as _moved,
)

globals().update({k: v for k, v in _moved.items() if not k.startswith("__")})
