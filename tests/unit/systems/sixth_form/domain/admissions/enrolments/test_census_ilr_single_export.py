"""One ILR export: the census_ilr return builder over the enrolment ILR records.

The Enrolment screens' ILR Export (``ilr.export_csv``) and the Census ILR
screens' (``return_export.export_ilr_csv``) are the same code path, and the
generated census return takes its learning delivery from ``enrolment_ilr``
and ``aim_outcomes``.
"""

from __future__ import annotations

import csv
import io

import pytest

from education_system.systems.sixth_form.domain.academics.qualifications import (
    learning_aims as la,
)
from education_system.systems.sixth_form.domain.admissions.enrolments import (
    enrolments as en,
)
from education_system.systems.sixth_form.domain.admissions.enrolments import (
    ilr,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students,
)
from education_system.systems.sixth_form.domains.finance.domain.census_ilr import (
    census_ilr as core,
)
from education_system.systems.sixth_form.domains.finance.domain.census_ilr import (
    return_builder as builder,
)
from education_system.systems.sixth_form.domains.finance.domain.census_ilr import (
    return_export as export,
)
from education_system.systems.sixth_form.domains.finance.domain.census_ilr import (
    return_validation as validation,
)

YEAR = "2025/26"
START = "2025-09-03"


@pytest.fixture
def funding_staff(ilr_export_dbs, sign_in):
    return sign_in("fin1", capabilities={access.FUNDING, access.STUDENTS_MANAGE})


def _student(first="Ava", dob="2009-05-06"):
    return students.create_student(
        {"first_name": first, "last_name": "Ilr", "date_of_birth": dob,
         "status": "Active"}, allow_duplicate=True).student_id


def _enrol(sid):
    return en.create_enrolment({"student_id": sid, "academic_year": YEAR,
                                "year_group": 12, "tutor_group": "12A",
                                "start_date": START})


def _a_level(sid, code="60118007", subject="Mathematics"):
    return la.add_aim(sid, {"qualification_type": "A Level", "subject": subject,
                            "start_date": START, "planned_end_date": "2027-06-30",
                            "planned_hours": 180, "aim_code": code})


def _rows(text):
    return list(csv.DictReader(io.StringIO(text)))


def test_both_ilr_exports_are_one_file(funding_staff):
    sid = _student()
    _enrol(sid)
    _a_level(sid)
    a = ilr.export_csv(YEAR)
    b = export.export_ilr_csv(YEAR)
    assert a.text == b.text
    assert type(a) is export.ExportResult and ilr.ExportResult is export.ExportResult
    assert ilr.EXPORT_COLUMNS == export.ILR_CSV_COLUMNS


def test_recorded_enrolment_values_reach_the_file(funding_staff):
    stay, leave = _student("Ava"), _student("Cat")
    e1, e2 = _enrol(stay), _enrol(leave)
    _a_level(stay)
    aim = _a_level(leave)
    ilr.set_ilr(e1.enrolment_id, {"plan_learn_hours": 560, "plan_eep_hours": 60})
    en.withdraw_enrolment(e2.enrolment_id, withdrawal_date="2025-11-20", reason="2")
    ilr.set_aim_outcome(aim.aim_id, 2)

    rows = _rows(export.export_ilr_csv(YEAR).text)
    learner = {r["LearnRefNumber"]: r for r in rows if r["RecordType"] == "Learner"}
    assert learner[stay[:12]]["PlanLearnHours"] == "560"
    assert learner[stay[:12]]["PlanEEPHours"] == "60"
    assert learner[stay[:12]]["FundModel"] == "25"
    assert learner[stay[:12]]["FeeStatus"] == ilr.FEE_16_19
    assert learner[stay[:12]]["LLDDHealthProb"] == "9"   # no SEND entry: not provided
    delivery = next(r for r in rows if r["RecordType"] == "LearningDelivery"
                    and r["LearnRefNumber"] == leave[:12])
    assert (delivery["CompStatus"], delivery["WithdrawReason"],
            delivery["Outcome"]) == ("3", "2", "2")
    assert delivery["LearnActEndDate"] == "2025-11-20"


def test_generated_return_takes_the_enrolment_ilr_record(funding_staff):
    sid = _student()
    e = _enrol(sid)
    aim = _a_level(sid)
    ilr.set_ilr(e.enrolment_id, {"plan_learn_hours": 560, "plan_eep_hours": 60})
    en.withdraw_enrolment(e.enrolment_id, withdrawal_date="2025-09-20", reason="44")
    ilr.set_aim_outcome(aim.aim_id, 3)
    ret = core.create_return({"return_type": "ILR R01", "academic_year": YEAR})
    builder.generate_return(ret.return_id)

    (ln,) = builder.list_learners(ret.return_id)
    assert (ln.enrolment_id, ln.fund_model, ln.fee_status) == (
        e.enrolment_id, 25, ilr.FEE_16_19)
    assert (ln.planned_qual_hours, ln.planned_eep_hours, ln.planned_hours) == (560, 60, 620)
    assert ln.funding_band == "Band 5" and ln.study_mode == ilr.FULL_TIME
    assert ln.early_leaver == 1
    (a,) = core.aims_for_return(ret.return_id)
    assert (a.completion_code, a.outcome_code, a.outcome_source,
            a.withdraw_reason_code) == (3, "3", "recorded", "44")
    rules = {f.rule for f in validation.check(ret.return_id)}
    assert "Early leaver" in rules and "No enrolment" not in rules
    xml = export.to_ilr_xml(ret.return_id, allow_errors=True).decode()
    assert "<WithdrawReason>44</WithdrawReason>" in xml
    assert "<LLDDHealthProb>9</LLDDHealthProb>" in xml


def test_ilr_only_checks_are_reported(funding_staff):
    adult = _student("Dan", dob="1990-01-01")
    _enrol(adult)
    _a_level(adult, code=None)
    loose = _student("Eve")          # on roll, aims, but never enrolled
    _a_level(loose)
    res = export.export_ilr_csv(YEAR)
    by_student = {}
    for p in res.problems:
        by_student.setdefault(p.student_id, set()).add(p.field)
    assert {"FeeStatus", "ULN", "LearnAimRef"} <= by_student[adult]
    assert "Enrolment" in by_student[loose]
    rows = _rows(res.text)
    adult_row = next(r for r in rows if r["RecordType"] == "Learner"
                     and r["LearnRefNumber"] == adult[:12])
    assert adult_row["FundModel"] == "" and adult_row["FeeStatus"] == ""
