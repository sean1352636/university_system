"""Tests for RetentionPolicyEngine (CRUD + job history only).

Execution tests (run_policy / run_all_policies) are skipped because they
require real system databases on disk.  CRUD and job-tracking operate
entirely on the shared retention DB and are safe to test in isolation.
"""

import pytest

from education_system.shared.services.data_retention.policy_engine import (
    RetentionPolicyEngine,
)


@pytest.fixture()
def engine(tmp_path):
    db = str(tmp_path / "retention.db")
    return RetentionPolicyEngine(retention_db_path=db)


# ── default seeding ──────────────────────────────────────────────────

def test_default_policies_seeded(engine):
    policies = engine.get_all_policies()
    # models.py seeds 6 default policies
    assert len(policies) >= 6


def test_active_policies_subset(engine):
    active = engine.get_active_policies()
    all_p = engine.get_all_policies()
    assert len(active) <= len(all_p)
    for p in active:
        assert p["is_active"] == 1


# ── add_policy ───────────────────────────────────────────────────────

def test_add_policy(engine):
    policy = engine.add_policy(
        entity_type="test_entity",
        retention_days=180,
        action="delete",
        system_key="sixth_form",
        description="Test policy",
    )
    assert policy["entity_type"] == "test_entity"
    assert policy["retention_days"] == 180
    assert policy["action"] == "delete"
    assert policy["system_key"] == "sixth_form"
    assert policy["is_active"] == 1


def test_add_policy_invalid_action(engine):
    with pytest.raises(Exception):
        engine.add_policy("x", 30, "invalid_action")


# ── update_policy ────────────────────────────────────────────────────

def test_update_policy(engine):
    policy = engine.add_policy("ent", 90, "archive")
    updated = engine.update_policy(policy["id"], retention_days=365, description="updated")
    assert updated["retention_days"] == 365
    assert updated["description"] == "updated"


def test_update_policy_no_valid_fields(engine):
    policy = engine.add_policy("ent", 90, "archive")
    with pytest.raises(ValueError, match="No valid fields"):
        engine.update_policy(policy["id"], bogus_field=123)


# ── deactivate_policy ────────────────────────────────────────────────

def test_deactivate_policy(engine):
    policy = engine.add_policy("ent", 90, "delete")
    assert engine.deactivate_policy(policy["id"]) is True

    all_p = engine.get_all_policies()
    deactivated = [p for p in all_p if p["id"] == policy["id"]]
    assert deactivated[0]["is_active"] == 0


def test_deactivated_policy_not_in_active(engine):
    policy = engine.add_policy("ent", 90, "delete")
    engine.deactivate_policy(policy["id"])

    active_ids = {p["id"] for p in engine.get_active_policies()}
    assert policy["id"] not in active_ids


# ── job history ──────────────────────────────────────────────────────

def test_job_history_empty_initially(engine):
    # default policies exist but no jobs have run
    jobs = engine.get_job_history()
    assert isinstance(jobs, list)
    assert len(jobs) == 0


def test_job_history_after_run(engine):
    """run_policy creates a job entry even if no real tables exist."""
    policy = engine.add_policy("nonexistent_entity", 30, "delete")
    result = engine.run_policy(policy["id"])
    assert result["status"] in ("completed", "failed")

    jobs = engine.get_job_history()
    assert len(jobs) >= 1
    assert jobs[0]["policy_id"] == policy["id"]
