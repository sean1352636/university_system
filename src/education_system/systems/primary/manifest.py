"""Manifest for the Primary School System.

Reception to Year 6 (EYFS, KS1, KS2).
"""

from education_system.platform.kernel.system_manifest import SystemManifest

MANIFEST = SystemManifest(
    key="primary",
    display_name="Primary School System",
    package_dir="systems/primary",
    interfaces=frozenset({"cli", "gui", "api"}),
)

#: Backwards-compatible alias. SYSTEM_NAME is re-exported from this
#: package's __init__ and used for window titles and CLI banners.
SYSTEM_NAME = MANIFEST.display_name
