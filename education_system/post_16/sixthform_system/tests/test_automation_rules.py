"""Tests for the automation rules engine."""

from __future__ import annotations

import pytest


def test_create_rule_validation(feature_db):
    ar = feature_db.mods["automation_rules"]
    with pytest.raises(ar.ValidationError):
        ar.create_rule(name="", trigger_key="risk_score", threshold=10, action_label="x")
    with pytest.raises(ar.ValidationError):
        ar.create_rule(name="r", trigger_key="bogus", threshold=10, action_label="x")
    with pytest.raises(ar.ValidationError):
        ar.create_rule(name="r", trigger_key="risk_score", threshold=10,
                       action_label="x", severity="Wat")


def test_attendance_rule_flags_only_at_risk(feature_db):
    ar = feature_db.mods["automation_rules"]
    ar.create_rule(name="Low attendance", trigger_key="attendance_below",
                   threshold=80, action_label="Notify tutor", severity="High")
    res = ar.run_rules()
    assert res["rules_run"] == 1
    actions = ar.list_actions(status="Open")
    # S1 has ~50% attendance (< 80); S2 is 100% → only S1 flagged.
    assert [a["student_id"] for a in actions] == ["S1"]
    assert actions[0]["severity"] == "High"


def test_run_is_idempotent(feature_db):
    ar = feature_db.mods["automation_rules"]
    ar.create_rule(name="Any risk", trigger_key="risk_score", threshold=0,
                   action_label="Review")
    first = ar.run_rules()
    assert first["new_actions"] == 2          # both students match score >= 0
    second = ar.run_rules()
    assert second["new_actions"] == 0         # existing Open actions not duplicated
    assert len(ar.list_actions(status="Open")) == 2


def test_resolve_then_rerun_reopens(feature_db):
    ar = feature_db.mods["automation_rules"]
    ar.create_rule(name="Any risk", trigger_key="risk_score", threshold=0,
                   action_label="Review")
    ar.run_rules()
    actions = ar.list_actions(status="Open")
    ar.resolve_action(actions[0]["action_id"], status="Done", by="tester")
    assert len(ar.list_actions(status="Open")) == 1
    assert len(ar.list_actions(status="Done")) == 1
    # The resolved student has no Open action, so a rerun re-raises one.
    again = ar.run_rules()
    assert again["new_actions"] == 1


def test_enable_disable_and_delete(feature_db):
    ar = feature_db.mods["automation_rules"]
    rid = ar.create_rule(name="Any risk", trigger_key="risk_score", threshold=0,
                         action_label="Review")
    ar.set_enabled(rid, False)
    assert ar.run_rules()["rules_run"] == 0   # disabled rule skipped
    ar.set_enabled(rid, True)
    assert ar.run_rules()["rules_run"] == 1
    ar.delete_rule(rid)
    assert ar.list_rules() == []


def test_resolve_validation(feature_db):
    ar = feature_db.mods["automation_rules"]
    with pytest.raises(ar.ValidationError):
        ar.resolve_action(1, status="Bogus")
