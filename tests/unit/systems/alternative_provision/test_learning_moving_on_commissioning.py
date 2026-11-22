from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.alternative_provision.core import records as r
from education_system.systems.alternative_provision.modules import (
    commissioning,
    learners,
    learning,
    placements,
    reintegration,
)

TODAY = date.today()


def ago(days: int) -> str:
    return (TODAY - timedelta(days=days)).isoformat()



def test_pep_only_for_looked_after(pupil):
    plan = {"learner_id": pupil, "kind": "Personal education plan (PEP)", "targets": "x",
            "review_date": (TODAY + timedelta(days=30)).isoformat()}
    with pytest.raises(r.ValidationError, match="looked-after"):
        r.save(learning.PLANS, plan)
    r.save(learners.LEARNERS, {"looked_after": 1}, record_id=pupil)
    r.save(learning.PLANS, plan)
    with pytest.raises(r.ValidationError, match="four months"):
        r.save(learning.PLANS, {**plan, "review_date": (TODAY + timedelta(days=200)).isoformat()})


def test_baseline_before_progress(pupil):
    check = {"learner_id": pupil, "subject": "English", "result": "Y6"}
    with pytest.raises(r.ValidationError, match="an English baseline first"):
        r.save(learning.PROGRESS, {**check, "kind": "Progress check"})
    r.save(learning.PROGRESS, {**check, "kind": "Baseline", "assessed_on": ago(10)})
    with pytest.raises(r.ValidationError, match="already an English baseline"):
        r.save(learning.PROGRESS, {**check, "kind": "Baseline"})
    r.save(learning.PROGRESS, {**check, "kind": "Progress check"})


def test_achieved_qualification_needs_result(pupil):
    with pytest.raises(r.ValidationError, match="result"):
        r.save(learning.QUALIFICATIONS_RT, {"learner_id": pupil, "qualification": "GCSE",
                                            "subject": "Maths", "status": "Achieved"})


def test_invoice_works_out_days_and_amount(pupil, placement):
    inv = r.save(commissioning.INVOICES, {"placement_id": placement, "period_from": ago(14),
                                          "period_to": ago(1)})
    row = r.get(commissioning.INVOICES, inv)
    assert row["invoice_no"] == "INV00001" and row["days"] == 10
    assert row["amount"] == 1200 and row["commissioner"] == "Oak High"
    assert row["learner_id"] == pupil
    with pytest.raises(r.ValidationError, match="overlaps"):
        r.save(commissioning.INVOICES, {"placement_id": placement, "period_from": ago(3),
                                        "period_to": ago(1)})
    with pytest.raises(r.ValidationError, match="inside the placement"):
        r.save(commissioning.INVOICES, {"placement_id": placement, "period_from": ago(40),
                                        "period_to": ago(30)})


def test_completed_reintegration_ends_placements(pupil, placement):
    with pytest.raises(r.ValidationError, match="phased return starts"):
        r.save(reintegration.REINTEGRATION, {"learner_id": pupil, "target_school": "Oak",
                                             "status": "Phased return"})
    plan = r.save(reintegration.REINTEGRATION, {"learner_id": pupil, "target_school": "Oak",
                                                "status": "Phased return",
                                                "phased_start": ago(10)})
    with pytest.raises(r.ValidationError, match="open reintegration plan"):
        r.save(reintegration.REINTEGRATION, {"learner_id": pupil, "target_school": "Elm"})
    r.save(reintegration.REINTEGRATION, {"status": "Completed", "full_return": ago(1)},
           record_id=plan)
    who = r.get(learners.LEARNERS, pupil)
    assert (who["status"], who["leave_date"]) == ("Reintegrated", ago(1))
    ended = r.get(placements.PLACEMENTS, placement)
    assert (ended["status"], ended["end_reason"]) == ("Ended", "Reintegrated to mainstream")
    assert "6-week" in reintegration._follow_flag(r.get(reintegration.REINTEGRATION, plan))
