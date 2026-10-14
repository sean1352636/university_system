"""Compatibility shim — moved to :mod:`...kernel.pagination`.

99 modules import this path. The names below keep the university
contract exactly: ``(page, per_page, offset)`` and an ``items`` envelope.
"""

from education_system.platform.delivery.api.kernel.pagination import (  # noqa: F401
    get_pagination_params,
    paginated_response,
)

__all__ = ["get_pagination_params", "paginated_response"]
