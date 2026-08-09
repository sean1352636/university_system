"""Tests for institutional_analytics_routes.

Exercises the analytics API endpoints end-to-end through a Flask test
client, against a temp DB seeded with a minimal operational schema. Also
covers the role gate (students are denied) and missing-token handling.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest
from flask import Flask

from education_system.platform.delivery.api.university.errors import register_error_handlers
from education_system.platform.delivery.api.university.routes.institutional_analytics_routes import (
    institutional_analytics_bp,
)
from education_system.systems.university.infrastructure.database import db as db_module


_SECRET = "analytics-test-secret"
_API_CONFIG = {
    "jwt": {
        "secret_key": _SECRET,
        "access_token_expires_minutes": 30,
        "refresh_token_expires_days": 7,
        "algorithm": "HS256",
    },
    "rate_limiting": {"enabled": False},
}


def _token(sub="admin", user_id=1, role="admin"):
    payload = {
        "sub": sub, "user_id": user_id, "role": role, "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return pyjwt.encode(payload, _SECRET, algorithm="HS256")


def _headers(role="admin"):
    return {"Authorization": f"Bearer {_token(role=role)}"}


SCHEMA = """
CREATE TABLE students (student_id TEXT, course TEXT, status TEXT, gender TEXT,
    age INTEGER, ucas_tariff INTEGER, gpa REAL);
CREATE TABLE student_modules (id INTEGER PRIMARY KEY, student_id TEXT,
    module_code TEXT, module_name TEXT, status TEXT, grade TEXT);
CREATE TABLE courses (id TEXT, course_code TEXT, course_name TEXT,
    current_enrollment INTEGER, max_enrollment INTEGER);
CREATE TABLE payments (payment_id INTEGER PRIMARY KEY, student_id TEXT,
    amount REAL, payment_method TEXT, payment_date TEXT, status TEXT);
"""


@pytest.fixture()
def seeded_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "api_analytics.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.executemany(
        "INSERT INTO students VALUES (?,?,?,?,?,?,?)",
        [
            ("s1", "CS", "Active", "male", 20, 120, None),
            ("s2", "CS", "Graduated", "female", 23, 128, None),
            ("s3", "DS", "Withdrawn", "other", 21, 96, None),
        ],
    )
    conn.executemany(
        "INSERT INTO student_modules (student_id, module_code, module_name, status, grade) "
        "VALUES (?,?,?,?,?)",
        [("s1", "CIS101", "Programming", "Completed", "First"),
         ("s2", "CIS101", "Programming", "Failed", "F")],
    )
    conn.executemany(
        "INSERT INTO courses VALUES (?,?,?,?,?)",
        [("CS", "CS", "Computer Science", 30, 30), ("DS", "DS", "Data Science", 10, 40)],
    )
    conn.executemany(
        "INSERT INTO payments (student_id, amount, payment_method, payment_date, status) "
        "VALUES (?,?,?,?,?)",
        [("s1", 1000.0, "Card", "2026-01-15", "completed")],
    )
    conn.commit()
    conn.close()
    yield db_path


@pytest.fixture()
def client(seeded_db):
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.config["API_CONFIG"] = _API_CONFIG
    register_error_handlers(app)
    app.register_blueprint(institutional_analytics_bp)
    return app.test_client()


class TestEndpoints:
    def test_overview(self, client):
        resp = client.get("/api/analytics/overview", headers=_headers())
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["headline"]["total_students"] == 3
        assert body["errors"] == {}

    def test_enrollment(self, client):
        resp = client.get("/api/analytics/enrollment", headers=_headers())
        assert resp.status_code == 200
        assert resp.get_json()["data"]["total_students"] == 3

    def test_retention(self, client):
        resp = client.get("/api/analytics/retention", headers=_headers())
        assert resp.status_code == 200
        assert resp.get_json()["data"]["overall"]["completion_rate"] is not None

    def test_modules_with_limit(self, client):
        resp = client.get("/api/analytics/modules?limit=1", headers=_headers())
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert len(data["modules"]) == 1
        assert data["totals"]["overall_pass_rate"] == 50.0

    def test_capacity(self, client):
        resp = client.get("/api/analytics/capacity", headers=_headers())
        assert resp.status_code == 200
        assert resp.get_json()["data"]["courses_at_capacity"] == 1

    def test_finance(self, client):
        resp = client.get("/api/analytics/finance", headers=_headers())
        assert resp.status_code == 200
        assert resp.get_json()["data"]["revenue"]["collected_total"] == 1000.0

    def test_demographics(self, client):
        resp = client.get("/api/analytics/demographics", headers=_headers())
        assert resp.status_code == 200
        assert resp.get_json()["data"]["by_gender"]


class TestAccessControl:
    def test_student_role_denied(self, client):
        resp = client.get("/api/analytics/overview", headers=_headers(role="student"))
        assert resp.status_code == 403

    def test_staff_role_allowed(self, client):
        resp = client.get("/api/analytics/overview", headers=_headers(role="staff"))
        assert resp.status_code == 200

    def test_missing_token_rejected(self, client):
        resp = client.get("/api/analytics/overview")
        assert resp.status_code == 401
