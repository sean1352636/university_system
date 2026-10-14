"""Compatibility shim — moved to :mod:`.kernel.pagination`.

Preserves the *platform* contract, which differs from the university one:
``get_pagination_params`` returns ``(per_page, offset)`` and the envelope
puts items under ``data``. See kernel/pagination.py for the comparison.
"""

from education_system.platform.delivery.api.kernel.pagination import (  # noqa: F401
    get_limit_offset as get_pagination_params,
    legacy_paginated_response as paginated_response,
)

__all__ = ["get_pagination_params", "paginated_response"]
