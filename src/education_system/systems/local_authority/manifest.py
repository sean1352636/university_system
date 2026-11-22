"""Manifest for the Local Authority Education System.

Listed in ``systems/registry.py`` and linked to the shared sign-in and the
launcher (2026-11-09). Not yet a cross-system (linked-platform) member.
"""

from education_system.platform.kernel.system_manifest import SystemManifest

MANIFEST = SystemManifest(
    key="local_authority",
    display_name="Local Authority Education System",
    package_dir="systems/local_authority",
    interfaces=frozenset({"cli", "gui"}),
)

#: Used for window titles and CLI banners.
SYSTEM_NAME = MANIFEST.display_name
