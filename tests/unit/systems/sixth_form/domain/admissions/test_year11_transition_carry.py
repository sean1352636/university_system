"""CTF contacts, gender and SEN reach the matched applicant; SEN detail
stays in the SEND-only area even when the person applying lacks SEND."""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
    applicant_details as det,
    year11_transition as y11,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.domain.operations.integrations import (
    ctf,
)


def _pupil():
    return ctf.CTFPupil(
        index=0, upn=None, uln=None, uci=None, surname="Testerson",
        forename="Zed", middle_names=None, preferred_surname=None,
        preferred_forename=None, dob="2010-03-04", gender_code="M",
        address=None,
        contacts=[ctf.CTFContact(order=1, title=None, surname="Testerson",
                                 forename="Sam", relationship_code="PAF",
                                 responsibility=True,
                                 phones=[("H", "07700900222")], email=None,
                                 address=None)],
        sen=[ctf.CTFSen(start_date="2019-09-01", provision="E",
                        needs=["SpLD"])])


@pytest.fixture
def applicant(admdb, sign_in, applicant_payload):
    sign_in("adm1")
    return adm.create_applicant(applicant_payload())


def _result():
    return y11.TransitionResult(preview=None, updated=[], results_recorded=0,
                                notes=[])


def test_contacts_carried_once(applicant):
    res = _result()
    assert y11._carry_contacts(applicant, _pupil(), res.notes) == 1
    assert y11._carry_contacts(applicant, _pupil(), res.notes) == 0
    c = det.list_contacts(applicant.applicant_id)[0]
    assert (c.name, c.relationship, c.is_emergency) == ("Sam Testerson",
                                                        "Father", True)


def test_sen_for_senco_when_user_lacks_send(applicant, admdb, sign_in):
    res = _result()
    y11._carry_sen(applicant, _pupil(), "f.xml", "Feeder High", res)
    assert res.sen_for_senco == [applicant.applicant_id]
    got = adm.get_applicant(applicant.applicant_id)
    assert got.lldd and got.ehcp
    view = det.get_sensitive(applicant.applicant_id)
    assert view.held["send"] and "send" not in view.visible
    assert any(e.detail == y11.SENCO_NOTE
               for e in adm.list_events(applicant.applicant_id))
    sign_in("senco", capabilities={access.SEND})
    assert "SpLD" in det.get_sensitive(applicant.applicant_id).visible["send"]
    # applying the same file again adds nothing
    sign_in("adm1")
    again = _result()
    y11._carry_sen(adm.get_applicant(applicant.applicant_id), _pupil(),
                   "f.xml", "Feeder High", again)
    assert again.sen_for_senco == []


def test_sen_written_directly_with_send(applicant, sign_in):
    sign_in("adm1", capabilities={access.ADMISSIONS, access.SEND})
    res = _result()
    y11._carry_sen(applicant, _pupil(), "f.xml", None, res)
    assert res.sen_recorded == [applicant.applicant_id]
