"""Two fail-open defects that must not come back.

1. The login route converted any exception from the MFA policy check into
   ``{"action": "allow"}``, so a database or import failure in the MFA store
   handed out full access and refresh tokens with no second factor.
2. The feedback routes took the caller's identity from a request parameter,
   so supplying the victim's id passed the ownership check.

The route bodies need a live Flask app, a signed JWT and a database to run
end to end, so these tests pin the decision logic directly and assert the
source no longer contains the patterns that caused the bugs.
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
import re

import pytest
from flask import Flask, g

from education_system.platform.delivery.api.university import auth as A
from education_system.api.university.operations import (
    feedback_system_routes as feedback,
)
from education_system.systems.university.shell.api.routes import auth_routes

pytestmark = pytest.mark.security


@pytest.fixture
def app():
    return Flask(__name__)


def _as(app, **user):
    ctx = app.test_request_context()
    ctx.push()
    g.current_user = user
    return ctx


# ---- 1. login fails closed when MFA cannot be evaluated ----

def test_mfa_unavailable_issues_no_tokens(app):
    class _Auth:
        logged_out = False

        def logout(self):
            self.logged_out = True

    auth = _Auth()
    with app.test_request_context():
        body, status = auth_routes._mfa_unavailable(auth)

    assert status == 503
    payload = body.get_json()
    assert "access_token" not in payload
    assert "refresh_token" not in payload
    assert auth.logged_out is True


def test_a_logout_failure_does_not_turn_the_refusal_into_a_login(app):
    class _BrokenAuth:
        def logout(self):
            raise RuntimeError("session store down")

    with app.test_request_context():
        _, status = auth_routes._mfa_unavailable(_BrokenAuth())

    assert status == 503


@pytest.mark.parametrize("action", ["allow", "grace", "require_mfa", "require_setup", "locked"])
def test_known_actions_are_accepted(action):
    assert action in auth_routes._KNOWN_MFA_ACTIONS


@pytest.mark.parametrize("action", [None, "", "ALLOW", "permit", "unknown", 0])
def test_unusable_actions_are_not_treated_as_allow(action):
    assert action not in auth_routes._KNOWN_MFA_ACTIONS


def test_login_has_no_allow_on_exception_fallback():
    source = inspect.getsource(auth_routes.login)
    # The exact shape of the old bug: an exception handler that manufactured
    # a permissive policy result.
    assert not re.search(r"except[^\n]*:\s*\n\s*mfa_result\s*=\s*\{\s*[\"']action[\"']\s*:\s*[\"']allow", source)
    assert 'mfa_result.get("action", "allow")' not in source


# ---- 2. feedback identity comes from the token ----

def test_owner_check_denies_a_non_owner(app):
    ctx = _as(app, sub="S12345", user_id=7, role="student")
    try:
        # Victim's submission, attacker's token.
        denial = A.deny_unless_owner_or_staff("S99999")
        assert denial is not None and denial[1] == 403
        assert A.deny_unless_owner_or_staff("S12345") is None
    finally:
        ctx.pop()


def test_delete_submission_uses_the_token_subject_only():
    source = inspect.getsource(feedback.delete_submission)
    assert "deny_unless_owner_or_staff" in source
    # The defect was reading the caller's identity out of the query string.
    assert "request.args.get" not in source


@pytest.mark.parametrize("handler", [
    "delete_submission",
    "upvote_submission",
    "remove_vote",
    "create_submission",
    "update_submission_status",
])
def test_no_handler_takes_its_caller_identity_from_the_request(handler):
    source = inspect.getsource(getattr(feedback, handler))
    for forged in ('request.args.get("user_id")', 'data.get("user_id")',
                   'data["user_id"]', 'data.get("updated_by")'):
        if forged in source:
            # Only permitted alongside an explicit staff check, which is how
            # create_submission still supports filing on someone's behalf.
            assert "is_staff()" in source, f"{handler} trusts {forged}"


@pytest.mark.parametrize("name", ["get_user_submissions", "get_user_votes"])
def test_per_user_feedback_reads_are_scoped(name):
    module_source = inspect.getsource(feedback)
    # The decorator must sit directly above the handler, below @token_required.
    assert re.search(
        r"@scoped_to\(\"student_id\"\)\s*\ndef %s\(" % name, module_source
    ), f"{name} is missing @scoped_to"
