"""Special Education (SEND) System.

Signed in through the unified launcher like the other systems::

    python -m education_system --specialeducation --gui     # or --cli

It is not yet a member of the cross-system linked platform (no learner
adapter, no ``paths.SYSTEM_DB_PATHS`` entry).
"""

# manifest.py is the single source of truth for the key, name and interfaces.
from education_system.systems.special_education.manifest import MANIFEST, SYSTEM_NAME  # noqa: F401

SYSTEM_KEY = MANIFEST.key
