"""The response for a route that exists but has no implementation yet.

A menu feature with no API route is invisible: a client cannot tell whether
it is unsupported or simply undiscovered. A route that answers 501 with the
feature's name is honest and, unlike a 404, appears in the OpenAPI document —
so the gap between "what the desktop app offers" and "what the API serves" is
countable rather than folklore.

501 rather than 404 or 200-with-empty-list: the resource is a legitimate part
of this API's surface, the server just does not implement it yet. A client
should not retry, and should not treat the empty case as "no records".
"""

from __future__ import annotations

from education_system.platform.delivery.api.kernel.problems import problem


def feature_pending(feature: str, system: str, *, category: str = ""):
    """501 naming the menu feature this route will serve."""
    return problem(
        501,
        f"{feature!r} is offered by the {system} main menu but is not yet "
        "implemented in the API.",
        type_slug="feature-not-implemented",
        feature=feature,
        system=system,
        category=category or None,
    )


__all__ = ["feature_pending"]
