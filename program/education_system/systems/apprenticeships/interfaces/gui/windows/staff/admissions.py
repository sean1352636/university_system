"""The admissions queue, as a tutor sees it.

One screen, not two: the admin version already gates Accept and Decline
on ``admission.decide``, which staff do not hold, so a tutor opening this
gets the same queue in read-only form. Re-exporting keeps a single
implementation while honouring the convention that each role's navigation
resolves modules inside its own package.
"""

from __future__ import annotations

from education_system.systems.apprenticeships.interfaces.gui.windows.admin.admissions import (
    render,
)

__all__ = ["render"]
