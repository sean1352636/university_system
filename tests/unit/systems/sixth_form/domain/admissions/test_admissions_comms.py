"""admissions_comms: applicant/referee mail goes through the messages
outbox (faked by the ``outbox`` fixture), is linked and logged."""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
)
from education_system.systems.sixth_form.domain.admissions import (
    admissions_comms as comms,
)
from education_system.systems.sixth_form.domain.admissions import (
    applicant_details as det,
)
from education_system.systems.sixth_form.domain.admissions import (
    references as refs,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)


@pytest.fixture
def applicant(admdb, outbox, sign_in, applicant_payload):
    sign_in("adm1")
    return adm.create_applicant(applicant_payload())


def test_send_to_applicant_queues_links_and_logs(applicant, outbox):
    out = comms.send_to_applicant(applicant.applicant_id, "Hello", "Body text")
    assert len(out) == 1 and len(outbox) == 1
    m = outbox[0]
    assert m.to_address == "zed.t@example.com"
    assert m.category == comms.CATEGORY and m.channel == "Email"
    assert out[0].label == "Queued (held by delivery mode)"
    log = comms.communications_log(applicant.applicant_id)
    assert [r["message_id"] for r in log] == [m.message_id]
    assert log[0]["kind"] == "custom" and log[0]["sent_by"] == "adm1"
    events = [e.detail for e in adm.list_events(applicant.applicant_id)]
    assert any("zed.t@example.com" in d and "held by delivery mode" in d
               for d in events)


def test_parents_get_copies_only_when_asked(applicant, outbox):
    det.add_contact(applicant.applicant_id, {
        "name": "Pat Testerson", "relationship": "Mother",
        "email": "pat@example.com"})
    comms.send_to_applicant(applicant.applicant_id, "S", "B")
    assert [m.to_address for m in outbox] == ["zed.t@example.com"]
    out = comms.send_to_applicant(applicant.applicant_id, "S", "B",
                                  include_parents=True)
    assert [q.recipient_role for q in out] == ["applicant", "parent"]
    assert outbox[-1].to_address == "pat@example.com"
    assert outbox[-1].subject.startswith("Copy: ")


def test_requires_admissions_capability(applicant, sign_in):
    sign_in("t1", capabilities={access.TEACHING})
    with pytest.raises(access.AccessDenied):
        comms.send_status_email(applicant.applicant_id)


def test_offer_letter_needs_offer(applicant, outbox):
    with pytest.raises(adm.ValidationError):
        comms.send_offer_letter(applicant.applicant_id)
    adm.make_offer(applicant.applicant_id, conditions="6 in Maths")
    out = comms.send_offer_letter(applicant.applicant_id)
    assert "6 in Maths" in outbox[-1].body
    assert out[0].kind == "offer-letter"


def test_interview_invite_includes_calendar(applicant, outbox):
    adm.schedule_interview(applicant.applicant_id,
                           interview_date=(_dt.date.today()
                                           + _dt.timedelta(days=5)).isoformat())
    comms.send_interview_invite(applicant.applicant_id)
    assert "BEGIN:VCALENDAR" in outbox[-1].body
    assert "interview.ics" in (outbox[-1].attachments_note or "")


def test_expiry_warnings_not_repeated(applicant, outbox):
    adm.make_offer(applicant.applicant_id)
    adm.set_offer_expiry(applicant.applicant_id,
                         (_dt.date.today() + _dt.timedelta(days=2)).isoformat())
    first = comms.send_expiry_warnings()
    again = comms.send_expiry_warnings()
    assert first["sent"] == [applicant.applicant_id]
    assert again["skipped"] == [applicant.applicant_id] and not again["sent"]


def test_referee_without_email_refused(applicant, outbox):
    r = refs.request_reference(applicant.applicant_id, referee_name="Mr P",
                               referee_phone="07700 900222")
    with pytest.raises(adm.ValidationError, match="no e-mail address"):
        comms.send_reference_request(r.reference_id)
    assert outbox == []


def test_reference_request_and_chase_update_tracker(applicant, outbox):
    r = refs.request_reference(applicant.applicant_id, referee_name="Mr R",
                               referee_email="ref@example.com", send=True)
    assert r.status == "Sent" and r.due_date
    assert outbox[-1].to_address == "ref@example.com"
    r = refs.chase(r.reference_id, send=True)
    assert r.status == "Chased" and r.chase_count == 1
    assert outbox[-1].subject.startswith("Reminder")
    kinds = [x["kind"] for x in comms.communications_log(
        applicant.applicant_id)]
    assert kinds == ["reference-chase", "reference-request"]
