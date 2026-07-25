"""Smoke test for the Primary School system.

Confirms the package imports, its data paths redirect cleanly to a temporary
location, and its REST API blueprints register onto a Flask app. Write-free.
"""

import importlib

from flask import Flask


def test_package_and_cli_import():
    import education_system.systems.primary  # noqa: F401
    import education_system.systems.primary.cli_main  # noqa: F401


def test_data_paths_redirect_to_temp_dir(tmp_path, monkeypatch):
    from education_system.systems.primary.infrastructure import paths as paths_mod

    monkeypatch.setenv("EDU_PRIMARY_DATA_DIR", str(tmp_path))
    importlib.reload(paths_mod)
    try:
        assert str(paths_mod.PUPILS_DB).startswith(str(tmp_path))
    finally:
        monkeypatch.delenv("EDU_PRIMARY_DATA_DIR", raising=False)
        importlib.reload(paths_mod)


def test_api_blueprints_register():
    from education_system.platform.delivery.api.primary.routes import ALL_BLUEPRINTS

    app = Flask(__name__)
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)
    rules = [r.rule for r in app.url_map.iter_rules()]

    assert len(ALL_BLUEPRINTS) > 10
    assert len(rules) > 20
    assert any(r.startswith("/api/") for r in rules)


def test_protected_endpoint_requires_auth():
    from education_system.platform.delivery.api.primary.routes import ALL_BLUEPRINTS

    app = Flask(__name__)
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)
    resp = app.test_client().get("/api/absence-requests/")
    assert resp.status_code in (401, 403), resp.status_code
