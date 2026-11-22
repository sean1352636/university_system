"""Student mobility: placements, learning agreements and credit recognition.

The module exists because a period abroad that nobody converts back into
home credit is indistinguishable, at graduation, from a year the student
did not study. So the tests concentrate on the guards against that: the
completion guard, the credit rollup trigger, and the two chase-lists.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

from education_system.systems.university.domains.curriculum.domain.student_mobility._db_init import (
    ensure_student_mobility_schema,
)
from education_system.systems.university.domains.curriculum.domain.student_mobility.services.student_mobility_service import (
    MobilityError,
    StudentMobilityService,
)


@pytest.fixture()
def service(tmp_path) -> StudentMobilityService:
    return StudentMobilityService(db_path=tmp_path / "mobility.db")


@pytest.fixture()
def agreement(service) -> int:
    return service.add_agreement("Uppsala University", country="Sweden",
                                 places_outgoing=2, subject_area="Computing")


@pytest.fixture()
def placement(service, agreement) -> int:
    return service.create_placement(
        "S12345", mobility_agreement_id=agreement, academic_year="2026/27",
        start_date="2026-09-01", end_date="2027-01-31", credits_expected=60)


def _days_from_now(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


# ----------------------------------------------------------------- schema

def test_bootstrap_is_idempotent(tmp_path):
    path = tmp_path / "twice.db"
    ensure_student_mobility_schema(path)
    ensure_student_mobility_schema(path)
    conn = sqlite3.connect(path)
    try:
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    assert {"mobility_agreements", "mobility_placements",
            "mobility_learning_agreements",
            "mobility_credit_recognitions"} <= tables


# -------------------------------------------------------------- placements

def test_placement_inherits_host_details_from_the_agreement(service, agreement):
    placement_id = service.create_placement("S1", mobility_agreement_id=agreement)
    record = service.get_placement(placement_id)
    assert record["host_institution"] == "Uppsala University"
    assert record["host_country"] == "Sweden"


def test_placement_needs_a_host(service):
    with pytest.raises(MobilityError):
        service.create_placement("S1")


def test_unknown_direction_is_rejected(service):
    with pytest.raises(MobilityError):
        service.create_placement("S1", host_institution="Elsewhere",
                                 direction="sideways")


def test_end_date_before_start_is_rejected(service):
    with pytest.raises(MobilityError):
        service.create_placement("S1", host_institution="Elsewhere",
                                 start_date="2027-01-01", end_date="2026-01-01")


def test_currently_away_uses_the_date_window(service, placement):
    service.set_status(placement, "In Progress")
    assert len(service.currently_away("2026-10-01")) == 1
    assert service.currently_away("2027-06-01") == []
    assert service.is_away("S12345", "2026-10-01")
    assert not service.is_away("S12345", "2027-06-01")


def test_place_availability_flags_over_subscription(service, agreement):
    for i in range(3):
        service.create_placement(f"S{i}", mobility_agreement_id=agreement)
    row = service.place_availability("outgoing")[0]
    assert row["places"] == 2
    assert row["taken"] == 3
    assert row["remaining"] == -1
    assert row["over_subscribed"]


def test_cancelled_placements_free_their_place(service, agreement):
    first = service.create_placement("S1", mobility_agreement_id=agreement)
    service.create_placement("S2", mobility_agreement_id=agreement)
    service.set_status(first, "Cancelled")
    assert service.place_availability("outgoing")[0]["taken"] == 1


# ----------------------------------------------------- learning agreements

def test_placement_without_a_learning_agreement_is_chased(service, placement):
    service.set_status(placement, "Approved")
    chased = service.unsigned_learning_agreements()
    assert [p["placement_id"] for p in chased] == [placement]


def test_signing_clears_the_chase_list(service, placement):
    service.set_status(placement, "Approved")
    service.add_learning_agreement_line(placement, "Algorithms",
                                        host_credits=7.5,
                                        home_module_code="CS201",
                                        home_credits=30)
    assert service.unsigned_learning_agreements()
    assert service.sign_learning_agreement(placement,
                                           approved_by_home="Dr Vance") == 1
    assert service.unsigned_learning_agreements() == []


def test_partially_signed_agreements_are_still_chased(service, placement):
    service.set_status(placement, "Approved")
    service.add_learning_agreement_line(placement, "Algorithms")
    service.sign_learning_agreement(placement)
    service.add_learning_agreement_line(placement, "Distributed Systems")
    assert [p["placement_id"] for p in
            service.unsigned_learning_agreements()] == [placement]


# -------------------------------------------------------- credit recognition

def test_completion_is_blocked_until_credit_comes_home(service, placement):
    service.set_status(placement, "In Progress")
    service.set_status(placement, "Returned")
    with pytest.raises(MobilityError) as excinfo:
        service.set_status(placement, "Completed")
    assert "credits recognised" in str(excinfo.value)


def test_recognition_rolls_up_onto_the_placement(service, placement):
    service.record_recognition(placement, home_module_code="CS201",
                               home_credits=30, host_grade="A")
    assert service.get_placement(placement)["credits_recognised"] == 30
    service.record_recognition(placement, home_module_code="CS202",
                               home_credits=30, host_grade="B")
    record = service.get_placement(placement)
    assert record["credits_recognised"] == 60
    assert record["recognition_state"] == "Recognised"


def test_partial_recognition_is_labelled(service, placement):
    service.record_recognition(placement, home_module_code="CS201",
                               home_credits=30)
    assert service.get_placement(placement)["recognition_state"] == \
        "Partially Recognised"


def test_completion_allowed_once_credit_is_recognised(service, placement):
    service.set_status(placement, "In Progress")
    service.set_status(placement, "Returned")
    service.record_recognition(placement, home_credits=60)
    assert service.set_status(placement, "Completed")["status"] == "Completed"


def test_unrecognised_outcomes_do_not_count(service, placement):
    service.record_recognition(placement, home_credits=30,
                               outcome="Not Recognised")
    assert service.get_placement(placement)["credits_recognised"] == 0


def test_credit_shortfall_reports_the_gap(service, placement):
    service.record_recognition(placement, home_credits=20)
    shortfall = service.credit_shortfall(placement)
    assert shortfall["credits_expected"] == 60
    assert shortfall["credits_recognised"] == 20
    assert shortfall["shortfall"] == 40


def test_awaiting_recognition_respects_the_grace_period(service, agreement):
    recent = service.create_placement(
        "S1", mobility_agreement_id=agreement, credits_expected=60,
        end_date=_days_from_now(-10))
    stale = service.create_placement(
        "S2", mobility_agreement_id=agreement, credits_expected=60,
        end_date=_days_from_now(-200))
    for placement_id in (recent, stale):
        service.set_status(placement_id, "In Progress")
        service.set_status(placement_id, "Returned")

    chased = service.awaiting_recognition(older_than_days=60)
    assert [p["placement_id"] for p in chased] == [stale]


def test_recognition_against_an_unknown_placement_is_rejected(service):
    with pytest.raises(MobilityError):
        service.record_recognition(9999, home_credits=10)


# ------------------------------------------------------------- monitoring

def test_preparation_gaps_lists_missing_insurance(service, placement):
    service.set_status(placement, "Approved")
    assert [p["placement_id"] for p in service.preparation_gaps()] == [placement]
    service.update_placement(placement, insurance_confirmed=1, risk_assessed=1)
    assert service.preparation_gaps() == []


def test_student_history_includes_plan_and_recognitions(service, placement):
    service.add_learning_agreement_line(placement, "Algorithms")
    service.record_recognition(placement, home_credits=30)
    history = service.student_history("S12345")
    assert len(history) == 1
    assert len(history[0]["learning_agreement"]) == 1
    assert len(history[0]["recognitions"]) == 1


def test_summary_counts_by_direction(service, agreement):
    service.create_placement("S1", mobility_agreement_id=agreement)
    service.create_placement("S2", host_institution="Elsewhere",
                             direction="incoming")
    summary = service.summary()
    assert summary["outgoing"] == 1
    assert summary["incoming"] == 1
    assert summary["agreements"] == 1
