"""Fail if constructing the core API imports GUI/scientific packages."""

from __future__ import annotations

import builtins

BLOCKED = {
    "tkinter", "numpy", "pandas", "scipy", "matplotlib", "seaborn",
    "sklearn", "torch", "tensorflow",
}
original_import = builtins.__import__


def guarded_import(name, *args, **kwargs):
    if name.split(".", 1)[0] in BLOCKED:
        raise AssertionError(f"Minimal core imported optional dependency {name}")
    return original_import(name, *args, **kwargs)


builtins.__import__ = guarded_import
try:
    from education_system.platform.delivery.api.university.core_api import (
        create_core_app,
    )
    app = create_core_app(validate_schema=False)
    assert any(rule.rule == "/portal/journey" for rule in app.url_map.iter_rules())
finally:
    builtins.__import__ = original_import

print("minimal core smoke passed")
