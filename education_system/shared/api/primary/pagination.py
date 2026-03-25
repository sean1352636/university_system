"""Pagination utilities for Primary School API — re-exports from shared module."""

from education_system.shared.api.pagination import get_pagination_params, paginated_response

__all__ = ["get_pagination_params", "paginated_response"]
