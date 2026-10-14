"""What the platform knows about each system: identity, adapter, intake.

The System Registry screen and ``GET /api/v1/systems`` both need one row per
system combining three sources that never met before: the system's own
manifest (key, display name, interfaces), whether it has registered a
transition adapter and what that adapter can do, and how its bus intake is
keeping up.

The manifests come from ``systems/registry.py``, the display-name source of
truth. The platform must not depend on any system at import time, so the
registry is resolved by name when this runs — the same late binding
``bus_consumers`` uses for the intake registrars — and if it cannot be
loaded the keys and labels in ``paths`` are used instead, with the error
reported on each row.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

from education_system.paths import SYSTEM_LABELS, SYSTEM_ORDER

logger = logging.getLogger(__name__)

_REGISTRY_MODULE = "education_system.systems.registry"


def manifests() -> tuple[list[dict[str, Any]], str | None]:
    """``([manifest dict, ...], error)`` in registry order."""
    try:
        registry = importlib.import_module(_REGISTRY_MODULE)
        return [{
            "key": m.key,
            "display_name": m.display_name,
            "package_dir": m.package_dir,
            "interfaces": sorted(m.interfaces),
        } for m in registry.all_manifests()], None
    except Exception as exc:
        logger.warning("System registry unavailable: %s", exc)
        return [{
            "key": key,
            "display_name": SYSTEM_LABELS.get(key, key),
            "package_dir": None,
            "interfaces": [],
        } for key in SYSTEM_ORDER], str(exc)


def _open_counts(db_path: str | None) -> tuple[dict[str, int], dict[str, int]]:
    from education_system.platform.features.analytics.transfer_monitor import (
        search_transitions,
    )
    inbound: dict[str, int] = {}
    outbound: dict[str, int] = {}
    for row in search_transitions(open_only=True, limit=2000, db_path=db_path):
        inbound[row["destination_system"]] = inbound.get(row["destination_system"], 0) + 1
        if row.get("source_system"):
            outbound[row["source_system"]] = outbound.get(row["source_system"], 0) + 1
    return inbound, outbound


def describe_systems(*, db_path: str | None = None) -> list[dict[str, Any]]:
    """One row per system: manifest, adapter capabilities, intake health."""
    rows, registry_error = manifests()
    try:
        from education_system.platform.cross_system.adapters import registry as adapters
        capability_matrix = adapters.capability_matrix()
    except Exception:
        logger.debug("Adapter registry unavailable", exc_info=True)
        capability_matrix = {}
    from education_system.platform.integrations.external import bus_drainer
    try:
        inbound, outbound = _open_counts(db_path)
    except Exception:
        logger.debug("Transition counts unavailable", exc_info=True)
        inbound, outbound = {}, {}

    out = []
    for row in rows:
        key = row["key"]
        caps = capability_matrix.get(key)
        out.append({
            **row,
            "registry_error": registry_error,
            "adapter_registered": caps is not None,
            "adapter_capabilities": caps or {},
            "intake": bus_drainer.intake_status(key, db_path=db_path),
            "open_inbound_transitions": inbound.get(key, 0),
            "open_outbound_transitions": outbound.get(key, 0),
        })
    return out


__all__ = ["describe_systems", "manifests"]
