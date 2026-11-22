"""Admissions cycles: CRUD, open cycle, results-day cycle, re-application."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
    applicant_details as det,
    cycles,
    entry_requirements as er,
    gcse_results_day as grd,
)

TODAY = dt.date.today()


def _open_cycle(name="2031/32", **kw):
    fields = dict(opens_on=(TODAY - dt.timedelta(days=10)).isoformat(),
                  closes_on=(TODAY + dt.timedelta(days=30)).isoformat())
    fields.update(kw)
    cycles.create_cycle(name, **fields)
    return cycles.set_cycle_status(name, "Open")


def test_create_validates_and_opens(admdb, sign_in):
    sign_in()
    with pytest.raises(adm.ValidationError):
        cycles.create_cycle("2031/33", opens_on="2030-01-01",
                            closes_on="2030-02-01")
    with pytest.raises(adm.ValidationError):
        cycles.create_cycle("2031/32", opens_on="2030-02-01",
                            closes_on="2030-01-01")
    c = cycles.create_cycle("2031/32", opens_on=TODAY.isoformat(),
                            closes_on=TODAY.isoformat())
    assert c.status == "Planned" and c.offer_response_days == 14
    assert cycles.open_cycle_for(TODAY) is None
    cycles.set_cycle_status("2031/32", "Open")
    assert cycles.open_cycle_for(TODAY) == "2031/32"
    assert adm.default_intake_year() == "2031/32"
    with pytest.raises(adm.ValidationError):
        cycles.set_cycle_status("2031/32", "Planned")


def test_overlapping_open_cycles_refused(admdb, sign_in):
    sign_in()
    _open_cycle("2031/32")
    cycles.create_cycle("2032/33", opens_on=TODAY.isoformat(),
                        closes_on=(TODAY + dt.timedelta(days=5)).isoformat())
    with pytest.raises(adm.ValidationError):
        cycles.set_cycle_status("2032/33", "Open")


def test_open_cycle_for_needs_no_table(admdb, sign_in):
    sign_in()
    adm.init_db()
    assert cycles.open_cycle_for(TODAY) is None


def test_create_requires_admissions(admdb, sign_in):
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    sign_in("t1", capabilities={"teaching"})
    with pytest.raises(access.AccessDenied):
        cycles.create_cycle("2031/32", opens_on="2030-01-01",
                            closes_on="2030-02-01")


def test_results_day_cycle_preferred(admdb, sign_in):
    sign_in()
    cycles.create_cycle("2040/41", opens_on="2039-09-01",
                        closes_on="2040-01-31", results_day="2040-08-20")
    assert grd.current_cycle(dt.date(2040, 8, 20)) == "2040/41"
    # No configured results day that summer: the old rule.
    assert grd.current_cycle(dt.date(2041, 8, 20)) == "2041/42"


def test_new_application_uses_open_cycle_and_offer_expiry(
        admdb, sign_in, applicant_payload):
    sign_in()
    _open_cycle(offer_response_days=10)
    a = adm.create_applicant(applicant_payload())
    assert a.intake_year == "2031/32"
    o = adm.make_offer(a.applicant_id)
    assert o.offer_expiry == (TODAY + dt.timedelta(days=10)).isoformat()


def test_reapply_copies_and_links(admdb, sign_in, applicant_payload):
    sign_in()
    _open_cycle()
    cycles.create_cycle("2032/33", opens_on=(TODAY + dt.timedelta(days=60)).isoformat(),
                        closes_on=(TODAY + dt.timedelta(days=90)).isoformat())
    a = adm.create_applicant(applicant_payload())
    det.add_contact(a.applicant_id, {"name": "Pat Testerson",
                                     "relationship": "Mother",
                                     "phone": "07700 900456"})
    det.update_profile(a.applicant_id, young_carer=True)
    er.record_gcse(a.applicant_id, "Mathematics", "7", result_type="Predicted")
    with pytest.raises(adm.ValidationError):
        cycles.reapply(a.applicant_id, "2032/33")      # still open
    adm.reject(a.applicant_id)
    with pytest.raises(adm.ValidationError):
        cycles.reapply(a.applicant_id, "2031/32")      # not a later cycle
    n = cycles.reapply(a.applicant_id, "2032/33")
    assert n.status == "Submitted" and n.intake_year == "2032/33"
    assert n.young_carer
    assert cycles.reapplied_from(n.applicant_id) == a.applicant_id
    assert cycles.reapplications_of(a.applicant_id) == [n.applicant_id]
    assert len(det.list_contacts(n.applicant_id)) == 1
    assert [g.subject for g in er.list_gcses(n.applicant_id)] == ["Mathematics"]
    assert any("Re-applied" in e.detail for e in adm.list_events(a.applicant_id))
    with pytest.raises(adm.ValidationError):
        cycles.reapply(a.applicant_id, "2032/33")      # one per cycle
    rep = cycles.rollover_report("2031/32", "2032/33")
    assert rep.reapplied == [(a.applicant_id, n.applicant_id)]
    assert rep.by_status == {"Rejected": 1}


def test_duplicate_applications_in_cycle(admdb, sign_in, applicant_payload):
    sign_in()
    _open_cycle()
    adm.create_applicant(applicant_payload())
    adm.create_applicant(applicant_payload(email="other@example.com"),
                         allow_duplicate=True)
    groups = cycles.duplicate_applications("2031/32")
    assert len(groups) == 1 and len(groups[0]) == 2


def test_lapse_and_warning(admdb, sign_in, applicant_payload):
    sign_in()
    a = adm.create_applicant(applicant_payload())
    b = adm.create_applicant(applicant_payload(email="b@example.com",
                                               first_name="Bea"),
                             allow_duplicate=True)
    adm.make_offer(a.applicant_id)
    adm.make_offer(b.applicant_id)
    adm.set_offer_expiry(a.applicant_id, (TODAY - dt.timedelta(days=1)).isoformat())
    adm.set_offer_expiry(b.applicant_id, (TODAY + dt.timedelta(days=2)).isoformat())
    assert [x.applicant_id for x in cycles.offers_needing_warning()] == [b.applicant_id]
    cycles.record_warning_sent(b.applicant_id, adm.get_applicant(b.applicant_id).offer_expiry)
    assert cycles.offers_needing_warning() == []
    done, errors = cycles.lapse_expired_offers()
    assert done == [a.applicant_id] and not errors
    lapsed = adm.get_applicant(a.applicant_id)
    assert lapsed.status == "Withdrawn"
    assert lapsed.withdrawal_reason == cycles.LAPSE_REASON
