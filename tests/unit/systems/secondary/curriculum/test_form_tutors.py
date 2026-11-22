"""Form tutors (domain.form_tutors)."""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
from education_system.systems.secondary.modules.curriculum.domain import year_groups as YG
from education_system.systems.secondary.modules.curriculum.domain import form_tutors as FT
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
YEAR = FT.current_year()
TODAY = dt.date.today().isoformat()
LOGINS = [{"username": "ann", "display_name": "Ann Tutor", "email": "ann@school.org",
           "role": "teacher"},
          {"username": "bob", "display_name": "Bob Cover", "email": "bob@school.org",
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
    monkeypatch.setattr(FT, "_staff", lambda: LOGINS)
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


@pytest.fixture
def school():
    fa = FG.create({"name": "10A", "year_group": 10}, actor=ADMIN)
    fb = FG.create({"name": "10B", "year_group": 10, "tutor_name": "Old Name"}, actor=ADMIN)
    YG.update(10, {"head_of_year": "Mr Head"}, actor=ADMIN)
    return {"a": fa, "b": fb, "ava": _pupil(), "ben": _pupil(), "cy": _pupil("10B")}


def _assign(form, who="ann", role="Tutor", **extra):
    return FT.create_assignment({"form_id": form.form_id, "tutor": who, "role": role,
                                 "start_date": f"{YEAR[:4]}-09-01", **extra}, actor=ADMIN)


# ── Assignments and the form record ──────────────────────────────────

def test_assignment_sets_the_form_tutor(school):
    a = _assign(school["a"])
    assert (a.tutor_name, a.tutor_username, a.contact_email, a.academic_year) == (
        "Ann Tutor", "ann", "ann@school.org", YEAR)
    f = FG.get(school["a"].form_id)
    assert (f.tutor_name, f.tutor_email) == ("Ann Tutor", "ann@school.org")
    _assign(school["a"], "bob", "Co-tutor")
    assert FG.get(school["a"].form_id).co_tutor_name == "Bob Cover"
    with pytest.raises(FT.ValidationError) as e:
        _assign(school["a"], "head")  # a second active Tutor
    assert "already the active tutor" in e.value.problems[0]
    with pytest.raises(FT.ValidationError):
        _assign(school["a"], "ann", status="Ended")  # same person, same role, same year
    with pytest.raises(FT.PermissionDenied):
        FT.create_assignment({"form_id": school["b"].form_id, "tutor": "bob"}, actor=ANN)
    # Tutor suspended, Bob covers: the form shows the cover.
    FT.update_assignment(a.assignment_id, {"status": "Suspended"}, actor=ADMIN)
    _assign(school["a"], "bob", "Cover")
    assert FG.get(school["a"].form_id).tutor_name == "Bob Cover"
    ended = FT.end_assignment(a.assignment_id, actor=ADMIN)
    assert ended.status == "Ended" and ended.end_date == TODAY
    # Re-typing the same name keeps the login.
    kept = FT.update_assignment(a.assignment_id, {"tutor": "Ann Tutor", "notes": "x"},
                                actor=ADMIN)
    assert kept.tutor_username == "ann"


def test_rules(school):
    with pytest.raises(FT.ValidationError) as e:
        FT.create_assignment({"form_id": school["a"].form_id, "tutor": "ann",
                              "academic_year": "2026/28", "start_date": "2026-09-05",
                              "end_date": "2026-09-01", "contact_email": "nope",
                              "role": "Boss"}, actor=ADMIN)
    text = " ".join(e.value.problems)
    for bit in ("Academic year", "End date", "Contact e-mail", "Role"):
        assert bit in text
    a = FT.create_assignment({"form_id": school["a"].form_id, "tutor": "Ms Typed"},
                             actor=ADMIN)
    assert a.tutor_username is None and a.tutor_name == "Ms Typed"


def test_import_and_mismatches(school):
    assert [(x["form"].name, x["role"]) for x in FT.mismatches()] == [("10B", "Tutor")]
    r = FT.import_from_forms(actor=ADMIN)
    assert r == {"created": 1, "skipped": 0}
    [a] = FT.list_assignments(form_id=school["b"].form_id)
    assert a.tutor_name == "Old Name" and a.role == "Tutor"
    assert FT.mismatches() == []
    assert FT.import_from_forms(actor=ADMIN)["created"] == 0


# ── Meetings ─────────────────────────────────────────────────────────

def test_meetings_who_and_rules(school):
    ava, cy = school["ava"], school["cy"]
    a = _assign(school["a"])
    b = _assign(school["b"], "bob")
    m = FT.add_meeting(a.assignment_id, {"meeting_type": "1-to-1", "pupils": [ava.admission_no],
                                         "agenda": "Settling in", "follow_up_actions":
                                         "Call home", "follow_up_due": TODAY}, actor=ANN)
    assert m.pupil_ids == (ava.pupil_id,) and m.follow_up_open
    with pytest.raises(FT.PermissionDenied):
        FT.add_meeting(a.assignment_id, {"agenda": "x"}, actor=BOB)
    for bad in ({"meeting_type": "1-to-1"},
                {"pupils": [cy.admission_no]},
                {"meeting_date": "2999-01-01"},
                {"follow_up_due": TODAY}):
        with pytest.raises(FT.ValidationError):
            FT.add_meeting(a.assignment_id, bad, actor=ANN)
    FT.add_meeting(b.assignment_id, {"agenda": "Form time"}, actor=BOB)
    # Each tutor sees their own form; the head of year sees the year; the lead all.
    assert {x.form_group for x in FT.list_meetings(actor=ANN)} == {"10A"}
    assert {x.form_group for x in FT.list_meetings(actor=BOB)} == {"10B"}
    assert len(FT.list_meetings(actor=HEAD)) == 2 and len(FT.list_meetings(actor=ADMIN)) == 2
    with pytest.raises(FT.PermissionDenied):
        FT.update_meeting(m.meeting_id, {"agenda": "y"}, actor=HEAD)  # can see, not change
    assert FT.update_meeting(m.meeting_id, {"decisions": "Weekly check-in"},
                             actor=ANN).decisions == "Weekly check-in"
    assert [x.meeting_id for x in FT.follow_ups(actor=ANN)] == [m.meeting_id]
    FT.complete_follow_up(m.meeting_id, actor=ANN)
    assert FT.follow_ups(actor=ANN) == []
    assert FT.complete_follow_up(m.meeting_id, actor=ANN, undo=True).follow_up_open
    s = FT.assignment_summary(a.assignment_id)
    assert s["meeting_count"] == 1 and s["by_type"] == {"1-to-1": 1} and s["pupils_seen"] == 1
    assert [x.meeting_id for x in FT.for_pupil(ava.pupil_id)["meetings"]] == [m.meeting_id]
    FT.delete_meeting(m.meeting_id, actor=ANN)
    assert FT.list_meetings(assignment_id=a.assignment_id) == []


def test_my_form_overview(school):
    ava, ben = school["ava"], school["ben"]
    a = _assign(school["a"])
    C.add_contact(ava.pupil_id, {"full_name": "Mum", "relationship": "Mother",
                                 "email": "mum@example.org"}, actor=ADMIN)
    FT.add_meeting(a.assignment_id, {"meeting_type": "1-to-1", "pupils": [ava.pupil_id]},
                   actor=ANN)
    assert [f.name for f in FT.my_forms(ANN)] == ["10A"]
    assert {f.name for f in FT.my_forms(HEAD)} == {"10A", "10B"}
    ov = FT.form_overview(school["a"].form_id, actor=ANN)
    rows = {r["pupil"].pupil_id: r for r in ov["pupils"]}
    assert rows[ava.pupil_id]["last_contact"] == TODAY and rows[ava.pupil_id]["email_contact"]
    assert rows[ben.pupil_id]["last_contact"] is None and not rows[ben.pupil_id]["email_contact"]
    assert [p.pupil_id for p in ov["no_contact_this_term"]] == [ben.pupil_id]
    with pytest.raises(FT.PermissionDenied):
        FT.form_overview(school["b"].form_id, actor=ANN)


# ── Year to year, coverage, reports ──────────────────────────────────

def test_carry_forward(school):
    a = _assign(school["a"])
    r = FT.carry_forward(actor=ADMIN)
    nxt = FT.next_year(YEAR)
    assert r["copied"] == 1 and r["to_year"] == nxt
    [new] = FT.list_assignments(academic_year=nxt)
    assert (new.tutor_username, new.start_date, new.status) == ("ann", f"{nxt[:4]}-09-01",
                                                                 "Active")
    old = FT.get_assignment(a.assignment_id)
    assert old.status == "Ended" and old.end_date == FT.year_end(YEAR)


def test_coverage_summary_export_and_delete_guard(school, tmp_path):
    _assign(school["a"])
    _assign(school["a"], "bob", "Mentor", status="Provisional")
    _assign(school["b"], "ann")
    cv = FT.coverage()
    assert cv["no_tutor"] == []
    assert cv["several_forms"] == {"Ann Tutor": ["10A (Year 10)", "10B (Year 10)"]}
    assert len(cv["provisional"]) == 1
    s = FT.cohort_summary(academic_year=YEAR)
    assert s["total"] == 3 and s["tutors"] == 2 and s["forms"] == 2
    assert s["by_role"] == {"Tutor": 2, "Mentor": 1}
    path = tmp_path / "t.csv"
    assert FT.export_csv(path, actor=ADMIN) == 3
    assert list(csv.DictReader(open(path, encoding="utf-8")))[0]["form"] == "10A"
    empty = FG.create({"name": "10C", "year_group": 10}, actor=ADMIN)
    _assign(empty, "head")
    with pytest.raises(FG.ValidationError):
        FG.delete(empty.form_id, actor=ADMIN)
