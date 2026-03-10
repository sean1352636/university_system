"""
Compatibility shim for ``university_system.infrastructure.ai``.

The AI utilities live under ``university_system.utils.ai`` but some
parts of the codebase import them from the ``infrastructure``
namespace.  This package forwards those imports to the correct
location.
"""

from importlib import import_module as _import_module

_mod = _import_module('university_system.utils.ai')

__all__ = getattr(_mod, '__all__', [])
for _name in dir(_mod):
    if not _name.startswith('_'):
        globals()[_name] = getattr(_mod, _name)
