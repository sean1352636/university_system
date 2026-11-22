"""The applicant's old reference_status follows the reference tracker."""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
)
from education_system.systems.sixth_form.domain.admissions import (
    references as refs,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)


@pytest.fixture
def applicant(admdb, sign_in, applicant_payload):
    sign_in("adm1")
    return adm.create_applicant(applicant_payload())


def test_hand_set_status_works_without_tracker(applicant):
    out = adm.set_reference_status(applicant.applicant_id, "Received")
    assert out.reference_status == "Received"
    assert refs.tracker_status(applicant.applicant_id) is None


def test_status_follows_tracker(applicant):
    aid = applicant.applicant_id
    r = refs.request_reference(aid, referee_name="Ms T",
                               referee_email="t@example.com")
    assert adm.get_applicant(aid).reference_status == "Requested"
    refs.record_received(r.reference_id, behaviour="Good")
    assert adm.get_applicant(aid).reference_status == "Received"
    with pytest.raises(adm.ValidationError, match="tracked"):
        adm.set_reference_status(aid, "Not requested")
    # Agreeing with the tracker is still allowed.
    assert adm.set_reference_status(aid, "Received").reference_status \
        == "Received"


def test_cancel_and_decline(applicant):
    aid = applicant.applicant_id
    r = refs.request_reference(aid, referee_name="Ms T",
                               referee_phone="07700 900333")
    refs.decline(r.reference_id)
    assert adm.get_applicant(aid).reference_status == "Declined"
    r2 = refs.request_reference(aid, referee_name="Mr U",
                                referee_phone="07700 900444")
    assert adm.get_applicant(aid).reference_status == "Requested"
    refs.cancel(r2.reference_id)
    assert adm.get_applicant(aid).reference_status == "Declined"


def test_sync_repairs_drift(applicant):
    aid = applicant.applicant_id
    refs.request_reference(aid, referee_name="Ms T",
                           referee_phone="07700 900333")
    with adm._connect() as conn:
        conn.execute("UPDATE admissions_applicants SET reference_status = "
                     "'Not requested' WHERE applicant_id = ?", (aid,))
        conn.commit()
    assert refs.sync_reference_status() == 1
    assert adm.get_applicant(aid).reference_status == "Requested"


def test_writes_need_admissions(applicant, sign_in):
    sign_in("t1", capabilities={access.TEACHING})
    with pytest.raises(access.AccessDenied):
        refs.request_reference(applicant.applicant_id, referee_name="X",
                               referee_phone="07700 900555")
