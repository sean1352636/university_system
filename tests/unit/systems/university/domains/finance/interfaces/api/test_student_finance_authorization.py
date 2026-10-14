"""Authorization regression tests for the student-finance API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
import pytest
from flask import Flask

from education_system.platform.delivery.api.university.auth import _blacklisted_tokens
from education_system.platform.delivery.api.university.errors import register_error_handlers
from education_system.api.university.finance.student_finance_routes import (
    student_finance_bp,
)


_SECRET = "student-finance-authorization-test"
_ROUTES = (
    "education_system.api.university.finance."
    "student_finance_routes"
)


class _Row(dict):
    def keys(self):
        return super().keys()


def _token(*, sub="S1", role="student", permissions=None):
    payload = {
        "sub": sub,
        "user_id": sub,
        "role": role,
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    if permissions is not None:
        payload["permissions"] = permissions
    return jwt.encode(payload, _SECRET, algorithm="HS256")


def _headers(**identity):
    return {"Authorization": f"Bearer {_token(**identity)}"}


@pytest.fixture()
def client():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        PROPAGATE_EXCEPTIONS=False,
        API_CONFIG={
            "jwt": {"secret_key": _SECRET, "algorithm": "HS256"},
            "rate_limiting": {"enabled": False},
        },
    )
    register_error_handlers(app)
    app.register_blueprint(student_finance_bp)
    _blacklisted_tokens.clear()
    identity_connection = MagicMock()
    identity_connection.execute.return_value.fetchone.return_value = (1,)
    with patch(
        "education_system.platform.identity.auth.db.connect",
        return_value=_connection_context(identity_connection),
    ):
        yield app.test_client()
    _blacklisted_tokens.clear()


def _connection_context(connection):
    context = MagicMock()
    context.__enter__.return_value = connection
    context.__exit__.return_value = False
    return context


def test_student_account_listing_is_forcibly_scoped_to_authenticated_owner(client):
    connection = MagicMock()
    rows_result = MagicMock()
    rows_result.fetchall.return_value = [_Row(account_id=1, student_id="S1")]
    count_result = MagicMock()
    count_result.fetchone.return_value = (1,)
    connection.execute.side_effect = [rows_result, count_result]

    with (
        patch(f"{_ROUTES}.get_connection", return_value=_connection_context(connection)),
        patch(f"{_ROUTES}.log_activity"),
    ):
        response = client.get(
            "/api/student-finance/accounts?student_id=S2",
            headers=_headers(sub="S1"),
        )

    assert response.status_code == 200
    assert connection.execute.call_args_list[0].args[1][0] == "S1"
    assert connection.execute.call_args_list[1].args[1] == ["S1"]


def test_student_cannot_read_another_students_account_by_id(client):
    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = _Row(
        account_id=9, student_id="S2", balance=100
    )

    with patch(
        f"{_ROUTES}.get_connection", return_value=_connection_context(connection)
    ):
        response = client.get(
            "/api/student-finance/accounts/9", headers=_headers(sub="S1")
        )

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/student-finance/accounts"),
        ("put", "/api/student-finance/accounts/1"),
        ("delete", "/api/student-finance/accounts/1"),
        ("post", "/api/student-finance/transactions"),
        ("post", "/api/student-finance/fees"),
        ("put", "/api/student-finance/fees/1"),
        ("delete", "/api/student-finance/fees/1"),
    ],
)
def test_students_cannot_call_money_changing_endpoints(client, method, path):
    response = getattr(client, method)(path, json={}, headers=_headers())
    assert response.status_code == 403


def test_staff_without_manage_finances_cannot_create_transaction(client):
    response = client.post(
        "/api/student-finance/transactions",
        json={"account_id": 1, "student_id": "S1", "transaction_type": "charge", "amount": 5},
        headers=_headers(sub="employee", role="staff", permissions=["manage_students_finance"]),
    )
    assert response.status_code == 403


def test_transaction_rejects_student_id_that_does_not_own_account(client):
    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = _Row(student_id="S1")

    with patch(f"{_ROUTES}.transaction", return_value=_connection_context(connection)):
        response = client.post(
            "/api/student-finance/transactions",
            json={"account_id": 1, "student_id": "S2", "transaction_type": "charge", "amount": 5},
            headers=_headers(sub="finance-admin", role="admin", permissions=["manage_finances"]),
        )

    assert response.status_code == 400
    assert connection.execute.call_count == 1
