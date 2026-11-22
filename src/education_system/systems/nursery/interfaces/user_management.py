"""User Management — System (Nursery System).

Roles and access across the shared sign-in database (``auth.db``): the access
matrix, role distribution, bulk grant / revoke / activate, and the admin,
locked, inactive and no-access lists. The rules live in
``domain.governance.user_management`` (built on the shared
``interfaces.user_accounts`` helpers, so password rules, cascades and session
invalidation come from the platform auth service). This module is the System
menu's entry point to it, used by the GUI and the CLI.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.nursery.domain.governance.user_management import (
    user_management as _rules,
)

FEATURE_NAME = "User Management"


def snapshot(auth: Any) -> _rules.Snapshot:
    """Active / inactive / locked / admin counts across the shared accounts."""
    return _rules.snapshot(auth)


def open_gui(host: Any) -> None:
    """Draw the User Management screen into the nursery GUI host."""
    from education_system.systems.nursery.interfaces.gui.governance.user_management import (
        user_management_views,
    )
    user_management_views.open_user_management_window(host)


def run_cli(auth: Any) -> bool:
    """Run the User Management terminal menu; True when handled."""
    from education_system.systems.nursery.interfaces.cli.governance.user_management import (
        user_management_cli,
    )
    return user_management_cli.dispatch(FEATURE_NAME, auth=auth)


__all__ = ["FEATURE_NAME", "open_gui", "run_cli", "snapshot"]
