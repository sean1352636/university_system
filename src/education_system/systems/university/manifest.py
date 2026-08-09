"""Manifest for the University System.

Higher education, and by far the largest system. The only one shipping its own
static web bundle (``assets/web``), hence the extra "web" interface.
"""

from education_system.platform.kernel.system_manifest import SystemManifest

MANIFEST = SystemManifest(
    key="university",
    display_name="University System",
    package_dir="systems/university",
    interfaces=frozenset({"cli", "gui", "api", "web"}),
)

#: Backwards-compatible alias. SYSTEM_NAME is re-exported from this
#: package's __init__ and used for window titles and CLI banners.
SYSTEM_NAME = MANIFEST.display_name
