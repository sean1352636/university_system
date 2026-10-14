"""Pagination for list endpoints.

Merged from ``delivery/api/pagination.py`` and
``delivery/api/university/pagination.py``. They shared function names and
**did not share contracts**, so both behaviours are kept here under
distinct names rather than being collapsed into one:

===================  ==============================  ===================
                     university (99 importers)       platform
===================  ==============================  ===================
params return        ``(page, per_page, offset)``    ``(per_page, offset)``
envelope key         ``items``                       ``data``
``total_pages`` at 0 ``1``                           ``0``
===================  ==============================  ===================

Collapsing them would have silently changed the shape of every response
on one side of that table — a caller unpacking three values would get
two, and a client reading ``items`` would find ``data``. Both are still
reachable; new code should use the canonical pair.
"""

from __future__ import annotations

from flask import request

#: Cap on ``per_page``, so a client cannot ask for the whole table.
MAX_PER_PAGE = 100
DEFAULT_PER_PAGE = 20


def get_pagination_params(
    default_page: int = 1,
    default_per_page: int = DEFAULT_PER_PAGE,
    max_per_page: int = MAX_PER_PAGE,
) -> tuple[int, int, int]:
    """Canonical form. Returns ``(page, per_page, offset)``.

    Every value is a non-negative integer; unparseable input falls back
    to the defaults rather than raising, because a bad ``?page=`` should
    not 500 a list endpoint.
    """
    try:
        page = max(1, int(request.args.get("page", default_page)))
    except (TypeError, ValueError):
        page = default_page
    try:
        per_page = min(max(1, int(request.args.get("per_page", default_per_page))),
                       max_per_page)
    except (TypeError, ValueError):
        per_page = default_per_page
    return page, per_page, (page - 1) * per_page


def get_limit_offset(
    default_per_page: int = DEFAULT_PER_PAGE,
    max_per_page: int = MAX_PER_PAGE,
) -> tuple[int, int]:
    """Legacy platform form. Returns ``(per_page, offset)`` — no page."""
    page, per_page, offset = get_pagination_params(
        default_per_page=default_per_page, max_per_page=max_per_page)
    return per_page, offset


def paginated_response(items: list, total: int, page: int, per_page: int,
                       *, key: str = "items") -> dict:
    """Canonical envelope. Items live under ``items`` by default."""
    total_pages = max(1, (total + per_page - 1) // per_page) if per_page > 0 else 1
    return {
        key: items,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }


def legacy_paginated_response(items: list, total: int, page: int | None = None,
                              per_page: int | None = None) -> dict:
    """Platform envelope: items under ``data``, and ``total_pages`` may be 0.

    Reads page/per_page from the query string when omitted, which is what
    the platform version did.
    """
    if page is None or per_page is None:
        q_page, q_per_page, _ = get_pagination_params()
        page = q_page if page is None else page
        per_page = q_per_page if per_page is None else per_page
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


__all__ = [
    "MAX_PER_PAGE", "DEFAULT_PER_PAGE",
    "get_pagination_params", "get_limit_offset",
    "paginated_response", "legacy_paginated_response",
]
