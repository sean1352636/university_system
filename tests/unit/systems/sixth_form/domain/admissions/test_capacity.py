"""Programme places, CapacityFull on offers, ranking and feeder rules."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
    applicant_details as det,
    capacity,
)

CYCLE = "2031/32"
MATHS = ("A Level", "Mathematics")


def _app(applicant_payload, first, days_ago=0, **kw):
    when = (dt.date.today() - dt.timedelta(days=days_ago)).isoformat()
    return adm.create_applicant(
        applicant_payload(first_name=first, email=f"{first.lower()}@example.com",
                          submitted_at=when, intake_year=CYCLE, **kw),
        allow_duplicate=True)


def test_places_and_capacity_full(admdb, sign_in, applicant_payload):
    sign_in()
    a = _app(applicant_payload, "Ann")
    b = _app(applicant_payload, "Ben")
    capacity.set_places(CYCLE, MATHS, 1)
    assert capacity.places_left(CYCLE, MATHS) == 1
    adm.make_offer(a.applicant_id)
    assert capacity.places_left(CYCLE, "A Level: Mathematics") == 0
    assert capacity.check_offer_capacity(a.applicant_id) == []   # own place
    assert capacity.check_offer_capacity(b.applicant_id) == ["A Level Mathematics"]
    with pytest.raises(capacity.CapacityFull) as exc:
        adm.make_offer(b.applicant_id)
    assert isinstance(exc.value, adm.ValidationError)
    assert adm.get_applicant(b.applicant_id).status == "Submitted"
    adm.make_offer(b.applicant_id, override_capacity=True)
    assert any("Capacity override" in e.detail
               for e in adm.list_events(b.applicant_id))


def test_unlimited_when_no_places_set(admdb, sign_in, applicant_payload):
    sign_in()
    a = _app(applicant_payload, "Ann")
    assert capacity.places_left(CYCLE, MATHS) is None
    assert capacity.check_offer_capacity(a.applicant_id) == []


def test_waitlist_if_full(admdb, sign_in, applicant_payload):
    sign_in()
    a = _app(applicant_payload, "Ann")
    b = _app(applicant_payload, "Ben")
    capacity.set_places(CYCLE, MATHS, 1)
    adm.make_offer(a.applicant_id)
    assert capacity.waitlist_if_full(b.applicant_id) == ["A Level Mathematics"]
    w = adm.get_applicant(b.applicant_id)
    assert w.status == "Waitlisted" and w.waitlist_rank == 1
    assert w.decision_reason == "Capacity reached"


def test_rank_by_criteria_then_date(admdb, sign_in, applicant_payload):
    sign_in()
    capacity.add_feeder_school("Partner High", guaranteed_place_scheme=False)
    early = _app(applicant_payload, "Early", days_ago=9)
    feeder = _app(applicant_payload, "Feeder", days_ago=1,
                  previous_school="partner  high")
    lac = _app(applicant_payload, "Lac", days_ago=2)
    det.update_profile(lac.applicant_id, looked_after=True)
    ranked = capacity.rank_applicants(CYCLE, MATHS)
    assert [r.applicant_id for r in ranked] == [
        lac.applicant_id, feeder.applicant_id, early.applicant_id]
    assert "Looked after" in ranked[0].reasons
    # Reorder: feeder school first.
    capacity.set_criteria_order(["feeder_school"])
    ranked = capacity.rank_applicants(CYCLE, MATHS)
    assert ranked[0].applicant_id == feeder.applicant_id
    capacity.set_criterion_enabled("feeder_school", False)
    ranked = capacity.rank_applicants(CYCLE, MATHS)
    assert ranked[0].applicant_id == lac.applicant_id


def test_distance_cannot_be_enabled(admdb, sign_in):
    sign_in()
    dist = next(c for c in capacity.list_criteria() if c.key == "distance")
    assert not dist.enabled and not dist.available
    with pytest.raises(adm.ValidationError):
        capacity.set_criterion_enabled("distance", True)


def test_apply_feeder_rules(admdb, sign_in, applicant_payload):
    sign_in()
    capacity.add_feeder_school("Scheme School", guaranteed_place_scheme=True)
    capacity.add_feeder_school("Plain School")
    a = _app(applicant_payload, "Ann", previous_school="Scheme School")
    b = _app(applicant_payload, "Ben", previous_school="Plain School")
    assert capacity.apply_feeder_rules(a.applicant_id) is True
    assert adm.get_applicant(a.applicant_id).guaranteed_place
    assert capacity.apply_feeder_rules(b.applicant_id) is False
    assert not adm.get_applicant(b.applicant_id).guaranteed_place
    with pytest.raises(adm.ValidationError):
        capacity.add_feeder_school("scheme school")


def test_places_need_admissions(admdb, sign_in):
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    sign_in("t1", capabilities={"teaching"})
    with pytest.raises(access.AccessDenied):
        capacity.set_places(CYCLE, MATHS, 5)
