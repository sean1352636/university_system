"""Manifest for the Nursery System.

Early years provision (0-5, EYFS). Route blueprints live under
``education_system/api/nursery/routes/`` and are mounted by the shared API
platform.
"""

from education_system.platform.kernel.system_manifest import SystemManifest

MANIFEST = SystemManifest(
    key="nursery",
    display_name="Nursery System",
    package_dir="systems/nursery",
    interfaces=frozenset({"cli", "gui", "api"}),
)

#: Backwards-compatible alias. SYSTEM_NAME is re-exported from this
#: package's __init__ and used for window titles and CLI banners.
SYSTEM_NAME = MANIFEST.display_name
