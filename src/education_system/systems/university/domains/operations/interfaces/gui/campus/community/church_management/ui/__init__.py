"""Moved to ``education_system.systems.university.plugins.community_services.interfaces.gui.church_management.ui`` (community services plugin).

A mirror, not an alias: an aliased package would resolve this package's
submodules through the new ``__path__`` and load each one a second time.
Submodules are aliased individually; this copies the package's names.
"""
# layout-shim: education_system.systems.university.plugins.community_services.interfaces.gui.church_management.ui
import importlib as _importlib

_new = _importlib.import_module("education_system.systems.university.plugins.community_services.interfaces.gui.church_management.ui")
globals().update({k: v for k, v in vars(_new).items()
                  if not (k.startswith("__") and k.endswith("__"))})
del _importlib, _new
