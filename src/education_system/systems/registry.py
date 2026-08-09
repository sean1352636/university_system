"""Registry of every education system's manifest.

Each system owns its identity in ``systems/<system>/manifest.py``; this module
is the one place that knows the full set. Callers that used to hard-code a
``{key: label}`` dict should read it from here instead, so a system's name is
defined exactly once.

Resolution is lazy and cached: importing this module costs nothing, and the
first call that needs the whole table imports the seven system packages
(measured at ~0.07s beyond interpreter start-up, against the ~0.21s the
launcher already spends importing ``launcher.systems``).

Deliberately *not* re-exported from ``systems/__init__.py``: that would make
importing any single system drag in all seven.
"""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module

from education_system.platform.kernel.system_manifest import SystemManifest

#: Declaration order, used for menus and any other listing. Roughly the learner
#: journey — early years through higher education — with the two post-16
#: destinations last.
SYSTEM_KEYS: tuple[str, ...] = (
    "nursery",
    "primary",
    "secondary",
    "sixth_form",
    "university",
    "apprenticeships",
    "fe_college",
)


@lru_cache(maxsize=None)
def get(key: str) -> SystemManifest:
    """Return the manifest for *key*, importing that system's package.

    Raises:
        KeyError: if *key* is not a known system.
    """
    if key not in SYSTEM_KEYS:
        raise KeyError(f"unknown system {key!r}; expected one of {list(SYSTEM_KEYS)}")
    module = import_module(f"education_system.systems.{key}.manifest")
    return module.MANIFEST


@lru_cache(maxsize=1)
def all_manifests() -> tuple[SystemManifest, ...]:
    """Return every system's manifest, in :data:`SYSTEM_KEYS` order."""
    return tuple(get(key) for key in SYSTEM_KEYS)


@lru_cache(maxsize=1)
def display_names() -> dict[str, str]:
    """Return ``{key: display_name}`` for every system."""
    return {m.key: m.display_name for m in all_manifests()}


@lru_cache(maxsize=1)
def package_dirs() -> dict[str, str]:
    """Return ``{key: package_dir}`` for every system."""
    return {m.key: m.package_dir for m in all_manifests()}


def providing(interface: str) -> tuple[str, ...]:
    """Return the keys of systems providing *interface*, in declaration order."""
    return tuple(m.key for m in all_manifests() if m.provides(interface))


__all__ = [
    "SYSTEM_KEYS",
    "all_manifests",
    "display_names",
    "get",
    "package_dirs",
    "providing",
]
