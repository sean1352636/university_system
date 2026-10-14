"""Moved to ``education_system.systems.university.plugins.campus_commerce.interfaces.gui.cinema.cinema_gui.special_features`` (campus commerce plugin).

A mirror, not an alias: an aliased package would resolve this package's
submodules through the new ``__path__`` and load each one a second time.
Submodules are aliased individually; this copies the package's names.
"""
# layout-shim: education_system.systems.university.plugins.campus_commerce.interfaces.gui.cinema.cinema_gui.special_features
import importlib as _importlib

_new = _importlib.import_module("education_system.systems.university.plugins.campus_commerce.interfaces.gui.cinema.cinema_gui.special_features")
globals().update({k: v for k, v in vars(_new).items()
                  if not (k.startswith("__") and k.endswith("__"))})
del _importlib, _new
