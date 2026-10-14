"""Collaborative (partner) provision service.

The register itself is ordinary CRUD; the tests concentrate on the three
queries the module exists for — reviews nobody did, agreements recruiting
past their contracted cap, and the map of what we award off-site — plus
the trigger that keeps a review's next-due date on the agreement.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

from education_system.systems.university.domains.academics.domain.collaborative_provision._db_init import (
    AGREEMENT_STATUSES,
    DELIVERY_MODELS,
    ensure_collaborative_provision_schema,
)
from education_system.systems.university.domains.academics.domain.collaborative_provision.services.collaborative_provision_service import (
    CollaborativeProvisionService,
)


@pytest.fixture()
def service(tmp_path) -> CollaborativeProvisionService:
    """A service on an isolated database — never the live one."""
    return CollaborativeProvisionService(db_path=tmp_path / "partners.db")


@pytest.fixture()
def partner(service) -> int:
    return service.add_partner("Riverside College",
                               partner_type="UK Further Education College",
                               country="UK", risk_level="High")


def _days_from_now(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


# ----------------------------------------------------------------- schema

def test_bootstrap_is_idempotent(tmp_path):
    path = tmp_path / "twice.db"
    ensure_collaborative_provision_schema(path)
    ensure_collaborative_provision_schema(path)
    conn = sqlite3.connect(path)
    try:
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    assert {"partner_institutions", "partnership_agreements",
            "collaborative_programmes", "partner_cohorts",
            "partner_reviews"} <= tables


def test_partner_name_is_required(service):
    with pytest.raises(ValueError):
        service.add_partner("   ")


def test_unknown_delivery_model_is_rejected(service, partner):
    with pytest.raises(ValueError):
        service.add_agreement(partner, "Handshake")


def test_unknown_agreement_status_is_rejected(service, partner):
    with pytest.raises(ValueError):
        service.add_agreement(partner, DELIVERY_MODELS[0], status="Vibes")


# ------------------------------------------------------------- monitoring

def test_overdue_reviews_lists_only_live_agreements(service, partner):
    live = service.add_agreement(partner, "Franchise", status="Active",
                                 review_due="2020-01-01")
    service.add_agreement(partner, "Validation", status="Terminated",
                          review_due="2020-01-01")
    overdue = service.overdue_reviews()
    assert [a["agreement_id"] for a in overdue] == [live]


def test_recording_a_review_clears_the_overdue_flag(service, partner):
    agreement = service.add_agreement(partner, "Franchise", status="Active",
                                      review_due="2020-01-01")
    assert service.overdue_reviews()
    service.add_review(partner, "Annual Monitoring", date.today().isoformat(),
                       agreement_id=agreement, outcome="Approved",
                       next_review_due=_days_from_now(365))
    # The trigger mirrors next_review_due onto the agreement, so the
    # coordinator does not have to type the date in two places.
    assert service.overdue_reviews() == []
    assert service.get_agreement(agreement)["review_due"] == _days_from_now(365)


def test_due_diligence_review_updates_the_partner(service, partner):
    service.add_review(partner, "Initial Due Diligence", "2026-05-01",
                       outcome="Approved", next_review_due="2029-05-01")
    record = service.get_partner(partner)
    assert record["due_diligence_date"] == "2026-05-01"
    assert record["due_diligence_due"] == "2029-05-01"


def test_over_recruited_counts_across_every_cohort(service, partner):
    """The cap is written per agreement, so it is breached per agreement
    even when the students arrive on two different programmes."""
    agreement = service.add_agreement(partner, "Franchise", status="Active",
                                      max_students=50)
    first = service.add_programme(agreement, "BSc Computing")
    second = service.add_programme(agreement, "BSc Networks")
    service.add_cohort(first, "2026/27", actual_headcount=30)
    service.add_cohort(second, "2026/27", actual_headcount=25)

    breaches = service.over_recruited()
    assert len(breaches) == 1
    assert breaches[0]["enrolled"] == 55
    assert breaches[0]["max_students"] == 50


def test_within_cap_is_not_reported(service, partner):
    agreement = service.add_agreement(partner, "Franchise", status="Active",
                                      max_students=50)
    programme = service.add_programme(agreement, "BSc Computing")
    service.add_cohort(programme, "2026/27", actual_headcount=50)
    assert service.over_recruited() == []


def test_registered_headcount_is_used_when_actual_is_missing(service, partner):
    agreement = service.add_agreement(partner, "Franchise", status="Active",
                                      max_students=10)
    programme = service.add_programme(agreement, "BSc Computing")
    service.add_cohort(programme, "2026/27", registered_headcount=12)
    assert service.over_recruited()[0]["enrolled"] == 12


def test_expiring_agreements_respects_the_window(service, partner):
    soon = service.add_agreement(partner, "Franchise", status="Active",
                                 end_date=_days_from_now(30))
    service.add_agreement(partner, "Validation", status="Active",
                          end_date=_days_from_now(900))
    assert [a["agreement_id"] for a in service.expiring_agreements(180)] == [soon]


def test_unlinked_programmes_reports_blank_codes(service, partner):
    agreement = service.add_agreement(partner, "Franchise", status="Active")
    service.add_programme(agreement, "BSc Computing", programme_code=None)
    service.add_programme(agreement, "BSc Networks", programme_code="NET-BSC")
    unlinked = service.unlinked_programmes()
    assert [p["programme_title"] for p in unlinked] == ["BSc Computing"]


# ---------------------------------------------------------------- reports

def test_provision_map_has_one_row_per_programme(service, partner):
    agreement = service.add_agreement(partner, "Franchise", status="Active")
    first = service.add_programme(agreement, "BSc Computing", award="BSc (Hons)")
    service.add_programme(agreement, "BSc Networks")
    service.add_cohort(first, "2026/27", actual_headcount=12)
    service.add_cohort(first, "2027/28", actual_headcount=8)

    rows = service.provision_map()
    assert len(rows) == 2
    computing = next(r for r in rows if r["programme_title"] == "BSc Computing")
    assert computing["students"] == 20
    assert computing["partner_name"] == "Riverside College"


def test_summary_counts_live_agreements_only(service, partner):
    service.add_agreement(partner, "Franchise", status="Active")
    service.add_agreement(partner, "Validation", status="Terminated")
    summary = service.summary()
    assert summary["partners"] == 1
    assert summary["agreements_live"] == 1
    assert summary["high_risk"] == 1


def test_deactivated_partners_drop_out_of_the_active_list(service, partner):
    service.deactivate_partner(partner)
    assert service.list_partners(active_only=True) == []
    # Kept, not deleted: an ended partnership still has graduates whose
    # award has to be explicable.
    assert len(service.list_partners(active_only=False)) == 1


def test_status_vocabulary_is_shared(service, partner):
    """The GUI, CLI and API all read these; a silent rename would leave
    stored rows unreachable from the filters."""
    for status in AGREEMENT_STATUSES:
        service.add_agreement(partner, "Franchise", status=status)
    assert len(service.list_agreements()) == len(AGREEMENT_STATUSES)
