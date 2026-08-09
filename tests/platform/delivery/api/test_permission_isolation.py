"""Permission / access-isolation tests.

Proves that a user cannot reach systems or roles outside the access explicitly
granted in ``user_systems`` — at two layers:

* RBAC layer  — ``RoleManager`` / ``UserAuth`` never report cross-system access.
* API layer   — the ``token_required`` / ``role_required`` / ``system_required``
                decorators return 401/403 for out-of-scope requests, and admit
                only the correct principals (including for the Nursery system,
                whose routes are mounted under /api/v1/nursery/).
"""

import os
import shutil
import sys

import pytest

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
)

from education_system.platform.identity.auth.core import UserAuth
from education_system.platform.identity.auth.db import connect
from education_system.platform.identity.auth.role_manager import RoleManager


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def _template_auth_db(tmp_path_factory):
    from education_system.platform.identity.auth.schema import initialise_auth_db, seed_default_users
    path = str(tmp_path_factory.mktemp("perm_tpl") / "template_auth.db")
    initialise_auth_db(path)
    seed_default_users(path)
    return path


@pytest.fixture
def auth_db(tmp_path, _template_auth_db):
    db_path = str(tmp_path / "test_auth.db")
    shutil.copy2(_template_auth_db, db_path)
    return db_path


def _user_id(auth_db, username):
    conn = connect(auth_db)
    try:
        return conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()["id"]
    finally:
        conn.close()


# ── RBAC layer ────────────────────────────────────────────────────────────

class TestRbacIsolation:
    def test_single_system_user_has_no_other_system(self, auth_db):
        rm = RoleManager(auth_db)
        uid = _user_id(auth_db, "admin")  # university-only admin
        assert rm.get_user_role_for_system(uid, "university") == "admin"
        for other in ("sixth_form", "secondary", "primary", "nursery"):
            assert rm.get_user_role_for_system(uid, other) is None

    def test_get_user_systems_lists_only_granted(self, auth_db):
        rm = RoleManager(auth_db)
        uid = _user_id(auth_db, "admin1")  # sixth-form-only admin
        keys = {s["system_key"] for s in rm.get_user_systems(uid)}
        assert keys == {"sixth_form"}

    def test_superadmin_spans_all_five(self, auth_db):
        rm = RoleManager(auth_db)
        uid = _user_id(auth_db, "superadmin")
        keys = {s["system_key"] for s in rm.get_user_systems(uid)}
        assert keys == {"university", "sixth_form", "secondary", "primary", "nursery"}

    def test_role_hierarchy(self, auth_db):
        rm = RoleManager(auth_db)
        assert rm.has_minimum_role("admin", "student") is True
        assert rm.has_minimum_role("student", "admin") is False

    def test_login_result_exposes_only_granted_systems(self, auth_db):
        auth = UserAuth(auth_db)
        result = auth.login("student1", "student1234")  # sixth-form student
        systems = {s["system_key"] for s in result["systems"]}
        assert systems == {"sixth_form"}


# ── API layer ─────────────────────────────────────────────────────────────

@pytest.fixture
def api(auth_db):
    """A minimal Flask app exposing routes guarded by each auth decorator."""
    from flask import Flask, jsonify, g
    from education_system.platform.delivery.api import auth as auth_mod

    auth_mod.init_auth(auth_db_path=auth_db, jwt_secret="test-secret-key-at-least-32-bytes-long!!")
    app = Flask(__name__)

    @app.route("/api/v1/university/resource")
    @auth_mod.token_required
    def uni_resource():
        return jsonify(role=g.current_user.get("role"))

    @app.route("/api/v1/college/resource")
    @auth_mod.token_required
    def college_resource():
        return jsonify(role=g.current_user.get("role"))

    @app.route("/api/v1/university/admin-only")
    @auth_mod.role_required("admin")
    def uni_admin_only():
        return jsonify(ok=True)

    @app.route("/api/v1/nursery/admin-only")
    @auth_mod.role_required("admin")
    def nursery_admin_only():
        return jsonify(ok=True)

    # Sixth-form routes mount under /api/v1/sixthform/ but the auth system_key is
    # "sixth_form" — exercises the path-alias normalisation.
    @app.route("/api/v1/sixthform/admin-only")
    @auth_mod.role_required("admin")
    def sixthform_admin_only():
        return jsonify(ok=True)

    app.config["TESTING"] = True
    return app.test_client()


def _token(auth_db, username, password):
    from education_system.platform.delivery.api import auth as auth_mod
    a = UserAuth(auth_db)
    result = a.login(username, password)
    return auth_mod.generate_token(
        result["user_id"], result["username"], result["systems"], "access"
    )


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


class TestApiIsolation:
    def test_no_token_is_401(self, api):
        assert api.get("/api/v1/university/resource").status_code == 401

    def test_bad_token_is_401(self, api):
        r = api.get("/api/v1/university/resource", headers=_auth_header("garbage"))
        assert r.status_code == 401

    def test_wrong_system_is_403(self, api, auth_db):
        # University student may not touch college routes.
        token = _token(auth_db, "S12345", "student123")
        r = api.get("/api/v1/college/resource", headers=_auth_header(token))
        assert r.status_code == 403

    def test_right_system_is_200(self, api, auth_db):
        token = _token(auth_db, "S12345", "student123")
        r = api.get("/api/v1/university/resource", headers=_auth_header(token))
        assert r.status_code == 200
        assert r.get_json()["role"] == "student"

    def test_insufficient_role_is_403(self, api, auth_db):
        # University student hitting an admin-only university route.
        token = _token(auth_db, "S12345", "student123")
        r = api.get("/api/v1/university/admin-only", headers=_auth_header(token))
        assert r.status_code == 403

    def test_correct_role_is_200(self, api, auth_db):
        token = _token(auth_db, "admin", "admin123")
        r = api.get("/api/v1/university/admin-only", headers=_auth_header(token))
        assert r.status_code == 200

    def test_admin_of_other_system_denied_on_nursery(self, api, auth_db):
        # A university admin is NOT an admin on nursery. This guards the
        # _KNOWN_SYSTEMS fix: without nursery in the scoped-system set, the
        # role check would fall back to the cross-system role and wrongly
        # admit this request.
        token = _token(auth_db, "admin", "admin123")
        r = api.get("/api/v1/nursery/admin-only", headers=_auth_header(token))
        assert r.status_code == 403

    def test_superadmin_allowed_on_nursery(self, api, auth_db):
        token = _token(auth_db, "superadmin", "SuperAdmin@123")
        r = api.get("/api/v1/nursery/admin-only", headers=_auth_header(token))
        assert r.status_code == 200

    def test_admin_of_other_system_denied_on_sixthform(self, api, auth_db):
        # Sixth-form routes live under /api/v1/sixthform/ but auth keys them
        # "sixth_form". A university admin is NOT a college admin. This guards the
        # sixthform→college path-alias fix: without it, the route reads as
        # unscoped and the role check falls back to the cross-system role,
        # wrongly admitting this request.
        token = _token(auth_db, "admin", "admin123")  # university admin only
        r = api.get("/api/v1/sixthform/admin-only", headers=_auth_header(token))
        assert r.status_code == 403

    def test_college_admin_allowed_on_sixthform(self, api, auth_db):
        # admin1 is a college (sixth-form) admin — the alias must let them in.
        token = _token(auth_db, "admin1", "admin1234")
        r = api.get("/api/v1/sixthform/admin-only", headers=_auth_header(token))
        assert r.status_code == 200


# ── Naming-consistency invariant ────────────────────────────────────────────

class TestRoutePrefixScoping:
    """Every prefix that unified_server mounts routes under MUST resolve to a
    known auth system_key, otherwise path-scoped role enforcement silently falls
    back to the user's best cross-system role — the privilege-escalation class of
    bug found for both nursery (missing from _KNOWN_SYSTEMS) and sixth-form
    (routes under /sixthform/ but keyed "sixth_form"). This test locks the invariant
    so a future rename or a new system can't reopen the gap.

    Keep MOUNTED_PREFIXES in step with the `_reprefix(..., "<prefix>")` calls in
    shared/api/unified_server.py.
    """

    MOUNTED_PREFIXES = ("nursery", "primary", "secondary", "sixthform", "university")

    def test_every_mounted_prefix_is_scoped(self):
        from education_system.platform.delivery.api.auth import (
            _system_key_from_path,
            _KNOWN_SYSTEMS,
        )
        unscoped = []
        for prefix in self.MOUNTED_PREFIXES:
            key = _system_key_from_path(f"/api/v1/{prefix}/anything")
            if key not in _KNOWN_SYSTEMS:
                unscoped.append((prefix, key))
        assert not unscoped, (
            "route prefixes that don't resolve to a known auth system_key "
            f"(privilege-escalation gap): {unscoped}"
        )
