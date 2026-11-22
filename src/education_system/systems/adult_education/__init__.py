"""Adult Education System (19+: community learning, Adult Skills Fund courses,
evening and part-time classes).

Signed in through the shared login and started by the unified launcher::

    python -m education_system --adulteducation --gui    # or --cli

Not yet a member of the cross-system linked platform.
"""

# manifest.py is the single source of truth for the key, name and interfaces.
from education_system.systems.adult_education.manifest import MANIFEST, SYSTEM_NAME  # noqa: F401

SYSTEM_KEY = MANIFEST.key
