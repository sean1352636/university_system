"""Behavioural tests for equality_diversity.access (RBAC + records/incidents)."""

from __future__ import annotations

import json

import pytest

from education_system.systems.university.domain.pastoral.equality_diversity import (
    access,
    integrations,
)


# --------------------------------------------------------------------------- #
# Stub the one module-level seam access reaches out to: integrations.audit.
# --------------------------------------------------------------------------- #
@pytest.fixture()
def audit_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(
        integrations, "audit",
        lambda actor, action, entity, entity_id=None, details=None: calls.append(
            (actor, action, entity, entity_id, details)
        ),
    )
    return calls


# --- Principal helpers ----------------------------------------------------- #

def _principal(role, **kw):
    return access.Principal(
        username="u",
        role=role,
        is_admin=role in access.ADMIN_ROLES,
        is_auditor=role in access.AUDITOR_ROLES,
        is_student=role in access.STUDENT_ROLES,
        **kw,
    )


def test_tabs_per_role():
    assert _principal("student").tabs() == ["My Data", "Reports"]
    assert "Admin" in _principal("auditor").tabs()
    assert "Add Record" not in _principal("auditor").tabs()
    admin_tabs = _principal("admin").tabs()
    assert "Add Record" in admin_tabs and "Admin" in admin_tabs
    standard = _principal("standard").tabs()
    assert "Admin" not in standard and "Add Record" in standard


def test_can_admin_only_capabilities():
    admin = _principal("admin")
    standard = _principal("standard")
    auditor = _principal("auditor")
    assert admin.can("delete_record") is True
    assert standard.can("delete_record") is False
    assert auditor.can("delete_record") is False
    # admin gets everything else too
    assert admin.can("add_note") is True


def test_can_auditor_read_and_export_only():
    auditor = _principal("auditor")
    assert auditor.can("view_audit_log") is False  # admin_only wins
    assert auditor.can("view_own") is True
    assert auditor.can("export_csv") is True
    assert auditor.can("add_record") is False


def test_can_student_scope():
    student = _principal("student")
    assert student.can("self_update") is True
    assert student.can("view_own") is True
    assert student.can("add_record") is False


def test_can_standard_staff_scope():
    standard = _principal("standard")
    assert standard.can("add_record") is True
    assert standard.can("view_own") is True
    assert standard.can("delete_record") is False  # admin_only
    assert standard.can("issue_token") is False    # admin_only


def test_mask_sensitive_fields():
    standard = _principal("standard")
    admin = _principal("admin")
    assert standard.mask("religion", "Christian") == "••••"
    assert standard.mask("department", "Physics") == "Physics"
    assert admin.mask("religion", "Christian") == "Christian"
    assert standard.mask("religion", None) == ""


def test_idle_timeout(monkeypatch):
    p = _principal("admin")
    p.touch()
    assert p.is_idle() is False
    # force last_activity far into the past
    p.last_activity -= access.IDLE_TIMEOUT_SECONDS + 1
    assert p.is_idle() is True


def test_principal_from_auth_none_when_no_user():
    class Auth:
        current_user = None

    assert access.principal_from_auth(Auth()) is None
    assert access.principal_from_auth(object()) is None


def test_principal_from_auth_builds_principal():
    class Auth:
        current_user = {"username": "boss", "role": "Administrator",
                        "id": 7, "email": "b@x.ac.uk"}

    p = access.principal_from_auth(Auth())
    assert p.is_admin is True and p.role == "administrator"
    assert p.user_id == 7 and p.email == "b@x.ac.uk"


def test_principal_from_auth_falls_back_to_email_username():
    class Auth:
        current_user = {"email": "e@x.ac.uk", "role": "student"}

    p = access.principal_from_auth(Auth())
    assert p.username == "e@x.ac.uk" and p.is_student is True


# --- deletion approval queue (feature 40) ---------------------------------- #

def test_deletion_request_approve_flow():
    qid = access.request_deletion("person", 5, json.dumps({"id": 5}), "alice")
    assert isinstance(qid, int)
    pending = access.list_pending_deletions()
    assert any(row[0] == qid for row in pending)

    # self-approval refused
    assert access.approve_deletion(qid, "alice") is None
    # different admin approves
    result = access.approve_deletion(qid, "bob")
    assert result == ("person", 5, json.dumps({"id": 5}))
    # already approved → None; and it left the pending queue
    assert access.approve_deletion(qid, "carol") is None
    assert all(row[0] != qid for row in access.list_pending_deletions())


def test_approve_deletion_unknown_id():
    assert access.approve_deletion(999, "bob") is None


# --- view log (feature 42) ------------------------------------------------- #

def test_record_view_and_views_of():
    access.record_view("person", 3, "viewer1")
    access.record_view("person", 3, "viewer2")
    access.record_view("person", 4, "viewer3")
    rows = access.views_of("person", 3)
    assert {r[0] for r in rows} == {"viewer1", "viewer2"}
    assert access.views_of("person", 4)[0][0] == "viewer3"


# --- records CRUD ---------------------------------------------------------- #

def test_create_get_and_list_records(audit_calls):
    rid = access.create_record("R100", "Staff", department="Physics",
                               gender="Female", ethnicity="Mixed",
                               salary=40000.0, created_by="tester")
    rec = access.get_record(rid)
    assert rec["ref_code"] == "R100" and rec["gender"] == "Female"
    assert access.get_record(9999) is None
    listed = access.list_records()
    assert any(r["id"] == rid for r in listed)
    assert audit_calls and audit_calls[0][1] == "create"


def test_list_records_search_and_filters(audit_calls):
    access.create_record("R1", "Staff", department="Physics", ethnicity="Mixed")
    access.create_record("R2", "Student", department="Biology", ethnicity="Arab")
    # search matches department/ethnicity/ref/person_type
    assert {r["ref_code"] for r in access.list_records(search="Physics")} == {"R1"}
    # demographic filter (allow-listed field)
    assert {r["ref_code"] for r in access.list_records(filters={"ethnicity": "Arab"})} == {"R2"}
    # non-allow-listed / empty filter ignored → returns everything
    assert len(access.list_records(filters={"bogus": "x", "gender": ""})) == 2


def test_list_records_include_deleted(audit_calls):
    rid = access.create_record("R9", "Staff")
    access.soft_delete_record(rid, requested_by="tester")
    assert all(r["id"] != rid for r in access.list_records())
    assert any(r["id"] == rid for r in access.list_records(include_deleted=True))


def test_update_record_paths(audit_calls):
    rid = access.create_record("R50", "Staff", department="Old")
    assert access.update_record(rid, {"department": "New"}, updated_by="ed") is True
    assert access.get_record(rid)["department"] == "New"
    # nothing editable → False, no audit for update
    assert access.update_record(rid, {"ref_code": "hax"}) is False
    # no matching row → False
    assert access.update_record(9999, {"department": "X"}) is False
    assert any(c[1] == "update" for c in audit_calls)


def test_soft_delete_missing_record(audit_calls):
    assert access.soft_delete_record(4242) is None


def test_create_record_duplicate_ref_raises(audit_calls):
    access.create_record("DUP", "Staff")
    with pytest.raises(Exception):
        access.create_record("DUP", "Staff")


# --- incidents ------------------------------------------------------------- #

def test_create_incident_sets_sla_and_lists(audit_calls):
    iid = access.create_incident("Harassment", department="Physics",
                                 severity="High", reported_by="rep")
    inc = access.get_incident(iid)
    assert inc["severity"] == "High" and inc["status"] == "Open"
    assert inc["sla_deadline"] is not None
    assert access.get_incident(9999) is None
    assert any(i["id"] == iid for i in access.list_incidents())
    assert any(i["id"] == iid for i in access.list_incidents(status="Open"))
    assert access.list_incidents(status="Closed") == []


def test_create_incident_anonymous(audit_calls):
    iid = access.create_incident("Bullying", reported_by="real",
                                 anonymous=True)
    inc = access.get_incident(iid)
    assert inc["reported_by"] == "anonymous" and inc["anonymous"] == 1


def test_create_incident_unknown_severity_defaults_sla(audit_calls):
    iid = access.create_incident("Other", severity="Weird")
    assert access.get_incident(iid)["sla_deadline"] is not None


def test_update_incident_status_and_assign(audit_calls):
    iid = access.create_incident("Discrimination", severity="Low")
    assert access.update_incident_status(iid, "Closed", actor="mgr") is True
    assert access.get_incident(iid)["status"] == "Closed"
    assert access.update_incident_status(9999, "Closed") is False
    assert access.assign_incident(iid, "invest.or", actor="mgr") is True
    assert access.get_incident(iid)["assigned_to"] == "invest.or"
    assert access.assign_incident(9999, "x") is False
