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


def test_manifest_routes_name_modules_that_exist(monkeypatch) -> None:
    """A route reference that points nowhere only fails once someone enables the plugin."""
    import importlib.util

    monkeypatch.delenv("EDUCATION_UNIVERSITY_PLUGINS", raising=False)
    missing = [
        reference
        for plugin in discover_plugins().values()
        for reference in plugin.routes
        if importlib.util.find_spec(reference.split(":", 1)[0]) is None
    ]
    assert not missing, f"manifest routes name missing modules: {missing}"


def test_already_registered_blueprints_are_skipped(monkeypatch) -> None:
    class Blueprint:
        def __init__(self, name):
            self.name = name

    class App:
        def __init__(self):
            self.blueprints = {"shared_bp": object()}
            self.registered = []

        def register_blueprint(self, blueprint) -> None:
            self.registered.append(blueprint.name)

    module = type("M", (), {"shared_bp": Blueprint("shared_bp"), "new_bp": Blueprint("new_bp")})
    monkeypatch.setenv("EDUCATION_UNIVERSITY_PLUGINS", "campus-commerce")
    monkeypatch.setattr(
        "education_system.systems.university.plugins.registry.importlib.import_module",
        lambda name: module,
    )
    from education_system.systems.university.plugins import registry

    manifests = registry.discover_plugins()
    fake = registry.PluginManifest(**{**{f: getattr(manifests["campus-commerce"], f)
                                          for f in ("id", "version", "capabilities", "permissions",
                                                    "data_classifications", "support", "raw")},
                                      "routes": ("education_system.x:shared_bp", "education_system.x:new_bp")})
    monkeypatch.setattr(registry, "discover_plugins", lambda: {"campus-commerce": fake})

    app = App()
    assert registry.register_enabled_plugin_routes(app) == ["campus-commerce"]
    assert app.registered == ["new_bp"]
