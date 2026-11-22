"""Manifest for the Training Provider System.

Listed in ``systems/registry.py`` and linked to the shared sign-in and the
launcher (2026-11-08). Not yet a cross-system (linked-platform) member.
"""

from education_system.platform.kernel.system_manifest import SystemManifest

MANIFEST = SystemManifest(
    key="training_provider",
    display_name="Training Provider System",
    package_dir="systems/training_provider",
    interfaces=frozenset({"cli", "gui"}),
)

#: Used for window titles and CLI banners.
SYSTEM_NAME = MANIFEST.display_name
