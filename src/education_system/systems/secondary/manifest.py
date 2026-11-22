"""Manifest for the Secondary School System (Years 7-11, KS3 and KS4)."""

from education_system.platform.kernel.system_manifest import SystemManifest

MANIFEST = SystemManifest(
    key="secondary",
    display_name="Secondary School System",
    package_dir="systems/secondary",
    interfaces=frozenset({"cli", "gui"}),
)

#: Used for window titles and CLI banners.
SYSTEM_NAME = MANIFEST.display_name
