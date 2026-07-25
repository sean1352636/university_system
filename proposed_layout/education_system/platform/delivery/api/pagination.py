"""Shared pagination utilities for all system APIs."""

from flask import request


def get_pagination_params() -> tuple[int, int]:
    """Extract pagination parameters from the request query string.

    Returns (limit, offset).
    """
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 20))))
    except (ValueError, TypeError):
        page = 1
        per_page = 20

    offset = (page - 1) * per_page
    return per_page, offset


def paginated_response(items: list, total: int, page: int = None, per_page: int = None) -> dict:
    """Build a paginated response envelope."""
    if page is None:
        try:
            page = max(1, int(request.args.get("page", 1)))
        except (ValueError, TypeError):
            page = 1
    if per_page is None:
        try:
            per_page = min(100, max(1, int(request.args.get("per_page", 20))))
        except (ValueError, TypeError):
            per_page = 20

    total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0

    return {
        "data": items,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }
