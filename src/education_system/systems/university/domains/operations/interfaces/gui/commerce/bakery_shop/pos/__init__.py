"""Moved to ``education_system.systems.university.plugins.campus_commerce.interfaces.gui.bakery_shop.pos`` (campus commerce plugin).

A mirror, not an alias: an aliased package would resolve this package's
submodules through the new ``__path__`` and load each one a second time.
Submodules are aliased individually; this copies the package's names.
"""
# layout-shim: education_system.systems.university.plugins.campus_commerce.interfaces.gui.bakery_shop.pos
import importlib as _importlib

_new = _importlib.import_module("education_system.systems.university.plugins.campus_commerce.interfaces.gui.bakery_shop.pos")
globals().update({k: v for k, v in vars(_new).items()
                  if not (k.startswith("__") and k.endswith("__"))})
del _importlib, _new
