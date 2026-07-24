"""Smoke test for the Nursery / Early Years system.

Confirms the package imports, its data paths redirect cleanly to a temporary
location (so tests never touch real data), and its REST API blueprints register
onto a Flask app. Write-free by design — it never opens the real nursery DB.
"""

import importlib

from flask import Flask
import pytest


def test_package_and_cli_import():
    import education_system.nursery_system  # noqa: F401
    import education_system.nursery_system.cli_main  # noqa: F401


def test_data_paths_redirect_to_temp_dir(tmp_path, monkeypatch):
    from education_system.nursery_system.core import paths as paths_mod

    monkeypatch.setenv("EDU_NURSERY_DATA_DIR", str(tmp_path))
    importlib.reload(paths_mod)
    try:
        # The DB now lives under the temp dir, proving the env override works
        # and that a test can fully isolate the nursery database.
        assert str(paths_mod.NURSERY_DB).startswith(str(tmp_path))
        assert paths_mod.DATA_DIR == tmp_path.resolve()
    finally:
        monkeypatch.delenv("EDU_NURSERY_DATA_DIR", raising=False)
        importlib.reload(paths_mod)  # restore defaults for other tests


def test_api_blueprints_register():
    from education_system.shared.api.nursery.routes import ALL_BLUEPRINTS

    app = Flask(__name__)
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)
    rules = [r.rule for r in app.url_map.iter_rules()]

    assert len(ALL_BLUEPRINTS) > 10
    assert len(rules) > 20
    assert any(r.startswith("/api/") for r in rules)


def test_protected_endpoint_requires_auth():
    from education_system.shared.api.nursery.routes import ALL_BLUEPRINTS

    app = Flask(__name__)
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)
    client = app.test_client()

    # The children directory is auth-protected: without a token it must be
    # rejected (401/403), never served and never 404 (which would mean the
    # route didn't register).
    resp = client.get("/api/children/")
    assert resp.status_code in (401, 403), resp.status_code
