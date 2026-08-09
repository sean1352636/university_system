"""Lazy university route catalogue.

Importing a core route no longer imports every optional desktop, analytics,
commerce and campus module. Legacy callers that import blueprint attributes
from this package are resolved lazily through ``all_routes``.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flask import Flask


def __getattr__(name: str) -> Any:
    module = import_module(
        "education_system.platform.delivery.api.university.routes.all_routes"
    )
    try:
        return getattr(module, name)
    except AttributeError as exc:
        raise AttributeError(f"Unknown university route export {name!r}") from exc


def register_routes(app: "Flask") -> None:
    module = import_module(
        "education_system.platform.delivery.api.university.routes.all_routes"
    )
    module.register_routes(app)


__all__ = ["register_routes"]
