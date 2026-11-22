"""Wellbeing (modules.wellbeing.domain.wellbeing)."""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.curriculum.domain import year_groups as YG
from education_system.systems.secondary.modules.wellbeing.domain import wellbeing as WB
from education_system.systems.secondary.modules.portals.domain import portal_accounts as PA
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
ANN = Principal(username="ann", role="teacher")
HEAD = Principal(username="head", role="teacher")
KID = Principal(username="kid", role="student")
LOGINS = [{"username": u, "display_name": n, "email": f"{u}@school.org", "role": "teacher"}
          for u, n in (("ann", "Ann Teacher"), ("head", "Mr Head"))]
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


_n = 0


def _pupil(**extra):
    global _n
    _n += 1
    return P.create_pupil({
        "legal_first_name": f"Pupil{_n}", "legal_last_name": f"Test{_n:03d}",
        "date_of_birth": "2011-01-15", "gender": "Female", "year_group": 10,
        "form_group": "10A", "admission_date": "2021-09-01", **extra}, actor=ADMIN)


def test_old_checkin_rules_and_summaries(tmp_path):
    p = _pupil()
    c = WB.log_checkin({"pupil_id": p.admission_no, "mood_rating": "2",
                        "confidence_rating": 3, "connection_rating": 4,
                        "stressors": "Exams"}, actor=ADMIN)
    assert c.average_rating == 3.0 and c.source == "Form tutor" and c.status == "Open"
    assert c.recorded_by == "admin2" and not c.safeguarding_flag
    with pytest.raises(WB.ValidationError) as e:
        WB.log_checkin({"pupil_id": p.pupil_id, "mood_rating": 7, "action_needed": True,
                        "follow_up_date": "2000-01-01"}, actor=ADMIN)
    text = " ".join(e.value.problems)
    for bit in ("between 1 and 5", "Action summary is required", "before check-in date"):
        assert bit in text
    with pytest.raises(WB.ValidationError) as e:
        WB.log_checkin({"pupil_id": p.pupil_id}, actor=ADMIN)
    assert "at least one rating" in " ".join(e.value.problems)
    WB.log_checkin({"pupil_id": p.pupil_id, "mood_rating": 5, "connection_rating": 5,
                    "source": "Counsellor"}, actor=ADMIN)
    assert WB.set_status(c.checkin_id, "InProgress", actor=ADMIN).status == "InProgress"
    s = WB.pupil_summary(p.pupil_id)
    assert s["count"] == 2 and s["avg_mood"] == 3.5 and len(s["trend"]) == 2
    co = WB.cohort_summary()
    assert co["total"] == 2 and co["by_source"]["Counsellor"] == 1
    assert list(WB.low_wellbeing()) == []           # latest is 5s
    with pytest.raises(WB.ValidationError):
        WB.low_wellbeing(threshold=9)
    out = tmp_path / "wb.csv"
    assert WB.export_csv(out, actor=ADMIN) == 2
    assert list(csv.reader(out.open()))[0][0] == "id"
    assert WB.delete(c.checkin_id, actor=ADMIN) and WB.get(c.checkin_id) is None


def test_safeguarding_words_flag_the_checkin():
    p = _pupil()
    assert WB.safeguarding_signs("He said he wants to die and hits me") == \
        ["suicide", "being hurt"]
    warn = WB.check_checkin({"notes": "Talked about self-harm", "mood_rating": 1})
    assert "Report a Safeguarding Concern" in warn[0] and "action needed" in warn[1]
    c = WB.log_checkin({"pupil_id": p.pupil_id, "notes": "Doesn't feel safe at home"},
                       actor=ANN)
    assert c.safeguarding_flag
    assert [x.checkin_id for x in WB.list_checkins(flagged_only=True)] == [c.checkin_id]


def test_who_sees_what():
    p = _pupil()
    mine = WB.log_checkin({"pupil_id": p.pupil_id, "mood_rating": 3}, actor=ANN)
    lead = WB.log_checkin({"pupil_id": p.pupil_id, "mood_rating": 4}, actor=ADMIN)
    assert [c.checkin_id for c in WB.list_checkins(actor=ANN)] == [mine.checkin_id]
    assert WB.list_checkins(actor=HEAD) == []
    assert WB.update(mine.checkin_id, {"notes": "Better"}, actor=ANN).notes == "Better"
    with pytest.raises(WB.PermissionDenied):
        WB.update(lead.checkin_id, {"notes": "x"}, actor=ANN)
    with pytest.raises(WB.PermissionDenied):
        WB.delete(mine.checkin_id, actor=ANN)
    YG.update(10, {"head_of_year": "Mr Head"}, actor=ADMIN)
    assert len(WB.list_checkins(actor=HEAD)) == 2
    with pytest.raises(WB.PermissionDenied):
        WB.list_checkins(actor=KID)
    with pytest.raises(WB.PermissionDenied):
        WB.create_referral({"pupil_id": p.pupil_id, "service": "CAMHS", "reason": "x"},
                           actor=HEAD)


def test_referrals_plans_and_caseload():
    p = _pupil()
    c = WB.log_checkin({"pupil_id": p.pupil_id, "mood_rating": 1, "action_needed": True,
                        "action_summary": "Refer", "follow_up_with": "Ms Key"}, actor=ADMIN)
    r = WB.create_referral({"pupil_id": p.pupil_id, "service": "camhs", "reason": "Low mood",
                            "urgency": "Urgent", "checkin_id": c.checkin_id}, actor=ADMIN)
    assert r.service == "CAMHS" and r.status == "Referred"
    assert WB.get_checkin(c.checkin_id).status == "Escalated"
    with pytest.raises(WB.ValidationError) as e:
        WB.create_referral({"pupil_id": p.pupil_id, "service": "CAMHS", "reason": "again"},
                           actor=ADMIN)
    assert "already has an open referral" in " ".join(e.value.problems)
    with pytest.raises(WB.ValidationError) as e:
        WB.create_referral({"pupil_id": p.pupil_id, "service": "School nurse", "reason": "x",
                            "consent": "Refused"}, actor=ADMIN)
    assert "Consent was refused" in " ".join(e.value.problems)
    r = WB.update_referral(r.referral_id, {"status": "Accepted",
                                           "first_appointment": TODAY.isoformat()}, actor=ADMIN)
    assert r.accepted_date == TODAY.isoformat()
    with pytest.raises(WB.ValidationError) as e:
        WB.update_referral(r.referral_id, {"status": "Completed"}, actor=ADMIN)
    assert "outcome" in " ".join(e.value.problems)
    rep = WB.referral_report()
    assert rep[0]["service"] == "CAMHS" and rep[0]["avg_wait"] == 0
    with pytest.raises(WB.ValidationError):
        WB.create_plan({"pupil_id": p.pupil_id, "need": "Anxiety"}, actor=ADMIN)
    w = WB.create_plan({"pupil_id": p.pupil_id, "need": "Anxiety", "key_adult": "Ms Key",
                        "strategies": "Time-out card", "review_date": TODAY.isoformat(),
                        "start_date": (TODAY - dt.timedelta(days=1)).isoformat()},
                       actor=ADMIN)
    assert w.review_due
    w = WB.review_plan(w.plan_id, actor=ADMIN, summary="Using the card")
    assert not w.review_due and len(WB.plan_reviews(w.plan_id)) == 1
    load = WB.caseload(actor=ADMIN)
    assert load[0]["referrals"] == ["CAMHS"] and load[0]["plan"].plan_id == w.plan_id
    assert WB.caseload(actor=ADMIN, key_adult="ms key")[0]["pupil_id"] == p.pupil_id
    assert WB.caseload(actor=ADMIN, key_adult="Nobody") == []
    w = WB.review_plan(w.plan_id, actor=ADMIN, summary="Done", close=True, outcome="Settled")
    assert w.status == "Closed" and w.closed_date
    info = WB.for_pupil(p.pupil_id, actor=ADMIN)
    assert info["visible"] and info["referrals"] and info["plan"] is None
    assert WB.for_pupil(p.pupil_id, actor=ANN) == {"visible": False}
    assert any(h["kind"] == "plan" for h in WB.history(pupil_id=p.pupil_id))


def test_surveys_and_self_check_in(monkeypatch):
    p, q = _pupil(), _pupil()
    s = WB.save_survey({"title": "Autumn mood", "year_group": 10, "status": "Open",
                        "close_date": (TODAY + dt.timedelta(days=3)).isoformat()}, actor=ADMIN)
    assert s.is_open_on() and s.scope == "Year 10"
    with pytest.raises(WB.PermissionDenied):
        WB.self_check_in(KID, p.pupil_id, {"mood_rating": 2})
    monkeypatch.setattr(PA, "pupils_for", lambda principal, kind=None: [p])
    c = WB.self_check_in(KID, p.pupil_id, {"mood_rating": 2, "connection_rating": 4})
    assert c.survey_id == s.survey_id and c.source == "Mood survey" and c.action_needed
    with pytest.raises(WB.PermissionDenied):
        WB.self_check_in(KID, q.pupil_id, {"mood_rating": 4})
    res = WB.survey_results(s.survey_id)
    assert res["pupils"] == 2 and res["responses"] == 1 and res["rate"] == 50.0
    assert [x.pupil_id for x in res["missing"]] == [q.pupil_id] and res["low"]
    with pytest.raises(WB.ValidationError):
        WB.delete_survey(s.survey_id, actor=ADMIN)
    with pytest.raises(WB.ValidationError):
        WB.save_survey({"title": "x", "open_date": "2026-02-02", "close_date": "2026-01-01"},
                       actor=ADMIN)
