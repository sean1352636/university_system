"""Staff absence (modules.staff.domain.staff_absence) on a scratch school DB.

Absences live in cover's ``cover_absences``; these tests check that HR's
actions make, move and cancel cover exactly as the Cover screen does.
"""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.curriculum.domain import cover as CV
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.curriculum.domain import timetable as TT
from education_system.systems.secondary.modules.staff.domain import staff_absence as SA
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
HR2 = Principal(username="hr", role="admin")
AHMED = Principal(username="ahmed", role="teacher")
LEE = Principal(username="lee", role="teacher")
LOGINS = [{"username": u, "display_name": n, "email": f"{u}@school.org", "role": r}
          for u, n, r in (("ahmed", "Mr Ahmed", "teacher"), ("lee", "Ms Lee", "teacher"),
                          ("admin2", "Admin", "admin"), ("hr", "HR Office", "admin"))]

TODAY = dt.date.today()
MON = TODAY + dt.timedelta(days=7 - TODAY.weekday() + 7)    # a Monday 1-2 weeks ahead
WED = MON + dt.timedelta(days=2)
FRI = MON + dt.timedelta(days=4)


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
def school():
    m = S.create({"code": "MATH", "name": "Mathematics", "department": "Maths"}, actor=ADMIN)
    e = S.create({"code": "ENG", "name": "English"}, actor=ADMIN)
    ma1 = TG.create({"code": "8/Ma1", "subject_id": m.subject_id, "year_group": 8,
                     "teacher_username": "ahmed", "room": "M1"}, actor=ADMIN)
    en1 = TG.create({"code": "8/En1", "subject_id": e.subject_id, "year_group": 8,
                     "teacher_username": "lee", "room": "E1"}, actor=ADMIN)
    for g, day, p in ((ma1, "Mon", 1), (ma1, "Wed", 2), (ma1, "Fri", 3), (en1, "Mon", 1)):
        TT.add_lesson({"group_id": g.group_id, "day": day, "period": p}, actor=ADMIN)
    return {"ma1": ma1, "en1": en1}


def _sick(start=MON, end=WED, actor=ADMIN, **extra):
    return SA.create_absence({"staff_username": "ahmed", "start_date": start.isoformat(),
                              "end_date": end.isoformat(), "absence_type": "Sickness",
                              **extra}, actor=actor)


# ── One store: cover is made from the HR record ──────────────────────

def test_absence_is_a_cover_absence_and_makes_cover(school):
    rec, lessons = _sick(reason="Flu - private")
    assert lessons == 2                                  # Mon P1, Wed P2
    a = CV.get_absence(rec.absence_id)
    assert a.reason == "Illness" and a.notes is None     # cover sees the category only
    assert len(CV.list_covers(absence_id=rec.absence_id)) == 2
    assert rec.reason == "Flu - private" and rec.is_sickness and rec.rtw_required
    assert rec.cover_pending == 2 and rec.cover_outstanding
    assert rec.days == 3.0 and rec.status == "Reported"
    log = (database.db_path().parent / "activity.log").read_text()
    assert "Flu" not in log


def test_cover_screen_absence_shows_with_defaults(school):
    a, _n = CV.create_absence({"teacher_username": "lee", "start_date": MON,
                               "end_date": MON, "reason": "Training / CPD"}, actor=ADMIN)
    rec = SA.get(a.absence_id)
    assert not rec.has_details
    assert (rec.absence_type, rec.status, rec.paid) == ("Training / CPD", "Active", True)
    rec2, _a, _c = SA.update_absence(a.absence_id, {"notes": "INSET"}, actor=ADMIN)
    assert rec2.has_details and rec2.notes == "INSET"


def test_return_moves_cover_and_rtw(school):
    rec, _n = _sick(start=MON, end=FRI)
    assert len(CV.list_covers(absence_id=rec.absence_id, include_cancelled=False)) == 3
    rec, added, cancelled = SA.record_return(rec.absence_id, returned_on=WED, actor=ADMIN)
    assert (rec.end_date, rec.status, cancelled) == (
        (MON + dt.timedelta(days=1)).isoformat(), "Returned", 2)
    assert rec.rtw_outstanding
    with pytest.raises(SA.ValidationError, match="return-to-work"):
        SA.close(rec.absence_id, actor=ADMIN)
    with pytest.raises(SA.ValidationError, match="happened"):
        SA.complete_rtw(rec.absence_id, completed_by="Head", meeting_on=WED, actor=ADMIN)


def test_extend_adds_cover_and_cancel_cancels_it(school):
    rec, _n = _sick(start=MON, end=MON)
    rec, added, _c = SA.extend(rec.absence_id, expected_return=FRI + dt.timedelta(days=3),
                               actor=ADMIN)
    assert rec.end_date == FRI.isoformat() and added == 2
    assert rec.expected_return == (FRI + dt.timedelta(days=3)).isoformat()
    rec = SA.cancel(rec.absence_id, actor=ADMIN)
    assert rec.status == "Cancelled" and CV.get_absence(rec.absence_id).status == "cancelled"
    assert not CV.list_covers(absence_id=rec.absence_id, include_cancelled=False)
    with pytest.raises(SA.ValidationError):
        SA.set_status(rec.absence_id, "Active", actor=ADMIN)


def test_delete_only_before_cover_is_assigned(school):
    rec, _n = _sick()
    c = CV.list_covers(absence_id=rec.absence_id)[0]
    CV.assign(c.cover_id, name="Mr Spare", actor=ADMIN)
    with pytest.raises(SA.ValidationError, match="assigned"):
        SA.delete(rec.absence_id, actor=ADMIN)
    CV.unassign(c.cover_id, actor=ADMIN)
    assert SA.delete(rec.absence_id, actor=ADMIN) == 2
    with pytest.raises(SA.NotFound):
        SA.get(rec.absence_id)


def test_old_actions_confirm_arrange_status_and_validation(school):
    rec, _n = _sick()
    assert SA.confirm(rec.absence_id, actor=ADMIN).status == "Active"
    assert SA.confirm(rec.absence_id, actor=ADMIN).status == "Confirmed"
    rec = SA.arrange_cover(rec.absence_id, source="Supply Agency", arranged_by="Office",
                           actor=ADMIN)
    assert (rec.cover_source, rec.cover_arranged_by) == ("Supply Agency", "Office")
    with pytest.raises(SA.ValidationError) as e:
        SA.update_absence(rec.absence_id, {"absence_type": "Nap", "days_lost": "-1",
                                           "fit_note_from": "2026-01-10",
                                           "fit_note_to": "2026-01-01"}, actor=ADMIN)
    assert len(e.value.problems) == 3
    with pytest.raises(SA.ValidationError):
        _sick(start=MON, end=MON)                       # overlaps (cover's own rule)


def test_fit_note_needed_after_seven_days(school):
    rec, _n = _sick(start=MON, end=MON + dt.timedelta(days=9))
    assert rec.fit_note_needed and "FIT" in rec.flags
    rec = SA.record_certificate(rec.absence_id, certificate_type="Fit Note",
                                received_on=TODAY, fit_from=MON, fit_to=FRI, actor=ADMIN)
    assert not rec.fit_note_needed


# ── Who may do what ──────────────────────────────────────────────────

def test_staff_report_own_sickness_and_see_only_their_own(school):
    rec, lessons = SA.report_sickness(actor=AHMED, start_date=MON, expected_return=WED,
                                      reason="migraine")
    assert rec.staff_username == "ahmed" and rec.end_date == (MON + dt.timedelta(days=1)).isoformat()
    assert lessons == 1 and rec.notified_by == "ahmed"
    assert [r.absence_id for r in SA.list_absences(actor=AHMED)] == [rec.absence_id]
    assert SA.list_absences(actor=LEE) == []
    with pytest.raises(SA.PermissionDenied):
        SA.get_absence(rec.absence_id, actor=LEE)
    with pytest.raises(SA.PermissionDenied):
        SA.update_absence(rec.absence_id, {"notes": "x"}, actor=AHMED)
    with pytest.raises(SA.ValidationError):
        SA.create_absence({"staff_username": "lee", "start_date": MON,
                           "absence_type": "Sickness"}, actor=AHMED)
    with pytest.raises(SA.PermissionDenied):
        SA.export_csv("x.csv", actor=AHMED)
    assert SA.cancel(rec.absence_id, actor=AHMED).status == "Cancelled"


def test_request_approve_decline_withdraw(school):
    rq = SA.request_absence({"start_date": FRI, "absence_type": "Medical Appointment",
                             "from_period": 3, "to_period": 3}, actor=AHMED)
    assert rq.status == "Requested" and rq.staff_username == "ahmed"
    assert not CV.list_absences(teacher="ahmed")         # nothing covered yet
    with pytest.raises(SA.PermissionDenied):
        SA.approve_request(rq.request_id, actor=LEE)
    rq, rec, lessons = SA.approve_request(rq.request_id, actor=ADMIN, note="ok")
    assert rq.status == "Approved" and rq.absence_id == rec.absence_id and lessons == 1
    assert rec.request_id == rq.request_id and rec.approved_by == "admin2"
    assert rec.status == "Confirmed" and rec.days == 0.5
    with pytest.raises(SA.ValidationError):
        SA.approve_request(rq.request_id, actor=ADMIN)
    with pytest.raises(SA.ValidationError, match="Sickness"):
        SA.request_absence({"start_date": MON, "absence_type": "Sickness"}, actor=LEE)
    r2 = SA.request_absence({"start_date": MON, "absence_type": "Unpaid Leave"}, actor=LEE)
    assert not r2.paid
    with pytest.raises(SA.ValidationError):
        SA.decline_request(r2.request_id, actor=ADMIN, note="")
    assert SA.decline_request(r2.request_id, actor=ADMIN, note="Exams").status == "Declined"
    r3 = SA.request_absence({"start_date": WED, "absence_type": "Jury Service"}, actor=LEE)
    with pytest.raises(SA.PermissionDenied):
        SA.withdraw_request(r3.request_id, actor=AHMED)
    assert SA.withdraw_request(r3.request_id, actor=LEE).status == "Withdrawn"
    own = SA.request_absence({"start_date": WED, "absence_type": "Training / CPD"},
                             actor=ADMIN)
    with pytest.raises(SA.ValidationError, match="Someone else"):
        SA.approve_request(own.request_id, actor=ADMIN)
    assert SA.approve_request(own.request_id, actor=HR2)[0].status == "Approved"


# ── Sickness record and reports ──────────────────────────────────────

def test_bradford_factor_and_triggers(school):
    base = TODAY - dt.timedelta(days=200)
    base -= dt.timedelta(days=base.weekday())               # a Monday
    for i in range(3):                                        # 3 one-day episodes
        d = base + dt.timedelta(days=14 * i)
        _sick(start=d, end=d)
    rec = SA.sickness_record("ahmed", actor=ADMIN)
    assert (rec["episodes"], rec["days"], rec["bradford"]) == (3, 3.0, 27.0)
    assert rec["triggers"] == ["3 episodes (trigger 3)"]
    SA.set_settings({"trigger_episodes": "5", "bradford_trigger": "20"}, actor=ADMIN)
    rec = SA.sickness_record("ahmed", actor=ADMIN)
    assert rec["triggers"] == ["Bradford 27 (trigger 20)"]
    over = SA.sickness_overview(actor=ADMIN, triggered_only=True)
    assert over[0]["username"] == "ahmed" and over[0]["department"] == "Maths"
    with pytest.raises(SA.ValidationError):
        SA.set_settings({"trigger_days": "0"}, actor=ADMIN)
    old = TODAY - dt.timedelta(days=500)
    _sick(start=old, end=old)
    assert SA.sickness_record("ahmed", actor=ADMIN)["episodes"] == 3   # outside 12 months


def test_reports_calendar_summary_and_export(school, tmp_path):
    _sick(start=MON, end=MON)
    SA.create_absence({"staff_username": "lee", "start_date": WED,
                       "absence_type": "Training / CPD"}, actor=ADMIN)
    by_type = {g["group"]: g for g in SA.report(by="type", actor=ADMIN)}
    assert by_type["Sickness"]["sickness_days"] == 1 and by_type["Training / CPD"]["days"] == 1
    depts = {g["group"] for g in SA.report(by="department", actor=ADMIN)}
    assert depts == {"Maths", "English"}
    assert SA.report(by="month", actor=ADMIN)[0]["group"] == MON.isoformat()[:7]
    cal = SA.calendar(MON.year, MON.month, actor=ADMIN)
    assert [r.staff_username for r in cal[MON.isoformat()]] == ["ahmed"]
    assert [r.staff_username for r in SA.on_date(WED, actor=ADMIN)] == ["lee"]
    s = SA.summary(actor=ADMIN)
    assert s["total"] == 2 and s["distinct_staff"] == 2 and s["cover_outstanding"] == 2
    out = tmp_path / "abs.csv"
    assert SA.export_csv(out, actor=ADMIN) == 2
    rows = list(csv.DictReader(out.open()))
    assert {r["department"] for r in rows} == {"Maths", "English"}
    assert SA.history(rows[0] and int(rows[0]["id"]))


def test_my_absence_for_my_day(school):
    SA.report_sickness(actor=AHMED, start_date=MON)
    SA.request_absence({"start_date": FRI, "absence_type": "Compassionate"}, actor=AHMED)
    mine = SA.my_absence(AHMED)
    assert len(mine["off_now"]) == 1 and len(mine["requests"]) == 1
    assert SA.my_absence(LEE) == {"off_now": [], "requests": [], "rtw_due": []}
