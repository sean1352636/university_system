"""Capability gates on finance, attendance, integrity, parent and library routes.

Every one of these endpoint groups carried only ``@token_required``, which
authenticates but authorises nothing: any account on the system could read or
write any record. These tests pin the capability matrix — who may read
somebody else's records, and who may write.

The handlers need a database to run end to end, so the decision helpers are
exercised directly and the wiring is asserted against the source.
"""

from __future__ import annotations

import inspect

import pytest
from flask import Flask, g

from education_system.api.university.academics import (
    attendance_routes as attendance,
    integrity_routes as integrity,
    library_routes as library,
    parent_routes as parents,
)
from education_system.api.university.finance import (
    student_finance_routes as finance,
)

pytestmark = pytest.mark.security

STUDENT = dict(sub="S12345", user_id=42, role="student")
INSTRUCTOR = dict(sub="prof", user_id=2, role="instructor")
STAFF = dict(sub="reg", user_id=3, role="staff")
ADMIN = dict(sub="admin", user_id=1, role="admin")


@pytest.fixture
def app():
    return Flask(__name__)


def _as(app, **user):
    ctx = app.test_request_context()
    ctx.push()
    g.current_user = user
    return ctx


# ---- finance ----

@pytest.mark.parametrize("user,read_any,may_mutate", [
    (STUDENT, False, False),
    (INSTRUCTOR, False, False),
    (STAFF, True, False),     # may see the ledger, may not move money
    (ADMIN, True, True),
])
def test_finance_capabilities(app, user, read_any, may_mutate):
    ctx = _as(app, **user)
    try:
        assert finance._may_read_any_finance() is read_any
        assert (finance._require_finance_mutation() is None) is may_mutate
    finally:
        ctx.pop()


def test_every_money_moving_endpoint_is_gated():
    mutating = [
        "create_account", "update_account", "delete_account",
        "create_transaction", "create_fee", "update_fee", "delete_fee",
    ]
    for name in mutating:
        source = inspect.getsource(getattr(finance, name))
        assert "_require_finance_mutation()" in source, f"{name} is ungated"


def test_every_finance_read_is_scoped():
    for name in ("list_accounts", "list_transactions", "list_fees"):
        assert "_scope_student(" in inspect.getsource(getattr(finance, name)), name
    for name in ("get_account", "get_transaction", "get_fee"):
        assert "_guard_row(" in inspect.getsource(getattr(finance, name)), name


def test_transaction_attribution_cannot_be_forged():
    source = inspect.getsource(finance.create_transaction)
    assert 'data.get("processed_by"' not in source


# ---- attendance ----

@pytest.mark.parametrize("user,may_write", [
    (STUDENT, False),
    (INSTRUCTOR, True),   # takes the register for their own modules
    (STAFF, True),
    (ADMIN, True),
])
def test_attendance_write_capability(app, user, may_write):
    ctx = _as(app, **user)
    try:
        assert (attendance._require_attendance_manager() is None) is may_write
    finally:
        ctx.pop()


def test_a_student_cannot_widen_their_attendance_view():
    source = inspect.getsource(attendance.list_records)
    assert "_may_read_any_attendance()" in source
    # The session_id filter must be dropped, or it reopens the whole class.
    assert "session_id = None" in source


# ---- integrity ----

@pytest.mark.parametrize("user,may_read", [
    (STUDENT, False),
    (INSTRUCTOR, True),
    (STAFF, True),
    (ADMIN, True),
])
def test_detection_results_capability(app, user, may_read):
    ctx = _as(app, **user)
    try:
        assert (integrity._require_detection_access() is None) is may_read
    finally:
        ctx.pop()


def test_student_case_view_withholds_internal_material():
    visible = set(integrity.STUDENT_VISIBLE_CASE_FIELDS)
    for withheld in ("notes", "ruling_rationale", "student_email", "system_key"):
        assert withheld not in visible
    # But the student can still see the allegation and the outcome.
    assert {"violation_type", "status", "ruling"} <= visible


def test_forensic_case_by_id_is_admin_only():
    assert "@admin_required" in inspect.getsource(integrity.get_forensic_case)


# ---- parents ----

@pytest.mark.parametrize("user,oversight", [
    (STUDENT, False), (INSTRUCTOR, False), (STAFF, False), (ADMIN, True),
])
def test_parent_oversight_is_administrative(app, user, oversight):
    ctx = _as(app, **user)
    try:
        assert parents._has_parent_oversight() is oversight
    finally:
        ctx.pop()


def test_a_parent_sees_only_their_own_rows(app):
    ctx = _as(app, sub="P100", user_id=9, role="parent")
    try:
        clause, params = parents._own_party_clause()
        assert clause == "parent_id = ?"
        assert params == ["P100"]
    finally:
        ctx.pop()


def test_a_teacher_sees_the_correspondence_addressed_to_them(app):
    ctx = _as(app, **INSTRUCTOR)
    try:
        clause, params = parents._own_party_clause()
        assert "teacher_id = ?" in clause
        assert params == ["prof", "prof"]
    finally:
        ctx.pop()


def test_parent_message_sender_is_not_taken_from_the_body():
    source = inspect.getsource(parents.create_message)
    assert "_has_parent_oversight()" in source
    assert "impersonating" in source  # the refusal path exists


# ---- library ----

@pytest.mark.parametrize("user,librarian", [
    (STUDENT, False), (INSTRUCTOR, False), (STAFF, True), (ADMIN, True),
])
def test_librarian_capability(app, user, librarian):
    ctx = _as(app, **user)
    try:
        assert library._is_librarian() is librarian
    finally:
        ctx.pop()


def test_a_borrower_cannot_act_for_someone_else(app):
    ctx = _as(app, **STUDENT)
    try:
        assert library._borrower_id(None) == "S12345"
        assert library._borrower_id("S12345") == "S12345"
        assert library._borrower_id("S99999") is None   # refused
    finally:
        ctx.pop()


def test_a_librarian_may_act_for_any_borrower(app):
    ctx = _as(app, **STAFF)
    try:
        assert library._borrower_id("S99999") == "S99999"
    finally:
        ctx.pop()


def test_returning_a_loan_checks_the_borrower():
    source = inspect.getsource(library.return_loan)
    assert "_is_librarian()" in source
    check_at = source.index("_is_librarian()")
    update_at = source.index("UPDATE book_loans SET status = 'returned'")
    assert check_at < update_at
