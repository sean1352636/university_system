"""Pagination helpers for list endpoints."""

from __future__ import annotations

from flask import request


def get_pagination_params(
    default_page: int = 1,
    default_per_page: int = 20,
    max_per_page: int = 100,
) -> tuple[int, int, int]:
    """Extract and validate pagination parameters from the query string.

    Returns:
        (page, per_page, offset) – all guaranteed to be non-negative integers.
    """
    try:
        page = max(1, int(request.args.get("page", default_page)))
    except (TypeError, ValueError):
        page = default_page

    try:
        per_page = min(max(1, int(request.args.get("per_page", default_per_page))), max_per_page)
    except (TypeError, ValueError):
        per_page = default_per_page

    offset = (page - 1) * per_page
    return page, per_page, offset


def paginated_response(
    items: list[dict],
    total: int,
    page: int,
    per_page: int,
) -> dict:
    """Wrap a list of items with pagination metadata."""
    total_pages = max(1, (total + per_page - 1) // per_page)
    return {
        "items": items,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }
