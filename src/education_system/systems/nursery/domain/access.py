"""Who may open what in the Nursery System (GUI and CLI).

Nursery has no role matrix and seeds only admin accounts, but User Accounts can
grant any shared role, and such a login used to get every screen. So the rule is
the minimal one: admin and staff keep every screen; a student or parent gets
their own account settings and a message; any other role gets nothing.
"""

from __future__ import annotations

from education_system.platform.identity.menu_access import MenuPolicy, Principal
from education_system.systems.nursery import SYSTEM_SLUG

__all__ = ["POLICY", "Principal", "from_auth", "set_current", "current_for"]


def _superadmin(user_info) -> bool:
    from education_system.launcher.roles import is_superadmin
    return is_superadmin(user_info)


POLICY = MenuPolicy(
    SYSTEM_SLUG,
    superadmin_check=_superadmin,
    messages={
        "student": ("Learner accounts cannot open the nursery's staff screens. "
                    "Please contact the nursery office."),
        "parent": ("Parent accounts cannot open the nursery's staff screens. "
                   "Please contact the nursery office."),
        "": ("Your account does not have a role that can use the Nursery "
             "System. Please contact the nursery office."),
    },
)

from_auth = POLICY.from_auth
set_current = POLICY.set_current
current_for = POLICY.current_for
