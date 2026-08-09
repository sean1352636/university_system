"""Manifest for the Sixth Form System.

Post-16 provision (16-19). Previously named inconsistently across the launcher
registries ("Sixth Form", "Sixth Form College", "Sixth Form System"); this
manifest is now the only place the name is defined.
"""

from education_system.platform.kernel.system_manifest import SystemManifest

MANIFEST = SystemManifest(
    key="sixth_form",
    display_name="Sixth Form System",
    package_dir="systems/sixth_form",
    interfaces=frozenset({"cli", "gui", "api"}),
)

#: Backwards-compatible alias. SYSTEM_NAME is re-exported from this
#: package's __init__ and used for window titles and CLI banners.
SYSTEM_NAME = MANIFEST.display_name
