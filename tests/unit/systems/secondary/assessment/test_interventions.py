"""Interventions (domain.interventions)."""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.assessment.domain import interventions as IV
from education_system.systems.secondary.modules.assessment.domain import target_grades as TGR
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
T1 = Principal(username="teacher1", role="teacher")
T2 = Principal(username="teacher2", role="teacher")
PUPIL = Principal(username="pupil1", role="student")
TODAY = dt.date.today().isoformat()
WEEK_AGO = (dt.date.today() - dt.timedelta(days=7)).isoformat()
CURRENT: dict = {}


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    CURRENT.clear()
    # Current grades come from assessment points / gradebook; fake them here.
    monkeypatch.setattr(TGR, "_current_grades", lambda pupil_id=None: {
        k: (g, "Autumn AP") for k, g in CURRENT.items()
        if pupil_id is None or k[0] == int(pupil_id)})
    monkeypatch.setattr(IV, "_staff", lambda: [
        {"username": "teacher1", "display_name": "Ann Teach", "email": None, "role": "teacher"},
        {"username": "teacher2", "display_name": "Bob Teach", "email": None,
         "role": "teacher"}])
    yield tmp_path
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


_n = 0


def _pupil(year=11, **extra):
    global _n
    _n += 1
    return P.create_pupil({
        "legal_first_name": f"Pupil{_n}", "legal_last_name": f"Test{_n:03d}",
        "date_of_birth": f"{2026 - year - 4}-01-15", "gender": "Female", "year_group": year,
        "admission_date": "2021-09-01", **extra}, actor=ADMIN)


@pytest.fixture
def school():
    maths = S.create({"code": "MATH", "name": "Mathematics", "key_stage": "KS4",
                      "qualification": "GCSE", "ebacc_category": "Maths"}, actor=ADMIN)
    eng = S.create({"code": "ENLA", "name": "English Language", "key_stage": "KS4",
                    "qualification": "GCSE", "ebacc_category": "English"}, actor=ADMIN)
    return {"maths": maths, "eng": eng, "ava": _pupil(), "ben": _pupil(), "cy": _pupil()}


def _start(pupil, actor=T1, **extra):
    return IV.create({"pupil": pupil.admission_no, "subject": "MATH",
                      "intervention_type": "Catch-up", "start_date": WEEK_AGO, **extra},
                     actor=actor)


# ── Creating ─────────────────────────────────────────────────────────

def test_create_fills_lead_and_grades(school):
    ava, m = school["ava"], school["maths"]
    TGR.upsert({"pupil": ava.admission_no, "subject": "MATH", "target_grade": "7"},
               actor=ADMIN)
    CURRENT[(ava.pupil_id, m.subject_id)] = "4"
    iv = _start(ava)
    assert iv.status == "Planned" and iv.frequency == "Weekly"
    assert iv.lead_username == "teacher1" and iv.led_by == "Ann Teach"
    assert (iv.baseline_grade, iv.target_grade, iv.current_grade) == ("4", "7", "4")
    # Named lead from the pick-list form.
    iv2 = _start(school["ben"], led_by="Bob Teach (teacher2)", intervention_type="Tutoring")
    assert iv2.lead_username == "teacher2"
    assert [h["action"] for h in IV.history(iv.intervention_id)] == ["create"]


def test_create_rules(school):
    ava = school["ava"]
    with pytest.raises(IV.ValidationError) as e:
        IV.create({"pupil": ava.admission_no, "intervention_type": "Magic",
                   "start_date": "2026-05-01", "end_date": "2026-04-01"}, actor=T1)
    assert any("Type" in p for p in e.value.problems)
    assert any("End date" in p for p in e.value.problems)
    with pytest.raises(IV.ValidationError):
        IV.create({"pupil": ava.admission_no, "status": "Complete", "outcome": "Successful"},
                  actor=T1)
    _start(ava)
    with pytest.raises(IV.ValidationError) as e:
        _start(ava)
    assert "already has an open intervention" in e.value.problems[0]
    _start(ava, intervention_type="Mentoring")  # different type is fine
    with pytest.raises(IV.PermissionDenied):
        _start(school["ben"], actor=PUPIL)
    left = _pupil()
    P.update_pupil(left.pupil_id, {"roll_status": "left", "leaving_date": "2026-10-20",
                                   "leaving_reason": "Moved away"}, actor=ADMIN)
    with pytest.raises(IV.ValidationError) as e:
        _start(left)
    assert "not on roll" in e.value.problems[0]


# ── Workflow and who can do what ─────────────────────────────────────

def test_status_workflow(school):
    ava, m = school["ava"], school["maths"]
    CURRENT[(ava.pupil_id, m.subject_id)] = "4"
    iv = _start(ava)
    with pytest.raises(IV.ValidationError):
        IV.set_status(iv.intervention_id, "Complete", actor=T1, outcome="Successful")
    IV.set_status(iv.intervention_id, "Active", actor=T1)
    with pytest.raises(IV.ValidationError) as e:
        IV.set_status(iv.intervention_id, "Complete", actor=T1)
    assert "Outcome is required" in e.value.problems[0]
    CURRENT[(ava.pupil_id, m.subject_id)] = "6"
    done = IV.set_status(iv.intervention_id, "Complete", actor=T1, outcome="Successful",
                         notes="Great progress")
    assert done.end_date == TODAY and done.current_grade == "6" and done.grade_change == 2
    assert "Great progress" in done.notes
    with pytest.raises(IV.PermissionDenied):
        IV.set_status(iv.intervention_id, "Active", actor=T1)  # only the lead reopens
    back = IV.set_status(iv.intervention_id, "Active", actor=ADMIN)
    assert back.outcome is None and back.end_date is None


def test_who_can_change_it(school):
    iv = _start(school["ava"])
    with pytest.raises(IV.PermissionDenied):
        IV.update(iv.intervention_id, {"goal": "x"}, actor=T2)
    assert IV.update(iv.intervention_id, {"goal": "Fractions"}, actor=T1).goal == "Fractions"
    assert IV.update(iv.intervention_id, {"led_by": "teacher2"},
                     actor=ADMIN).lead_username == "teacher2"
    assert IV.update(iv.intervention_id, {"location": "Room 4"}, actor=T2).location == "Room 4"
    with pytest.raises(IV.PermissionDenied):
        IV.delete(iv.intervention_id, actor=T2)
    with pytest.raises(IV.ValidationError):
        IV.update(iv.intervention_id, {"pupil_id": school["ben"].pupil_id}, actor=ADMIN)
    IV.delete(iv.intervention_id, actor=ADMIN)
    with pytest.raises(IV.NotFound):
        IV.get(iv.intervention_id)


# ── Sessions and reviews ─────────────────────────────────────────────

def test_sessions_and_reviews(school):
    iv = _start(school["ava"])
    with pytest.raises(IV.ValidationError):  # still Planned
        IV.record_session(iv.intervention_id, {"attendance": "Present"}, actor=T1)
    IV.set_status(iv.intervention_id, "Active", actor=T1)
    future = (dt.date.today() + dt.timedelta(days=3)).isoformat()
    with pytest.raises(IV.ValidationError):
        IV.record_session(iv.intervention_id, {"session_date": future,
                                               "attendance": "Present"}, actor=T1)
    days = [(dt.date.today() - dt.timedelta(days=d)).isoformat() for d in (6, 5, 4, 3, 2)]
    for d, mark in zip(days, ("Present", "Late", "Absent", "Cancelled", "Absent")):
        IV.record_session(iv.intervention_id, {"session_date": d, "attendance": mark},
                          actor=T1)
    IV.record_session(iv.intervention_id, {"session_date": days[-1], "attendance": "Present"},
                      actor=T1)  # same date replaces
    a = IV.session_attendance(iv.intervention_id)
    assert a["ran"] == 4 and a["pct"] == 75.0 and a["Cancelled"] == 1
    with pytest.raises(IV.PermissionDenied):
        IV.record_session(iv.intervention_id, {"attendance": "Present"}, actor=T2)
    rv = IV.add_review(iv.intervention_id, {"on_track": False, "progress_notes": "Slow"},
                       actor=T1)
    assert rv.attendance_pct == 75.0 and rv.on_track is False and rv.reviewer == "teacher1"
    with pytest.raises(IV.ValidationError):
        IV.add_review(iv.intervention_id, {"attendance_pct": "120"}, actor=T1)
    s = IV.intervention_summary(iv.intervention_id)
    assert s["review_count"] == 1 and s["off_track"] == 1 and s["avg_attendance"] == 75.0
    IV.delete_review(rv.review_id, actor=T1)
    assert IV.list_reviews(iv.intervention_id) == []
    sid = IV.sessions(iv.intervention_id)[0].session_id
    IV.delete_session(sid, actor=T1)
    assert len(IV.sessions(iv.intervention_id)) == 4


def test_due_for_review(school):
    iv = _start(school["ava"], start_date="2026-01-05", status="Active")
    assert [d["intervention"].intervention_id for d in IV.due_for_review()] == [
        iv.intervention_id]
    IV.add_review(iv.intervention_id, {}, actor=T1)
    assert IV.due_for_review() == []


# ── Groups ───────────────────────────────────────────────────────────

def test_group_create_and_register(school):
    ava, ben, cy = school["ava"], school["ben"], school["cy"]
    _start(cy, status="Active")
    res = IV.create_many([ava.pupil_id, ben.pupil_id, cy.pupil_id],
                         {"subject": "MATH", "intervention_type": "Catch-up",
                          "programme": "Y11 maths P6", "status": "Active",
                          "start_date": WEEK_AGO}, actor=T1)
    assert len(res["created"]) == 2 and list(res["skipped"]) == [cy.admission_no]
    assert IV.programmes() == ["Y11 maths P6"]
    ids = [r.intervention_id for r in res["created"]]
    n = IV.register_programme("Y11 maths P6", TODAY, {ids[0]: "Present", ids[1]: "Absent"},
                              actor=T1)
    assert n == 2
    assert IV.session_attendance(ids[1])["Absent"] == 1
    with pytest.raises(IV.ValidationError):
        IV.create_many([ava.pupil_id], {"intervention_type": "Nope"}, actor=T1)


# ── Who needs one? ───────────────────────────────────────────────────

def test_suggestions_skip_pupils_already_covered(school):
    ava, ben, m = school["ava"], school["ben"], school["maths"]
    for p, cur in ((ava, "4"), (ben, "7")):
        TGR.upsert({"pupil": p.admission_no, "subject": "MATH", "target_grade": "7"},
                   actor=ADMIN)
        CURRENT[(p.pupil_id, m.subject_id)] = cur
    rows = IV.suggestions(year_group=11, include=("below target",))
    assert [(r["pupil"].pupil_id, r["subject"], r["type"]) for r in rows] == [
        (ava.pupil_id, "MATH", "Catch-up")]
    assert rows[0]["severity"] == 2  # well below
    _start(ava)
    assert IV.suggestions(year_group=11, include=("below target",)) == []


# ── Reports ──────────────────────────────────────────────────────────

def test_summary_impact_and_export(school, tmp_path):
    ava, ben, m = school["ava"], school["ben"], school["maths"]
    CURRENT[(ava.pupil_id, m.subject_id)] = "4"
    CURRENT[(ben.pupil_id, m.subject_id)] = "5"
    a = _start(ava, status="Active", reason="=HYPERLINK(1)")
    b = _start(ben, status="Active")
    IV.record_session(a.intervention_id, {"attendance": "Present"}, actor=T1)
    IV.record_session(b.intervention_id, {"attendance": "Absent"}, actor=T1)
    CURRENT[(ava.pupil_id, m.subject_id)] = "6"
    IV.set_status(a.intervention_id, "Complete", actor=T1, outcome="Successful")
    IV.set_status(b.intervention_id, "Complete", actor=T1, outcome="Unsuccessful")
    _start(school["cy"], intervention_type="Mentoring", subject="")

    s = IV.cohort_summary(year_group=11)
    assert s["total"] == 3 and s["open"] == 1 and s["pupils"] == 3
    assert s["by_status"] == {"Complete": 2, "Planned": 1}
    assert s["by_outcome"] == {"Successful": 1, "Unsuccessful": 1}

    imp = {r["group"]: r for r in IV.impact()}
    c = imp["Catch-up"]
    assert c["count"] == 2 and c["complete"] == 2 and c["success_pct"] == 50.0
    assert c["avg_grade_change"] == 1.0 and c["attendance_pct"] == 50.0
    assert imp["Mentoring"]["avg_grade_change"] is None
    assert {r["group"] for r in IV.impact(by="subject")} == {"Mathematics", "(no subject)"}

    path = tmp_path / "iv.csv"
    assert IV.export_csv(path, actor=ADMIN) == 3
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    ra = next(r for r in rows if r["id"] == str(a.intervention_id))
    assert ra["reason"].startswith("'=") and ra["grade_change"] == "2.0"
    assert ra["sessions_attended"] == "1"
    assert [r.intervention_id for r in IV.for_pupil(ava.pupil_id)] == [a.intervention_id]
