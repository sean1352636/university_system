"""Housing applications and notifications are owner-scoped.

Both route modules previously required only a valid token:

* housing — anyone could list every application, file one under an arbitrary
  ``student_id``, and PUT any application including ``status`` /
  ``reviewed_by`` / ``review_date``, i.e. approve their own application and
  forge the reviewer.
* notifications — anyone could list or search every notification, fetch one by
  id, plant a notification in another user's feed, and read others'
  preferences.

The handlers need a database to run end to end, so these tests pin the
decision helpers and assert the field/scope logic is wired in.
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

from education_system.api.university.operations import (
    housing_routes as housing,
)
from education_system.systems.university.shell.api.routes import (
    notification_center_routes as notif,
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
INSTRUCTOR = dict(sub="prof", user_id=2, role="instructor")
STAFF = dict(sub="reg", user_id=3, role="staff")
ADMIN = dict(sub="admin", user_id=1, role="admin")


# ---- housing ----

@pytest.mark.parametrize("user,read,decide", [
    (STUDENT, False, False),
    (INSTRUCTOR, False, False),
    (STAFF, True, False),      # may see records, may not decide them
    (ADMIN, True, True),
])
def test_housing_capabilities(app, user, read, decide):
    ctx = _as(app, **user)
    try:
        assert housing._may_read_any_housing() is read
        assert housing._may_decide_housing() is decide
    finally:
        ctx.pop()


def test_decision_fields_are_not_student_editable():
    assert housing.STAFF_ONLY_FIELDS == {"status", "reviewed_by", "review_date"}
    assert not (housing.STUDENT_EDITABLE_FIELDS & housing.STAFF_ONLY_FIELDS)


def test_update_rejects_staff_fields_from_a_non_decider():
    source = inspect.getsource(housing.update_application)
    assert "STAFF_ONLY_FIELDS if may_decide else frozenset()" in source
    # The old hard-coded allow-list must be gone.
    assert '"status", "preferred_building_id"' not in source


def test_listings_pin_the_student_filter():
    for handler in (housing.list_applications, housing.list_assignments):
        source = inspect.getsource(handler)
        assert "_may_read_any_housing()" in source
        assert "student_id = current_subject_id()" in source


def test_create_application_does_not_trust_the_body():
    source = inspect.getsource(housing.create_application)
    assert "current_subject_id()" in source
    assert "_may_decide_housing()" in source
    assert 'data["student_id"]' not in source


# ---- notifications ----

@pytest.mark.parametrize("user,oversight,send", [
    (STUDENT, False, False),
    (INSTRUCTOR, False, True),   # may notify others, may not read theirs
    (STAFF, False, False),
    (ADMIN, True, True),
])
def test_notification_capabilities(app, user, oversight, send):
    ctx = _as(app, **user)
    try:
        assert notif._has_oversight() is oversight
        assert notif._may_notify_others() is send
    finally:
        ctx.pop()


def test_reads_are_pinned_to_the_caller(app):
    ctx = _as(app, **STUDENT)
    try:
        # Asking for someone else's id is silently replaced with your own.
        scoped, denial = notif._scope_user_id("999")
        assert denial is None
        assert scoped == 42
        # Asking for nothing does not mean "everyone".
        scoped, _ = notif._scope_user_id(None)
        assert scoped == 42
    finally:
        ctx.pop()


def test_oversight_keeps_the_requested_scope(app):
    ctx = _as(app, **ADMIN)
    try:
        assert notif._scope_user_id("999") == ("999", None)
        assert notif._scope_user_id(None) == (None, None)
    finally:
        ctx.pop()


def test_a_caller_without_a_local_id_is_denied(app):
    ctx = _as(app, sub="S12345", role="student")
    try:
        scoped, denial = notif._scope_user_id(None)
        assert scoped is None
        assert denial is not None and denial[1] == 403
    finally:
        ctx.pop()


def test_self_addressing_needs_no_capability(app):
    ctx = _as(app, **STUDENT)
    try:
        assert notif._resolve_notification_target(None) == 42
        assert notif._resolve_notification_target(42) == 42
        assert notif._resolve_notification_target("42") == 42
        # Someone else, without the send capability: refused before any DB hit.
        assert notif._resolve_notification_target(99) is None
    finally:
        ctx.pop()


def test_search_branch_is_scoped():
    source = inspect.getsource(notif.list_notifications)
    assert "_scope_user_id(user_id)" in source
    # The search branch must carry the user_id constraint, not just the
    # paginated branch below it.
    search_branch = source[source.index("if search:"):source.index("conditions = []")]
    assert "user_id = ?" in search_branch
