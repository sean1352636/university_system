"""Tests for the Nursery Collections & Late Pickup domain.

Covers the door check (authorised list, validity window, collection password)
and the late-collection log's fee and escalation policy.
"""

from __future__ import annotations

import datetime as _dt

import pytest


@pytest.fixture
def collections(fresh_data_dir):
    """The collections domain wired to a throwaway database."""
    import importlib

    from education_system.nursery_system.core import database as db_mod
    importlib.reload(db_mod)
    from education_system.nursery_system.modules.domain.collections import (
        collections as mod,
    )
    importlib.reload(mod)
    mod.init_db()
    return mod


# ── Password hashing ─────────────────────────────────────────────────────────

def test_password_hash_is_salted_and_verifiable(collections):
    a = collections.hash_password("bluebell")
    b = collections.hash_password("bluebell")
    assert a != b, "each hash must carry its own salt"
    assert "bluebell" not in a
    assert collections.verify_password("bluebell", a)
    assert collections.verify_password("bluebell", b)
    assert not collections.verify_password("Bluebell", a)


def test_verify_password_rejects_missing_or_malformed_hashes(collections):
    assert not collections.verify_password("x", None)
    assert not collections.verify_password("x", "")
    assert not collections.verify_password("x", "not-a-hash")


# ── The door check ───────────────────────────────────────────────────────────

def test_unknown_person_is_refused(collections):
    result = collections.verify_collector("NCH001", "A Stranger")
    assert result.allowed is False
    assert "NOT on this child's authorised" in result.reason


def test_blank_name_is_refused(collections):
    assert collections.verify_collector("NCH001", "  ").allowed is False


def test_authorised_collector_without_password_is_allowed(collections):
    c = collections.create_collector({
        "pupil_id": "NCH005", "full_name": "Chloe Bennett",
        "relationship": "Parent", "id_checked": True, "photo_on_file": True})
    result = collections.verify_collector("NCH005", "Chloe Bennett")
    assert result.allowed is True
    assert result.collector.collector_id == c.collector_id


def test_password_is_required_then_checked(collections):
    collections.create_collector({
        "pupil_id": "NCH005", "full_name": "Ivy Bennett",
        "relationship": "Grandparent", "password": "seashell"})

    no_password = collections.verify_collector("NCH005", "Ivy Bennett")
    assert no_password.allowed is False
    assert no_password.password_required is True

    wrong = collections.verify_collector("NCH005", "Ivy Bennett", "wrong")
    assert wrong.allowed is False

    right = collections.verify_collector("NCH005", "Ivy Bennett", "seashell")
    assert right.allowed is True


def test_short_password_is_rejected(collections):
    with pytest.raises(collections.ValidationError):
        collections.create_collector({"pupil_id": "NCH005",
                                      "full_name": "Too Short",
                                      "password": "ab"})


def test_revoked_collector_is_refused(collections):
    c = collections.create_collector({"pupil_id": "NCH005",
                                      "full_name": "Old Neighbour"})
    collections.revoke_collector(c.collector_id, "No longer known to family")

    result = collections.verify_collector("NCH005", "Old Neighbour")
    assert result.allowed is False
    assert "revoked" in result.reason.lower()
    assert "No longer known to family" in collections.get_collector(
        c.collector_id).notes


def test_collector_outside_validity_window_is_refused(collections):
    collections.create_collector({
        "pupil_id": "NCH005", "full_name": "Summer Nanny",
        "valid_from": "2020-06-01", "valid_until": "2020-08-31"})
    result = collections.verify_collector("NCH005", "Summer Nanny")
    assert result.allowed is False
    assert "only authorised" in result.reason


def test_validity_window_rejects_reversed_dates(collections):
    with pytest.raises(collections.ValidationError):
        collections.create_collector({
            "pupil_id": "NCH005", "full_name": "Backwards",
            "valid_from": "2025-09-01", "valid_until": "2025-08-01"})


def test_emergency_contact_marked_can_collect_is_honoured(collections):
    with collections.connect() as conn:
        conn.execute(
            "INSERT INTO emergency_contacts (contact_id, pupil_id, full_name, "
            "relationship, phone_primary, priority, can_collect) "
            "VALUES ('NEC900', 'NCH005', 'Aunt Bea', 'Aunt/Uncle', "
            "'07700 900999', 1, 1)")
        conn.commit()
    result = collections.verify_collector("NCH005", "Aunt Bea")
    assert result.allowed is True
    assert "emergency contact" in result.reason


def test_unknown_child_yields_a_refusal_not_an_error(collections):
    assert collections.verify_collector("NOPE", "Anyone").allowed is False


def test_unchecked_id_is_allowed_but_flagged(collections):
    collections.create_collector({"pupil_id": "NCH005",
                                  "full_name": "New Neighbour"})
    result = collections.verify_collector("NCH005", "New Neighbour")
    assert result.allowed is True
    assert "ID not yet verified" in result.reason


def test_editing_a_collector_keeps_the_existing_password(collections):
    c = collections.create_collector({"pupil_id": "NCH005",
                                      "full_name": "Keep Password",
                                      "password": "acorn"})
    collections.update_collector(c.collector_id, {
        "full_name": "Keep Password", "phone": "07700 900123", "password": ""})
    assert collections.verify_collector("NCH005", "Keep Password",
                                        "acorn").allowed is True


def test_clear_password_flag_removes_it(collections):
    c = collections.create_collector({"pupil_id": "NCH005",
                                      "full_name": "Drop Password",
                                      "password": "acorn"})
    collections.update_collector(c.collector_id, {
        "full_name": "Drop Password", "clear_password": True})
    assert collections.get_collector(c.collector_id).has_password is False


# ── Fee & escalation policy ──────────────────────────────────────────────────

@pytest.mark.parametrize("minutes,expected", [
    (0, 0.0), (5, 0.0), (6, 5.0), (20, 5.0), (21, 10.0), (65, 20.0),
])
def test_compute_fee_charges_per_started_block_after_grace(
        collections, minutes, expected):
    assert collections.compute_fee(minutes) == expected


@pytest.mark.parametrize("minutes,stage", [
    (0, "none"), (10, "parent-called"), (35, "emergency-contacts-called"),
    (65, "manager-informed"), (95, "dsl-informed"), (150, "local-authority"),
])
def test_suggested_escalation_climbs_the_ladder(collections, minutes, stage):
    assert collections.suggested_escalation(minutes) == stage


def test_minutes_between_never_goes_negative(collections):
    assert collections.minutes_between("18:00", "18:25") == 25
    assert collections.minutes_between("18:00", "17:45") == 0


# ── Late collection log ──────────────────────────────────────────────────────

def test_log_derives_minutes_fee_and_escalation(collections):
    r = collections.log_late_collection({
        "pupil_id": "NCH001", "event_date": "2025-06-10",
        "due_time": "18:00", "collected_time": "18:40"})
    assert r.minutes_late == 40
    assert r.fee_amount == collections.compute_fee(40)
    assert r.escalation_stage == "emergency-contacts-called"
    assert r.fee_status == "due"
    assert r.outstanding == r.fee_amount


def test_explicit_fee_and_stage_win_over_the_policy(collections):
    r = collections.log_late_collection({
        "pupil_id": "NCH001", "event_date": "2025-06-10", "due_time": "18:00",
        "collected_time": "18:40", "fee_amount": "0", "fee_status": "waived",
        "escalation_stage": "none"})
    assert r.fee_amount == 0.0
    assert r.escalation_stage == "none"
    assert r.outstanding == 0.0


def test_open_record_has_no_collected_time(collections):
    r = collections.log_late_collection({
        "pupil_id": "NCH001", "event_date": "2025-06-10", "due_time": "18:00"})
    assert r.collected_time is None
    assert r.minutes_late == 0

    closed = collections.close_late_collection(r.record_id, "18:50", "A Parent")
    assert closed.collected_time == "18:50"
    assert closed.minutes_late == 50
    assert closed.fee_amount == collections.compute_fee(50)
    assert closed.collected_by == "A Parent"


def test_log_rejects_missing_due_time(collections):
    with pytest.raises(collections.ValidationError):
        collections.log_late_collection({"pupil_id": "NCH001",
                                         "event_date": "2025-06-10"})


def test_log_rejects_unknown_child(collections):
    with pytest.raises(collections.ValidationError):
        collections.log_late_collection({"pupil_id": "NOPE",
                                         "event_date": "2025-06-10",
                                         "due_time": "18:00"})


def test_log_rejects_bad_escalation_stage(collections):
    with pytest.raises(collections.ValidationError):
        collections.log_late_collection({
            "pupil_id": "NCH001", "event_date": "2025-06-10",
            "due_time": "18:00", "escalation_stage": "panic"})


def test_waive_fee_clears_the_outstanding_amount(collections):
    r = collections.log_late_collection({
        "pupil_id": "NCH001", "event_date": "2025-06-10", "due_time": "18:00",
        "collected_time": "18:40"})
    assert r.outstanding > 0

    waived = collections.waive_fee(r.record_id, "Setting ran the pickup late")
    assert waived.fee_status == "waived"
    assert waived.outstanding == 0.0
    assert "Setting ran the pickup late" in waived.notes


def test_summary_counts_gaps_and_outstanding_fees(collections):
    today = _dt.date.today().isoformat()
    collections.log_late_collection({
        "pupil_id": "NCH001", "event_date": today, "due_time": "18:00",
        "collected_time": "18:20"})
    s = collections.summary(today)
    assert s["late_today"] >= 1
    assert s["fees_outstanding"] > 0
    assert s["children_without_collectors"] >= 0
    assert isinstance(collections.children_without_collectors(), list)
