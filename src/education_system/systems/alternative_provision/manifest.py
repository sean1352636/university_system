"""Manifest for the Alternative Provision System.

Listed in ``systems/registry.py`` and linked to the shared sign-in and the
launcher (2026-11-08). Not yet a cross-system (linked-platform) member.
"""

from education_system.platform.kernel.system_manifest import SystemManifest

MANIFEST = SystemManifest(
    key="alternative_provision",
    display_name="Alternative Provision System",
    package_dir="systems/alternative_provision",
    interfaces=frozenset({"cli", "gui"}),
)

#: Used for window titles and CLI banners.
SYSTEM_NAME = MANIFEST.display_name
