"""Safeguarding (modules.safeguarding.domain.safeguarding + safeguarding_records)."""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.safeguarding.domain import safeguarding as SG
from education_system.systems.secondary.modules.safeguarding.domain import (
    safeguarding_records as SR,
)
from education_system.systems.secondary.modules.safeguarding.domain import (
    safeguarding_reports as SGR,
)
from education_system.systems.secondary.modules.pupils.domain import enrolment as EN
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
ANN = Principal(username="ann", role="teacher")
BOB = Principal(username="bob", role="teacher")
KID = Principal(username="kid", role="student")
LOGINS = [{"username": "ann", "display_name": "Ann Teacher", "email": "ann@school.org",
           "role": "teacher"},
          {"username": "bob", "display_name": "Bob Teacher", "email": None, "role": "teacher"},
          {"username": "admin2", "display_name": "Mrs Dsl", "email": "dsl@school.org",
           "role": "admin"}]
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


def _report(pupil, actor=ANN, **extra):
    return SG.report_concern({"pupil_id": pupil.admission_no,
                              "description": "Bruise on arm, said dad grabbed her",
                              "child_words": "Dad got cross and grabbed me", **extra},
                             actor=actor)


def _rows(sql, *args):
    with database.connect() as conn:
        return conn.execute(sql, args).fetchall()


# ── The old rules ────────────────────────────────────────────────────

def test_old_concern_fields_rules_actions_and_summaries():
    ava = _pupil()
    c = SG.raise_concern({"pupil_id": ava.pupil_id, "description": "Disclosed at break",
                          "incident_time": "10:45", "location": "Playground"}, actor=ADMIN)
    assert (c.category, c.severity, c.status, c.confidential) == (
        "Disclosure", "Medium", "Open", True)
    assert c.raised_date == TODAY.isoformat() and c.raised_by == "Mrs Dsl"
    with pytest.raises(SG.ValidationError) as e:
        SG.raise_concern({"pupil_id": ava.pupil_id, "incident_time": "25:00",
                          "status": "Referred", "category": "Nonsense"}, actor=ADMIN)
    text = " ".join(e.value.problems)
    for bit in ("Description is required", "HH:MM", "Referral body is required",
                "Category must be one of"):
        assert bit in text
    with pytest.raises(SG.ValidationError) as e:
        SG.set_status(c.concern_id, "Closed", actor=ADMIN)
    assert "Outcome is required" in str(e.value)
    # old category names still accepted
    old = SG.raise_concern({"pupil_id": ava.pupil_id, "description": "x",
                            "category": "Prevent / radicalisation", "severity": "Critical"},
                           actor=ADMIN)
    assert old.category == SG.PREVENT
    a = SG.add_action({"concern_id": c.concern_id, "action_type": "Parent contact",
                       "summary": "Rang mum", "due_date": TODAY.isoformat(),
                       "assigned_to": "Mrs Dsl"}, actor=ADMIN)
    assert a.outstanding and a.action_date == TODAY.isoformat()
    with pytest.raises(SG.ValidationError):
        SG.add_action({"concern_id": c.concern_id}, actor=ADMIN)
    s = SGR.concern_summary(c.concern_id, actor=ADMIN)
    assert s["action_count"] == 1 and s["by_type"] == {"Parent contact": 1}
    assert SG.complete_action(a.action_id, actor=ADMIN).completed_date
    assert SG.delete_action(a.action_id, actor=ADMIN)
    cs = SGR.cohort_summary(actor=ADMIN)
    assert cs["total"] == 2 and cs["open_critical"] == 1 and cs["by_category"][SG.PREVENT] == 1
    assert list(SGR.pupils_with_concerns(actor=ADMIN)) == [ava.pupil_id]
    c = SG.set_status(c.concern_id, "Closed", actor=ADMIN, outcome="Resolved")
    assert c.closed_date == TODAY.isoformat()
    # referral fields on the concern live in the referral store
    r = SG.update(old.concern_id, {"referral_body": "Police", "referral_reference": "P1"},
                  actor=ADMIN)
    assert (r.referral_body, r.referral_reference) == ("Police", "P1")
    assert SG.list_referrals(actor=ADMIN, concern_id=old.concern_id)[0].agency == "Police"
    with pytest.raises(SG.ValidationError) as e:
        SG.delete(old.concern_id, actor=ADMIN, reason="wrong")
    assert "referral was made" in str(e.value)
    assert SG.delete(c.concern_id, actor=ADMIN, reason="Logged for the wrong pupil")
    assert any(h["action"] == "delete" for h in SG.history(actor=ADMIN))


# ── Need to know ─────────────────────────────────────────────────────

def test_staff_report_and_see_only_their_own_status():
    ava = _pupil()
    rep, alert = _report(ava, body_map="Left upper arm, 3 finger marks",
                         immediate_action="Stayed with her, told DSL")
    assert alert == {} and rep.status.startswith("Received")
    c = SG.get(rep.concern_id, actor=ADMIN)
    assert c.status == SG.NEW and c.reported_by == "ann" and c.raised_by == "Ann Teacher"
    assert c.child_words.startswith("Dad") and "finger" in c.body_map
    # a reporter can't set DSL fields
    rep2, _ = SG.report_concern({"pupil_id": ava.pupil_id, "description": "x",
                                 "status": "Closed", "notes": "dsl only"}, actor=BOB)
    assert SG.get(rep2.concern_id, actor=ADMIN).status == SG.NEW
    assert SG.get(rep2.concern_id, actor=ADMIN).notes is None
    assert [m.concern_id for m in SG.my_reports(actor=ANN)] == [rep.concern_id]
    with pytest.raises(SG.PermissionDenied):
        SG.my_report(rep.concern_id, actor=BOB)
    for fn in (lambda: SG.get(rep.concern_id, actor=ANN),
               lambda: SG.list_concerns(actor=ANN),
               lambda: SGR.concern_summary(rep.concern_id, actor=ANN),
               lambda: SR.chronology(ava.pupil_id, actor=ANN),
               lambda: SR.transfer_file(ava.pupil_id, actor=ANN),
               lambda: SG.access_log(actor=ANN),
               lambda: SGR.export_csv("x.csv", actor=ANN)):
        with pytest.raises(SG.PermissionDenied):
            fn()
    with pytest.raises(SG.PermissionDenied):
        _report(ava, actor=KID)
    SG.add_information(rep.concern_id, "She said it happened again", actor=ANN)
    acts = SG.list_actions(rep.concern_id, actor=ADMIN)
    assert acts[0].action_type == "Further information"
    # DSL notes never reach the reporter's view
    SG.triage(rep.concern_id, actor=ADMIN, level="Referral to children's social care",
              note="Strategy discussion booked")
    assert SG.my_report(rep.concern_id, actor=ANN).status == "With the DSL"
    assert not hasattr(SG.my_report(rep.concern_id, actor=ANN), "notes")
    # The activity log carries ids only - never the child's words.
    log = (activity_log.log_path()).read_text()
    assert "grabbed" not in log and "safeguarding.report" in log


def test_reading_is_logged():
    ava = _pupil()
    rep, _ = _report(ava)
    SG.get(rep.concern_id, actor=ADMIN)
    SR.chronology(ava.pupil_id, actor=ADMIN)
    whats = [(a["what"], a["pupil_id"]) for a in SG.access_log(actor=ADMIN)]
    assert ("concern", ava.pupil_id) in whats and ("chronology", ava.pupil_id) in whats
    assert SG.access_log(actor=ADMIN, username="admin2")[0]["username"] == "admin2"
    assert SG.access_log(actor=ADMIN, username="ann") == []


# ── Urgent ───────────────────────────────────────────────────────────

def test_urgent_report_emails_the_team_without_details():
    ava = _pupil()
    rep, alert = _report(ava, immediate_danger=True)
    assert rep.urgent and alert["emails"] == 1 and alert["message_id"]
    body = _rows("SELECT address, subject, body FROM email_recipients")[0]
    assert body["address"] == "dsl@school.org" and "URGENT" in body["subject"]
    assert "grabbed" not in body["body"] and ava.legal_first_name not in body["body"]
    assert f"#{rep.concern_id}" in body["subject"]
    c = SG.get(rep.concern_id, actor=ADMIN)
    assert c.notified_count == 1 and not c.needs_phone_call and c.severity == "High"
    item = SGR.due(actor=ADMIN)[0]
    assert item["kind"] == "Triage" and item["overdue"] and item["what"].startswith("URGENT")
    assert SGR.my_day(actor=ADMIN)["urgent"] == 1 and SGR.my_day(actor=ANN) is None


def test_urgent_with_no_team_emails_needs_a_phone_call():
    ava = _pupil()
    SG.set_team_member("bob", {"team_role": "DSL", "phone": "01234 567890"}, actor=ADMIN)
    assert [m["name"] for m in SG.team()] == ["Bob Teacher"]
    rep, alert = _report(ava, urgent="yes")
    assert alert["emails"] == 0 and alert["phone"][0]["phone"] == "01234 567890"
    c = SG.get(rep.concern_id, actor=ADMIN)
    assert c.needs_phone_call
    assert SGR.due(actor=ADMIN)[0]["kind"] == "Phone the DSL"
    SG.record_phoned(rep.concern_id, actor=ANN, who="Bob Teacher")
    assert not SG.get(rep.concern_id, actor=ADMIN).needs_phone_call
    with pytest.raises(SG.ValidationError):
        SG.set_team_member("nobody", {}, actor=ADMIN)
    with pytest.raises(SG.PermissionDenied):
        SG.set_team_member("ann", {}, actor=ANN)
    assert SG.remove_team_member("bob", actor=ADMIN)
    assert [m["username"] for m in SG.team()] == ["admin2"]   # falls back to lead logins


# ── Triage, referrals, closing ──────────────────────────────────────

def test_triage_referral_outcome_close_and_reopen():
    ava = _pupil()
    rep, _ = _report(ava)
    assert [c.concern_id for c in SG.awaiting_triage(actor=ADMIN)] == [rep.concern_id]
    with pytest.raises(SG.ValidationError):
        SG.triage(rep.concern_id, actor=ADMIN, level="")
    c = SG.triage(rep.concern_id, actor=ADMIN, level="Referral to children's social care",
                  severity="High", category="Physical abuse")
    assert (c.status, c.level_of_need, c.category, c.dsl_reviewer) == (
        "Open", "Referral to children's social care", "Physical abuse", "Mrs Dsl")
    r = SG.add_referral(c.concern_id, {"agency": "MASH / Social Care", "reference": "M-77"},
                        actor=ADMIN)
    assert r.pending and SG.get(c.concern_id, actor=ADMIN).status == "Referred"
    late = (TODAY - dt.timedelta(days=10)).isoformat()
    with database.connect() as conn:
        conn.execute("UPDATE safeguarding_referrals SET referral_date = ?", (late,))
        conn.execute("UPDATE safeguarding_concerns SET raised_date = ?", (late,))
    assert any(x["kind"] == "Referral" for x in SGR.due(actor=ADMIN))
    r = SG.record_referral_outcome(r.referral_id, actor=ADMIN, outcome="Section 47 enquiry")
    assert not r.pending
    with pytest.raises(SG.ValidationError):
        SG.add_referral(c.concern_id, {"agency": "LADO"}, actor=ADMIN)
    with pytest.raises(SG.ValidationError):
        SG.reopen(c.concern_id, actor=ADMIN, reason="x")      # still open
    SG.add_action({"concern_id": c.concern_id, "summary": "Core group",
                   "due_date": TODAY.isoformat()}, actor=ADMIN)
    c = SG.close_concern(c.concern_id, actor=ADMIN, outcome="CP plan in place")
    assert c.status == "Closed" and not [a for a in SG.list_actions(c.concern_id, actor=ADMIN)
                                         if a.outstanding]
    with pytest.raises(SG.ValidationError):
        SG.reopen(c.concern_id, actor=ADMIN, reason="")
    c = SG.reopen(c.concern_id, actor=ADMIN, reason="New disclosure")
    assert c.status == "Open" and c.closed_date is None
    kinds = [a.action_type for a in SG.list_actions(c.concern_id, actor=ADMIN)]
    for k in ("Triage", "Referral", "Referral outcome", "Case closed", "Case reopened"):
        assert k in kinds


def test_lado_needs_who_the_allegation_is_about():
    ava = _pupil()
    rep, _ = _report(ava)
    with pytest.raises(SG.ValidationError) as e:
        SG.triage(rep.concern_id, actor=ADMIN, level=SG.LADO_LEVEL)
    assert "allegation is about" in str(e.value)
    c = SG.triage(rep.concern_id, actor=ADMIN, level=SG.LADO_LEVEL, allegation_about="Mr X")
    r = SG.add_referral(c.concern_id, {"agency": "LADO"}, actor=ADMIN)
    assert r.agency == "LADO"
    assert SG.triage(_report(ava)[0].concern_id, actor=ADMIN,
                     level="No further action").status == "Closed"


# ── Plans and flags ─────────────────────────────────────────────────

def test_plans_flags_and_profile_line():
    ava = _pupil()
    with pytest.raises(SG.ValidationError) as e:
        SR.add_plan({"pupil_id": ava.pupil_id, "plan_type": SR.CP,
                     "start_date": TODAY.isoformat()}, actor=ADMIN)
    assert "category" in str(e.value)
    cp = SR.add_plan({"pupil_id": ava.pupil_id, "plan_type": SR.CP, "category": "Neglect",
                      "start_date": TODAY.isoformat(), "local_authority": "Kent",
                      "next_review": TODAY.isoformat()}, actor=ADMIN)
    with pytest.raises(SG.ValidationError) as e:
        SR.add_plan({"pupil_id": ava.pupil_id, "plan_type": SR.CP, "category": "Neglect",
                     "start_date": TODAY.isoformat()}, actor=ADMIN)
    assert "Overlaps" in str(e.value)
    SR.add_plan({"pupil_id": ava.pupil_id, "plan_type": SR.LAC,
                 "start_date": "2024-01-01"}, actor=ADMIN)
    f = SR.flags(ava.pupil_id, actor=ADMIN)
    assert f["cp"] and f["cp_category"] == "Neglect" and f["looked_after"]
    assert SR.profile_line(ava.pupil_id, actor=ADMIN).startswith("Safeguarding: CP plan")
    assert SR.profile_line(ava.pupil_id, actor=ANN) is None
    assert [p.plan_id for p in SR.plan_reviews_due(actor=ADMIN)] == [cp.plan_id]
    ended = SR.end_plan(cp.plan_id, actor=ADMIN, note="Stepped down to CIN")
    assert ended.end_date == TODAY.isoformat() and "Stepped down" in ended.notes
    tomorrow = TODAY + dt.timedelta(days=1)
    assert not SR.flags(ava.pupil_id, actor=ADMIN, today=tomorrow)["cp"]
    with pytest.raises(SG.PermissionDenied):
        SR.add_plan({"pupil_id": ava.pupil_id, "plan_type": SR.CIN,
                     "start_date": TODAY.isoformat()}, actor=ANN)


def test_looked_after_falls_back_to_admissions():
    ava = _pupil()
    from education_system.systems.secondary.modules.admissions.domain import admissions  # noqa: F401
    with database.connect() as conn:
        conn.execute(
            "INSERT INTO applications (route, academic_year, year_group, legal_first_name, "
            "legal_last_name, date_of_birth, gender, looked_after, parent_name, "
            "parent_relationship, received_date, status, admitted_pupil_id) VALUES "
            "('in_year', '2021/22', 7, 'A', 'B', '2011-01-15', 'Female', 'previous', 'Mum', "
            "'Mother', '2021-06-01', 'admitted', ?)", (ava.pupil_id,))
    f = SR.flags(ava.pupil_id, actor=ADMIN)
    assert f["previously_looked_after"] and f["from_admissions"]
    assert "Previously looked after (from admissions)" in f["labels"]
    SR.add_plan({"pupil_id": ava.pupil_id, "plan_type": SR.LAC,
                 "start_date": TODAY.isoformat()}, actor=ADMIN)
    f = SR.flags(ava.pupil_id, actor=ADMIN)       # a recorded plan wins
    assert f["looked_after"] and not f["previously_looked_after"] and not f["from_admissions"]


# ── Prevent ──────────────────────────────────────────────────────────

def test_prevent_referral_is_a_concern():
    ava = _pupil()
    pr = SR.create_prevent({"pupil_id": ava.pupil_id, "description": "Sharing extremist video",
                            "prevent_type": "Far-right extremism", "risk_level": "High",
                            "pathway": "Channel referral (Prevent)",
                            "referral_date": TODAY.isoformat(), "referral_ref": "CH-1",
                            "indicators": "Language change"}, actor=ADMIN)
    c = pr.concern
    assert c.category == SG.PREVENT and c.severity == "High"
    assert c.level_of_need == "Prevent / Channel" and c.referral_body == "Channel (Prevent)"
    assert [x.referral_id for x in SR.list_prevent(actor=ADMIN, open_only=True)] == \
        [c.concern_id]
    pr = SR.update_prevent(c.concern_id, {"channel_status": "Channel panel"}, actor=ADMIN)
    assert pr.concern.status == "Escalated"
    pr = SR.close_prevent(c.concern_id, actor=ADMIN, status="Closed — supported",
                          outcome="Supported", notes="Mentoring done")
    assert pr.concern.status == "Closed" and "Mentoring" in pr.concern.outcome
    assert SR.list_prevent(actor=ADMIN, open_only=True) == []
    assert SR.prevent_summary(actor=ADMIN)["channel"] == 1
    SG.reopen(c.concern_id, actor=ADMIN, reason="New posts")
    assert SR.get_prevent(c.concern_id, actor=ADMIN).channel_status == "Open"


# ── Chronology and transfer ─────────────────────────────────────────

def test_chronology_transfer_file_and_record_transfer(tmp_path):
    ava = _pupil(upn=None)
    rep, _ = _report(ava, incident_date=(TODAY - dt.timedelta(days=3)).isoformat())
    SG.triage(rep.concern_id, actor=ADMIN, level="Early help")
    SR.add_plan({"pupil_id": ava.pupil_id, "plan_type": SR.EARLY_HELP,
                 "start_date": TODAY.isoformat()}, actor=ADMIN)
    chron = SR.chronology(ava.pupil_id, actor=ADMIN)
    assert chron[0]["kind"] == "Concern" and "Dad got cross" in chron[0]["text"]
    assert {"Triage", "Plan"} <= {e["kind"] for e in chron}
    EN.record_leaver(ava.pupil_id, leaving_date=TODAY.isoformat(), reason=EN.MOVED_SCHOOL,
                     actor=ADMIN, details={"destination_school": "Hill High"})
    due = SR.leavers_to_transfer(actor=ADMIN)
    assert [x["pupil"].pupil_id for x in due] == [ava.pupil_id]
    assert due[0]["destination"] == "Hill High"
    text = SR.transfer_file(ava.pupil_id, actor=ADMIN)
    assert "CONFIDENTIAL - CHILD PROTECTION FILE" in text and "Hill High" in text
    assert "Dad got cross" in text and "Early help" in text
    with pytest.raises(SG.ValidationError):
        SR.record_transfer(ava.pupil_id, {}, actor=ADMIN)
    t = SR.record_transfer(ava.pupil_id, {"method": "Secure electronic transfer"},
                           actor=ADMIN)
    assert t.destination == "Hill High"
    assert SG.get(rep.concern_id, actor=ADMIN).status == "Transferred"
    assert SR.leavers_to_transfer(actor=ADMIN) == []
    t = SR.receipt_confirmed(t.transfer_id, actor=ADMIN, received_by="Mr New DSL")
    assert t.received_date == TODAY.isoformat()
    assert any(a["what"] == "transfer file" for a in SG.access_log(actor=ADMIN,
                                                                     pupil_id=ava.pupil_id))
    with pytest.raises(SG.ValidationError):
        SG.delete(rep.concern_id, actor=ADMIN, reason="x")
    # the record outlives a delete attempt on the pupil
    with pytest.raises(P.ValidationError):
        P.delete_pupil(ava.pupil_id, actor=ADMIN, reason="error")


def test_reports_and_export(tmp_path):
    ava, ben = _pupil(), _pupil(year_group=8, form_group="8B", date_of_birth="2013-03-01",
                             admission_date="2024-09-01")
    _report(ava, category="Neglect")
    _report(ben, category="Online safety")
    g = {x["group"]: x for x in SGR.analysis(actor=ADMIN, by="category")}
    assert g["Neglect"]["concerns"] == 1 and g["Online safety"]["pupils"] == 1
    assert {x["group"] for x in SGR.analysis(actor=ADMIN, by="year")} == {"Year 10", "Year 8"}
    with pytest.raises(SG.ValidationError):
        SGR.analysis(actor=ADMIN, by="nope")
    out = tmp_path / "sg.csv"
    assert SGR.export_csv(out, actor=ADMIN) == 2
    rows = list(csv.reader(out.open()))
    assert rows[0][0] == "id" and "grabbed" not in out.read_text()
    assert [c.pupil_year for c in SG.list_concerns(actor=ADMIN, year_group=8)] == [8]
