"""Comprehensive tests for finance_routes: fees, payments, scholarships, account."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest
from flask import Flask

from education_system.shared.api.university.auth import _blacklisted_tokens
from education_system.shared.api.university.errors import register_error_handlers
from education_system.shared.api.university.routes.finance_routes import finance_bp, _row_to_dict

# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

_SECRET = "finance-test-secret"
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
        "sub": sub, "user_id": user_id, "role": role,
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return pyjwt.encode(payload, _SECRET, algorithm="HS256")


def _headers():
    return {"Authorization": f"Bearer {_token()}"}


class _FakeRow:
    def __init__(self, data: dict):
        self._data = data

    def keys(self):
        return self._data.keys()

    def __getitem__(self, key):
        return self._data[key]


@pytest.fixture()
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.config["API_CONFIG"] = _API_CONFIG
    register_error_handlers(app)
    app.register_blueprint(finance_bp)
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def _clear():
    _blacklisted_tokens.clear()
    yield
    _blacklisted_tokens.clear()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

class TestRowToDict:

    def test_converts_row(self):
        row = _FakeRow({"payment_id": 1, "amount": 500.0})
        d = _row_to_dict(row)
        assert d == {"payment_id": 1, "amount": 500.0}

    def test_none_returns_empty_dict(self):
        assert _row_to_dict(None) == {}


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

class TestFinanceAuth:

    def test_fees_requires_token(self, client):
        assert client.get("/api/finance/fees?student_id=S1").status_code == 401

    def test_payments_get_requires_token(self, client):
        assert client.get("/api/finance/payments").status_code == 401

    def test_payments_post_requires_token(self, client):
        assert client.post("/api/finance/payments", json={}).status_code == 401

    def test_scholarships_requires_token(self, client):
        assert client.get("/api/finance/scholarships").status_code == 401

    def test_account_requires_token(self, client):
        assert client.get("/api/finance/account/S1").status_code == 401


# ---------------------------------------------------------------------------
# Fees
# ---------------------------------------------------------------------------

class TestFees:

    @patch("education_system.shared.api.university.routes.finance_routes.log_activity")
    @patch("education_system.shared.api.university.routes.finance_routes.get_connection")
    def test_list_fees_success(self, mock_conn, mock_log, client):
        student_row = _FakeRow({"1": 1})
        fee_row = _FakeRow({
            "fee_id": 1, "student_id": "S1", "amount": 5000,
            "fee_name": "Tuition", "fee_description": "Term fee",
        })
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = student_row
        conn.execute.return_value.fetchall.return_value = [fee_row]
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/finance/fees?student_id=S1", headers=_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["student_id"] == "S1"
        assert len(data["fees"]) == 1

    def test_fees_missing_student_id(self, client):
        resp = client.get("/api/finance/fees", headers=_headers())
        assert resp.status_code == 400

    @patch("education_system.shared.api.university.routes.finance_routes.get_connection")
    def test_fees_student_not_found(self, mock_conn, client):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/finance/fees?student_id=NOEXIST", headers=_headers())
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Payments GET
# ---------------------------------------------------------------------------

class TestListPayments:

    @patch("education_system.shared.api.university.routes.finance_routes.log_activity")
    @patch("education_system.shared.api.university.routes.finance_routes.get_connection")
    def test_list_all_payments(self, mock_conn, mock_log, client):
        payment_row = _FakeRow({"payment_id": 1, "student_id": "S1", "amount": 500})
        count_row = MagicMock()
        count_row.__getitem__ = lambda self, i: 1
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [payment_row]
        conn.execute.return_value.fetchone.return_value = count_row
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/finance/payments", headers=_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert "items" in data
        assert "pagination" in data

    @patch("education_system.shared.api.university.routes.finance_routes.log_activity")
    @patch("education_system.shared.api.university.routes.finance_routes.get_connection")
    def test_list_payments_by_student(self, mock_conn, mock_log, client):
        student_row = _FakeRow({"1": 1})
        payment_row = _FakeRow({"payment_id": 2, "student_id": "S1", "amount": 200})
        count_row = MagicMock()
        count_row.__getitem__ = lambda self, i: 1
        conn = MagicMock()
        conn.execute.return_value.fetchone.side_effect = [student_row, count_row]
        conn.execute.return_value.fetchall.return_value = [payment_row]
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/finance/payments?student_id=S1", headers=_headers())
        assert resp.status_code == 200

    @patch("education_system.shared.api.university.routes.finance_routes.get_connection")
    def test_list_payments_student_not_found(self, mock_conn, client):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/finance/payments?student_id=NOEXIST", headers=_headers())
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Payments POST
# ---------------------------------------------------------------------------

class TestCreatePayment:

    @patch("education_system.shared.api.university.routes.finance_routes.log_activity")
    @patch("education_system.shared.api.university.routes.finance_routes.transaction")
    @patch("education_system.shared.api.university.routes.finance_routes.get_connection")
    def test_create_success(self, mock_conn, mock_tx, mock_log, client):
        student_row = _FakeRow({"1": 1})
        new_row = _FakeRow({
            "payment_id": 10, "student_id": "S1", "amount": 300,
            "payment_type": "tuition", "status": "completed",
        })
        conn = MagicMock()
        conn.execute.return_value.fetchone.side_effect = [student_row, new_row]
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        tx_conn = MagicMock()
        last_id_row = MagicMock()
        last_id_row.__getitem__ = lambda self, i: 10
        tx_conn.execute.return_value.fetchone.return_value = last_id_row
        mock_tx.return_value.__enter__ = MagicMock(return_value=tx_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.post(
            "/api/finance/payments",
            json={"student_id": "S1", "amount": 300, "payment_type": "tuition"},
            headers=_headers(),
        )
        assert resp.status_code == 201
        assert resp.get_json()["payment_id"] == 10

    def test_create_missing_fields(self, client):
        resp = client.post(
            "/api/finance/payments",
            json={"student_id": "S1"},
            headers=_headers(),
        )
        assert resp.status_code == 400

    def test_create_missing_amount(self, client):
        resp = client.post(
            "/api/finance/payments",
            json={"student_id": "S1", "payment_type": "tuition"},
            headers=_headers(),
        )
        assert resp.status_code == 400

    def test_create_missing_payment_type(self, client):
        resp = client.post(
            "/api/finance/payments",
            json={"student_id": "S1", "amount": 100},
            headers=_headers(),
        )
        assert resp.status_code == 400

    def test_create_negative_amount(self, client):
        resp = client.post(
            "/api/finance/payments",
            json={"student_id": "S1", "amount": -50, "payment_type": "tuition"},
            headers=_headers(),
        )
        assert resp.status_code == 400

    def test_create_zero_amount(self, client):
        resp = client.post(
            "/api/finance/payments",
            json={"student_id": "S1", "amount": 0, "payment_type": "tuition"},
            headers=_headers(),
        )
        assert resp.status_code == 400

    def test_create_non_numeric_amount(self, client):
        resp = client.post(
            "/api/finance/payments",
            json={"student_id": "S1", "amount": "abc", "payment_type": "tuition"},
            headers=_headers(),
        )
        assert resp.status_code == 400

    def test_create_empty_body(self, client):
        resp = client.post("/api/finance/payments", json={}, headers=_headers())
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Scholarships
# ---------------------------------------------------------------------------

class TestScholarships:

    @patch("education_system.shared.api.university.routes.finance_routes.log_activity")
    @patch("education_system.shared.api.university.routes.finance_routes.get_connection")
    def test_list_scholarships(self, mock_conn, mock_log, client):
        row = _FakeRow({"scholarship_id": 1, "scholarship_name": "Merit", "status": "active"})
        count_row = MagicMock()
        count_row.__getitem__ = lambda self, i: 1
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [row]
        conn.execute.return_value.fetchone.return_value = count_row
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/finance/scholarships", headers=_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert "items" in data
        assert "pagination" in data

    @patch("education_system.shared.api.university.routes.finance_routes.log_activity")
    @patch("education_system.shared.api.university.routes.finance_routes.get_connection")
    def test_scholarships_empty(self, mock_conn, mock_log, client):
        count_row = MagicMock()
        count_row.__getitem__ = lambda self, i: 0
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = []
        conn.execute.return_value.fetchone.return_value = count_row
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/finance/scholarships", headers=_headers())
        assert resp.status_code == 200
        assert resp.get_json()["items"] == []


# ---------------------------------------------------------------------------
# Student account
# ---------------------------------------------------------------------------

class TestStudentAccount:

    @patch("education_system.shared.api.university.routes.finance_routes.log_activity")
    @patch("education_system.shared.api.university.routes.finance_routes.get_connection")
    def test_account_success(self, mock_conn, mock_log, client):
        student_row = _FakeRow({"1": 1})
        fees_sum = MagicMock()
        fees_sum.__getitem__ = lambda self, i: 5000.0
        payments_sum = MagicMock()
        payments_sum.__getitem__ = lambda self, i: 3000.0
        conn = MagicMock()
        conn.execute.return_value.fetchone.side_effect = [student_row, fees_sum, payments_sum]
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/finance/account/S1", headers=_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["student_id"] == "S1"
        assert data["total_fees"] == 5000.0
        assert data["total_payments"] == 3000.0
        assert data["balance"] == 2000.0

    @patch("education_system.shared.api.university.routes.finance_routes.get_connection")
    def test_account_student_not_found(self, mock_conn, client):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/finance/account/NOEXIST", headers=_headers())
        assert resp.status_code == 404

    @patch("education_system.shared.api.university.routes.finance_routes.log_activity")
    @patch("education_system.shared.api.university.routes.finance_routes.get_connection")
    def test_account_zero_balance(self, mock_conn, mock_log, client):
        student_row = _FakeRow({"1": 1})
        fees_sum = MagicMock()
        fees_sum.__getitem__ = lambda self, i: 1000.0
        payments_sum = MagicMock()
        payments_sum.__getitem__ = lambda self, i: 1000.0
        conn = MagicMock()
        conn.execute.return_value.fetchone.side_effect = [student_row, fees_sum, payments_sum]
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/finance/account/S1", headers=_headers())
        assert resp.status_code == 200
        assert resp.get_json()["balance"] == 0.0

    @patch("education_system.shared.api.university.routes.finance_routes.log_activity")
    @patch("education_system.shared.api.university.routes.finance_routes.get_connection")
    def test_account_negative_balance(self, mock_conn, mock_log, client):
        """Overpayment results in negative balance."""
        student_row = _FakeRow({"1": 1})
        fees_sum = MagicMock()
        fees_sum.__getitem__ = lambda self, i: 1000.0
        payments_sum = MagicMock()
        payments_sum.__getitem__ = lambda self, i: 2000.0
        conn = MagicMock()
        conn.execute.return_value.fetchone.side_effect = [student_row, fees_sum, payments_sum]
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/finance/account/S1", headers=_headers())
        assert resp.status_code == 200
        assert resp.get_json()["balance"] == -1000.0
