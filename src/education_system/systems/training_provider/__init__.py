"""Training Provider System (short courses, accredited qualifications and CPD
for individuals and employer clients).

Signed in through the shared login and started by the unified launcher::

    python -m education_system --trainingprovider --gui    # or --cli

Not yet a member of the cross-system linked platform.
"""

# manifest.py is the single source of truth for the key, name and interfaces.
from education_system.systems.training_provider.manifest import MANIFEST, SYSTEM_NAME  # noqa: F401

SYSTEM_KEY = MANIFEST.key
