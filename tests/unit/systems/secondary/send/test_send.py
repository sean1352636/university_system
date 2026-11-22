"""SEND register, plans, reviews, provision map and access (modules.send.domain.send).

Built on the pupil's SEN status and the SEN details store; scratch databases only.
"""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.send.domain import send as S
from education_system.systems.secondary.modules.pupils.domain import sen_details as SD
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
ANN = Principal(username="ann", role="teacher")
KID = Principal(username="kid", role="student")
TODAY = dt.date.today()


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    monkeypatch.setattr(accounts, "staff_logins", lambda: [])
    yield tmp_path
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


_n = 0


def _pupil(year=10, **extra):
    global _n
    _n += 1
    return P.create_pupil({
        "legal_first_name": f"Pupil{_n}", "legal_last_name": f"Test{_n:03d}",
        "date_of_birth": f"{2025 - year - 5}-01-15", "gender": "Female", "year_group": year,
        "form_group": f"{year}A", "admission_date": f"{2025 - year + 7}-09-01", **extra},
        actor=ADMIN)


def test_senco_who_is_not_a_pupil_editor_changes_the_sen_status(monkeypatch):
    from education_system.systems.secondary.modules.send.domain import send_common
    senco_roles = frozenset({"admin", "superadmin", "senco"})
    for mod, name in ((P, "SEND_EDITORS"), (send_common, "SEND_EDITORS"),
                      (S, "SEND_EDITORS"), (SD, "SEN_EDITORS")):
        monkeypatch.setattr(mod, name, senco_roles)
    senco = Principal(username="sue", role="senco")
    assert not senco.can_edit_pupils
    ava = _pupil()
    S.save_record(ava.pupil_id, {"stage": S.SUPPORT, "primary_need": "SPLD"}, actor=senco)
    assert P.get_pupil(ava.pupil_id).sen_status == "K"
    assert P.history(ava.pupil_id)[0]["actor"] == "sue"
    with pytest.raises(P.PermissionDenied):          # still only that field
        P.update_pupil(ava.pupil_id, {"sen_status": "E"}, actor=senco)
    with pytest.raises(P.PermissionDenied):
        P.set_sen_status(ava.pupil_id, "N", actor=ANN)
    with pytest.raises(P.ValidationError):
        P.set_sen_status(ava.pupil_id, "Z", actor=senco)
    assert P.set_sen_status(ava.pupil_id, "N", actor=senco).sen_status == "N"


def test_record_builds_on_sen_status_and_details():
    ava = _pupil()
    rec = S.save_record(ava.pupil_id, {"stage": S.SUPPORT, "primary_need": "SPLD",
                                       "secondary_need": "SLCN", "strategies": "Seat near front",
                                       "provision": "Reading group", "senco": "Ms Senco",
                                       "keyworker": "Mr Key", "diagnosis": "Dyslexia"},
                        actor=ADMIN)
    assert P.get_pupil(ava.pupil_id).sen_status == "K"          # the pupil record
    assert SD.get(ava.pupil_id).strategies == "Seat near front"  # the SEN details store
    assert rec.stage == S.SUPPORT and rec.area == "Cognition and learning"
    assert rec.senco == "Ms Senco" and rec.status == "Active" and rec.added_on
    # Monitoring is a register entry for a pupil with no census SEN status.
    ben = _pupil()
    mon = S.save_record(ben.admission_no, {"stage": S.MONITORING}, actor=ADMIN)
    assert mon.stage == S.MONITORING and P.get_pupil(ben.pupil_id).sen_status == "N"
    assert {r.pupil_id for r in S.list_records()} == {ava.pupil_id, ben.pupil_id}
    assert [r.pupil_id for r in S.list_records(stage=S.MONITORING)] == [ben.pupil_id]
    assert [r.pupil_id for r in S.list_records(area="Cognition and learning")] == [ava.pupil_id]
    # The plan reference only goes with an EHC plan (the SEN details rule).
    with pytest.raises(S.ValidationError) as e:
        S.save_record(ava.pupil_id, {"ehcp_reference": "EHC1"}, actor=ADMIN)
    assert "EHC plan" in " ".join(e.value.problems)
    # Assessment requested, then the plan.
    rec = S.save_record(ava.pupil_id, {"stage": S.ASSESSING}, actor=ADMIN)
    assert rec.stage == S.ASSESSING and rec.ehcna_requested_on == TODAY.isoformat()
    rec = S.save_record(ava.pupil_id, {"stage": S.EHCP, "ehcp_reference": "EHC1",
                                       "ehcp_issued_on": TODAY.isoformat()}, actor=ADMIN)
    assert rec.stage == S.EHCP and rec.ehcna_status == "Plan issued"
    assert S.delete(ben.pupil_id, actor=ADMIN) and S.get_for(ben.pupil_id) is None


def test_only_the_senco_changes_but_staff_read_strategies():
    ava = _pupil()
    with pytest.raises(S.PermissionDenied):
        S.save_record(ava.pupil_id, {"stage": S.SUPPORT}, actor=ANN)
    S.save_record(ava.pupil_id, {"stage": S.SUPPORT, "primary_need": "ASD",
                                 "strategies": "Warn before changes"}, actor=ADMIN)
    S.add_arrangement({"pupil_id": ava.pupil_id, "category": "Rest breaks",
                       "status": "Active", "approved_by": "SENCO"}, actor=ADMIN)
    rows = S.strategies(actor=ANN)
    assert rows[0]["strategies"] == "Warn before changes" and rows[0]["adjustments"] == \
        "Rest breaks"
    with pytest.raises(S.PermissionDenied):
        S.strategies(actor=KID)
    with pytest.raises(S.PermissionDenied):
        S.add_review({"pupil_id": ava.pupil_id, "progress": "x"}, actor=ANN)


def test_plan_cycles_assess_plan_do_review():
    ava = _pupil()
    S.save_record(ava.pupil_id, {"stage": S.SUPPORT, "primary_need": "MLD"}, actor=ADMIN)
    with pytest.raises(S.ValidationError):
        S.create_plan({"pupil_id": ava.pupil_id, "status": "Active"}, actor=ADMIN)  # no outcomes
    pl = S.create_plan({"pupil_id": ava.pupil_id, "outcomes": "Read 50 words a minute",
                        "strategies": "Chunk tasks", "status": "Active"}, actor=ADMIN)
    assert pl.cycle == 1 and pl.review_date > pl.start_date
    res = S.review_plan(pl.plan_id, {"review_notes": "Now 40 wpm", "outcome": "Adjust",
                                     "parent_views": "Happy"}, actor=ADMIN)
    assert res["plan"].status == "Reviewed" and res["next"].cycle == 2
    assert res["next"].outcomes == "Read 50 words a minute"
    assert res["review"].outcome == "Adjust" and res["review"].plan_id == pl.plan_id
    assert S.get(ava.pupil_id).next_review_date == res["next"].review_date
    with pytest.raises(S.ValidationError):
        S.update_plan(pl.plan_id, {"outcomes": "x"}, actor=ADMIN)       # reviewed: frozen
    with pytest.raises(S.ValidationError):
        S.delete_plan(res["next"].plan_id, actor=ADMIN)                  # active, not draft
    done = S.review_plan(res["next"].plan_id, {"review_notes": "Met", "outcome": "Discharge"},
                         actor=ADMIN)
    assert done["next"] is None and S.get(ava.pupil_id).status == "Discharged"
    assert "Outcomes (plan)" in S.plan_text(pl)


def test_ehcp_annual_review_deadlines_and_la():
    ava = _pupil()
    issued = (TODAY - dt.timedelta(days=360)).isoformat()
    rec = S.save_record(ava.pupil_id, {"stage": S.EHCP, "primary_need": "SEMH",
                                       "ehcp_reference": "EHC9", "ehcp_issued_on": issued},
                        actor=ADMIN)
    assert S.ehcp_due(rec) == S.add_months(issued, 12).isoformat()
    assert any(d["item"] == "EHC plan annual review" for d in S.due())
    meet = (TODAY - dt.timedelta(days=20)).isoformat()
    rv = S.add_review({"pupil_id": ava.pupil_id, "review_type": S.ANNUAL, "review_date": meet,
                       "progress": "Good year"}, actor=ADMIN)
    assert rv.next_review_date == S.add_months(meet, 12).isoformat()
    assert S.ehcp_due(S.get(ava.pupil_id)) == S.add_months(meet, 12).isoformat()
    late = [d for d in S.due() if "report to the LA" in d["item"]]
    assert late and late[0]["overdue"]
    with pytest.raises(S.ValidationError):
        S.record_la(rv.review_id, actor=ADMIN, decision="Amend the plan")  # report first
    rv = S.record_la(rv.review_id, actor=ADMIN, report_sent_on=TODAY.isoformat(),
                     decision="Amend the plan")
    assert rv.la_decision == "Amend the plan"
    assert not [d for d in S.due() if "LA" in d["item"]]
    bob = _pupil()
    with pytest.raises(S.ValidationError):           # no EHC plan
        S.add_review({"pupil_id": bob.pupil_id, "review_type": S.ANNUAL, "progress": "x"},
                     actor=ADMIN)
    # EHC needs assessment: 6-week decision.
    req = (TODAY - dt.timedelta(days=50)).isoformat()
    S.save_record(bob.pupil_id, {"stage": S.ASSESSING, "ehcna_requested_on": req},
                  actor=ADMIN)
    assert any("6 weeks" in d["item"] and d["overdue"] for d in S.due())


def test_provision_map_costs():
    a, b = _pupil(), _pupil(year=8)
    for p in (a, b):
        S.save_record(p.pupil_id, {"stage": S.SUPPORT, "primary_need": "SPLD"}, actor=ADMIN)
    rows = S.add_provision_many([a.pupil_id, b.pupil_id], {
        "provision": "Phonics group", "hours_per_week": 1.5, "weeks": 10,
        "cost_per_hour": 30, "status": "Active", "need_area": "Cognition and learning"},
        actor=ADMIN)
    assert rows[0].group_size == 2 and rows[0].cost == 225.0 and rows[0].start_date
    S.add_provision({"pupil_id": a.pupil_id, "provision": "Laptop", "fixed_cost": 400},
                    actor=ADMIN)
    with pytest.raises(S.ValidationError):
        S.add_provision({"pupil_id": a.pupil_id, "provision": "TA", "in_ehcp": True},
                        actor=ADMIN)                     # no EHC plan
    m = {g["provision"]: g for g in S.provision_map()}
    assert m["Phonics group"]["pupils"] == 2 and m["Phonics group"]["cost"] == 450.0
    assert m["Laptop"]["cost"] == 400.0
    x = S.update_provision(rows[0].provision_id, {"status": "Ended"}, actor=ADMIN)
    assert x.end_date == TODAY.isoformat()


def test_access_arrangements_form8_expiry_and_copy():
    y8, y10 = _pupil(year=8), _pupil(year=10)
    S.save_record(y10.pupil_id, {"stage": S.SUPPORT, "primary_need": "SPLD"}, actor=ADMIN)
    form8 = {"arrangement_type": S.EXAM_ACCESS, "category": "Extra time (25%)",
             "evidence_source": S.FORM_8, "assessor": "Dr A", "status": "Active",
             "approved_by": "SENCO"}
    with pytest.raises(S.ValidationError) as e:
        S.add_arrangement({**form8, "pupil_id": y8.pupil_id,
                           "assessed_on": TODAY.isoformat()}, actor=ADMIN)
    assert "start of Year 9" in " ".join(e.value.problems)
    a = S.add_arrangement({**form8, "pupil_id": y10.pupil_id,
                           "assessed_on": TODAY.isoformat()}, actor=ADMIN)
    assert a.status == "Active" and a.approval_date == TODAY.isoformat()
    with pytest.raises(S.ValidationError):           # active needs approver
        S.add_arrangement({"pupil_id": y10.pupil_id, "category": "Reader",
                           "status": "Active"}, actor=ADMIN)
    old = S.add_arrangement({"pupil_id": y10.pupil_id, "category": "Rest breaks",
                             "status": "Active", "approved_by": "SENCO",
                             "start_date": "2024-01-01", "end_date": "2024-06-01"},
                            actor=ADMIN)
    assert [x.arrangement_id for x in S.expired_arrangements()] == [old.arrangement_id]
    assert S.expire_overdue(actor=ADMIN) == 1
    assert S.get_arrangement(old.arrangement_id).status == "Expired"
    assert S.copy_exam_access(y10.pupil_id, actor=ADMIN).exam_access == "Extra time (25%)"
    assert S.access_summary()["total"] == 2


def test_agencies_reports_family_and_export(tmp_path):
    a, b, c = _pupil(year=7), _pupil(year=7), _pupil(year=9)
    S.save_record(a.pupil_id, {"stage": S.SUPPORT, "primary_need": "ASD"}, actor=ADMIN)
    S.save_record(b.pupil_id, {"stage": S.EHCP, "primary_need": "ASD"}, actor=ADMIN)
    S.save_record(c.pupil_id, {"stage": S.SUPPORT, "primary_need": "SEMH"}, actor=ADMIN)
    g = S.add_agency({"pupil_id": a.pupil_id, "agency": "CAMHS",
                      "next_appointment": (TODAY + dt.timedelta(days=5)).isoformat()},
                     actor=ADMIN)
    assert g.status == "Referred" and g.referred_on == TODAY.isoformat()
    assert any(d["item"] == "CAMHS appointment" for d in S.due())
    grid = {r["need"]: r for r in S.needs_by_year()}
    assert grid["ASD"][7] == 2 and grid["SEMH"][9] == 1 and grid["ASD"]["total"] == 2
    y7 = next(r for r in S.stage_by_year() if r["year"] == 7)
    assert (y7["K"], y7["E"], y7["on_roll"]) == (1, 1, 2)
    s = S.cohort_summary()
    assert s["ehcp_count"] == 1 and s["support_count"] == 2
    assert {x["area"] for x in S.by_area()} == {"Communication and interaction",
                                                "Social, emotional and mental health"}
    # Invitation to the family.
    assert S.invite_to_review(a.pupil_id, when="Tue 3pm", actor=ADMIN)["emails"] == 0
    C.add_contact(a.pupil_id, {"full_name": "Mum Test", "relationship": "Mother",
                               "email": "mum@example.org"}, actor=ADMIN)
    assert S.invite_to_review(a.pupil_id, when="Tue 3pm", actor=ADMIN)["emails"] == 1
    pl = S.create_plan({"pupil_id": a.pupil_id, "outcomes": "Join a club"}, actor=ADMIN)
    assert S.share_plan(pl.plan_id, actor=ADMIN)["emails"] == 1
    assert S.get_plan(pl.plan_id).shared_on == TODAY.isoformat()
    with database.connect() as conn:
        body = conn.execute("SELECT body FROM email_recipients WHERE subject LIKE "
                            "'Invitation%'").fetchone()[0]
    assert "Tue 3pm" in body
    out = tmp_path / "send.csv"
    assert S.export_csv(out, actor=ADMIN) == 3
    assert list(csv.reader(out.open()))[0][0] == "admission_no"
    assert any(h["item"] == "plan" and h["action"] == "share" for h in S.history(a.pupil_id))
    assert S.for_profile(a.pupil_id)["stage"] == S.SUPPORT
    # Ids only in the activity log - never the need.
    log = (activity_log.log_path()).read_text()
    assert "ASD" not in log and "CAMHS" not in log
