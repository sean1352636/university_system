"""The canonical authorization decorator surface.

One import site for the gates, so a route module does not have to know
whether a given decorator came from the shared auth layer or the
university principals module:

    token_required        a valid access token
    require_staff         a recognised staff role (+ optional permission)
    staff_required        same, usable bare or with arguments
    authorize_object      object-scope check — the IDOR gate
    scoped_to             authorize_object driven by a view argument
    deny_unless_owner_or_staff
    role_required         one of a set of roles
    system_required       access to a named system

Why this module exists: there are on the order of 378 routes that take an
object identifier, and only a handful currently carry a gate. Naming the
gates in one place is what lets an authz-coverage test assert "every
mounted route has one" against :mod:`...registry`, rather than grepping
for decorator names across a dozen packages.
"""

from education_system.platform.delivery.api.security.principals import (  # noqa: F401
    authorize_object,
    current_subject_id,
    deny_unless_owner_or_staff,
    is_staff,
    require_staff,
    scoped_to,
    staff_required,
    token_required,
)
from education_system.platform.delivery.api.security.authentication import (  # noqa: F401
    role_required,
    system_required,
)
from education_system.platform.delivery.api.security.authentication import (  # noqa: F401
    token_required as shared_token_required,
)

__all__ = [
    "token_required",
    "shared_token_required",
    "require_staff",
    "staff_required",
    "authorize_object",
    "scoped_to",
    "deny_unless_owner_or_staff",
    "role_required",
    "system_required",
    "is_staff",
    "current_subject_id",
]
