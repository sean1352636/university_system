"""Attendance concerns (modules.attendance.domain.attendance_concerns)."""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.attendance.domain import attendance as AT
from education_system.systems.secondary.modules.curriculum.domain import year_groups as YG
from education_system.systems.secondary.modules.attendance.domain import attendance_concerns as AC
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
ANN = Principal(username="ann", role="teacher")
HEAD = Principal(username="head", role="teacher")
LOGINS = [{"username": u, "display_name": n, "email": f"{u}@school.org", "role": "teacher"}
          for u, n in (("ann", "Ann Teacher"), ("head", "Mr Head"))]

TODAY = dt.date.today()
MON = TODAY - dt.timedelta(days=TODAY.weekday()) - dt.timedelta(days=21)
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


_n = 0


def _pupil(**extra):
    global _n
    _n += 1
    return P.create_pupil({
        "legal_first_name": f"Pupil{_n}", "legal_last_name": f"Test{_n:03d}",
        "date_of_birth": "2011-01-15", "gender": "Female", "year_group": 10,
        "form_group": "10A", "admission_date": "2021-09-01", **extra}, actor=ADMIN)


def _present(p, start, end):
    AT.record_range(p.pupil_id, start, end, "/", actor=ADMIN, sessions=("AM",))
    AT.record_range(p.pupil_id, start, end, "\\", actor=ADMIN, sessions=("PM",))


def _absent_pupil():
    """Two weeks present, one week of unauthorised absence (10 sessions)."""
    p = _pupil()
    _present(p, MON, FRI + dt.timedelta(days=7))
    AT.record_range(p.pupil_id, MON + dt.timedelta(days=14), FRI + dt.timedelta(days=14), "O",
                    actor=ADMIN)
    return p


def test_old_fields_rules_and_summary():
    p = _pupil()
    c = AC.create({"pupil_id": p.admission_no, "attendance_pct": "86", "key_worker": "Ms K",
                   "intervention": "Morning check-in"}, actor=ADMIN)
    assert (c.concern_type, c.status, c.stage, c.threshold_pct) == (
        "Persistent absence", "Open", "Concern noted", 90.0)
    assert c.level == "Moderate (85-89%)" and c.next_review_date > c.opened_date
    assert c.academic_year == AC.year_of(c.opened_date)
    with pytest.raises(AC.ValidationError) as e:
        AC.create({"pupil_id": p.pupil_id}, actor=ADMIN)
    assert "already has an open case" in " ".join(e.value.problems)
    with pytest.raises(AC.ValidationError) as e:
        AC.update(c.concern_id, {"next_review_date": "2000-01-01", "status": "Nope",
                                 "attendance_pct": "120"}, actor=ADMIN)
    text = " ".join(e.value.problems)
    for bit in ("before opened date", "Status must be", "between 0 and 100"):
        assert bit in text
    closed = AC.close(c.concern_id, actor=ADMIN, reason="Back to 96%")
    assert closed.status == "Closed" and closed.closed_date == TODAY.isoformat()
    reopened = AC.set_status(c.concern_id, "Monitoring", actor=ADMIN)
    assert reopened.closed_date is None
    s = AC.cohort_summary()
    assert s["total"] == 1 and s["open"] == 1 and s["by_stage"] == {"Concern noted": 1}
    assert AC.delete(c.concern_id, actor=ADMIN)
    assert AC.get_concern(c.concern_id) is None


def test_figures_come_from_the_registers():
    p = _absent_pupil()
    s = AC.figures(p.pupil_id, MON, TODAY)
    assert s.attendance_pct == pytest.approx(66.7, abs=0.1)
    assert [x.pupil_id for x, _s in AC.candidates()] == [p.pupil_id]
    trend = AC.weekly_trend(p.pupil_id, weeks=4)
    assert [w["pct"] for w in trend] == [100.0, 100.0, 0.0]
    t = AC.penalty_threshold(p.pupil_id)
    assert t["sessions"] == 10 and t["met"]
    made = AC.open_from_attendance([p.pupil_id], actor=ADMIN)
    c = made["created"][0]
    assert c.attendance_pct is not None and c.target_pct == 90.0
    assert AC.candidates() == []
    assert AC.open_from_attendance([p.pupil_id], actor=ADMIN)["skipped"]
    assert [x.concern_id for x, _t in AC.penalty_watch()] == [c.concern_id]
    d = AC.dashboard()
    assert d["school"]["persistent"] == 1 and d["by_year"][0]["open"] == 1
    assert d["by_form"][0]["group"] == "10A"


def test_permissions_tutor_and_head_of_year_notes():
    p = _pupil()
    with pytest.raises(AC.PermissionDenied):
        AC.create({"pupil_id": p.pupil_id}, actor=ANN)
    c = AC.create({"pupil_id": p.pupil_id}, actor=ADMIN)
    assert AC.list_concerns()[0].concern_id == c.concern_id      # staff can read
    with pytest.raises(AC.PermissionDenied):
        AC.add_note(c.concern_id, {"summary": "Rang home"}, actor=HEAD)
    YG.update(10, {"head_of_year": "Mr Head"}, actor=ADMIN)
    n = AC.add_note(c.concern_id, {"action_type": "Phone call", "summary": "Rang home"},
                    actor=HEAD)
    assert n.action_type == "Phone call"
    with pytest.raises(AC.ValidationError):
        AC.add_note(c.concern_id, {"action_type": "LA referral", "summary": "x"}, actor=HEAD)
    with pytest.raises(AC.PermissionDenied):
        AC.delete_action(n.action_id, actor=HEAD)
    with pytest.raises(AC.PermissionDenied):
        AC.export_csv("x.csv", actor=Principal(username="kid", role="student"))
    assert any(h["action"] == "note" for h in AC.history(c.concern_id))


def test_stages_move_forward_and_support_comes_first():
    p = _absent_pupil()
    c = AC.create({"pupil_id": p.pupil_id}, actor=ADMIN)
    with pytest.raises(AC.ValidationError) as e:
        AC.advance_stage(c.concern_id, AC.NOTICE, actor=ADMIN)
    assert "Offer support first" in " ".join(e.value.problems)
    with pytest.raises(AC.ValidationError) as e:
        AC.refer_to_la(c.concern_id, "Penalty notice", actor=ADMIN)
    assert "notice to improve first" in " ".join(e.value.problems)
    c = AC.advance_stage(c.concern_id, AC.MEETING, actor=ADMIN,
                         meeting_date=TODAY.isoformat(), support_plan="Breakfast club")
    assert c.status == "Monitoring" and c.support_plan == "Breakfast club"
    with pytest.raises(AC.ValidationError) as e:
        AC.advance_stage(c.concern_id, "Letter 1", actor=ADMIN)
    assert "only move forward" in " ".join(e.value.problems)
    c = AC.advance_stage(c.concern_id, AC.NOTICE, actor=ADMIN)
    c = AC.refer_to_la(c.concern_id, "Penalty notice", actor=ADMIN)
    assert (c.stage, c.status, c.la_referral_type) == ("LA referral", "Escalated",
                                                       "Penalty notice")
    c = AC.record_la_outcome(c.concern_id, "Penalty notice issued", actor=ADMIN)
    assert c.la_outcome == "Penalty notice issued"
    with pytest.raises(AC.ValidationError):
        AC.delete(c.concern_id, actor=ADMIN)
    kinds = [a.action_type for a in AC.list_actions(c.concern_id)]
    assert kinds.count("Stage") == 3 and "LA referral" in kinds and "LA outcome" in kinds


def test_penalty_referral_needs_the_threshold():
    p = _pupil()
    _present(p, MON, FRI)
    c = AC.create({"pupil_id": p.pupil_id}, actor=ADMIN)
    with pytest.raises(AC.ValidationError) as e:
        AC.refer_to_la(c.concern_id, "Penalty notice", actor=ADMIN, leave_in_term_time=True)
    assert "threshold isn't met" in " ".join(e.value.problems)


def test_review_against_target_and_cme():
    p = _pupil()
    _present(p, MON, FRI)
    c = AC.create({"pupil_id": p.pupil_id, "attendance_pct": "80", "target_pct": "92",
                   "opened_date": MON.isoformat()}, actor=ADMIN)
    r = AC.record_review(c.concern_id, actor=ADMIN, summary="Much better")
    assert r["met"] and r["concern"].status == "Improving" and r["since"] == 100.0
    assert r["concern"].next_review_date > TODAY.isoformat()
    q = _pupil()
    AT.record_range(q.pupil_id, MON, TODAY - dt.timedelta(days=1), "N", actor=ADMIN)
    run = AC.unexplained_run(q.pupil_id)
    assert run >= 10
    assert [x.pupil_id for x, _n in AC.cme_watch()] == [q.pupil_id]
    cq = AC.create({"pupil_id": q.pupil_id, "concern_type": "Other"}, actor=ADMIN)
    assert any("missing education" in w for w in AC.check({}, actor=ADMIN,
                                                          concern_id=cq.concern_id))
    cq = AC.set_cme(cq.concern_id, True, actor=ADMIN, reported_date=TODAY.isoformat())
    assert cq.cme and AC.list_concerns(cme_only=True)[0].concern_id == cq.concern_id
    assert AC.cohort_summary()["cme"] == 1


def test_letters_go_through_the_outbox_and_move_the_stage(tmp_path):
    p = _absent_pupil()
    c = AC.create({"pupil_id": p.pupil_id, "target_pct": "95"}, actor=ADMIN)
    assert AC.send_letter(c.concern_id, "letter_1", actor=ADMIN)["no_email"]
    C.add_contact(p.pupil_id, {"full_name": "Mum Test", "relationship": "Mother",
                               "email": "mum@example.org"}, actor=ADMIN)
    with pytest.raises(AC.ValidationError) as e:
        AC.send_letter(c.concern_id, "meeting", actor=ADMIN)
    assert "meeting date" in " ".join(e.value.problems)
    sent = AC.send_letter(c.concern_id, "letter_1", actor=ADMIN, note="Please call us")
    assert sent["emails"] == 1 and AC.get(c.concern_id).stage == "Letter 1"
    with database.connect() as conn:
        body = conn.execute("SELECT body FROM email_recipients WHERE subject LIKE "
                            "'Attendance -%'").fetchone()[0]
    assert "concerned about" in body and "95%" in body and "Please call us" in body
    sent = AC.send_letter(c.concern_id, "meeting", actor=ADMIN,
                          meeting_date=(TODAY + dt.timedelta(days=3)).isoformat())
    assert AC.get(c.concern_id).stage == AC.MEETING
    assert any(a.action_type == "Letter sent" for a in AC.list_actions(c.concern_id))
    out = tmp_path / "ac.csv"
    assert AC.export_csv(out, actor=ADMIN) == 1
    rows = list(csv.reader(out.open()))
    assert rows[0][0] == "id" and rows[1][11] == AC.MEETING
    info = AC.for_pupil(p.pupil_id)
    assert info["open"].concern_id == c.concern_id and info["band"] == "persistent"
    assert [x.concern_id for x in AC.for_staff(ADMIN)] == [c.concern_id]
    assert AC.for_staff(ANN) == []
