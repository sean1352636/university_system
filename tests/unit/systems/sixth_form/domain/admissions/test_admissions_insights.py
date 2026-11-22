"""Conversion, time-in-stage, reasons and capacity reports."""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
    admissions_insights as ins,
    capacity,
)

CYCLE = "2031/32"


def _app(applicant_payload, first, **kw):
    return adm.create_applicant(
        applicant_payload(first_name=first, email=f"{first.lower()}@example.com",
                          intake_year=CYCLE, **kw), allow_duplicate=True)


def test_offered_then_withdrawn_still_counts_as_offered(
        admdb, sign_in, applicant_payload):
    sign_in()
    capacity.add_feeder_school("Partner High")
    a = _app(applicant_payload, "Ann", previous_school="partner high")
    b = _app(applicant_payload, "Ben")
    adm.make_offer(a.applicant_id)
    adm.withdraw(a.applicant_id, reason="Moved away")
    adm.reject(b.applicant_id)
    tot = ins.conversion_totals(cycle=CYCLE)
    assert (tot.applied, tot.offered, tot.accepted) == (2, 1, 0)
    by_school = {r.group: r for r in ins.conversion_by("feeder_school", cycle=CYCLE)}
    assert by_school["Partner High"].offered == 1
    assert by_school["Partner High"].is_feeder is True
    assert ins.conversion_by("programme", cycle=CYCLE)[0].group == "A Level Mathematics"
    with pytest.raises(adm.ValidationError):
        ins.conversion_by("colour")
    reasons = ins.reasons_breakdown(cycle=CYCLE)
    assert reasons.withdrawn == {"Moved away": 1}
    assert reasons.rejected == {"(no reason recorded)": 1}
    assert "Moved away" in ins.to_csv(reasons.rows())


def test_time_in_stage_and_capacity(admdb, sign_in, applicant_payload):
    sign_in()
    a = _app(applicant_payload, "Ann")
    adm.make_offer(a.applicant_id)
    stages = {s.stage: s for s in ins.time_in_stage(cycle=CYCLE)}
    assert stages["Submitted"].applicants == 1
    assert stages["Offer Made"].current == 1
    capacity.set_places(CYCLE, ("A Level", "Mathematics"), 3)
    row = ins.offers_vs_capacity(CYCLE)[0]
    assert (row.places, row.offers_made, row.places_left) == (3, 1, 2)


def test_reports_capability(admdb, sign_in):
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    sign_in("t1", capabilities={"teaching"})
    with pytest.raises(access.AccessDenied):
        ins.conversion_totals()
    sign_in("r1", capabilities={"reports"})
    assert ins.conversion_totals().applied == 0
