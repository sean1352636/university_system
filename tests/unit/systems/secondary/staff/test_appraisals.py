"""Appraisals & CPD (modules.staff.domain.appraisals / appraisals_cpd)."""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.staff.domain import appraisals as AP
from education_system.systems.secondary.modules.staff.domain import appraisals_cpd as CP
from education_system.systems.secondary.modules.staff.domain import staff_directory as SD
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.core.academic_calendar.school_year import current_year, year_of
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
BOSS = Principal(username="boss", role="teacher")
ANN = Principal(username="ann", role="teacher")
BOB = Principal(username="bob", role="teacher")
LOGINS = [{"username": u, "display_name": n, "email": f"{u}@school.org", "role": "teacher"}
          for u, n in (("boss", "Bea Boss"), ("ann", "Ann Staff"), ("bob", "Bob Other"))]
YEAR = current_year()
TODAY = dt.date.today()


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    monkeypatch.setattr(accounts, "staff_logins", lambda: LOGINS)
    yield tmp_path
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


@pytest.fixture
def staff():
    boss = SD.create({"first_name": "Bea", "last_name": "Boss", "username": "boss",
                      "role": "Head of Department"}, actor=ADMIN)
    ann = SD.create({"first_name": "Ann", "last_name": "Staff", "username": "ann",
                     "line_manager_id": boss.staff_id, "job_title": "Teacher of Maths"},
                    actor=ADMIN)
    bob = SD.create({"first_name": "Bob", "last_name": "Other", "username": "bob"}, actor=ADMIN)
    return boss, ann, bob


def _ready(ann):
    a = AP.create_appraisal({"staff_id": ann.staff_id}, actor=ADMIN)
    AP.add_objective(a.appraisal_id, {"title": "Raise Y11 outcomes",
                                      "success_criteria": "80% grade 4+"}, actor=BOSS)
    return a


def test_create_defaults_appraiser_to_line_manager(staff):
    boss, ann, _bob = staff
    a = AP.create_appraisal({"staff_id": ann.label}, actor=ADMIN)
    assert (a.appraiser_id, a.academic_year, a.job_role, a.status, a.pay_progression) == (
        boss.staff_id, YEAR, "Teacher of Maths", "Setting Objectives", "Pending")
    with pytest.raises(AP.ValidationError, match="already has an appraisal"):
        AP.create_appraisal({"staff_id": ann.staff_id}, actor=ADMIN)
    with pytest.raises(AP.ValidationError, match="appraise themselves"):
        AP.create_appraisal({"staff_id": boss.staff_id, "appraiser_id": boss.staff_id},
                            actor=ADMIN)
    with pytest.raises(AP.PermissionDenied):
        AP.create_appraisal({"staff_id": boss.staff_id}, actor=BOSS)


def test_start_cycle_for_all_current_staff(staff):
    r = AP.start_cycle(YEAR, actor=ADMIN)
    assert len(r["created"]) == 3 and sorted(r["no_appraiser"]) == ["Bea Boss", "Bob Other"]
    assert AP.start_cycle(YEAR, actor=ADMIN)["created"] == []


def test_who_sees_what(staff):
    boss, ann, bob = staff
    a = _ready(ann)
    AP.create_appraisal({"staff_id": bob.staff_id}, actor=ADMIN)
    assert [x.appraisal_id for x in AP.list_appraisals(actor=ANN)] == [a.appraisal_id]
    assert [x.appraisal_id for x in AP.list_appraisals(actor=BOSS)] == [a.appraisal_id]
    assert len(AP.list_appraisals(actor=ADMIN)) == 2
    with pytest.raises(AP.PermissionDenied):
        AP.get_appraisal(a.appraisal_id, actor=BOB)
    # The appraisee adds comments and progress, but not grades.
    AP.update_appraisal(a.appraisal_id, {"appraisee_comments": "Going well",
                                         "self_review_completed": True}, actor=ANN)
    with pytest.raises(AP.PermissionDenied):
        AP.update_appraisal(a.appraisal_id, {"overall_grade": 1}, actor=ANN)
    o = AP.list_objectives(a.appraisal_id)[0]
    assert AP.update_objective(o.objective_id, {"progress_percent": "40"},
                               actor=ANN).progress_percent == 40
    with pytest.raises(AP.PermissionDenied):
        AP.update_objective(o.objective_id, {"title": "Easier"}, actor=ANN)
    with pytest.raises(AP.PermissionDenied):
        AP.update_appraisal(a.appraisal_id, {"appraiser_id": bob.staff_id}, actor=BOSS)


def test_cycle_steps_and_rules(staff):
    _boss, ann, _bob = staff
    a = AP.create_appraisal({"staff_id": ann.staff_id}, actor=ADMIN)
    with pytest.raises(AP.ValidationError, match="Add the objectives first"):
        AP.set_objectives(a.appraisal_id, actor=BOSS)
    o = AP.add_objective(a.appraisal_id, {"title": "Coach NQTs"}, actor=BOSS)
    with pytest.raises(AP.ValidationError, match="needs success criteria"):
        AP.set_objectives(a.appraisal_id, actor=BOSS)
    with pytest.raises(AP.ValidationError, match="Set the objectives"):
        AP.record_mid_year(a.appraisal_id, actor=BOSS)
    AP.update_objective(o.objective_id, {"success_criteria": "Two ECTs pass"}, actor=BOSS)
    a = AP.set_objectives(a.appraisal_id, actor=BOSS, on="2026-09-20")
    assert a.status == "In Progress"
    with pytest.raises(AP.ValidationError, match="Removed instead"):
        AP.delete_objective(o.objective_id, actor=BOSS)
    a = AP.record_mid_year(a.appraisal_id, actor=BOSS, reviewed_on="2027-02-01", notes="OK")
    assert a.status == "Awaiting End Year"
    with pytest.raises(AP.ValidationError) as e:
        AP.record_end_year(a.appraisal_id, actor=BOSS)
    assert "outcome" in str(e.value) and "pay progression" in str(e.value)
    a = AP.record_end_year(a.appraisal_id, actor=BOSS, reviewed_on="2027-07-01",
                           overall_grade=2, pay_progression="Yes", outcome="Met objectives")
    assert (a.status, a.grade_label, a.is_open) == ("Completed", "Good", False)
    with pytest.raises(AP.ValidationError, match="kept"):
        AP.delete_appraisal(a.appraisal_id, actor=ADMIN)
    assert "Coach NQTs" in AP.appraisal_text(a.appraisal_id, actor=ANN)


def test_mid_year_overdue(staff):
    _boss, ann, _bob = staff
    a = _ready(ann)
    long_ago = (TODAY - dt.timedelta(days=AP.MID_YEAR_AFTER_DAYS + 5)).isoformat()
    AP.update_appraisal(a.appraisal_id, {"objectives_set_on": long_ago,
                                         "status": "In Progress"}, actor=ADMIN)
    assert [x.appraisal_id for x in AP.list_appraisals(actor=ADMIN, mid_year_overdue=True)] \
        == [a.appraisal_id]


def test_observations_link_to_appraisal(staff):
    boss, ann, bob = staff
    a = _ready(ann)
    ob = AP.add_observation({"staff_id": ann.staff_id, "class_observed": "8/Ma1",
                             "judgement": "Effective", "observed_on": TODAY.isoformat()},
                            actor=BOSS)
    assert (ob.appraisal_id, ob.observer_id) == (a.appraisal_id, boss.staff_id)
    with pytest.raises(AP.PermissionDenied):
        AP.add_observation({"staff_id": ann.staff_id}, actor=BOB)
    with pytest.raises(AP.ValidationError, match="after it happens"):
        AP.add_observation({"staff_id": ann.staff_id, "observed_on": "2999-01-01"}, actor=BOSS)
    AP.update_observation(ob.observation_id, {"staff_response": "Thanks"}, actor=ANN)
    with pytest.raises(AP.PermissionDenied):
        AP.update_observation(ob.observation_id, {"judgement": "Highly effective"}, actor=ANN)
    assert [o.observation_id for o in AP.list_observations(actor=ANN)] == [ob.observation_id]
    assert AP.list_observations(actor=BOB) == []


def test_training_request_budget_and_evaluation(staff):
    _boss, ann, bob = staff
    CP.set_budget(YEAR, "500", actor=ADMIN)
    start = TODAY.isoformat()
    r = CP.request_cpd({"title": "Maths hub", "provider": "NCETM", "start_date": start,
                        "cost": "400", "cover_needed": True}, actor=ANN)
    assert (r.status, r.staff_id, r.cover_needed) == ("Requested", ann.staff_id, True)
    with pytest.raises(AP.PermissionDenied):
        CP.request_cpd({"staff_id": ann.staff_id, "title": "X"}, actor=BOB)
    with pytest.raises(AP.PermissionDenied):
        CP.decide(r.record_id, True, actor=ANN)
    r = CP.decide(r.record_id, True, actor=ADMIN)
    assert r.status == "Approved"
    b = CP.budget(YEAR)
    assert (b["available"], b["used"], b["remaining"]) == (500.0, 400.0, 100.0)
    r2 = CP.request_cpd({"title": "Conference", "start_date": start, "cost": "200"}, actor=ANN)
    with pytest.raises(AP.ValidationError, match="over"):
        CP.decide(r2.record_id, True, actor=ADMIN)
    with pytest.raises(AP.ValidationError, match="Say why"):
        CP.decide(r2.record_id, False, actor=ADMIN)
    assert CP.decide(r2.record_id, False, actor=ADMIN, note="Budget").status == "Declined"
    with pytest.raises(AP.ValidationError, match="once it has been attended"):
        CP.record_evaluation(r.record_id, actor=ANN, rating=4)
    CP.mark_attended(r.record_id, actor=ANN, hours_completed="6")
    r = CP.record_evaluation(r.record_id, actor=ANN, rating=4, impact="Better questioning")
    assert (r.status, r.evaluation_rating) == ("Completed", 4)
    log = CP.cpd_log(ann.staff_id, actor=ANN)
    assert log["hours"] == 6 and log["by_year"][year_of(start)]["courses"] == 1
    assert CP.list_records(actor=BOB) == []
    assert len(CP.list_records(actor=ADMIN)) == 2


def test_activity_catalogue_and_booking(staff):
    _boss, ann, _bob = staff
    act = CP.create_activity({"title": "INSET: behaviour", "activity_type": "INSET Day",
                              "activity_date": "2026-09-01", "hours": "6", "cost": "0"},
                             actor=ADMIN)
    rec = CP.create_record({"staff_id": ann.staff_id, "activity_id": act.activity_id},
                           actor=ADMIN)
    assert (rec.title, rec.status, rec.booked_on is not None) == (
        "INSET: behaviour", "Booked", True)
    assert CP.get_activity(act.activity_id).records == 1
    assert CP.mark_activity_completed(act.activity_id, actor=ADMIN).status == "Completed"
    CP.mark_attended(rec.record_id, actor=ADMIN, attended_on="2026-09-01")
    assert CP.list_records(actor=ADMIN, awaiting_cert=True)[0].record_id == rec.record_id
    CP.file_certificate(rec.record_id, actor=ANN, ref="C-1")
    assert CP.list_records(actor=ADMIN, awaiting_cert=True) == []
    with pytest.raises(AP.PermissionDenied):
        CP.create_activity({"title": "X", "activity_date": "2026-09-01"}, actor=ANN)


def test_statutory_training_expiry_and_due(staff):
    _boss, ann, bob = staff
    t = CP.add_training({"staff_id": ann.staff_id, "training_type": "Safeguarding / KCSIE",
                         "completed_on": "2025-09-01"}, actor=ADMIN)
    assert t.expires_on == "2026-09-01"
    fa = CP.add_training({"staff_id": ann.staff_id, "training_type": "First aid at work",
                          "completed_on": (TODAY - dt.timedelta(days=3 * 365 - 20)).isoformat()},
                         actor=ADMIN)
    assert fa.expires_on > TODAY.isoformat()
    due = {(d["staff"], d["training_type"]): d["state"] for d in CP.training_due(actor=ADMIN)}
    if t.expires_on < TODAY.isoformat():
        assert due[("Ann Staff", "Safeguarding / KCSIE")] == "Overdue"
    assert due[("Ann Staff", "Prevent")] == "Missing"
    assert due[("Ann Staff", "First aid at work")] == "Due soon"
    assert due[("Bob Other", "Safeguarding / KCSIE")] == "Missing"
    mine = CP.training_due(actor=ANN)
    assert {d["staff"] for d in mine} == {"Ann Staff"}
    assert CP.list_training(actor=BOB) == []
    with pytest.raises(AP.PermissionDenied):
        CP.add_training({"staff_id": bob.staff_id, "training_type": "Prevent",
                         "completed_on": "2026-01-01"}, actor=BOB)
    new = CP.update_training(t.training_id, {"completed_on": "2026-06-01"}, actor=ADMIN)
    assert new.expires_on == "2027-06-01"


def test_summary_export_and_staff_delete_guard(staff, tmp_path):
    _boss, ann, _bob = staff
    _ready(ann)
    s = CP.summary(actor=ADMIN)
    assert (s["appraisals"], s["open"]) == (1, 1)
    path = tmp_path / "a.csv"
    assert CP.export_csv(path, "appraisals", actor=ADMIN) == 1
    assert list(csv.reader(open(path, encoding="utf-8")))[1][2] == "Ann Staff"
    with pytest.raises(SD.ValidationError, match="appraisal"):
        SD.delete(ann.staff_id, actor=ADMIN)
