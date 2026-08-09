"""Manifest for the FE College System.

Further education. A full member of the cross-system registry: its own
student_journey slot, an entry in paths.SYSTEM_DB_PATHS, and a PhaseAdapter.
"""

from education_system.platform.kernel.system_manifest import SystemManifest

MANIFEST = SystemManifest(
    key="fe_college",
    display_name="FE College System",
    package_dir="systems/fe_college",
    interfaces=frozenset({"cli", "gui", "api"}),
)

#: Backwards-compatible alias. SYSTEM_NAME is re-exported from this
#: package's __init__ and used for window titles and CLI banners.
SYSTEM_NAME = MANIFEST.display_name
