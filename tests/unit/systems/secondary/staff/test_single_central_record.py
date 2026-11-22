"""Single central record (modules.staff.domain.single_central_record)."""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.curriculum.domain import cover as CV
from education_system.systems.secondary.modules.staff.domain import single_central_record as SCR
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
ANN = Principal(username="ann", role="teacher")
LOGINS = [{"username": u, "display_name": n, "email": f"{u}@school.org", "role": "teacher"}
          for u, n in (("ann", "Ann Teacher"), ("head", "Mr Head"))]
TODAY = dt.date.today()
PAST = (TODAY - dt.timedelta(days=100)).isoformat()
CERT = "001234567890"


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


def _all_clear(p):
    for t in SCR.required_checks(p):
        data = {"check_type": t, "status": "Clear", "checked_on": PAST, "reference": "seen"}
        if t == SCR.DBS:
            data = {"check_type": t, "status": "Cleared", "dbs_number": CERT,
                    "issued_on": PAST, "checked_on": PAST}
        SCR.add_check(p.person_id, data, actor=ADMIN)


def test_required_checks_by_category():
    teacher = SCR.create_person({"username": "ann", "teaching_role": True,
                                 "start_date": PAST}, actor=ADMIN)
    assert teacher.full_name == "Ann Teacher" and teacher.category == "Staff"
    assert SCR.required_checks(teacher) == (
        "Identity", "Qualifications", "DBS", "Barred list", "Prohibition from teaching",
        "Right to work", "References", "Medical fitness")
    gov = SCR.create_person({"full_name": "G. Vernor", "category": "Governor"}, actor=ADMIN)
    assert SCR.required_checks(gov) == ("Identity", "DBS", "Section 128")
    vol = SCR.create_person({"full_name": "Val", "category": "Volunteer",
                             "regulated_activity": False, "lived_overseas": True}, actor=ADMIN)
    assert SCR.required_checks(vol) == ("Identity", "Overseas", "References")
    head = SCR.create_person({"username": "head", "leadership_role": True,
                              "childcare_relevant": True}, actor=ADMIN)
    assert {"Section 128", "Disqualification by association"} <= set(
        SCR.required_checks(head))
    with pytest.raises(SCR.ValidationError):
        SCR.create_person({"username": "ann"}, actor=ADMIN)      # already on the record
    with pytest.raises(SCR.ValidationError):
        SCR.create_person({"username": "nobody"}, actor=ADMIN)
    with pytest.raises(SCR.PermissionDenied):
        SCR.create_person({"full_name": "X"}, actor=ANN)
    with pytest.raises(SCR.PermissionDenied):
        SCR.list_people(actor=ANN)


def test_states_missing_expired_overdue_and_complete():
    p = SCR.create_person({"username": "ann", "start_date": PAST}, actor=ADMIN)
    st = SCR.person_status(p)
    assert set(v["state"] for v in st.values()) == {"missing"}
    _all_clear(p)
    assert all(v["state"] == "ok" for v in SCR.person_status(p).values())
    rtw = SCR.add_check(p.person_id, {"check_type": "Right to work", "status": "Clear",
                                      "checked_on": PAST, "issued_on": PAST,
                                      "expires_on": (TODAY - dt.timedelta(days=1)).isoformat()},
                        actor=ADMIN)
    assert rtw.checked_by == "admin2"                          # who checked: filled in
    assert SCR.person_status(p)["Right to work"]["state"] == "expired"
    dbs = [c for c in SCR.checks_for_person(p.person_id, actor=ADMIN) if c.check_type == "DBS"][0]
    dbs = SCR.subscribe_update_service(dbs.check_id, update_id="C123", actor=ADMIN,
                                       next_check_due=(TODAY - dt.timedelta(days=2)).isoformat())
    assert dbs.status == "Update Service Active" and dbs.update_check_overdue
    probs = {(x["check"], x["state"]) for x in SCR.problems(actor=ADMIN)}
    assert probs == {("Right to work", "expired"), ("DBS", "overdue")}
    dbs = SCR.record_update_check(dbs.check_id, actor=ADMIN)
    assert dbs.next_update_check_due == (TODAY + dt.timedelta(days=365)).isoformat()
    rem = SCR.reminders(actor=ADMIN, within_days=400)
    assert {r["what"] for r in rem} >= {"Update Service status check", "Right to work expires"}
    s = SCR.summary(actor=ADMIN)
    assert s["people"] == 1 and s["dbs_active"] == 1 and s["update_service_subscribed"] == 1


def test_dbs_rules_and_old_actions():
    p = SCR.create_person({"full_name": "Sam Gov", "category": "Governor"}, actor=ADMIN)
    with pytest.raises(SCR.ValidationError) as e:
        SCR.add_check(p.person_id, {"check_type": "DBS", "status": "Cleared",
                                    "dbs_number": "12ab"}, actor=ADMIN)
    assert len(e.value.problems) == 2
    with pytest.raises(SCR.ValidationError, match="DBS details"):
        SCR.add_check(p.person_id, {"check_type": "Identity", "dbs_number": CERT}, actor=ADMIN)
    with pytest.raises(SCR.ValidationError, match="future"):
        SCR.add_check(p.person_id, {"check_type": "Identity", "status": "Clear",
                                    "checked_on": (TODAY + dt.timedelta(days=3)).isoformat()},
                      actor=ADMIN)
    c = SCR.add_check(p.person_id, {"check_type": "DBS"}, actor=ADMIN)
    assert (c.status, c.dbs_level) == ("Applied", "Enhanced with Barred List")
    c = SCR.issue_certificate(c.check_id, dbs_number="0012 3456 7890", actor=ADMIN)
    assert c.status == "Cleared" and c.dbs_number == CERT and c.issued_on
    c = SCR.see_certificate(c.check_id, actor=ADMIN)
    assert c.certificate_seen_on == TODAY.isoformat() and c.unsigned
    c = SCR.sign_off(c.check_id, signed_off_by="Head", actor=ADMIN)
    assert not c.unsigned
    with pytest.raises(SCR.ValidationError):
        SCR.complete_risk_assessment(c.check_id, outcome="", actor=ADMIN)
    assert SCR.complete_risk_assessment(c.check_id, outcome="Low", actor=ADMIN).risk_assessment_outcome == "Low"
    assert SCR.start_renewal(c.check_id, actor=ADMIN).status == "Renewing"
    assert SCR.mark_lapsed(c.check_id, actor=ADMIN).status == "Lapsed"
    assert SCR.person_status(p)["DBS"]["state"] == "problem"
    ident = SCR.add_check(p.person_id, {"check_type": "Identity", "status": "Clear"},
                          actor=ADMIN)
    with pytest.raises(SCR.ValidationError):
        SCR.mark_lapsed(ident.check_id, actor=ADMIN)
    assert SCR.list_checks(actor=ADMIN, check_type="DBS", status="Lapsed")
    with pytest.raises(SCR.ValidationError):
        SCR.delete_person(p.person_id, actor=ADMIN)
    assert SCR.record_leaving(p.person_id, actor=ADMIN, end_date=PAST).end_date == PAST
    assert SCR.list_people(actor=ADMIN) == []
    assert SCR.history(p.person_id)


def test_supply_link_and_roster_dbs_kept_in_step():
    s = CV.create_supply({"full_name": "Sid Supply", "agency_name": "TeachCo"}, actor=ADMIN)
    s2 = CV.create_supply({"full_name": "Pat Supply", "dbs_cleared": True,
                           "dbs_checked_on": PAST}, actor=ADMIN)
    assert len(SCR.missing_people(actor=ADMIN)["supply"]) == 2
    assert SCR.sync_supply(actor=ADMIN) == 2
    people = {p.full_name: p for p in SCR.list_people(actor=ADMIN, category="Supply")}
    sid = people["Sid Supply"]
    assert sid.supply_id == s.supply_id and sid.agency_name == "TeachCo"
    assert "Agency confirmation" in SCR.required_checks(sid)
    # Pat: roster says cleared, the SCR has only a check to confirm -> flagged
    pat = people["Pat Supply"]
    flagged = [x for x in SCR.problems(actor=ADMIN) if x["person"].person_id == pat.person_id
               and "roster" in x["detail"]]
    assert flagged
    SCR.add_check(sid.person_id, {"check_type": "DBS", "status": "Cleared",
                                  "dbs_number": CERT, "issued_on": PAST}, actor=ADMIN)
    assert CV.get_supply(s.supply_id).dbs_cleared                  # roster updated
    c = [c for c in SCR.checks_for_person(pat.person_id, actor=ADMIN)][0]
    SCR.update_check(c.check_id, {"status": "Refused"}, actor=ADMIN)
    assert not CV.get_supply(s2.supply_id).dbs_cleared
    assert SCR.sync_supply(actor=ADMIN) == 0
    with pytest.raises(SCR.ValidationError):
        SCR.create_person({"category": "Staff", "supply_id": s.supply_id,
                           "full_name": "X"}, actor=ADMIN)


def test_logins_export_and_text(tmp_path):
    assert SCR.add_from_logins(actor=ADMIN) == 2
    assert SCR.missing_people(actor=ADMIN)["logins"] == []
    ann = SCR.find_person("ann")
    _all_clear(ann)
    SCR.create_person({"full_name": "=cmd()", "category": "Contractor"}, actor=ADMIN)
    out = tmp_path / "scr.csv"
    assert SCR.export_csv(out, actor=ADMIN) == 3
    rows = {r["name"]: r for r in csv.DictReader(out.open(encoding="utf-8"))}
    assert rows["Ann Teacher"]["DBS: number"] == CERT and rows["Ann Teacher"]["outstanding"] == ""
    assert rows["'=cmd()"]["Section 128: status"] == "n/a"
    assert rows["Mr Head"]["Identity: status"] == "MISSING"
    text = SCR.scr_text(actor=ADMIN)
    assert "Ann Teacher" in text and "MISSING" in text and CERT in text
    only = SCR.record(actor=ADMIN, problems_only=True)
    assert {p.full_name for p, _s in only} == {"Mr Head", "=cmd()"}
