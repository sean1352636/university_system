"""ILR learning delivery, condition of funding, fees and enrolment reports."""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.academics.qualifications import (
    learning_aims as la,
)
from education_system.systems.sixth_form.domain.academics.qualifications import (
    prior_attainment as pa,
)
from education_system.systems.sixth_form.domain.admissions.enrolments import (
    enrolment_reports as rep,
)
from education_system.systems.sixth_form.domain.admissions.enrolments import (
    enrolments as en,
)
from education_system.systems.sixth_form.domain.admissions.enrolments import (
    funding,
    ilr,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students,
)

YEAR = "2025/26"
START = "2025-09-03"


@pytest.fixture
def staff(admdb, sign_in, monkeypatch):
    """Enrolment writer + finance, with the fees tables on the temp DB."""
    from education_system.systems.sixth_form.domains.finance.domain.fees import (
        fee_rules,
        fees,
    )
    monkeypatch.setattr(fees, "DB_PATH", admdb["path"])
    monkeypatch.setattr(fees, "_DB_READY", False)
    monkeypatch.setattr(fee_rules, "DB_PATH", None)
    monkeypatch.setattr(fee_rules, "_READY", set())
    return sign_in("enr1", capabilities={access.STUDENTS_MANAGE,
                                         access.FINANCE})


def _student(first="Ava", dob="2009-05-06"):
    return students.create_student(
        {"first_name": first, "last_name": "Ilr", "date_of_birth": dob,
         "status": "Active"}, allow_duplicate=True).student_id


def _enrol(sid, **over):
    return en.create_enrolment({"student_id": sid, "academic_year": YEAR,
                                "year_group": 12, "tutor_group": "12A",
                                "start_date": START, **over})


def _a_level(sid, hours=180, code="60118007"):
    return la.add_aim(sid, {"qualification_type": "A Level",
                            "subject": "Mathematics", "start_date": START,
                            "planned_end_date": "2027-06-30",
                            "planned_hours": hours, "aim_code": code})


def test_ilr_defaults_are_derived_and_overrides_validated(staff):
    sid = _student()
    e = _enrol(sid)
    _a_level(sid)
    rec = ilr.get_ilr(e.enrolment_id)
    assert rec.fee_status == ilr.FEE_16_19 and rec.fee_status_source == "derived"
    assert rec.fund_model == 25
    assert rec.plan_learn_hours == 180 and rec.plan_learn_hours_source == "derived"
    assert rec.mode == ilr.PART_TIME and rec.funding_band == "Band 1"
    rec = ilr.set_ilr(e.enrolment_id, {"plan_learn_hours": 560,
                                       "plan_eep_hours": 60})
    assert rec.total_hours == 620 and rec.mode == ilr.FULL_TIME
    assert rec.funding_band == "Band 5"
    with pytest.raises(en.ValidationError, match="funding model 99"):
        ilr.set_ilr(e.enrolment_id, {"fee_status": ilr.FEE_OVERSEAS,
                                     "fund_model": 25})
    with pytest.raises(en.ValidationError, match="EDU code"):
        ilr.set_ilr(e.enrolment_id, {"destination_type": "EDU",
                                     "destination_code": 9})
    # clearing a recorded value brings the derived one back
    rec = ilr.set_ilr(e.enrolment_id, {"plan_learn_hours": None})
    assert rec.plan_learn_hours == 180
    assert any(h["action"] == "ILR updated"
               for h in en.enrolment_history(enrolment_id=e.enrolment_id))


def test_ilr_writes_are_gated(staff, sign_in, admdb):
    e = _enrol(_student())
    sign_in("t1", capabilities={access.STUDENTS_VIEW})
    with pytest.raises(access.AccessDenied):
        ilr.set_ilr(e.enrolment_id, {"notes": "x"})
    with pytest.raises(access.AccessDenied):
        ilr.export_csv(YEAR)
    # the refusal is logged on the one export path
    assert ("t1", "ilr", "export ILR", {"allowed": False}) in admdb["sensitive_log"]
    assert ilr.get_ilr(e.enrolment_id).fund_model == 25  # reads open


def test_early_leaver_and_outcomes(staff):
    early, later = _student("Ben"), _student("Cat")
    e1, e2 = _enrol(early), _enrol(later)
    _a_level(early)
    _a_level(later)
    en.withdraw_enrolment(e1.enrolment_id, withdrawal_date="2025-09-20",
                          reason="44")
    en.withdraw_enrolment(e2.enrolment_id, withdrawal_date="2025-11-20",
                          reason="2")
    rows = ilr.early_leavers(YEAR)
    assert [r.student_id for r in rows] == [early]
    assert rows[0].days_in_learning == 18
    rec = ilr.get_ilr(e1.enrolment_id)
    assert rec.early_leaver and not rec.funded
    aim = ilr.get_ilr(e2.enrolment_id).aims[0]
    assert (aim.comp_status, aim.outcome, aim.withdraw_reason) == (3, 3, "2")
    with pytest.raises(en.ValidationError, match="2 or 3"):
        ilr.set_aim_outcome(aim.aim_id, 1)
    assert ilr.set_aim_outcome(aim.aim_id, 2).outcome == 2
    assert ilr.get_ilr(e2.enrolment_id).aims[0].outcome_source == "recorded"


def test_outcome_refused_on_a_continuing_aim(staff):
    sid = _student()
    _enrol(sid)
    aim = _a_level(sid)
    with pytest.raises(en.ValidationError, match="still continuing"):
        ilr.set_aim_outcome(aim.aim_id, 1)


def test_export_lists_problems(staff, ilr_export_dbs, tmp_path):
    sid = _student()
    e = _enrol(sid)
    _a_level(sid, code=None)
    out = tmp_path / "ilr.csv"
    res = ilr.export_csv(YEAR, path=out)
    assert res.learners == 1 and res.deliveries == 1
    assert out.read_text().startswith("RecordType,")
    fields = {p.field for p in res.problems}
    assert {"ULN", "LearnAimRef"} <= fields
    assert all(p.student_id == sid and p.enrolment_id == e.enrolment_id
               for p in res.problems)
    assert {p.severity for p in res.problems} <= {"Error", "Warning", "Info"}
    # ilr.export_csv is the census_ilr export, not a second one
    assert isinstance(res, ilr.ExportResult)
    assert ("enr1", "ilr", "export ILR", {}) in ilr_export_dbs["sensitive_log"]


def test_condition_of_funding_gaps_and_apply(staff):
    sid = _student()
    e = _enrol(sid)
    pa.add_result(sid, {"subject": "English Language", "grade": "3"})
    pa.add_result(sid, {"subject": "Mathematics", "grade": "6"})
    gaps = funding.condition_of_funding_gaps(e.enrolment_id)
    assert [(g.area, g.requirement) for g in gaps] == [("English", "GCSE")]
    bad = funding.apply_condition_of_funding(
        e.enrolment_id, qualification_types={"English": "Functional Skills"})
    assert not bad.created and "GCSE" in bad.problems[0]
    res = funding.apply_condition_of_funding(e.enrolment_id)
    assert [a.label for a in res.created] == ["GCSE English Language"]
    assert res.created[0].start_date == START
    assert res.created[0].planned_end_date == en.academic_year_dates(YEAR)[1]
    assert funding.condition_of_funding_gaps(e.enrolment_id) == []
    assert funding.cof_report(YEAR, only_gaps=True) == []


def test_condition_of_funding_does_not_apply_to_full_cost(staff):
    e = _enrol(_student(dob="2004-01-01"))
    assert ilr.get_ilr(e.enrolment_id).fee_status is None  # staff decide
    ilr.set_ilr(e.enrolment_id, {"fee_status": ilr.FEE_FULL_COST})
    pos = funding.cof_position(e.enrolment_id)
    assert not pos.applies and pos.compliant


HOME = "Home (UK national, resident 3+ years)"


def _fee_rules():
    from education_system.systems.sixth_form.domains.finance.domain.fees import (
        fee_rules,
    )
    return fee_rules


def test_fee_statuses_match_finance_rule_statuses():
    assert set(_fee_rules().FEE_STATUSES) == set(ilr.FEE_PAYING)


def test_fee_due_raise_and_cancel_through_finance(staff):
    from education_system.systems.sixth_form.domains.finance.domain.fees import (
        fees,
    )
    fr = _fee_rules()
    sid = _student(dob="2004-01-01")
    e = _enrol(sid)
    ilr.set_ilr(e.enrolment_id, {"fee_status": ilr.FEE_FULL_COST})
    assert "residency" in " ".join(funding.fee_due(e.enrolment_id).problems)
    fr.set_profile(sid, residency_category=HOME, by="enr1")
    assert "No fee rule" in " ".join(funding.fee_due(e.enrolment_id).problems)
    with pytest.raises(fr.ValidationError):
        fr.create_rule({"age_band": fr.AGE_19_PLUS, "annual_fee": 100,
                        "fee_status": ilr.FEE_16_19})
    # A general 19+ home rule that charges nothing is flagged, not used.
    fr.create_rule({"age_band": fr.AGE_19_PLUS, "residency_category": HOME,
                    "annual_fee": 0})
    assert "add a fee rule for fee status" in " ".join(
        funding.fee_due(e.enrolment_id).problems)
    rule = fr.create_rule({"academic_year": YEAR, "age_band": fr.AGE_19_PLUS,
                           "fee_status": ilr.FEE_FULL_COST, "annual_fee": 3500})
    due = funding.fee_due(e.enrolment_id)
    assert not due.problems and due.rule.rule_id == rule.rule_id
    assert (due.age_band, due.net_fee, due.to_raise) == (fr.AGE_19_PLUS, 3500.0, 3500.0)
    inv = funding.raise_fee(e.enrolment_id)
    assert inv.fee_status == ilr.FEE_FULL_COST and inv.net_fee == 3500.0
    item = fees.get_item(inv.fee_id)
    assert item.category == "Tuition" and item.amount == 3500.0
    assert [c.invoice_id for c in funding.list_charges(e.enrolment_id)] == [inv.invoice_id]
    due = funding.fee_due(e.enrolment_id)
    assert (due.already_raised, due.to_raise) == (3500.0, 0.0)
    with pytest.raises(en.ValidationError, match="No tuition fee left"):
        funding.raise_fee(e.enrolment_id)
    funding.cancel_fee_charge(inv.invoice_id, reason="wrong status")
    assert fees.get_item(inv.fee_id).stored_status == "Cancelled"
    assert funding.fee_due(e.enrolment_id).to_raise == 3500.0
    # Finance's own calculation (no fee status) ignores status-only rules.
    assert fr.calculate_fee(sid, YEAR).gross_fee == 0.0


def test_co_funded_needs_its_own_rule_and_takes_remissions(staff):
    fr = _fee_rules()
    sid = _student(dob="2003-03-03")
    e = _enrol(sid)
    ilr.set_ilr(e.enrolment_id, {"fee_status": ilr.FEE_19_CO})
    fr.set_profile(sid, residency_category=HOME, by="enr1")
    fr.create_rule({"age_band": fr.AGE_19_PLUS, "annual_fee": 3500})
    assert "pays a share" in " ".join(funding.fee_due(e.enrolment_id).problems)
    fr.create_rule({"age_band": fr.AGE_19_PLUS, "fee_status": ilr.FEE_19_CO,
                    "annual_fee": 1750})
    fr.add_remission({"student_id": sid, "academic_year": YEAR,
                      "remission_type": "Percentage", "value": 50,
                      "reason": "Low income / benefits", "approved_by": "enr1"})
    due = funding.fee_due(e.enrolment_id)
    assert not due.problems
    assert (due.gross_fee, due.remission_amount, due.net_fee) == (1750.0, 875.0, 875.0)


def test_funded_statuses_owe_nothing(staff):
    e = _enrol(_student(dob="2004-01-01"))
    ilr.set_ilr(e.enrolment_id, {"fee_status": ilr.FEE_19_FULL})
    due = funding.fee_due(e.enrolment_id)
    assert not due.fee_paying and not due.problems
    assert (due.net_fee, due.to_raise) == (0.0, 0.0)


def test_targets_and_withdrawal_analytics(staff):
    a, b, c = _student("A"), _student("B"), _student("C")
    for sid in (a, b, c):
        _enrol(sid)
        _a_level(sid)
    rep.set_target(YEAR, 12, 4)
    rep.set_target(YEAR, 12, 2, programme="A Level", subject="Mathematics")
    rows = {(r.programme, r.subject): r for r in rep.targets_vs_actuals(YEAR)}
    assert rows[(None, None)].actual == 3 and rows[(None, None)].variance == -1
    assert rows[("A Level", "Mathematics")].actual == 3
    en.withdraw_enrolment(en.list_for_student(a)[0].enrolment_id,
                          withdrawal_date="2025-09-10", reason="44")
    en.withdraw_enrolment(en.list_for_student(b)[0].enrolment_id,
                          withdrawal_date="2026-01-15", reason="3")
    wa = rep.withdrawal_analytics(YEAR)
    assert (wa.starts, wa.withdrawals, wa.early_leavers) == (2, 1, 1)
    assert wa.retention_pct == 50.0
    assert wa.by_month == {"2025-09": 1, "2026-01": 1}
    counts = {(s.status, s.count) for s in rep.status_counts(YEAR)}
    assert counts == {("Enrolled", 1), ("Withdrawn", 2)}
    text = rep.to_csv(wa.breakdown_rows())
    assert text.splitlines()[0] == "dimension,value,withdrawals"
    assert rep.to_csv(funding.cof_report(YEAR, live_only=False)).startswith(
        "enrolment_id,")
