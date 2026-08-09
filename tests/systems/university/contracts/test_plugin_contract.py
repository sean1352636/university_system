from __future__ import annotations

import pytest

from education_system.systems.university.plugins.registry import (
    CapabilityUnavailableError,
    discover_plugins,
    register_enabled_plugin_routes,
)


def test_plugins_are_valid_and_cannot_write_canonical_data(monkeypatch) -> None:
    monkeypatch.delenv("EDUCATION_UNIVERSITY_PLUGINS", raising=False)
    plugins = discover_plugins()

    assert {"campus-commerce", "community-services"} <= plugins.keys()
    assert all(not plugin.raw["canonicalWrites"] for plugin in plugins.values())
    assert all(plugin.permissions for plugin in plugins.values())
    assert all(plugin.data_classifications for plugin in plugins.values())


def test_peripheral_plugins_are_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("EDUCATION_UNIVERSITY_PLUGINS", raising=False)
    from education_system.systems.university.plugins.registry import enabled_plugin_ids

    assert enabled_plugin_ids() == frozenset()


def test_enabled_plugin_reports_missing_capability_dependency(monkeypatch) -> None:
    class App:
        def register_blueprint(self, blueprint) -> None:
            raise AssertionError("an unavailable blueprint must not be registered")

    monkeypatch.setenv("EDUCATION_UNIVERSITY_PLUGINS", "campus-commerce")

    def missing_module(name: str):
        error = ModuleNotFoundError("No module named 'optional_commerce'")
        error.name = "optional_commerce"
        raise error

    monkeypatch.setattr(
        "education_system.systems.university.plugins.registry.importlib.import_module",
        missing_module,
    )

    with pytest.raises(CapabilityUnavailableError, match="declared dependency profile"):
        register_enabled_plugin_routes(App())
