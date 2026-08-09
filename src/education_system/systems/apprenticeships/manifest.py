"""Manifest for the Apprenticeships System.

A post-16 destination beside the phase chain rather than a step on it:
secondary, sixth form and FE feed it, it runs concurrently with university for a
degree apprenticeship, and it feeds back for a top-up.
"""

from education_system.platform.kernel.system_manifest import SystemManifest

MANIFEST = SystemManifest(
    key="apprenticeships",
    display_name="Apprenticeships System",
    package_dir="systems/apprenticeships",
    interfaces=frozenset({"cli", "gui", "api"}),
)

#: Backwards-compatible alias. SYSTEM_NAME is re-exported from this
#: package's __init__ and used for window titles and CLI banners.
SYSTEM_NAME = MANIFEST.display_name
