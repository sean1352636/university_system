"""Every main-menu feature must have an API route.

The GUI and CLI of each system present a navigation tree; a feature that
exists there but nowhere in the API is invisible to any other client. This
asserts the two stay in step, in both directions:

* a feature added to a menu without regenerating routes fails here;
* a generated route whose menu entry was removed fails here too, so the
  API does not accumulate endpoints for features that no longer exist.

Routes are enumerated from ``registry.py`` — the same mount table the server
uses — so this checks what is actually served, not what is on disk.
"""

from __future__ import annotations

import pytest
from flask import Flask

from education_system.platform.delivery.api.registry import SYSTEMS
from education_system.platform.delivery.api.versioning import reprefix
from education_system.systems.menu_inventory import SOURCES, all_menus, slugify

#: system_key in menu_inventory -> mount key in the registry.
MOUNT_KEYS = {
    "nursery": "nursery",
    "primary": "primary",
    "secondary": "school",
    "sixth_form": "sixthform",
    "fe_college": "fecollege",
    "apprenticeships": "apprentice",
}


def _mounted_paths(mount_key: str) -> set[str]:
    mount = next(m for m in SYSTEMS if m.key == mount_key)
    app = Flask(mount_key)
    for blueprint in mount.load():
        app.register_blueprint(
            blueprint, url_prefix=reprefix(blueprint.url_prefix, mount_key))
    return {str(rule) for rule in app.url_map.iter_rules()}


@pytest.fixture(scope="module")
def menus():
    return all_menus()


def test_every_system_menu_is_readable(menus):
    """Guard the guard: a menu that fails to load would vacuously pass."""
    missing = sorted(set(SOURCES) - set(menus))
    assert not missing, f"could not read the menu for: {', '.join(missing)}"
    for system, menu in menus.items():
        assert menu, f"{system} produced an empty menu"


@pytest.mark.parametrize("system", sorted(MOUNT_KEYS))
def test_every_menu_feature_has_a_route(system, menus):
    paths = _mounted_paths(MOUNT_KEYS[system])
    missing = []
    for category, features in sorted(menus[system].items()):
        for feature in features:
            expected = f"/api/v1/{MOUNT_KEYS[system]}/menu/{slugify(category)}/{slugify(feature)}"
            if expected not in paths:
                missing.append(f"{category} / {feature}  ->  {expected}")
    assert not missing, (
        f"{system}: menu features with no API route:\n  "
        + "\n  ".join(missing)
        + "\n\nRegenerate with: python tools/gen_menu_routes.py"
    )


@pytest.mark.parametrize("system", sorted(MOUNT_KEYS))
def test_no_menu_routes_for_features_that_no_longer_exist(system, menus):
    expected = {
        f"/api/v1/{MOUNT_KEYS[system]}/menu/{slugify(category)}/{slugify(feature)}"
        for category, features in menus[system].items()
        for feature in features
    }
    served = {p for p in _mounted_paths(MOUNT_KEYS[system]) if "/menu/" in p}
    orphans = sorted(served - expected)
    assert not orphans, (
        f"{system}: menu routes with no matching menu entry:\n  "
        + "\n  ".join(orphans)
        + "\n\nThe feature was removed from the menu. Regenerate with: "
        "python tools/gen_menu_routes.py"
    )
