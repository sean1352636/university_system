"""Tests for the international-compliance visa_service module.

Module-level functions create their tables idempotently via init_db() against
the isolated DEFAULT_DB_PATH. _audit() and email helpers are best-effort and
swallow failures, so no stubbing is required.
"""

from datetime import date, timedelta

import pytest

from education_system.post_18.university_system.modules.domain.student_affairs.international_compliance.services import (
    visa_service as vs,
)


# --------------------------------------------------------------------------
# Pure-logic helpers
# --------------------------------------------------------------------------

def test_is_atas_required_for_module():
    assert vs.is_atas_required_for_module("CIS200-Research") is True
    assert vs.is_atas_required_for_module("HIST101") is False
    assert vs.is_atas_required_for_module("") is False


def test_generate_cas_number_format():
    cas = vs.generate_cas_number()
    assert cas.startswith("E4U")
    assert len(cas) == 14


def test_bucket_for_days_left():
    assert vs._bucket_for_days_left(95) is None
    assert vs._bucket_for_days_left(89) == 90
    assert vs._bucket_for_days_left(31) == 60
    assert vs._bucket_for_days_left(14) == 14
    assert vs._bucket_for_days_left(3) == 7


def test_outcome_from_event_type():
    assert vs._outcome_from_event_type("attendance") == "engaged"
    assert vs._outcome_from_event_type("missed") == "missed"
    assert vs._outcome_from_event_type("at_risk") == "partial"
    assert vs._outcome_from_event_type(None) == "engaged"


# --------------------------------------------------------------------------
# Visa records
# --------------------------------------------------------------------------

def test_upsert_and_get_visa_record(temp_db):
    rec = vs.VisaRecord(student_id="STU001", nationality="IN", status="active",
                        visa_expiry_date="2027-01-01")
    row_id = vs.upsert_visa_record(rec)
    assert isinstance(row_id, int)

    got = vs.get_visa_record("STU001")
    assert got["student_id"] == "STU001"
    assert got["nationality"] == "IN"
    assert got["status"] == "active"


def test_upsert_visa_record_updates_existing(temp_db):
    vs.upsert_visa_record(vs.VisaRecord(student_id="STU002", nationality="CN"))
    row_id2 = vs.upsert_visa_record(vs.VisaRecord(student_id="STU002", nationality="US",
                                                  status="active"))
    got = vs.get_visa_record("STU002")
    assert got["nationality"] == "US"
    assert got["status"] == "active"
    # Same row reused (unique student_id) => only one record listed
    assert len(vs.list_visa_records()) == 1


def test_list_expiring_visas(temp_db):
    soon = (date.today() + timedelta(days=30)).isoformat()
    later = (date.today() + timedelta(days=200)).isoformat()
    vs.upsert_visa_record(vs.VisaRecord(student_id="STU_A", status="active",
                                        visa_expiry_date=soon))
    vs.upsert_visa_record(vs.VisaRecord(student_id="STU_B", status="active",
                                        visa_expiry_date=later))
    expiring = vs.list_expiring_visas(within_days=90)
    ids = {r["student_id"] for r in expiring}
    assert "STU_A" in ids
    assert "STU_B" not in ids


# --------------------------------------------------------------------------
# CAS
# --------------------------------------------------------------------------

def test_issue_and_withdraw_cas(temp_db):
    cas = vs.issue_cas("STU003", "MSc CS", "2026-09-01", "2027-09-01",
                       tuition_fee_gbp=20000.0)
    assert cas["status"] == "issued"
    cas_number = cas["cas_number"]

    assert vs.withdraw_cas(cas_number, "student withdrew") is True
    # Second withdrawal is a no-op
    assert vs.withdraw_cas(cas_number, "again") is False

    all_cas = vs.list_cas_for_student("STU003")
    assert all_cas[0]["status"] == "withdrawn"


def test_update_cas_payment(temp_db):
    cas = vs.issue_cas("STU004", "BA", "2026-09-01", "2027-06-01",
                       tuition_fee_gbp=9000.0)
    credited = vs.update_cas_payment("STU004", 3000.0)
    assert credited == cas["cas_number"]
    rows = vs.list_cas_for_student("STU004")
    assert rows[0]["tuition_fee_paid_gbp"] == 3000.0


def test_update_cas_payment_no_cas_returns_none(temp_db):
    assert vs.update_cas_payment("NOBODY", 100.0) is None
    assert vs.update_cas_payment("STU004", 0) is None


# --------------------------------------------------------------------------
# Engagement checks + change of circumstance
# --------------------------------------------------------------------------

def test_record_engagement_check(temp_db):
    rid = vs.record_engagement_check("STU005", term="Term 1", method="attendance")
    assert isinstance(rid, int)
    checks = vs.list_engagement_checks("STU005")
    assert len(checks) == 1
    assert checks[0]["outcome"] == "engaged"


def test_missed_engagement_opens_coc(temp_db):
    vs.record_engagement_check("STU006", term="Term 1", method="attendance",
                               outcome="missed")
    pending = vs.list_pending_coc()
    types = {c["change_type"] for c in pending}
    assert "missed_engagement" in types


def test_log_change_of_circumstance_sets_due_date(temp_db):
    occurred = "2026-01-01"
    coc_id = vs.log_change_of_circumstance("STU007", "withdrawal", occurred_on=occurred)
    pending = vs.list_pending_coc()
    row = [c for c in pending if c["id"] == coc_id][0]
    assert row["ukvi_report_due"] == "2026-01-11"  # +10 days


def test_log_change_of_circumstance_invalid_type(temp_db):
    with pytest.raises(ValueError):
        vs.log_change_of_circumstance("STU008", "not_a_real_type")


def test_mark_coc_reported(temp_db):
    coc_id = vs.log_change_of_circumstance("STU009", "suspension")
    assert vs.mark_coc_reported(coc_id, "UKVI-REF-123") is True
    # No longer pending
    assert all(c["id"] != coc_id for c in vs.list_pending_coc())


# --------------------------------------------------------------------------
# Right to study + ATAS
# --------------------------------------------------------------------------

def test_right_to_study_check(temp_db):
    assert vs.has_passing_right_to_study("STU010") is False
    vs.record_right_to_study_check("STU010", method="in_person",
                                   documents_seen="passport", outcome="pass")
    assert vs.has_passing_right_to_study("STU010") is True


def test_atas_clearance(temp_db):
    assert vs.has_valid_atas("STU011") is False
    vs.record_atas_clearance("STU011", "CIS200", "CERT1",
                             issued_on="2026-01-01", expires_on=None, status="cleared")
    assert vs.has_valid_atas("STU011") is True
    assert vs.has_valid_atas("STU011", module_code="CIS200") is True
