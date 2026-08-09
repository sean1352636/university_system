from __future__ import annotations

import sqlite3

from flask import Flask, g, jsonify

from education_system.platform.delivery.api.tenant_middleware import (
    register_tenant_middleware,
)
from education_system.platform.kernel.core import tenant_models
from education_system.platform.kernel.core.tenant_models import create_tenant, init_tenant_db


def _app(registry, monkeypatch, *, strict=True):
    monkeypatch.setattr(tenant_models, "_DEFAULT_TENANTS_DB", str(registry))
    app = Flask(__name__)

    @app.get("/api/v1/university/value")
    def value():
        tenant = g.tenant
        with sqlite3.connect(tenant.config["database"]) as connection:
            return jsonify({"value": connection.execute("SELECT value FROM data").fetchone()[0]})

    register_tenant_middleware(app, str(registry), require_tenant=strict)
    return app


def test_requests_are_routed_to_physically_separate_databases(tmp_path, monkeypatch):
    registry = tmp_path / "tenants.db"
    paths = {}
    for slug, value in (("north", "north-only"), ("south", "south-only")):
        path = tmp_path / f"{slug}.db"
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE data (value TEXT)")
            connection.execute("INSERT INTO data VALUES (?)", (value,))
        paths[slug] = path
        init_tenant_db(str(registry))
        create_tenant(slug.title(), slug, config={"database": str(path)}, db_path=str(registry))

    app = _app(registry, monkeypatch)
    with app.test_client() as client:
        assert client.get("/api/v1/university/value").status_code == 400
        assert client.get("/api/v1/university/value", headers={"X-Tenant-ID": "unknown"}).status_code == 404
        north = client.get("/api/v1/university/value", headers={"X-Tenant-ID": "north"})
        south = client.get("/api/v1/university/value", headers={"X-Tenant-ID": "south"})
    assert north.get_json()["value"] == "north-only"
    assert south.get_json()["value"] == "south-only"


def test_conflicting_header_and_token_claim_are_rejected(tmp_path, monkeypatch):
    import jwt

    registry = tmp_path / "tenants.db"
    init_tenant_db(str(registry))
    create_tenant("North", "north", db_path=str(registry))
    create_tenant("South", "south", db_path=str(registry))
    app = _app(registry, monkeypatch)
    token = jwt.encode(
        {"tenant_id": "south"}, "irrelevant-test-key-at-least-32-bytes", algorithm="HS256"
    )
    with app.test_client() as client:
        response = client.get(
            "/api/v1/university/value",
            headers={"X-Tenant-ID": "north", "Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 403
