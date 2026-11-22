"""Alternative Provision System (pupil referral units, AP academies and
commissioned placements for pupils who can't attend mainstream school).

Signed in through the shared login and started by the unified launcher::

    python -m education_system --alternativeprovision --gui    # or --cli

Not yet a member of the cross-system linked platform.
"""

# manifest.py is the single source of truth for the key, name and interfaces.
from education_system.systems.alternative_provision.manifest import MANIFEST, SYSTEM_NAME  # noqa: F401

SYSTEM_KEY = MANIFEST.key
