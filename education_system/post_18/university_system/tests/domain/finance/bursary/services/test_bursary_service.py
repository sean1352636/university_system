"""Tests for bursary_service.py — bursary funds, applications, evidence,
awards and scheduled payments.

The autouse ``_isolate_db`` fixture (tests/conftest.py) points DEFAULT_DB_PATH
at a throw-away copy of the template DB, so ``BursaryService()`` with no
db_path creates and operates on the isolated database. ``init_schema`` builds
all bursary tables on construction.
"""

import pytest

from education_system.post_18.university_system.modules.domain.finance.bursary.services.bursary_service import (
    BursaryService,
    BursaryError,
    _add_months,
    _validate_date,
)
from datetime import datetime


@pytest.fixture
def svc():
    """A BursaryService bound to the isolated default DB."""
    return BursaryService()


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_validate_date_ok(self):
        dt = _validate_date("2025-01-15", "start_date")
        assert dt == datetime(2025, 1, 15)

    def test_validate_date_bad(self):
        with pytest.raises(BursaryError):
            _validate_date("15/01/2025", "start_date")

    def test_add_months_simple(self):
        assert _add_months(datetime(2025, 1, 31), 1) == datetime(2025, 2, 28)

    def test_add_months_year_rollover(self):
        assert _add_months(datetime(2025, 12, 10), 2) == datetime(2026, 2, 10)


# ---------------------------------------------------------------------------
# Funds
# ---------------------------------------------------------------------------

class TestFunds:
    def test_create_and_get_fund(self, svc):
        fid = svc.create_fund("Hardship 2025", "hardship", 10000.0)
        assert isinstance(fid, int) and fid > 0
        fund = svc.get_fund(fid)
        assert fund["name"] == "Hardship 2025"
        assert fund["total_budget"] == 10000.0
        assert fund["allocated"] == 0
        assert fund["status"] == "open"

    def test_create_fund_requires_name(self, svc):
        with pytest.raises(BursaryError):
            svc.create_fund("   ")

    def test_create_fund_invalid_type(self, svc):
        with pytest.raises(BursaryError):
            svc.create_fund("X", fund_type="not-a-type")

    def test_create_fund_negative_budget(self, svc):
        with pytest.raises(BursaryError):
            svc.create_fund("X", total_budget=-1)

    def test_list_funds_filter(self, svc):
        svc.create_fund("A", "hardship", 100)
        svc.create_fund("B", "emergency", 200)
        hardship = svc.list_funds(fund_type="hardship")
        assert all(f["fund_type"] == "hardship" for f in hardship)
        assert any(f["name"] == "A" for f in hardship)

    def test_get_fund_missing(self, svc):
        with pytest.raises(BursaryError):
            svc.get_fund(999999)

    def test_update_fund_budget(self, svc):
        fid = svc.create_fund("A", "hardship", 100)
        svc.update_fund_budget(fid, 500)
        assert svc.get_fund(fid)["total_budget"] == 500

    def test_update_fund_budget_below_allocated(self, svc):
        fid = svc.create_fund("A", "hardship", 1000)
        aid = _approved_application(svc, fid, 800)
        svc.award_bursary(aid, 800, "one_off", 1, "2025-01-01")
        with pytest.raises(BursaryError):
            svc.update_fund_budget(fid, 500)  # < allocated 800


# ---------------------------------------------------------------------------
# Applications + evidence
# ---------------------------------------------------------------------------

def _approved_application(svc, fund_id, amount=500):
    aid = svc.submit_application(1, fund_id, amount, household_income=12000, circumstances="need")
    svc.update_application_status(aid, "approved", "looks good")
    return aid


class TestApplications:
    def test_submit_and_get(self, svc):
        fid = svc.create_fund("A", "hardship", 5000)
        aid = svc.submit_application(42, fid, 500)
        app = svc.get_application(aid)
        assert app["student_id"] == 42
        assert app["status"] == "submitted"
        assert app["requested_amount"] == 500

    def test_submit_requires_positive_amount(self, svc):
        fid = svc.create_fund("A", "hardship", 5000)
        with pytest.raises(BursaryError):
            svc.submit_application(1, fid, 0)

    def test_submit_unknown_fund(self, svc):
        with pytest.raises(BursaryError):
            svc.submit_application(1, 987654, 100)

    def test_list_applications_filters(self, svc):
        fid = svc.create_fund("A", "hardship", 5000)
        svc.submit_application(1, fid, 100)
        svc.submit_application(2, fid, 200)
        assert len(svc.list_applications(fund_id=fid)) == 2
        assert len(svc.list_applications(student_id=1)) == 1

    def test_update_status_invalid(self, svc):
        fid = svc.create_fund("A", "hardship", 5000)
        aid = svc.submit_application(1, fid, 100)
        with pytest.raises(BursaryError):
            svc.update_application_status(aid, "bogus")

    def test_update_status_sets_decided_at(self, svc):
        fid = svc.create_fund("A", "hardship", 5000)
        aid = svc.submit_application(1, fid, 100)
        svc.update_application_status(aid, "approved", "ok")
        app = svc.get_application(aid)
        assert app["status"] == "approved"
        assert app["decided_at"] is not None


class TestEvidence:
    def test_add_and_list_evidence(self, svc):
        fid = svc.create_fund("A", "hardship", 5000)
        aid = svc.submit_application(1, fid, 100)
        eid = svc.add_evidence(aid, "bank_statement", "stmt.pdf", "3 months")
        rows = svc.list_evidence(aid)
        assert len(rows) == 1
        assert rows[0]["evidence_id"] == eid
        assert rows[0]["verified"] == 0

    def test_add_evidence_requires_type(self, svc):
        fid = svc.create_fund("A", "hardship", 5000)
        aid = svc.submit_application(1, fid, 100)
        with pytest.raises(BursaryError):
            svc.add_evidence(aid, "  ")

    def test_verify_evidence(self, svc):
        fid = svc.create_fund("A", "hardship", 5000)
        aid = svc.submit_application(1, fid, 100)
        eid = svc.add_evidence(aid, "bank_statement")
        svc.verify_evidence(eid, "officer_jane")
        row = svc.list_evidence(aid)[0]
        assert row["verified"] == 1
        assert row["verified_by"] == "officer_jane"

    def test_verify_missing_evidence(self, svc):
        with pytest.raises(BursaryError):
            svc.verify_evidence(999999, "officer")


# ---------------------------------------------------------------------------
# Awards + payments
# ---------------------------------------------------------------------------

class TestAwards:
    def test_award_requires_approved(self, svc):
        fid = svc.create_fund("A", "hardship", 5000)
        aid = svc.submit_application(1, fid, 500)  # still 'submitted'
        with pytest.raises(BursaryError):
            svc.award_bursary(aid, 500, "one_off", 1, "2025-01-01")

    def test_award_exceeds_budget(self, svc):
        fid = svc.create_fund("A", "hardship", 100)
        aid = _approved_application(svc, fid, 500)
        with pytest.raises(BursaryError):
            svc.award_bursary(aid, 500, "one_off", 1, "2025-01-01")

    def test_award_one_off_creates_single_payment(self, svc):
        fid = svc.create_fund("A", "hardship", 5000)
        aid = _approved_application(svc, fid, 600)
        award_id = svc.award_bursary(aid, 600, "one_off", 1, "2025-01-01")
        schedule = svc.get_payment_schedule(award_id)
        assert len(schedule) == 1
        assert schedule[0]["amount"] == 600
        # fund allocation and application status updated
        assert svc.get_fund(fid)["allocated"] == 600
        assert svc.get_application(aid)["status"] == "awarded"

    def test_award_monthly_splits_and_absorbs_rounding(self, svc):
        fid = svc.create_fund("A", "hardship", 5000)
        aid = _approved_application(svc, fid, 1000)
        award_id = svc.award_bursary(aid, 1000, "monthly", 3, "2025-01-31")
        schedule = svc.get_payment_schedule(award_id)
        assert len(schedule) == 3
        assert round(sum(p["amount"] for p in schedule), 2) == 1000.0

    def test_award_invalid_frequency(self, svc):
        fid = svc.create_fund("A", "hardship", 5000)
        aid = _approved_application(svc, fid, 500)
        with pytest.raises(BursaryError):
            svc.award_bursary(aid, 500, "daily", 1, "2025-01-01")

    def test_mark_payment_paid(self, svc):
        fid = svc.create_fund("A", "hardship", 5000)
        aid = _approved_application(svc, fid, 300)
        award_id = svc.award_bursary(aid, 300, "one_off", 1, "2025-01-01")
        pid = svc.get_payment_schedule(award_id)[0]["payment_id"]
        svc.mark_payment_paid(pid, "REF-001")
        row = svc.get_payment_schedule(award_id)[0]
        assert row["status"] == "paid"
        assert row["reference"] == "REF-001"

    def test_mark_payment_paid_requires_reference(self, svc):
        with pytest.raises(BursaryError):
            svc.mark_payment_paid(1, "  ")

    def test_mark_missing_payment(self, svc):
        with pytest.raises(BursaryError):
            svc.mark_payment_paid(999999, "REF")


class TestSummary:
    def test_application_summary(self, svc):
        fid = svc.create_fund("A", "hardship", 5000)
        aid = _approved_application(svc, fid, 400)
        svc.add_evidence(aid, "bank_statement")
        award_id = svc.award_bursary(aid, 400, "one_off", 1, "2025-01-01")
        summary = svc.get_application_summary(aid)
        assert summary["application"]["application_id"] == aid
        assert summary["fund"]["fund_id"] == fid
        assert len(summary["evidence"]) == 1
        assert summary["award"]["award_id"] == award_id
        assert len(summary["payments"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
