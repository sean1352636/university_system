"""Validated, disabled-by-default university runtime plugin registry."""

from __future__ import annotations

import importlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema

PLUGIN_ROOT = Path(__file__).resolve().parent


class CapabilityUnavailableError(RuntimeError):
    """An enabled optional capability cannot be loaded in this installation."""

    def __init__(self, plugin_id: str, module_name: str, dependency: str) -> None:
        self.plugin_id = plugin_id
        self.module_name = module_name
        self.dependency = dependency
        super().__init__(
            f"University plugin {plugin_id!r} is enabled, but capability module "
            f"{module_name!r} is unavailable because {dependency!r} is not "
            "installed. Install the plugin's declared dependency profile or "
            "disable it in EDUCATION_UNIVERSITY_PLUGINS."
        )


@dataclass(frozen=True, slots=True)
class PluginManifest:
    id: str
    version: str
    capabilities: tuple[str, ...]
    routes: tuple[str, ...]
    permissions: tuple[str, ...]
    data_classifications: tuple[str, ...]
    support: str
    raw: dict[str, Any]


def load_manifest(path: Path) -> PluginManifest:
    raw = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads(
        (PLUGIN_ROOT / "manifest.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(raw, schema)
    if raw.get("canonicalWrites"):
        raise ValueError("Optional plugins cannot write canonical student data")
    return PluginManifest(
        id=raw["id"],
        version=raw["version"],
        capabilities=tuple(raw["capabilities"]),
        routes=tuple(raw.get("routes", ())),
        permissions=tuple(raw["permissions"]),
        data_classifications=tuple(raw["dataClassifications"]),
        support=raw["support"],
        raw=raw,
    )


def discover_plugins() -> dict[str, PluginManifest]:
    manifests = {}
    for path in sorted(PLUGIN_ROOT.glob("*/plugin.json")):
        manifest = load_manifest(path)
        if manifest.id in manifests:
            raise ValueError(f"Duplicate plugin id {manifest.id!r}")
        manifests[manifest.id] = manifest
    return manifests


def enabled_plugin_ids() -> frozenset[str]:
    value = os.getenv("EDUCATION_UNIVERSITY_PLUGINS", "")
    return frozenset(item.strip() for item in value.split(",") if item.strip())


def register_enabled_plugin_routes(app) -> list[str]:
    manifests = discover_plugins()
    enabled = enabled_plugin_ids()
    unknown = enabled - manifests.keys()
    if unknown:
        raise ValueError(f"Unknown university plugins: {', '.join(sorted(unknown))}")
    registered = []
    for plugin_id in sorted(enabled):
        manifest = manifests[plugin_id]
        for reference in manifest.routes:
            module_name, attribute = reference.split(":", 1)
            try:
                module = importlib.import_module(module_name)
            except ModuleNotFoundError as exc:
                raise CapabilityUnavailableError(
                    plugin_id, module_name, exc.name or module_name
                ) from exc
            blueprint = getattr(module, attribute)
            # Core may already register a plugin's blueprints unconditionally
            # (campus commerce's routes still are); enabling the plugin must
            # not then fail on a duplicate blueprint name.
            if getattr(blueprint, "name", None) in getattr(app, "blueprints", {}):
                continue
            app.register_blueprint(blueprint)
        registered.append(plugin_id)
    return registered


__all__ = [
    "CapabilityUnavailableError",
    "PluginManifest",
    "discover_plugins",
    "enabled_plugin_ids",
    "load_manifest",
    "register_enabled_plugin_routes",
]
