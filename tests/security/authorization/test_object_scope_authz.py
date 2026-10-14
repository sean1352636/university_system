"""Object-level authorization: horizontal privilege escalation is denied.

Covers task 2 — user A must not reach user B's records. Exercises the shared
`authorize_object` / `scoped_to` primitives directly (route wiring is verified
by the presence of the decorators; these tests pin the decision logic).
"""

from __future__ import annotations

import pytest
from flask import Flask, g

from education_system.platform.delivery.api.university import auth as A

pytestmark = pytest.mark.security


@pytest.fixture
def app():
    return Flask(__name__)


def _as(app, **user):
    ctx = app.test_request_context()
    ctx.push()
    g.current_user = user
    return ctx


def test_student_can_reach_own_record(app):
    ctx = _as(app, sub="S12345", user_id=7, role="student")
    try:
        assert A.authorize_object("S12345") is None
    finally:
        ctx.pop()


def test_student_cannot_reach_other_students_record(app):
    ctx = _as(app, sub="S12345", user_id=7, role="student")
    try:
        # Horizontal escalation: A asking for B's id must be denied (403).
        denial = A.authorize_object("S99999")
        assert denial is not None
        assert denial[1] == 403
    finally:
        ctx.pop()


def test_staff_may_reach_any_record(app):
    ctx = _as(app, sub="prof", user_id=2, role="instructor")
    try:
        assert A.authorize_object("S99999") is None
        assert A.is_staff() is True
    finally:
        ctx.pop()


def test_unknown_role_denied(app):
    ctx = _as(app, sub="x", user_id=3, role="wizard")
    try:
        assert A.authorize_object("x") is not None
    finally:
        ctx.pop()


def test_missing_owner_id_denies_non_staff(app):
    ctx = _as(app, sub="S1", user_id=1, role="student")
    try:
        assert A.authorize_object(None) is not None
    finally:
        ctx.pop()


def test_scoped_to_denies_cross_subject(app):
    """The decorator returns the handler only for the owner or staff."""
    calls = {"n": 0}

    @A.scoped_to("student_id")
    def handler(student_id):
        calls["n"] += 1
        return "ok"

    ctx = _as(app, sub="S1", user_id=1, role="student")
    try:
        # Own id -> handler runs
        assert handler(student_id="S1") == "ok"
        # Someone else's id -> 403 tuple, handler NOT run
        result = handler(student_id="S2")
        assert isinstance(result, tuple) and result[1] == 403
        assert calls["n"] == 1
    finally:
        ctx.pop()


def test_staff_required_blocks_students(app):
    @A.staff_required
    def handler():
        return "ok"

    ctx = _as(app, sub="S1", user_id=1, role="student")
    try:
        result = handler()
        assert isinstance(result, tuple) and result[1] == 403
    finally:
        ctx.pop()

    ctx = _as(app, sub="prof", user_id=2, role="staff")
    try:
        assert handler() == "ok"
    finally:
        ctx.pop()


# ---- per-blueprint owner-scope helpers (budget / betting) -------------------

def test_budget_owner_scope_helper(app):
    import education_system.api.university.finance.budget_routes as B

    ctx = _as(app, sub="S1", user_id=1, role="student")
    try:
        assert B._deny_unless_owner_or_staff("S1") is None            # own
        assert B._deny_unless_owner_or_staff("S2")[1] == 403          # other student
        assert B._deny_unless_owner_or_staff(None)[1] == 403          # unknown owner
    finally:
        ctx.pop()

    ctx = _as(app, sub="prof", user_id=2, role="staff")
    try:
        assert B._deny_unless_owner_or_staff("anyone") is None        # staff bypass
    finally:
        ctx.pop()


def test_betting_owner_scope_helper(app):
    import education_system.systems.university.plugins.campus_commerce.api.betting_routes as BET

    ctx = _as(app, sub="alice", user_id=1, role="student")
    try:
        assert BET._deny_unless_betting_owner_or_staff("alice") is None
        assert BET._deny_unless_betting_owner_or_staff("bob")[1] == 403
    finally:
        ctx.pop()

    ctx = _as(app, sub="admin", user_id=9, role="admin")
    try:
        assert BET._deny_unless_betting_owner_or_staff("bob") is None
    finally:
        ctx.pop()


def test_central_deny_unless_owner_or_staff(app):
    """The shared row-level helper used across advising/study/accessibility."""
    ctx = _as(app, sub="S1", user_id=1, role="student")
    try:
        assert A.deny_unless_owner_or_staff("S1") is None       # own record
        assert A.deny_unless_owner_or_staff("S2")[1] == 403      # someone else's
        assert A.deny_unless_owner_or_staff(None)[1] == 403      # unresolved owner
    finally:
        ctx.pop()

    ctx = _as(app, sub="advisor", user_id=2, role="faculty")
    try:
        assert A.deny_unless_owner_or_staff("S2") is None        # staff bypass
    finally:
        ctx.pop()


# ---- permission-claim enforcement (previously dead code) --------------------

def _perm_ok(app, role, perm, **extra):
    ctx = _as(app, sub="u", user_id=1, role=role, **extra)
    try:
        return A.authorize_object("staff-boundary", permission=perm) is None
    finally:
        ctx.pop()


def test_permission_argument_now_enforces(app):
    # manage_grades is admin/staff-only in the canonical map.
    assert _perm_ok(app, "admin", "manage_grades") is True
    assert _perm_ok(app, "staff", "manage_grades") is True
    assert _perm_ok(app, "instructor", "manage_grades") is False


def test_grade_entry_capability_allows_instructors(app):
    # enter_grades / edit_grades ARE held by instructors.
    assert _perm_ok(app, "instructor", "enter_grades") is True
    assert _perm_ok(app, "instructor", "edit_grades") is True


def test_role_aliases_resolve(app):
    # superadmin -> admin perms; teacher/faculty -> instructor perms.
    assert _perm_ok(app, "superadmin", "manage_grades") is True
    assert _perm_ok(app, "teacher", "enter_grades") is True
    assert _perm_ok(app, "faculty", "manage_grades") is False


def test_explicit_permissions_claim_is_authoritative(app):
    # A token that carries its own permissions list is trusted over the role
    # (the permission branch only applies to staff roles, so use one).
    assert _perm_ok(app, "staff", "manage_grades", permissions=["something_else"]) is False
    assert _perm_ok(app, "staff", "manage_grades", permissions=["manage_grades"]) is True


def test_no_permission_required_keeps_staff_pass(app):
    assert _perm_ok(app, "instructor", None) is True
