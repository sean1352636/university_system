"""Staff Directory (modules.staff.domain.staff_directory)."""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.curriculum.domain import timetable as TT
from education_system.systems.secondary.modules.staff.domain import departments as DP
from education_system.systems.secondary.modules.staff.domain import staff_directory as SD
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
ANN = Principal(username="ann", role="teacher")
PUPIL = Principal(username="kid", role="student")
LOGINS = [{"username": u, "display_name": n, "email": f"{u}@school.org", "role": r}
          for u, n, r in (("ann", "Ann Teacher", "teacher"), ("head", "Mr Bob Head", "teacher"),
                          ("admin2", "Admin Two", "admin"))]


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


def _person(**extra):
    data = {"first_name": "Cara", "last_name": "Cook", "role": "Caretaker", **extra}
    return SD.create(data, actor=ADMIN)


def test_create_defaults_code_and_old_fields():
    c = _person(title="Ms", room="B2", work_phone="01234 567890", is_tutor=True)
    assert c.staff_code.startswith("T") and len(c.staff_code) == 8
    assert (c.role_type, c.employment_status, c.contract_type, c.fte) == (
        "support", "Full-time", "Full-time", 1.0)
    assert c.username is None and c.flags == "T" and c.formal_name == "Ms Cook"
    assert SD.get(c.staff_code) == SD.get(c.staff_id) == SD.get(c.label)
    with pytest.raises(SD.NotFound):
        SD.get("nobody")


def test_validation_rules():
    with pytest.raises(SD.ValidationError) as e:
        SD.create({"first_name": "", "last_name": "X", "role": "Wizard", "fte": "2",
                   "work_email": "nope", "trn": "12"}, actor=ADMIN)
    text = str(e.value)
    for bit in ("First name is required", "Role must be", "FTE must be between",
                "Work e-mail doesn't look", "7 digits"):
        assert bit in text
    with pytest.raises(SD.ValidationError, match="FTE is required"):
        _person(contract_type="Part-time")
    assert _person(contract_type="Part-time", fte="0.6").fte == 0.6
    with pytest.raises(SD.ValidationError, match="full-time contract is 1.0"):
        _person(fte="0.5")


def test_login_link_rules_and_email_fallback():
    a = SD.create({"first_name": "Ann", "last_name": "Teacher", "username": "ANN"}, actor=ADMIN)
    assert a.username == "ann" and a.email == "ann@school.org"
    assert SD.for_username("Ann").staff_id == a.staff_id == SD.me(ANN).staff_id
    with pytest.raises(SD.ValidationError, match="already has a record"):
        SD.create({"first_name": "A", "last_name": "B", "username": "ann"}, actor=ADMIN)
    with pytest.raises(SD.ValidationError, match="No active staff login"):
        SD.create({"first_name": "A", "last_name": "B", "username": "ghost"}, actor=ADMIN)


def test_import_logins_makes_records_once():
    made = SD.import_logins(actor=ADMIN)
    assert {m.username for m in made} == {"ann", "head", "admin2"}
    head = SD.for_username("head")
    assert (head.title, head.first_name, head.last_name) == ("Mr", "Bob", "Head")
    assert SD.for_username("admin2").role == "Administrator"
    assert SD.import_logins(actor=ADMIN) == [] and SD.unlinked_logins() == []


def test_permissions_and_redaction():
    c = _person(home_address="1 High St", emergency_contact_name="Dan", salary_amount="30000")
    with pytest.raises(SD.PermissionDenied):
        SD.create({"first_name": "X", "last_name": "Y"}, actor=ANN)
    with pytest.raises(SD.PermissionDenied):
        SD.update(c.staff_id, {"room": "A1"}, actor=ANN)
    with pytest.raises(SD.PermissionDenied):
        SD.profile(c.staff_id, actor=PUPIL)
    seen = SD.list_staff(actor=ANN)[0]
    assert seen.home_address is None and seen.salary_amount is None and seen.room is None
    assert SD.list_staff(actor=ADMIN)[0].home_address == "1 High St"
    assert SD.profile(c.staff_id, actor=ANN)["member"].emergency_contact_name is None
    assert "1 High St" in SD.profile_text(c.staff_id, actor=ADMIN)
    assert "1 High St" not in SD.profile_text(c.staff_id, actor=ANN)


def test_line_manager_rules_and_reports():
    boss = _person(first_name="Bea", last_name="Boss", role="Principal")
    c = _person(line_manager_id=boss.label)
    assert c.line_manager_id == boss.staff_id and c.line_manager_name == "Bea Boss"
    assert [r.staff_id for r in SD.reports_to(boss.staff_id)] == [c.staff_id]
    with pytest.raises(SD.ValidationError, match="own line manager"):
        SD.update(c.staff_id, {"line_manager_id": c.staff_id}, actor=ADMIN)
    with pytest.raises(SD.ValidationError, match="reports"):
        SD.update(boss.staff_id, {"line_manager_id": c.staff_id}, actor=ADMIN)


def test_ect_needs_teaching_role_and_shows_in_summary():
    with pytest.raises(SD.ValidationError, match="Only teaching staff"):
        _person(ect_status="ECT year 1")
    t = _person(first_name="Ed", last_name="New", role="Teacher", ect_status="ECT year 1",
                qts_date="2026-07-01")
    assert t.qts and t.in_induction
    s = SD.summary()
    assert [m.staff_id for m in s["ects_without_mentor"]] == [t.staff_id]
    assert "Principal" in s["unfilled_critical"]
    mentor = _person(first_name="Mo", last_name="Mentor", role="Teacher")
    SD.update(t.staff_id, {"ect_mentor_id": mentor.staff_code}, actor=ADMIN)
    assert SD.summary()["ects_without_mentor"] == []
    assert [m.staff_id for m in SD.mentees(mentor.staff_id)] == [t.staff_id]


def test_leavers_kept_reinstate_and_delete_rules():
    c = _person(start_date="2020-09-01")
    left = SD.mark_left(c.staff_id, "2026-08-31", reason="Retired", actor=ADMIN)
    assert left.is_leaver and left.employment_status == "Left"
    assert SD.list_staff() == [] and [m.staff_id for m in SD.list_staff(leavers_only=True)] \
        == [c.staff_id]
    with pytest.raises(SD.ValidationError, match="leavers' records are kept"):
        SD.delete(c.staff_id, actor=ADMIN)
    back = SD.reinstate(c.staff_id, actor=ADMIN, status="Part-time")
    assert not back.is_leaver and back.leave_date is None
    boss = _person(first_name="Bea", last_name="Boss")
    SD.update(c.staff_id, {"line_manager_id": boss.staff_id}, actor=ADMIN)
    with pytest.raises(SD.ValidationError, match="direct report"):
        SD.delete(boss.staff_id, actor=ADMIN)
    d = DP.create({"name": "Science"}, actor=ADMIN)
    DP.add_member(d.department_id, {"staff_id": c.staff_id}, actor=ADMIN)
    with pytest.raises(SD.ValidationError, match="department membership"):
        SD.delete(c.staff_id, actor=ADMIN)
    oops = _person(first_name="Typo")
    assert SD.delete(oops.staff_id, actor=ADMIN) and SD.find(oops.staff_id) is None
    assert any(h["action"] == "leave" for h in SD.history(c.staff_id))


def test_future_leave_date_is_still_current():
    later = (dt.date.today() + dt.timedelta(days=30)).isoformat()
    c = _person(leave_date=later)
    assert not c.is_leaver and SD.list_staff()[0].staff_id == c.staff_id


def test_search_and_filters():
    _person()
    t = _person(first_name="Tom", last_name="Maths", role="Teacher", department="Mathematics",
                is_dsl=True)
    assert [m.staff_id for m in SD.list_staff(search="math")] == [t.staff_id]
    assert [m.staff_id for m in SD.list_staff(role_type="teaching")] == [t.staff_id]
    assert [m.staff_id for m in SD.list_staff(dsl=True)] == [t.staff_id]
    assert [m.staff_id for m in SD.list_staff(department="mathematics")] == [t.staff_id]


def test_profile_reads_forms_groups_and_timetable():
    ann = SD.create({"first_name": "Ann", "last_name": "Teacher", "username": "ann"},
                    actor=ADMIN)
    FG.create({"name": "8A", "year_group": 8, "tutor_name": "Ann Teacher"}, actor=ADMIN)
    m = S.create({"code": "MATH", "name": "Mathematics"}, actor=ADMIN)
    g = TG.create({"code": "8/Ma1", "subject_id": m.subject_id, "year_group": 8,
                   "teacher_username": "ann", "room": "M1"}, actor=ADMIN)
    TT.add_lesson({"group_id": g.group_id, "day": "Mon", "period": 1}, actor=ADMIN)
    p = SD.profile(ann.staff_id, actor=ANN)
    assert [(f.name, role) for f, role in p["forms"]] == [("8A", "Tutor")]
    assert [x.code for x in p["groups"]] == ["8/Ma1"]
    assert len(p["lessons"]) == 1 and p["cover"] == []
    text = SD.profile_text(ann.staff_id, actor=ANN)
    assert "8A (Year 8) - Tutor" in text and "8/Ma1" in text


def test_export_csv_personal_only_for_editors(tmp_path):
    _person(home_address="1 High St")
    path = tmp_path / "staff.csv"
    assert SD.export_csv(path, actor=ANN) == 1
    rows = list(csv.reader(open(path, encoding="utf-8")))
    assert "home_address" not in rows[0]
    with pytest.raises(SD.PermissionDenied):
        SD.export_csv(path, actor=ANN, include_personal=True)
    SD.export_csv(path, actor=ADMIN, include_personal=True)
    rows = list(csv.reader(open(path, encoding="utf-8")))
    assert rows[1][rows[0].index("home_address")] == "1 High St"
