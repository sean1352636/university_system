"""Detentions (modules.behaviour.domain.detentions)."""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.assessment.domain import interventions as IV
from education_system.systems.secondary.modules.curriculum.domain import year_groups as YG
from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
from education_system.systems.secondary.modules.behaviour.domain import detentions as DT
from education_system.systems.secondary.modules.portals.domain import my_day as MD
from education_system.systems.secondary.modules.portals.domain import portal as PT
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
ANN = Principal(username="ann", role="teacher")
BOB = Principal(username="bob", role="teacher")
SAM = Principal(username="sam", role="teacher")
HEAD = Principal(username="head", role="teacher")
LOGINS = [{"username": u, "display_name": n, "email": f"{u}@school.org", "role": "teacher"}
          for u, n in (("ann", "Ann Teacher"), ("bob", "Bob Teacher"), ("sam", "Sam Super"),
                       ("head", "Mr Head"))]


def _weekday(after: dt.date, weekday: int | None = None) -> dt.date:
    """The next weekday (or the next *weekday*, 0 = Monday) after *after*."""
    d = after + dt.timedelta(days=1)
    while (d.weekday() >= 5) if weekday is None else (d.weekday() != weekday):
        d += dt.timedelta(days=1)
    return d


TODAY = dt.date.today()
DAY = _weekday(TODAY + dt.timedelta(days=2))      # a school day with notice
LATER = _weekday(DAY)


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


def _pupil(form="10A"):
    global _n
    _n += 1
    return P.create_pupil({
        "legal_first_name": f"Pupil{_n}", "legal_last_name": f"Test{_n:03d}",
        "date_of_birth": "2011-01-15", "gender": "Female", "year_group": 10,
        "form_group": form, "admission_date": "2021-09-01"}, actor=ADMIN)


def _set(pupil, actor=ANN, day=DAY, **extra):
    return DT.create({"pupil_id": pupil.pupil_id, "detention_date": day.isoformat(),
                      "start_time": "15:30", "reason": "Homework not done", **extra},
                     actor=actor)


def _after(monkeypatch, day: dt.date) -> None:
    """Pretend it's *day* (so a detention can be marked)."""
    monkeypatch.setattr(DT, "_today", lambda: day)


# ── The old rules ────────────────────────────────────────────────────

def test_schedule_defaults_and_old_rules():
    ava = _pupil()
    d = _set(ava, supervisor="Sam Super")
    assert (d.status, d.duration_min, d.detention_type) == ("Scheduled", 30, "After school")
    assert d.set_by == "Ann Teacher" and d.set_by_username == "ann"
    assert d.supervisor_username == "sam" and d.academic_year == DT.year_of(d.detention_date)
    by_adm = DT.create({"pupil": ava.admission_no, "detention_date": LATER.isoformat(),
                        "reason": "Late"}, actor=ANN)
    assert by_adm.pupil_id == ava.pupil_id
    for bad, bit in (({"reason": ""}, "Reason is required"),
                     ({"reason": "x" * 201}, "200 chars"),
                     ({"duration_min": 4}, "between 5 and 480"),
                     ({"duration_min": "ten"}, "whole number"),
                     ({"start_time": "25:00"}, "HH:MM"),
                     ({"detention_type": "Weekly"}, "Detention type must be one of"),
                     ({"detention_date": "2020-01-06"}, "has passed"),
                     ({"detention_date": "05/11/2026"}, "YYYY-MM-DD")):
        with pytest.raises(DT.ValidationError) as e:
            _set(ava, day=LATER, **{"start_time": "12:30", **bad})
        assert any(bit in p for p in e.value.problems), (bad, e.value.problems)


def test_clashes_days_and_lead_only_types():
    ava = _pupil()
    _set(ava, start_time="15:30", duration_min=60)
    with pytest.raises(DT.ValidationError, match="Already has detention"):
        _set(ava, start_time="16:00")
    assert _set(ava, start_time="12:30", detention_type="Lunchtime").status == "Scheduled"
    saturday = _weekday(TODAY, 5)
    with pytest.raises(DT.ValidationError, match="isn't a school day"):
        _set(ava, day=saturday, actor=ADMIN)
    with pytest.raises(DT.ValidationError, match="must be on a Friday"):
        _set(ava, day=_weekday(TODAY + dt.timedelta(days=1), 0), detention_type="Friday")
    for kind, day in (("SLT", LATER), ("Saturday", saturday)):
        with pytest.raises(DT.ValidationError, match="Only the detentions lead"):
            _set(ava, day=day, detention_type=kind)
        assert _set(ava, day=day, detention_type=kind, actor=ADMIN).detention_type == kind
    left = _pupil()
    P.update_pupil(left.pupil_id, {"roll_status": "left", "leaving_date": "2026-07-20",
                                   "leaving_reason": "Moved away"}, actor=ADMIN)
    with pytest.raises(DT.ValidationError, match="not on roll"):
        _set(left)


def test_warnings_ask_but_do_not_refuse():
    ava = _pupil()
    soon = dt.datetime.combine(DAY, dt.time(9, 0))
    w = DT.check({"pupil_id": ava.pupil_id, "detention_date": DAY.isoformat(),
                  "start_time": "15:30", "reason": "x"}, actor=ANN, now=soon)
    assert any("24 hours' notice" in x for x in w)
    assert not DT.check({"pupil_id": ava.pupil_id, "detention_date": DAY.isoformat(),
                         "start_time": "12:30", "detention_type": "Lunchtime", "reason": "x"},
                        actor=ANN, now=soon)
    _set(ava)
    w = DT.check({"pupil_id": ava.pupil_id, "detention_date": DAY.isoformat(),
                  "start_time": "12:30", "detention_type": "Lunchtime", "reason": "x"},
                 actor=ANN, now=soon)
    assert any("already has a detention that day" in x for x in w)


# ── Who may do what ──────────────────────────────────────────────────

def test_permissions(monkeypatch):
    ava = _pupil()
    d = _set(ava, supervisor="Sam Super")
    with pytest.raises(DT.PermissionDenied):
        DT.update(d.detention_id, {"location": "R1"}, actor=BOB)
    assert DT.update(d.detention_id, {"location": "R1"}, actor=ANN).location == "R1"
    with pytest.raises(DT.PermissionDenied):
        DT.delete(d.detention_id, actor=ANN)
    with pytest.raises(DT.PermissionDenied):
        DT.set_status(d.detention_id, "Cancelled", actor=BOB)
    YG.update(10, {"head_of_year": "Mr Head"}, actor=ADMIN)
    assert DT.can_mark(HEAD, d) and DT.can_mark(SAM, d) and not DT.can_mark(BOB, d)
    with pytest.raises(DT.ValidationError, match="hasn't happened yet"):
        DT.set_status(d.detention_id, "Attended", actor=SAM)
    _after(monkeypatch, DAY)
    done = DT.set_status(d.detention_id, "Attended", actor=SAM, note="On time")
    assert (done.status, done.marked_by, done.notes) == ("Attended", "sam", "On time")
    assert not DT.can_edit(ANN, done)          # no longer scheduled
    with pytest.raises(DT.ValidationError, match="Only the detentions lead can reopen"):
        DT.set_status(d.detention_id, "Scheduled", actor=ANN)
    with pytest.raises(DT.ValidationError, match="Use Reschedule"):
        DT.set_status(d.detention_id, "Rescheduled", actor=ADMIN)
    assert DT.delete(d.detention_id, actor=ADMIN)
    assert [h["action"] for h in DT.history(d.detention_id)][:1] == ["delete"]


# ── Behaviour, reschedule, follow-up ─────────────────────────────────

def test_from_behaviour_reschedule_and_follow_up(monkeypatch):
    ava, ben = _pupil(), _pupil()
    e = BH.log_incident({"pupil_id": ava.pupil_id, "incident_type": "Disruption",
                         "description": "Shouting"}, actor=ANN)
    d = DT.from_behaviour(e.entry_id, {"detention_date": DAY.isoformat(),
                                       "start_time": "15:30"}, actor=ANN)
    assert d.related_entry_id == e.entry_id and d.reason.startswith("Disruption")
    assert f"Detention set for {DAY.isoformat()}" in BH.get(e.entry_id).action_taken
    good = BH.log_incident({"pupil_id": ava.pupil_id, "incident_type": "Achievement",
                            "description": "Great"}, actor=ANN)
    with pytest.raises(DT.ValidationError, match="isn't a negative entry"):
        _set(ava, day=LATER, related_entry_id=good.entry_id)
    with pytest.raises(DT.ValidationError, match="another pupil"):
        _set(ben, related_entry_id=e.entry_id)
    _after(monkeypatch, DAY)
    DT.set_status(d.detention_id, "Missed", actor=ANN)
    assert [x.detention_id for x in DT.missed_to_follow_up()] == [d.detention_id]
    new = DT.reschedule(d.detention_id, new_date=LATER.isoformat(), actor=ANN)
    old = DT.get(d.detention_id)
    assert (old.status, old.rescheduled_to, new.rescheduled_from) == (
        "Rescheduled", new.detention_id, d.detention_id)
    assert new.related_entry_id == e.entry_id and new.status == "Scheduled"
    assert DT.missed_to_follow_up() == []
    with pytest.raises(DT.ValidationError, match="Cannot reschedule"):
        DT.reschedule(d.detention_id, new_date=LATER.isoformat(), actor=ANN)
    _after(monkeypatch, LATER)
    DT.set_status(new.detention_id, "Missed", actor=ANN)
    rows = DT.concerns(today=LATER)
    assert [(c["pupil_id"], c["missed"]) for c in rows] == [(ava.pupil_id, 2)]
    monkeypatch.setattr(BH, "_today", lambda: LATER)
    assert any("missed 2 detentions" in r for c in BH.concerns() for r in c["reasons"])
    assert ava.pupil_id in {s["pupil"].pupil_id for s in IV.suggestions(include=("behaviour",))}


# ── Sessions and registers ───────────────────────────────────────────

def test_sessions_capacity_move_and_register(monkeypatch):
    ava, ben, cal = _pupil(), _pupil(), _pupil()
    with pytest.raises(DT.PermissionDenied):
        DT.save_session({"session_date": DAY.isoformat()}, actor=ANN)
    s = DT.save_session({"session_date": DAY.isoformat(), "detention_type": "After school",
                         "start_time": "15:20", "duration_min": 60, "location": "R12",
                         "supervisor": "Sam Super", "capacity": 2}, actor=ADMIN)
    a = DT.create({"pupil_id": ava.pupil_id, "session_id": s.session_id, "reason": "Late"},
                  actor=ANN)
    assert (a.detention_date, a.start_time, a.duration_min, a.location, a.supervisor_username
            ) == (DAY.isoformat(), "15:20", 60, "R12", "sam")
    DT.set_many([ben.pupil_id], {"session_id": s.session_id, "reason": "Late"}, actor=ANN)
    with pytest.raises(DT.ValidationError, match="place"):
        DT.create({"pupil_id": cal.pupil_id, "session_id": s.session_id, "reason": "x"},
                  actor=ANN)
    with pytest.raises(DT.ValidationError, match="part of a session"):
        DT.update(a.detention_id, {"location": "R1"}, actor=ADMIN)
    with pytest.raises(DT.ValidationError, match="already booked"):
        DT.save_session({"capacity": 1}, actor=ADMIN, session_id=s.session_id)
    DT.save_session({"location": "Hall"}, actor=ADMIN, session_id=s.session_id)
    assert DT.get(a.detention_id).location == "Hall"       # booked pupils follow
    with pytest.raises(DT.ValidationError, match="still booked"):
        DT.cancel_session(s.session_id, actor=ADMIN)
    s2 = DT.save_session({"session_date": LATER.isoformat(), "start_time": "15:20",
                          "duration_min": 60, "supervisor": "Sam Super"}, actor=ADMIN)
    assert DT.move_session(s.session_id, s2.session_id, actor=ADMIN) == 2
    assert DT.cancel_session(s.session_id, actor=ADMIN).status == "Cancelled"
    reg = DT.session_register(s2.session_id)
    assert {d.pupil_id for d in reg} == {ava.pupil_id, ben.pupil_id}
    assert [d.pupil_id for d in DT.supervising(SAM, LATER)] == [d.pupil_id for d in reg]
    _after(monkeypatch, LATER)
    marks = {reg[0].detention_id: "Attended", reg[1].detention_id: "Missed"}
    with pytest.raises(DT.PermissionDenied):
        DT.mark_register(marks, actor=BOB)
    DT.mark_register(marks, actor=SAM)
    s3 = DT.pupil_summary(reg[0].pupil_id)
    assert (s3["attended"], s3["minutes_served"], s3["rescheduled"]) == (1, 60, 1)
    c = DT.cohort_summary()
    assert (c["attended"], c["missed"], c["attendance_pct"]) == (1, 1, 50)
    assert {g["group"] for g in DT.analysis(by="type")} == {"After school"}


# ── Families, My Day, export ─────────────────────────────────────────

def test_notice_portal_my_day_and_export(tmp_path, monkeypatch):
    ava, ben = _pupil(), _pupil()
    C.add_contact(ava.pupil_id, {"full_name": "Mum", "relationship": "Mother",
                                 "email": "mum@example.org"}, actor=ADMIN)
    a = _set(ava, supervisor="Sam Super", reason="=SUM(A1)")
    b = _set(ben)
    res = DT.notify_parents([a.detention_id, b.detention_id], actor=ANN, note="Thanks")
    assert res["emails"] == 1 and [p.pupil_id for p in res["no_email"]] == [ben.pupil_id]
    assert DT.get(a.detention_id).parents_notified_at
    assert not DT.get(b.detention_id).parents_notified_at
    with database.connect() as conn:
        body = conn.execute("SELECT body FROM email_recipients WHERE subject LIKE "
                            "'Detention%'").fetchone()[0]
    assert "After school detention" in body and "Thanks" in body and DAY.strftime("%d %B %Y") in body
    fam = DT.for_family(ava.pupil_id)
    assert [d.detention_id for d in fam["upcoming"]] == [a.detention_id]
    monkeypatch.setattr(PT, "_pupil", lambda *_a: ava)
    assert PT.behaviour(ADMIN, ava.pupil_id)["detentions"]["upcoming"][0].detention_id == \
        a.detention_id
    monkeypatch.setattr(DT, "_today", lambda: DAY)
    assert [d.detention_id for d in MD.detentions_today(SAM, DAY)] == [a.detention_id]
    path = tmp_path / "d.csv"
    assert DT.export_csv(path, actor=ANN) == 2
    rows = list(csv.reader(path.open(encoding="utf-8")))
    assert rows[0][:5] == ["id", "date", "time", "minutes", "type"]
    assert any(r[11] == "'=SUM(A1)" for r in rows[1:])
    with pytest.raises(DT.PermissionDenied):
        DT.export_csv(path, actor=Principal(username="kid", role="student"))
