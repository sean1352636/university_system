"""Behaviour & rewards (domain.behaviour)."""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.assessment.domain import interventions as IV
from education_system.systems.secondary.modules.curriculum.domain import year_groups as YG
from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
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
HEAD = Principal(username="head", role="teacher")
TODAY = dt.date.today()
LOGINS = [{"username": "ann", "display_name": "Ann Teacher", "email": "ann@school.org",
           "role": "teacher"},
          {"username": "bob", "display_name": "Bob Teacher", "email": "bob@school.org",
           "role": "teacher"},
          {"username": "head", "display_name": "Mr Head", "email": "head@school.org",
           "role": "teacher"}]


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


def _pupil(form="10A", **extra):
    global _n
    _n += 1
    return P.create_pupil({
        "legal_first_name": f"Pupil{_n}", "legal_last_name": f"Test{_n:03d}",
        "date_of_birth": "2011-01-15", "gender": "Female", "year_group": 10,
        "form_group": form, "admission_date": "2021-09-01", **extra}, actor=ADMIN)


def _log(pupil, kind="Achievement", actor=ANN, **extra):
    return BH.log_incident({"pupil_id": pupil.pupil_id, "incident_type": kind,
                            "description": "Something", **extra}, actor=actor)


# ── The old rules ────────────────────────────────────────────────────

def test_log_defaults_and_old_rules():
    ava = _pupil()
    good = _log(ava)
    bad = _log(ava, "Lateness")
    assert (good.points, good.polarity, good.share_with_parents) == (1, "positive", True)
    assert (bad.points, bad.polarity, bad.share_with_parents) == (-1, "negative", False)
    assert good.raised_by == "Ann Teacher" and good.raised_by_username == "ann"
    assert good.status == "Open" and good.severity == "Low"
    assert good.academic_year == BH.current_year()
    by_adm = BH.log_incident({"pupil": ava.admission_no, "incident_type": "Uniform",
                              "description": "Tie"}, actor=ANN)
    assert by_adm.pupil_id == ava.pupil_id
    for bad_data, bit in (({"points": -3}, "Positive incident types"),
                          ({"incident_type": "Damage", "points": 4}, "Negative incident types"),
                          ({"points": 101}, "between"),
                          ({"entry_time": "25:00"}, "HH:MM"),
                          ({"description": ""}, "Description is required"),
                          ({"description": "x" * 501}, "500"),
                          ({"incident_type": "Nonsense"}, "isn't a behaviour type"),
                          ({"severity": "Huge"}, "Severity"),
                          ({"entry_date": (TODAY + dt.timedelta(days=2)).isoformat()},
                           "future"),
                          ({"status": "Escalated"}, "escalated to")):
        with pytest.raises(BH.ValidationError) as e:
            _log(ava, **bad_data)
        assert bit in " ".join(e.value.problems), bad_data
    left = _pupil(roll_status="left", leaving_date=TODAY.isoformat(), leaving_reason="Moved")
    with pytest.raises(BH.ValidationError) as e:
        _log(left)
    assert "not on roll" in e.value.problems[0]
    with pytest.raises(BH.PermissionDenied):
        _log(ava, actor=Principal(username="kid", role="student"))


def test_who_can_change_what():
    YG.update(10, {"head_of_year": "Mr Head"}, actor=ADMIN)
    ava = _pupil()
    e = _log(ava, "Disruption", severity="Medium")
    assert BH.update(e.entry_id, {"notes": "Spoke to her"}, actor=ANN).notes == "Spoke to her"
    with pytest.raises(BH.PermissionDenied):
        BH.update(e.entry_id, {"notes": "x"}, actor=BOB)
    with pytest.raises(BH.PermissionDenied):
        BH.set_status(e.entry_id, "Resolved", actor=BOB)
    # Head of year can change status but not details.
    esc = BH.set_status(e.entry_id, "Escalated", actor=HEAD, escalated_to="Deputy head",
                        action_taken="Referred")
    assert (esc.status, esc.escalated_to, esc.action_taken) == ("Escalated", "Deputy head",
                                                                "Referred")
    with pytest.raises(BH.PermissionDenied):
        BH.update(e.entry_id, {"notes": "y"}, actor=HEAD)
    # Once it isn't open, the raiser can't edit details - the lead can.
    with pytest.raises(BH.PermissionDenied):
        BH.update(e.entry_id, {"notes": "z"}, actor=ANN)
    assert BH.update(e.entry_id, {"points": -5}, actor=ADMIN).points == -5
    # Changing the type takes the new type's default points.
    assert BH.update(e.entry_id, {"incident_type": "Defiance"}, actor=ADMIN).points == -1
    with pytest.raises(BH.PermissionDenied):
        BH.delete(e.entry_id, actor=ANN)
    BH.delete(e.entry_id, actor=ADMIN, reason="Logged twice")
    with pytest.raises(BH.NotFound):
        BH.get(e.entry_id)
    assert [h["action"] for h in BH.history(e.entry_id)][0] == "delete"


# ── Summaries ────────────────────────────────────────────────────────

def test_summaries_threshold_and_withdrawn():
    ava, ben = _pupil(), _pupil()
    _log(ava, points=5)
    for _ in range(3):
        _log(ben, "Disruption", points=-4)
    w = _log(ben, "Damage", points=-10)
    BH.set_status(w.entry_id, "Withdrawn", actor=ANN)
    s = BH.pupil_summary(ben.pupil_id)
    assert (s["total"], s["negative"], s["total_points"]) == (3, 3, -12)
    assert s["by_status"] == {"Open": 3, "Withdrawn": 1}
    c = BH.cohort_summary(year_group=10)
    assert (c["total"], c["positive"], c["negative"], c["pupils"]) == (4, 1, 3, 2)
    assert [t["pupil_id"] for t in BH.pupils_above_threshold()] == [ben.pupil_id]
    assert BH.pupils_above_threshold(points_below=-20) == []
    # Withdrawn and restored: it counts again.
    BH.set_status(w.entry_id, "Open", actor=ADMIN)
    assert BH.pupil_summary(ben.pupil_id)["total_points"] == -22
    by_type = {g["group"]: g for g in BH.analysis(by="type")}
    assert by_type["Disruption"]["negative"] == 3 and by_type["Achievement"]["points"] == 5
    assert {g["group"] for g in BH.analysis(by="staff")} == {"Ann Teacher"}
    with pytest.raises(BH.ValidationError):
        BH.analysis(by="colour")


def test_concerns_feed_intervention_suggestions():
    ava, ben = _pupil(), _pupil()
    for _ in range(3):
        _log(ava, "Lateness")
    _log(ben, "Bullying", severity="Critical")
    rows = {c["pupil_id"]: c for c in BH.concerns()}
    assert "3 negative entries" in rows[ava.pupil_id]["reasons"][0]
    assert rows[ben.pupil_id]["severity"] == 2
    sugg = [s for s in IV.suggestions(include=("behaviour",))]
    assert {s["pupil"].pupil_id for s in sugg} == {ava.pupil_id, ben.pupil_id}
    assert all(s["type"] == "Behaviour" for s in sugg)


# ── Several at once, rewards, houses ─────────────────────────────────

def test_log_many_and_rewards():
    ava, ben = _pupil(), _pupil()
    with pytest.raises(BH.ValidationError):  # all or nothing
        BH.log_many([ava.pupil_id, "NOPE"], {"incident_type": "Achievement",
                                             "description": "x"}, actor=ANN)
    assert BH.list_entries() == []
    done = BH.log_many([ava.pupil_id, ben.admission_no],
                       {"incident_type": "House points", "points": 60,
                        "description": "Sports day"}, actor=ANN)
    assert len(done) == 2
    ms = BH.milestones(pupil_id=ava.pupil_id)
    assert [m["level"] for m in ms] == ["Bronze"]
    assert BH.next_level(ava.pupil_id) == {"points": 60, "next": "Silver", "needed": 40}
    _log(ava, points=50)
    assert {m["level"] for m in BH.milestones(pupil_id=ava.pupil_id)} == {"Bronze", "Silver"}
    assert BH.present([m["milestone_id"] for m in ms], actor=ANN) == 1
    assert BH.milestones(pupil_id=ava.pupil_id, unpresented=True)[0]["level"] == "Silver"
    assert [t["pupil_id"] for t in BH.leaderboard()] == [ava.pupil_id, ben.pupil_id]


def test_houses():
    ava, ben, cy = _pupil(), _pupil(), _pupil("10B")
    with pytest.raises(BH.PermissionDenied):
        BH.save_house("Red", actor=ANN)
    with pytest.raises(BH.ValidationError):
        BH.save_house("Blue", actor=ADMIN, colour="blue")
    BH.save_house("Red", actor=ADMIN, colour="#FF0000")
    BH.save_house("Blue", actor=ADMIN)
    BH.assign_house([ava.pupil_id, ben.pupil_id], "Red", actor=ADMIN)
    BH.assign_house([cy.pupil_id], "Blue", actor=ADMIN)
    _log(ava, points=10)
    _log(cy, points=4)
    _log(ben, "Lateness")  # negatives don't take house points away
    table = BH.house_table()
    assert [(h["house"], h["points"], h["pupils"]) for h in table] == [("Red", 10, 2),
                                                                       ("Blue", 4, 1)]
    with pytest.raises(BH.ValidationError):
        BH.save_house("Blue", actor=ADMIN, active=False)  # still has pupils
    BH.assign_house([cy.pupil_id], None, actor=ADMIN)
    assert BH.house_of(cy.pupil_id) is None
    assert [p.pupil_id for p in BH.without_house()] == [cy.pupil_id]


def test_types():
    with pytest.raises(BH.PermissionDenied):
        BH.save_type("Kindness", "positive", 2, actor=ANN)
    t = BH.save_type("Kindness", "positive", 2, actor=ADMIN)
    assert (t.default_points, t.active) == (2, True)
    ava = _pupil()
    assert _log(ava, "Kindness").points == 2
    with pytest.raises(BH.ValidationError):
        BH.save_type("Kindness", "negative", -1, actor=ADMIN)  # in use
    BH.save_type("Kindness", "positive", 2, actor=ADMIN, active=False)
    with pytest.raises(BH.ValidationError):
        _log(ava, "Kindness")
    assert "Kindness" not in {x.name for x in BH.list_types()}


# ── Families and export ──────────────────────────────────────────────

def test_note_home_portal_and_export(tmp_path, monkeypatch):
    ava, ben = _pupil(), _pupil()
    C.add_contact(ava.pupil_id, {"full_name": "Mum", "relationship": "Mother",
                                 "email": "mum@example.org"}, actor=ADMIN)
    good = _log(ava, points=3)
    bad = _log(ava, "Lateness")
    other = _log(ben, "Lateness")
    assert [e.entry_id for e in BH.for_family(ava.pupil_id)["entries"]] == [good.entry_id]
    res = BH.notify_parents([bad.entry_id, other.entry_id], actor=ANN, note="Thanks")
    assert res["emails"] == 1 and [p.pupil_id for p in res["no_email"]] == [ben.pupil_id]
    after = BH.get(bad.entry_id)
    assert after.parents_notified_at and after.share_with_parents
    assert not BH.get(other.entry_id).parents_notified_at
    fam = BH.for_family(ava.pupil_id)
    assert {e.entry_id for e in fam["entries"]} == {good.entry_id, bad.entry_id}
    assert fam["positive_points"] == 3
    monkeypatch.setattr(PT, "_pupil", lambda *_a: ava)  # portal access is tested elsewhere
    assert {e.entry_id for e in PT.behaviour(ADMIN, ava.pupil_id)["entries"]} == {
        good.entry_id, bad.entry_id}
    _log(ava, description="=SUM(A1)")
    path = tmp_path / "b.csv"
    assert BH.export_csv(path, actor=ADMIN, pupil_id=ava.pupil_id) == 3
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    assert rows[0]["description"].startswith("'=")
    assert len(BH.recent(2)) == 2
