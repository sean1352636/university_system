"""Manifest for the Secondary School System.

Years 7-11 (KS3, KS4). Note the key is ``secondary`` while some older
cross-system identity columns still use the ``school`` prefix.
"""

from education_system.platform.kernel.system_manifest import SystemManifest

MANIFEST = SystemManifest(
    key="secondary",
    display_name="Secondary School System",
    package_dir="systems/secondary",
    interfaces=frozenset({"cli", "gui", "api"}),
)

#: Backwards-compatible alias. SYSTEM_NAME is re-exported from this
#: package's __init__ and used for window titles and CLI banners.
SYSTEM_NAME = MANIFEST.display_name
