"""Suspensions & exclusions (modules.behaviour.domain.exclusions)."""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.attendance.domain import attendance as AT
from education_system.systems.secondary.modules.curriculum.domain import year_groups as YG
from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
from education_system.systems.secondary.modules.behaviour.domain import exclusions as EX
from education_system.systems.secondary.modules.portals.domain import portal as PT
from education_system.systems.secondary.modules.pupils.domain import enrolment as EN
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


def _monday(d: dt.date) -> dt.date:
    return d - dt.timedelta(days=d.weekday())


TODAY = dt.date.today()
# A Monday a few weeks back, so registers can be marked (no calendar: weekdays count).
MON = _monday(TODAY) - dt.timedelta(days=21)
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


def _case(pupil, start=MON, end=FRI, actor=ADMIN, **extra):
    data = {"pupil_id": pupil.pupil_id, "start_date": start.isoformat(),
            "end_date": end.isoformat() if end else "", "reason": "Fighting at lunch",
            "reason_category": "Physical assault against a pupil",
            "decision_maker": "Mrs Head", **extra}
    return EX.create_case(data, actor=actor)


# ── The old rules ────────────────────────────────────────────────────

def test_old_case_fields_defaults_and_rules():
    ava = _pupil()
    c = _case(ava)
    assert (c.case_type, c.severity, c.status) == ("Fixed-term suspension", "High", "Open")
    assert c.days == 5                      # school days, filled in from the dates
    assert c.academic_year == EX.year_of(c.start_date)
    by_adm = EX.create_case({"pupil_id": ava.admission_no, "case_type": "Parental meeting",
                             "start_date": TODAY.isoformat(), "reason": "Catch up"},
                            actor=ADMIN)
    assert by_adm.pupil_id == ava.pupil_id and by_adm.days is None
    with pytest.raises(EX.ValidationError) as e:
        EX.create_case({"pupil_id": ava.pupil_id, "case_type": "Other",
                        "start_date": "2026-01-10", "end_date": "2026-01-01", "days": "400",
                        "status": "Appealed"}, actor=ADMIN)
    text = " ".join(e.value.problems)
    for bit in ("End date cannot be before", "Reason is required", "between 0 and 365",
                "Appeal decision is required"):
        assert bit in text
    upd = EX.set_status(by_adm.case_id, "Overturned", actor=ADMIN, appeal_decision="Agreed")
    assert upd.status == "Overturned"
    ev = EX.add_event({"case_id": c.case_id, "event_type": "Phone call",
                       "summary": "Rang mum"}, actor=ADMIN)
    assert ev.event_date == TODAY.isoformat()
    with pytest.raises(EX.ValidationError):
        EX.add_event({"case_id": c.case_id}, actor=ADMIN)
    assert [x.event_type for x in EX.list_events(c.case_id)] == ["Phone call"]
    EX.delete_event(ev.event_id, actor=ADMIN)
    s = EX.cohort_summary()
    assert s["total"] == 2 and s["by_type"]["Fixed-term suspension"] == 1
    assert s["total_days"] == 5 and s["pupils"] == 1
    assert EX.delete_case(by_adm.case_id, actor=ADMIN)
    assert EX.get_case(by_adm.case_id) is None


def test_only_the_headteachers_office_decides_but_staff_see_and_hoy_adds_events():
    ava = _pupil()
    with pytest.raises(EX.PermissionDenied):
        _case(ava, actor=ANN)
    c = _case(ava)
    assert EX.list_cases(year_group=10)[0].case_id == c.case_id   # staff can read
    with pytest.raises(EX.PermissionDenied):
        EX.update_case(c.case_id, {"notes": "x"}, actor=ANN)
    with pytest.raises(EX.PermissionDenied):
        EX.add_event({"case_id": c.case_id, "summary": "Work sent"}, actor=HEAD)
    YG.update(10, {"head_of_year": "Mr Head"}, actor=ADMIN)
    assert EX.add_event({"case_id": c.case_id, "event_type": "Work set",
                         "summary": "Work sent"}, actor=HEAD).event_type == "Work set"
    with pytest.raises(EX.PermissionDenied):
        EX.export_csv("x.csv", actor=Principal(username="kid", role="student"))


def test_formal_cases_need_dates_decider_and_category():
    ava = _pupil()
    with pytest.raises(EX.ValidationError) as e:
        EX.create_case({"pupil_id": ava.pupil_id, "start_date": MON.isoformat(),
                        "reason": "x"}, actor=ADMIN)
    text = " ".join(e.value.problems)
    assert "needs an end date" in text and "reason category" in text and "who decided" in text
    with pytest.raises(EX.ValidationError) as e:
        _case(ava, case_type="Permanent exclusion")
    assert "no end date" in " ".join(e.value.problems)
    sat = MON + dt.timedelta(days=5)
    with pytest.raises(EX.ValidationError) as e:
        _case(ava, start=sat, end=sat + dt.timedelta(days=2))
    assert "isn't a school day" in " ".join(e.value.problems)


def test_overlaps_and_the_45_day_limit():
    ava = _pupil()
    _case(ava)
    with pytest.raises(EX.ValidationError) as e:
        _case(ava, start=FRI, end=FRI + dt.timedelta(days=3))
    assert "Overlaps case" in " ".join(e.value.problems)
    # 5 days used: another 41 is too many in a year (start of the same year).
    start = MON + dt.timedelta(days=7)
    if EX.year_of(start.isoformat()) == EX.year_of(MON.isoformat()):
        with pytest.raises(EX.ValidationError) as e:
            _case(ava, start=start, end=start, days="41")
        assert "the limit is 45" in " ".join(e.value.problems)
        ok = _case(ava, start=start, end=start, days="40")
        assert EX.suspension_days(ava.pupil_id, academic_year=ok.academic_year) == 45
        # A withdrawn case stops counting.
        EX.withdraw(ok.case_id, actor=ADMIN, reason="Made in error")
        assert EX.suspension_days(ava.pupil_id, academic_year=ok.academic_year) == 5
        assert EX.get(ok.case_id).appeal_decision.startswith("Withdrawn")


def test_no_extending_once_the_family_is_told():
    ava = _pupil()
    c = _case(ava, end=MON + dt.timedelta(days=1))
    EX.record_parents_told(c.case_id, actor=ADMIN, how="Phone call", day=MON.isoformat())
    with pytest.raises(EX.ValidationError) as e:
        EX.update_case(c.case_id, {"end_date": FRI.isoformat()}, actor=ADMIN)
    assert "can't be extended" in " ".join(e.value.problems)
    shorter = EX.update_case(c.case_id, {"end_date": MON.isoformat()}, actor=ADMIN)
    assert shorter.days == 1      # days recounted from the new dates


def test_deadlines_governors_and_education_from_day_six():
    ava = _pupil()
    end = MON + dt.timedelta(days=7)      # Monday to the next Tuesday: 6 school days
    c = _case(ava, end=end)
    assert c.days == 6
    steps = {d["step"]: d for d in EX.deadlines(c.case_id)}
    assert steps["Tell the family (without delay)"]["overdue"]
    assert steps["Education from day 6"]["due"] == (MON + dt.timedelta(days=7)).isoformat()
    assert any(s.startswith("Governors consider reinstatement (if the parents ask)")
               for s in steps)
    assert steps["Reintegration meeting"]["due"] == (end + dt.timedelta(days=1)).isoformat()
    EX.record_notified(c.case_id, "la", actor=ADMIN)
    EX.update_case(c.case_id, {"provision_from": end.isoformat(),
                               "reintegration_date": TODAY.isoformat()}, actor=ADMIN)
    steps = {d["step"]: d for d in EX.deadlines(c.case_id)}
    assert steps["Tell the local authority"]["done"]
    assert steps["Education from day 6"]["done"] and steps["Reintegration meeting"]["done"]
    assert any(c2.case_id == c.case_id for c2, _d in EX.due())
    warnings = EX.check({"pupil_id": ava.pupil_id, "start_date": TODAY.isoformat(),
                         "end_date": TODAY.isoformat(), "reason": "x",
                         "reason_category": "Damage", "decision_maker": "Mrs Head"},
                        actor=ADMIN)
    assert any("already has 6" in w for w in warnings)


def test_permanent_exclusion_governors_review_and_off_roll(monkeypatch):
    ava = _pupil()
    c = _case(ava, end=None, case_type="Permanent exclusion", severity="Critical")
    assert EX.governors_required(c) == "must"
    assert "governors must consider" in " ".join(EX.off_roll_problems(c))
    with pytest.raises(EX.ValidationError):
        EX.remove_from_roll(c.case_id, actor=ADMIN)
    meet = MON + dt.timedelta(days=7)
    c = EX.record_governors(c.case_id, decision="Upheld", meeting_date=meet.isoformat(),
                            actor=ADMIN)
    assert c.status == "InProgress" and c.governors_decision == "Upheld"
    due = EX.review_deadline(c)
    assert due == meet + dt.timedelta(days=21)          # 15 school days later
    assert "independent review until" in " ".join(EX.off_roll_problems(c, today=due))
    # A review is asked for and quashes it: back to the governors.
    c = EX.record_review(c.case_id, actor=ADMIN, requested_date=(meet + dt.timedelta(days=2)
                                                                 ).isoformat())
    assert c.status == "Appealed"
    c = EX.record_review(c.case_id, actor=ADMIN, review_date=TODAY.isoformat(),
                         outcome="Quash")
    assert c.governors_decision is None
    c = EX.record_governors(c.case_id, decision="Upheld", actor=ADMIN)
    c = EX.record_review(c.case_id, actor=ADMIN, review_date=TODAY.isoformat(),
                         outcome="Upheld")
    assert not EX.off_roll_problems(c)
    assert [x.case_id for x in EX.ready_for_off_roll()] == [c.case_id]
    c = EX.remove_from_roll(c.case_id, actor=ADMIN)
    assert c.off_roll_date == TODAY.isoformat() and c.status == "Closed"
    p = P.get_pupil(ava.pupil_id)
    assert p.roll_status == "left" and p.leaving_reason == EN.EXCLUSION
    with pytest.raises(EX.ValidationError):
        EX.delete_case(c.case_id, actor=ADMIN)
    kinds = [e.event_type for e in EX.list_events(c.case_id)]
    assert kinds.count("Governors decision") == 2 and "Appeal lodged" in kinds


def test_governors_reinstate_overturns():
    ava = _pupil()
    c = _case(ava, end=None, case_type="Permanent exclusion")
    c = EX.record_governors(c.case_id, decision="Reinstated", actor=ADMIN)
    assert c.status == "Overturned" and not c.counts
    assert EX.out_on(MON + dt.timedelta(days=30)) == []


def test_attendance_marks_e_then_b():
    ava = _pupil()
    end = MON + dt.timedelta(days=7)
    c = _case(ava, end=end)
    EX.update_case(c.case_id, {"provision_from": end.isoformat()}, actor=ADMIN)
    got = EX.mark_attendance(c.case_id, actor=ADMIN)
    assert got["saved"] == 12            # 6 school days, AM and PM
    assert AT.get_for(ava.pupil_id, MON, "AM").code == "E"
    assert AT.get_for(ava.pupil_id, end, "PM").code == "B"
    assert EX.mark_attendance(c.case_id, actor=ADMIN)["saved"] == 0   # kept, not doubled
    assert [x.pupil_id for x in EX.out_on(MON)] == [ava.pupil_id]


def test_behaviour_link_concerns_notice_portal_and_export(tmp_path, monkeypatch):
    ava = _pupil()
    c = _case(ava)
    e = BH.log_incident({"pupil_id": ava.pupil_id, "incident_type": "Disruption",
                         "description": "Hit another pupil"}, actor=ADMIN)
    c2 = EX.from_behaviour(e.entry_id, {"case_type": "Internal exclusion",
                                        "start_date": TODAY.isoformat()}, actor=ADMIN)
    assert c2.related_entry_id == e.entry_id and c2.reason.startswith("Disruption")
    assert "Internal exclusion" in (BH.get(e.entry_id).action_taken or "")
    assert any(x["pupil_id"] == ava.pupil_id and "suspended 1 time" in x["reason"]
               for x in EX.concerns(today=MON))
    assert any("suspended" in " ".join(x["reasons"]) for x in BH.concerns(today=MON)
               if x["pupil_id"] == ava.pupil_id)
    # Not told yet: the portal doesn't show it.
    assert EX.for_family(ava.pupil_id, academic_year=c.academic_year) == []
    C.add_contact(ava.pupil_id, {"full_name": "Mum Test", "relationship": "Mother",
                                 "email": "mum@example.org"}, actor=ADMIN)
    sent = EX.notify_parents(c.case_id, actor=ADMIN)
    assert sent["emails"] == 1
    with database.connect() as conn:
        body = conn.execute("SELECT body FROM email_recipients WHERE subject LIKE "
                            "'Suspension%'").fetchone()[0]
    assert "decided to suspend" in body and "Fighting at lunch" in body
    fam = EX.for_family(ava.pupil_id, academic_year=c.academic_year)
    assert fam and fam[0]["type"] == "Fixed-term suspension"
    monkeypatch.setattr(PT, "_pupil", lambda *_a: ava)
    if c.academic_year == EX.current_year():
        assert PT.behaviour(ADMIN, ava.pupil_id)["exclusions"] == fam
    out = tmp_path / "cases.csv"
    assert EX.export_csv(out, actor=ADMIN) >= 1
    rows = list(csv.reader(out.open()))
    assert rows[0][0] == "id" and rows[1][5]
    assert any(h["action"] == "notify" for h in EX.history(c.case_id))
