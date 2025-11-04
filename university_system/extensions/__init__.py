"""
Compatibility shim for the ``university_system.extensions`` package.

All extension modules live under ``university_system.modules.extensions``.
This stub ensures that imports like ``university_system.extensions``
continue to resolve correctly by re‑exporting the real package's
contents.  Prefer importing from ``university_system.modules.extensions``
directly in new code.
"""

from importlib import import_module as _import_module

# This module is designed to run on import to provide compatibility
# It should not be run as a standalone script
if __name__ == '__main__':
    raise RuntimeError(
        "This module is a compatibility shim and should not be run directly. "
        "Import it instead: from university_system import extensions"
    )

_real_extensions = _import_module('university_system.modules.extensions')

__all__ = getattr(_real_extensions, '__all__', [])
for _name in dir(_real_extensions):
    if not _name.startswith('_'):
        globals()[_name] = getattr(_real_extensions, _name)
