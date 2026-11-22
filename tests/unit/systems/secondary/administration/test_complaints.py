"""Complaints (modules.administration.domain.complaints)."""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.administration.domain import complaints as CM
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
ANN = Principal(username="ann", role="teacher")
BOB = Principal(username="bob", role="teacher")
LOGINS = [{"username": u, "display_name": n, "email": f"{u}@school.org", "role": "teacher"}
          for u, n in (("ann", "Ann Teacher"), ("bob", "Bob Teacher"))]
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


def _new(**extra):
    data = {"complainant_name": "Mrs Parent", "contact_email": "parent@example.org",
            "subject": "Homework load in maths", "category": "Teaching & Learning",
            "received_on": TODAY.isoformat(), **extra}
    return CM.create_complaint(data, actor=ADMIN)


def test_old_fields_rules_and_summary(tmp_path):
    c = _new(severity=4, stage="Informal")
    assert (c.stage, c.status, c.complainant_role, c.severity_label) == (
        CM.STAGE_1, "Received", "Parent / Carer", "Serious")
    # Deadlines in school days (no calendar: weekdays).
    assert c.ack_due == CM.school_days_after(TODAY, 5).isoformat()
    assert c.target_response_date == CM.school_days_after(TODAY, 10).isoformat()
    with pytest.raises(CM.ValidationError) as e:
        CM.create_complaint({"severity": 9, "category": "Nope", "status": "Closed",
                             "closed_on": "1999-01-01", "contact_email": "bad"}, actor=ADMIN)
    text = " ".join(e.value.problems)
    for bit in ("Complainant name is required", "Subject is required", "Severity must be 1-5",
                "Category must be", "doesn't look like", "before the complaint"):
        assert bit in text
    anon = CM.create_complaint({"complainant_role": "Anonymous", "subject": "Litter"},
                               actor=ADMIN)
    assert anon.complainant_name == "Anonymous"
    assert CM.update_complaint(c.complaint_id, {"notes": "Called"}, actor=ADMIN).notes == \
        "Called"
    with pytest.raises(CM.ValidationError):
        CM.update_complaint(c.complaint_id, {"stage": "Stage 2 - Formal"}, actor=ADMIN)
    s = CM.summary()
    assert s.total == 2 and s.open_count == 2 and s.serious_or_major == 1
    assert CM.list_complaints(subject_like="maths")[0].complaint_id == c.complaint_id
    out = tmp_path / "c.csv"
    assert CM.export_csv(out, actor=ADMIN) == 2
    assert list(csv.reader(out.open()))[0][0] == "id"
    assert CM.delete_complaint(anon.complaint_id, actor=ADMIN)
    assert CM.get_complaint(anon.complaint_id) is None


def test_stage_1_with_staff_member_then_escalate_to_head_and_panel():
    c = _new(assigned_to="Ann Teacher")
    with pytest.raises(CM.PermissionDenied):
        CM.create_complaint({"complainant_name": "x", "subject": "y"}, actor=ANN)
    assert [x.complaint_id for x in CM.list_complaints(actor=ANN)] == [c.complaint_id]
    assert CM.list_complaints(actor=BOB) == []
    with pytest.raises(CM.PermissionDenied):
        CM.add_event(c.complaint_id, {"summary": "x"}, actor=BOB)
    c = CM.acknowledge(c.complaint_id, actor=ANN)
    assert c.status == "Acknowledged" and c.acknowledged_on == TODAY.isoformat()
    CM.add_event(c.complaint_id, {"event_type": "Phone call", "summary": "Spoke to mum"},
                 actor=ANN)
    with pytest.raises(CM.ValidationError) as e:
        CM.escalate(c.complaint_id, actor=ADMIN, to_stage=CM.STAGE_2)
    assert "Wait for the" in " ".join(e.value.problems)
    c = CM.issue_response(c.complaint_id, actor=ANN, summary="Homework reduced",
                          outcome="Partially Upheld")
    assert c.status == "Response Issued" and c.complainant_informed
    with pytest.raises(CM.PermissionDenied):
        CM.escalate(c.complaint_id, actor=ANN, to_stage=CM.STAGE_2)
    c = CM.escalate(c.complaint_id, actor=ADMIN, to_stage="Formal Stage 1", reason="Unhappy")
    assert (c.stage, c.status, c.outcome, c.escalated_to_stage_2) == (
        CM.STAGE_2, "Escalated", None, True)
    assert c.target_response_date == CM.school_days_after(TODAY, 15).isoformat()
    assert not CM.can_handle_stage_1(ANN, c) and CM.can_see(ANN, c)
    with pytest.raises(CM.PermissionDenied):
        CM.issue_response(c.complaint_id, actor=ANN, summary="x", outcome="Upheld")
    c = CM.issue_response(c.complaint_id, actor=ADMIN, summary="Head agrees",
                          outcome="Not Upheld")
    c = CM.escalate(c.complaint_id, actor=ADMIN, to_stage=CM.STAGE_3)
    assert c.governors_informed and c.escalated_to_appeal
    with pytest.raises(CM.ValidationError) as e:
        CM.issue_response(c.complaint_id, actor=ADMIN, summary="x", outcome="Upheld")
    assert "governors' panel" in " ".join(e.value.problems)
    with pytest.raises(CM.ValidationError) as e:
        CM.set_panel(c.complaint_id, actor=ADMIN, panel_date=TODAY.isoformat(),
                     members="Gov A, Ann Teacher")
    text = " ".join(e.value.problems)
    assert "at least 3" in text and "involved" in text
    c = CM.set_panel(c.complaint_id, actor=ADMIN, panel_date=TODAY.isoformat(),
                     members=["Gov A", "Gov B", "Gov C"])
    c = CM.issue_response(c.complaint_id, actor=ADMIN, summary="Panel decision",
                          outcome="Not Upheld")
    c = CM.close_complaint(c.complaint_id, actor=ADMIN)
    assert c.status == "Closed" and c.closed_on == TODAY.isoformat()
    with pytest.raises(CM.ValidationError):
        CM.delete_complaint(c.complaint_id, actor=ADMIN)
    kinds = [e.event_type for e in CM.list_events(c.complaint_id)]
    assert kinds.count("Escalated") == 2 and "Panel" in kinds and "Phone call" in kinds
    rep = CM.annual_report(CM.year_of(TODAY.isoformat()))
    assert rep["received"] == 1 and rep["by_stage_reached"][CM.STAGE_3] == 1
    assert rep["panels"] == 1 and rep["on_time_pct"] == 100.0


def test_overdue_withdraw_and_close_rules():
    old = (TODAY - dt.timedelta(days=40)).isoformat()
    c = _new(received_on=old)
    lates = {what for x, what, _due in CM.overdue() if x.complaint_id == c.complaint_id}
    assert lates == {"Acknowledgement", f"{CM.STAGE_1} response"}
    assert CM.list_complaints(overdue_only=True)[0].complaint_id == c.complaint_id
    # The response is overdue, so the complainant may escalate without it.
    assert not CM.escalation_problems(c, CM.STAGE_2)
    with pytest.raises(CM.ValidationError):
        CM.close_complaint(c.complaint_id, actor=ADMIN)
    c = CM.withdraw(c.complaint_id, actor=ADMIN, reason="Sorted informally")
    assert c.outcome == "Withdrawn" and c.status == "Closed"
    c = CM.set_status(c.complaint_id, "Under Investigation", actor=ADMIN)
    assert c.closed_on is None
    assert CM.record_satisfaction(c.complaint_id, actor=ADMIN,
                                  satisfaction="Satisfied").complainant_satisfaction == \
        "Satisfied"


def test_unreasonable_and_serial_complainants_and_other_procedures():
    a = _new()
    _new(subject="Uniform policy")
    with pytest.raises(CM.ValidationError):
        CM.flag_unreasonable(a.complaint_id, True, actor=ADMIN)
    CM.flag_unreasonable(a.complaint_id, True, actor=ADMIN, notes="One contact per week")
    assert all(c.unreasonable for c in CM.list_complaints())       # both from Mrs Parent
    warn = CM.check({"complainant_name": "Mrs Parent", "contact_email": "parent@example.org",
                     "subject": "Maths homework again", "category": "Admissions"},
                    actor=ADMIN)
    text = " ".join(warn)
    assert "unreasonable" in text and "complaint number 3" in text and "appeal panel" in text
    serial = CM.serial_complainants(min_count=2)
    assert serial[0]["count"] == 2 and serial[0]["flagged"]
    CM.flag_unreasonable(a.complaint_id, False, actor=ADMIN)
    assert not any(c.unreasonable for c in CM.list_complaints())


def test_letters_go_through_the_outbox():
    p = P.create_pupil({"legal_first_name": "Ava", "legal_last_name": "Test",
                        "date_of_birth": "2011-01-15", "gender": "Female", "year_group": 10,
                        "form_group": "10A", "admission_date": "2021-09-01"}, actor=ADMIN)
    c = _new(pupil_id=p.admission_no)
    assert c.pupil_id == p.pupil_id and c.pupil_name == "Ava Test"
    assert CM.list_complaints(pupil_id=p.pupil_id)
    sent = CM.send_letter(c.complaint_id, "acknowledgement", actor=ADMIN)
    assert sent["emails"] == 1
    with pytest.raises(CM.ValidationError):
        CM.send_letter(c.complaint_id, "response", actor=ADMIN)
    CM.issue_response(c.complaint_id, actor=ADMIN, summary="We will review it",
                      outcome="Upheld")
    CM.send_letter(c.complaint_id, "response", actor=ADMIN)
    with database.connect() as conn:
        bodies = [r[0] for r in conn.execute("SELECT body FROM email_recipients")]
    assert "We aim to send you a full response by" in bodies[0]
    assert "We will review it" in bodies[1] and "within 10 school days" in bodies[1]
    none = _new(contact_email="")
    assert CM.send_letter(none.complaint_id, "acknowledgement", actor=ADMIN)["emails"] == 0
    assert any(h["action"] == "letter" for h in CM.history(c.complaint_id))
