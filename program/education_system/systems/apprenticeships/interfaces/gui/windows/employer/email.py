"""Correspondence, as employers see it.

The same screen as the provider's, scoped by the service to what this
role may read, and with the send actions hidden because neither holds
``email.send``. Nav resolves modules inside each role's own package, so
a shared screen is re-exported rather than duplicated.
"""

from __future__ import annotations

from education_system.systems.apprenticeships.interfaces.gui.windows.admin.email import (
    render,
)

__all__ = ["render"]
