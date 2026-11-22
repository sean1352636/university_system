"""Manifest for the Adult Education System.

Listed in ``systems/registry.py`` and linked to the shared sign-in and the
launcher (2026-11-08). Not yet a cross-system (linked-platform) member.
"""

from education_system.platform.kernel.system_manifest import SystemManifest

MANIFEST = SystemManifest(
    key="adult_education",
    display_name="Adult Education System",
    package_dir="systems/adult_education",
    interfaces=frozenset({"cli", "gui"}),
)

#: Used for window titles and CLI banners.
SYSTEM_NAME = MANIFEST.display_name
