"""Private messages and student documents are scoped to their owner.

Both route modules previously required only a valid token:

* ``GET /api/communication/messages`` returned every message in the system
  when called with no filters, and anyone else's when called with theirs.
* ``PUT /api/communication/messages/<id>/read`` updated by id with no check.
* ``GET /api/documents/student-documents`` enumerated every current document,
  and ``/student-documents/<id>`` returned any student's document by id.

The handlers need a database to run end to end, so these tests pin the
decision helpers and assert the query/ownership logic is wired in.
"""

from __future__ import annotations

import pytest

pytest.skip(
    "The university API routes (systems/university/shell/api) were removed "
    "so they can be rebuilt module by module. This file specifies the "
    "security/contract behaviour those routes must keep — re-enable it when "
    "the matching module is rebuilt. Backup of the removed tree: "
    "var/backups/maintenance/api-removal-20260908_204628/api-trees.tar.gz",
    allow_module_level=True,
)


import inspect

import pytest
from flask import Flask, g

from education_system.platform.delivery.api.university import auth as A
from education_system.systems.university.shell.api.routes import (
    communication_routes as comms,
    document_routes as docs,
)

pytestmark = pytest.mark.security


@pytest.fixture
def app():
    return Flask(__name__)


def _as(app, **user):
    ctx = app.test_request_context()
    ctx.push()
    g.current_user = user
    return ctx


STUDENT = dict(sub="S12345", user_id=42, role="student")
OTHER_STUDENT = dict(sub="S99999", user_id=77, role="student")
INSTRUCTOR = dict(sub="prof", user_id=2, role="instructor")
STAFF = dict(sub="reg", user_id=3, role="staff")
ADMIN = dict(sub="admin", user_id=1, role="admin")


# ---- messages ----

def test_message_identity_uses_the_local_numeric_id(app):
    """``messages.sender_id`` is a users(id) FK, not a username."""
    ctx = _as(app, **STUDENT)
    try:
        assert comms._own_user_id() == 42
        assert comms._is_party_to({"sender_id": 42, "recipient_id": 9}) is True
        assert comms._is_party_to({"sender_id": 9, "recipient_id": 42}) is True
        assert comms._is_party_to({"sender_id": 9, "recipient_id": 10}) is False
        # The username must not be accepted as a party id.
        assert comms._is_party_to({"sender_id": "S12345", "recipient_id": 9}) is False
    finally:
        ctx.pop()


def test_missing_local_id_is_not_a_party(app):
    ctx = _as(app, sub="S12345", role="student")
    try:
        assert comms._own_user_id() is None
        assert comms._is_party_to({"sender_id": 1, "recipient_id": 2}) is False
    finally:
        ctx.pop()


@pytest.mark.parametrize("user,expected", [
    (STUDENT, False),
    (INSTRUCTOR, False),   # staff role, but lacks manage_communication
    (STAFF, True),
    (ADMIN, True),
])
def test_message_oversight_requires_the_capability(app, user, expected):
    ctx = _as(app, **user)
    try:
        assert comms._has_message_oversight() is expected
    finally:
        ctx.pop()


def test_list_messages_constrains_non_oversight_callers():
    source = inspect.getsource(comms.list_messages)
    assert "_has_message_oversight()" in source
    assert "(sender_id = ? OR recipient_id = ?)" in source


def test_mark_read_loads_before_updating():
    source = inspect.getsource(comms.mark_message_read)
    select_at = source.index("SELECT sender_id, recipient_id FROM messages")
    update_at = source.index("UPDATE messages SET is_read")
    assert select_at < update_at, "the ownership check must precede the write"
    assert 'recipient_id' in source and '403' in source


# ---- student documents ----

@pytest.mark.parametrize("user,expected", [
    (STUDENT, False),
    (INSTRUCTOR, False),   # staff role, but lacks view_any_student
    (STAFF, True),
    (ADMIN, True),
])
def test_document_oversight_requires_the_capability(app, user, expected):
    ctx = _as(app, **user)
    try:
        assert docs._has_student_oversight() is expected
    finally:
        ctx.pop()


def test_student_document_owner_check(app):
    """``student_documents.student_id`` is TEXT — the student's username."""
    ctx = _as(app, **STUDENT)
    try:
        assert A.authorize_object("S12345", permission=docs.STUDENT_RECORD_OVERSIGHT) is None
        denial = A.authorize_object("S99999", permission=docs.STUDENT_RECORD_OVERSIGHT)
        assert denial is not None and denial[1] == 403
    finally:
        ctx.pop()

    ctx = _as(app, **OTHER_STUDENT)
    try:
        assert A.authorize_object("S99999", permission=docs.STUDENT_RECORD_OVERSIGHT) is None
    finally:
        ctx.pop()


def test_instructor_cannot_read_a_student_document_without_the_capability(app):
    ctx = _as(app, **INSTRUCTOR)
    try:
        denial = A.authorize_object("S12345", permission=docs.STUDENT_RECORD_OVERSIGHT)
        assert denial is not None and denial[1] == 403
    finally:
        ctx.pop()


def test_list_student_documents_pins_the_filter_to_the_caller():
    source = inspect.getsource(docs.list_student_documents)
    assert "_has_student_oversight()" in source
    assert "student_id = current_subject_id()" in source


def test_get_student_document_checks_before_returning_metadata():
    source = inspect.getsource(docs.get_student_document)
    check_at = source.index("authorize_object(")
    return_at = source.index("return jsonify(")
    assert check_at < return_at
