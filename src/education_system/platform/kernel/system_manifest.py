"""The contract each education system publishes about itself.

A system's identity — its key, how it should be named in the UI, and which
interfaces it actually provides — belongs to that system, not to whichever
caller happens to need it. Before this existed the same facts were restated in
five places (``launcher.main.SYSTEM_DISPLAY_NAMES`` and ``SYSTEM_PACKAGE_DIRS``,
``launcher.roles.SYSTEM_NAMES``, ``launcher.system_switch.SYSTEM_LABELS``, and
each package's own ``SYSTEM_NAME``) and had already drifted: the sixth form was
variously "Sixth Form", "Sixth Form System" and "Sixth Form College", and the
university exported no name at all.

Each system now declares one :class:`SystemManifest` in its ``manifest.py``,
and :mod:`education_system.systems.registry` collects them.

This module is deliberately dependency-free — plain stdlib, no imports from any
system — so that reading a system's identity never drags its implementation in.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Interfaces a system can provide. Used to validate manifests rather than to
#: describe what the launcher can do with them: a system declaring "api" owns
#: route blueprints under ``interfaces/api/routes/``, which the shared API
#: platform mounts; it does not mean the system hosts its own server.
KNOWN_INTERFACES = frozenset({"cli", "gui", "api", "web"})


@dataclass(frozen=True, slots=True)
class SystemManifest:
    """Immutable description of one education system.

    Attributes:
        key: Stable identifier used by the launcher, auth seeding, the
            cross-system registry and ``paths.SYSTEM_DB_PATHS``. Never
            user-facing, never translated.
        display_name: The one canonical human-readable name. All seven systems
            use the "<Name> System" form.
        package_dir: Repo-relative path of the system package, used to locate
            shipped assets such as ``assets/web``.
        interfaces: Which of :data:`KNOWN_INTERFACES` this system provides.
    """

    key: str
    display_name: str
    package_dir: str
    interfaces: frozenset[str]

    def __post_init__(self) -> None:
        unknown = self.interfaces - KNOWN_INTERFACES
        if unknown:
            raise ValueError(
                f"{self.key}: unknown interface(s) {sorted(unknown)}; "
                f"expected a subset of {sorted(KNOWN_INTERFACES)}"
            )
        if not self.key or not self.key.islower():
            raise ValueError(f"system key must be a lowercase identifier, got {self.key!r}")

    def provides(self, interface: str) -> bool:
        """Return whether this system provides *interface*."""
        return interface in self.interfaces
