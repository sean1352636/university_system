"""The controller every FE College window talks to.

The implementation lives in
:mod:`education_system.systems.fe_college.services.session`, because the CLI
holds exactly the same object: identity resolution ("which staff record is this
account?") and view scoping ("what may they see?") are rules, and a rule
implemented twice is a rule that drifts. This module is the GUI's name for it.

Windows should keep importing ``CollegeController`` from here — it is the GUI's
stable entry point regardless of where the implementation sits.
"""

from __future__ import annotations

from education_system.systems.fe_college.services.session import (
    ROLE_VIEWS,
    CollegeSession,
    Identity,
)

# The GUI's name for the shared session object.
CollegeController = CollegeSession

__all__ = ["ROLE_VIEWS", "CollegeController", "CollegeSession", "Identity"]
