"""The single mount table: the whole URL surface, as data.

Every system's blueprints were registered by a hand-written ``try/except``
block in the app factory — five near-identical copies of "import these
names, loop, reprefix, register, log, swallow failure". The consequence
was that nothing could enumerate the API. When the university blueprints
stopped importing, the app logged one ERROR line and served on, missing
62 route modules, and no test noticed.

Declaring the surface as data fixes that. This list is:

* what :func:`.app.create_app` mounts,
* what ``openapi/spec.py`` walks to generate the spec,
* what an authz-coverage test iterates.

With roughly 378 routes that take an object identifier and only a handful
carrying a capability gate, "every route has a gate" becomes a test
against :func:`iter_routes` rather than a grep somebody has to remember
to run.

Blueprints are resolved lazily, by import path, so a broken system does
not stop the others from mounting — but the failure is recorded on the
:class:`Mount` instead of vanishing into a log line.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

from education_system.platform.delivery.api.versioning import API_PREFIX, reprefix

logger = logging.getLogger(__name__)


@dataclass
class Mount:
    """One system's blueprints, and where they hang.

    ``loader`` names the module and attribute to import, e.g.
    ``("education_system.api.nursery.routes",
    "ALL_BLUEPRINTS")``. Kept as a string pair rather than an imported
    object so building the table never imports a system.
    """
    key: str
    prefix: str
    module: str
    attribute: str = "ALL_BLUEPRINTS"
    #: Names to pull when the module exports blueprints individually
    #: rather than as one list.
    names: tuple[str, ...] = ()
    #: False for a system whose routes are not written yet. It still
    #: appears here so the gap is visible and countable.
    wired: bool = True
    label: str = ""
    #: Set when loading fails, so callers can report rather than guess.
    error: str | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if not self.label:
            self.label = self.key.replace("_", " ").title()

    def load(self) -> list[Any]:
        """Import and return this system's blueprints.

        Never raises: a system that cannot be imported records the reason
        on ``self.error`` and contributes nothing. That keeps one broken
        system from taking down the whole API, while leaving the failure
        inspectable — see :func:`mount_report`.
        """
        self.error = None
        if not self.wired:
            self.error = "not wired yet"
            return []
        try:
            module = importlib.import_module(self.module)
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            logger.error("Mount %r could not import %s: %s",
                         self.key, self.module, exc)
            return []
        try:
            if self.names:
                return [getattr(module, n) for n in self.names]
            return list(getattr(module, self.attribute))
        except AttributeError as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            logger.error("Mount %r: %s", self.key, exc)
            return []


#: The entire system surface. Order is mount order.
SYSTEMS: list[Mount] = [
    Mount(
        key="university",
        prefix=f"{API_PREFIX}/university",
        module="education_system.api.university",
        # The university route package was removed on 2026-09-08 and is being
        # rebuilt module by module. ALL_BLUEPRINTS there grows one blueprint
        # at a time; the unified server mounts it through this entry.
        wired=True,
        label="University",
    ),
    Mount(
        key="sixthform",
        prefix=f"{API_PREFIX}/sixthform",
        module="education_system.api.sixth_form.routes",
        label="Sixth Form College",
    ),
    Mount(
        key="school",
        prefix=f"{API_PREFIX}/school",
        module="education_system.api.secondary.routes",
        label="Secondary School",
    ),
    Mount(
        key="primary",
        prefix=f"{API_PREFIX}/primary",
        module="education_system.api.primary.routes",
        label="Primary School",
    ),
    Mount(
        key="nursery",
        prefix=f"{API_PREFIX}/nursery",
        module="education_system.api.nursery.routes",
        label="Nursery / Early Years",
    ),
    Mount(
        key="fecollege",
        prefix=f"{API_PREFIX}/fecollege",
        module="education_system.api.fe_college.routes",
        # Wired now that the main-menu routes give it a surface; the resource
        # modules beside them are still empty.
        wired=True,
        label="FE College",
    ),
    Mount(
        key="apprentice",
        prefix=f"{API_PREFIX}/apprentice",
        module="education_system.api.apprenticeships.routes",
        wired=True,
        label="Apprenticeships",
    ),
]

#: Platform blueprints — not system-scoped, mounted at the version root.
PLATFORM: list[tuple[str, str]] = [
    ("education_system.platform.delivery.api.routes.auth_routes", "auth_bp"),
    ("education_system.platform.delivery.api.routes.health_routes", "health_bp"),
    ("education_system.platform.delivery.api.routes.admin_control_routes",
     "admin_control_bp"),
    ("education_system.platform.delivery.api.routes.metrics_routes", "metrics_bp"),
    ("education_system.platform.delivery.api.routes.tenant_routes", "tenant_bp"),
    ("education_system.platform.delivery.api.routes.retention_routes", "retention_bp"),
    ("education_system.platform.delivery.api.routes.journey_routes", "journey_bp"),
    # Learners, transfers, systems and events — mounted at the version root
    # because its routes are /learners, /transfers, /systems, /events.
    ("education_system.platform.delivery.api.routes.learners_routes", "learners_bp"),
    ("education_system.platform.delivery.api.routes.notification_routes",
     "notification_prefs_bp"),
    ("education_system.platform.delivery.api.routes.warehouse_routes", "warehouse_bp"),
    ("education_system.platform.delivery.api.routes.webhook_routes", "webhook_bp"),
    ("education_system.platform.delivery.api.lms_routes", "lms_bp"),
]

#: Mount key -> the system's registry key, where the URL segment differs.
#: The URL segments predate the canonical keys and are kept for clients;
#: this is how /api/v1/systems and the index put the two side by side.
MOUNT_SYSTEM_KEYS: dict[str, str] = {
    "sixthform": "sixth_form",
    "school": "secondary",
    "fecollege": "fe_college",
    "apprentice": "apprenticeships",
}


def system_key_for(mount: Mount) -> str:
    """The registry system key a mount serves."""
    return MOUNT_SYSTEM_KEYS.get(mount.key, mount.key)


def mounts_by_system() -> dict[str, Mount]:
    """``{system key: Mount}`` for every system in the mount table."""
    return {system_key_for(m): m for m in SYSTEMS}


def get_mount(key: str) -> Mount | None:
    for mount in SYSTEMS:
        if mount.key == key:
            return mount
    return None


def wired_systems() -> list[Mount]:
    return [m for m in SYSTEMS if m.wired]


def unwired_systems() -> list[Mount]:
    """Systems declared but with no routes yet — the visible backlog."""
    return [m for m in SYSTEMS if not m.wired]


def iter_mounted_blueprints() -> Iterator[tuple[Mount, Any, str]]:
    """Yield ``(mount, blueprint, url_prefix)`` for everything mountable."""
    for mount in SYSTEMS:
        for blueprint in mount.load():
            yield mount, blueprint, reprefix(blueprint.url_prefix, mount.key)


def iter_routes(app) -> Iterator[dict]:
    """Every mounted route on *app*, as inspectable records.

    The input to coverage tests: which system a rule belongs to, what
    methods it answers, and the view function to check for a gate.
    """
    for rule in app.url_map.iter_rules():
        view = app.view_functions.get(rule.endpoint)
        system = None
        for mount in SYSTEMS:
            if str(rule.rule).startswith(mount.prefix):
                system = mount.key
                break
        yield {
            "rule": str(rule.rule),
            "endpoint": rule.endpoint,
            "methods": sorted(rule.methods - {"HEAD", "OPTIONS"}),
            "system": system,
            "view": view,
            # A route taking an identifier is the IDOR surface — these are
            # the ones an authz test must insist on.
            "takes_object_id": bool(rule.arguments),
        }


def mount_report() -> list[dict]:
    """What loaded, what did not, and why. For startup logging and tests."""
    report = []
    for mount in SYSTEMS:
        blueprints = mount.load()
        report.append({
            "key": mount.key,
            "label": mount.label,
            "prefix": mount.prefix,
            "wired": mount.wired,
            "blueprints": len(blueprints),
            "error": mount.error,
        })
    return report


__all__ = ["Mount", "SYSTEMS", "PLATFORM", "get_mount", "wired_systems",
           "unwired_systems", "iter_mounted_blueprints", "iter_routes",
           "mount_report"]
