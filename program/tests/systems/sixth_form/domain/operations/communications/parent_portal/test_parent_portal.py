"""Tests for the parent portal accounts + snapshots."""

from __future__ import annotations

import pytest


def test_account_creation_validation(feature_db):
    pp = feature_db.mods["parent_portal"]
    with pytest.raises(pp.ValidationError):
        pp.create_account(username="", password="longenough", full_name="P")
    with pytest.raises(pp.ValidationError):
        pp.create_account(username="p", password="short", full_name="P")
    with pytest.raises(pp.ValidationError):
        pp.create_account(username="p", password="longenough", full_name="")


def test_duplicate_username_rejected(feature_db):
    pp = feature_db.mods["parent_portal"]
    pp.create_account(username="dup", password="password1", full_name="A")
    with pytest.raises(pp.ValidationError):
        pp.create_account(username="dup", password="password2", full_name="B")


def test_authenticate_success_and_failure(feature_db):
    pp = feature_db.mods["parent_portal"]
    pp.create_account(username="parent1", password="password1", full_name="Pat")
    assert pp.authenticate("parent1", "password1") is not None
    assert pp.authenticate("parent1", "wrong") is None
    assert pp.authenticate("ghost", "password1") is None
    # Username is case-insensitive.
    assert pp.authenticate("PARENT1", "password1") is not None


def test_disabled_account_cannot_login(feature_db):
    pp = feature_db.mods["parent_portal"]
    aid = pp.create_account(username="parent2", password="password1", full_name="Pat")
    pp.set_active(aid, False)
    assert pp.authenticate("parent2", "password1") is None


def test_link_unknown_student_rejected(feature_db):
    pp = feature_db.mods["parent_portal"]
    aid = pp.create_account(username="parent3", password="password1", full_name="Pat")
    with pytest.raises(pp.ValidationError):
        pp.link_student(aid, "GHOST")


def test_dashboard_aggregates_linked_children(feature_db):
    pp = feature_db.mods["parent_portal"]
    aid = pp.create_account(username="parent4", password="password1", full_name="Pat")
    pp.link_student(aid, "S1", relationship="Mother")
    dash = pp.account_dashboard(aid)
    assert dash["account"]["username"] == "parent4"
    assert len(dash["children"]) == 1
    child = dash["children"][0]
    assert child["full_name"] == "Alex Atrisk"
    assert child["relationship"] == "Mother"
    assert child["risk_band"] in ("Low", "Medium", "High", "Critical")
    assert len(child["subjects"]) == 3
    # 30-day behaviour split is exposed (1 positive, 1 negative seeded).
    assert child["behaviour_30d"] == {"positive": 1, "negative": 1}


def test_snapshot_excludes_no_extra_pii(feature_db):
    pp = feature_db.mods["parent_portal"]
    snap = pp.student_snapshot("S2")
    # Only the safe, aggregated keys are present.
    assert set(snap) == {"student_id", "full_name", "status", "attendance_pct",
                         "risk_band", "behaviour_30d", "subjects", "ucas"}


def test_unlink(feature_db):
    pp = feature_db.mods["parent_portal"]
    aid = pp.create_account(username="parent5", password="password1", full_name="Pat")
    pp.link_student(aid, "S1")
    assert len(pp.linked_students(aid)) == 1
    pp.unlink_student(aid, "S1")
    assert pp.linked_students(aid) == []
