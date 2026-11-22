"""Local Authority Education System (a council's education duties: admissions,
attendance and welfare, children missing education, home education,
exclusions, SEND / EHC plans and home-to-school transport).

Signed in through the shared login and started by the unified launcher::

    python -m education_system --localauthority --gui    # or --cli

Not yet a member of the cross-system linked platform.
"""

# manifest.py is the single source of truth for the key, name and interfaces.
from education_system.systems.local_authority.manifest import MANIFEST, SYSTEM_NAME  # noqa: F401

SYSTEM_KEY = MANIFEST.key
