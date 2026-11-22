"""Manifest for the Special Education (SEND) System.

Registered in ``systems/registry.py`` and the launcher (2026-11-08). Not yet
a cross-system member (no adapter, no ``paths.SYSTEM_DB_PATHS`` entry).
"""

from education_system.platform.kernel.system_manifest import SystemManifest

MANIFEST = SystemManifest(
    key="special_education",
    display_name="Special Education (SEND) System",
    package_dir="systems/special_education",
    interfaces=frozenset({"cli", "gui"}),
)

#: Used for window titles and CLI banners.
SYSTEM_NAME = MANIFEST.display_name
