"""Departments (modules.staff.domain.departments)."""

from __future__ import annotations

import csv

import pytest

from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.staff.domain import departments as DP
from education_system.systems.secondary.modules.staff.domain import staff_directory as SD
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
ANN = Principal(username="ann", role="teacher")
BOB = Principal(username="bob", role="teacher")
LOGINS = [{"username": u, "display_name": n, "email": f"{u}@school.org", "role": "teacher"}
          for u, n in (("ann", "Ann Head"), ("bob", "Bob Other"))]


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


@pytest.fixture
def people():
    ann = SD.create({"first_name": "Ann", "last_name": "Head", "username": "ann",
                     "role": "Head of Department"}, actor=ADMIN)
    bob = SD.create({"first_name": "Bob", "last_name": "Other", "username": "bob",
                     "fte": "1"}, actor=ADMIN)
    ta = SD.create({"first_name": "Tia", "last_name": "Assist", "role": "Teaching Assistant",
                    "contract_type": "Part-time", "fte": "0.5"}, actor=ADMIN)
    return ann, bob, ta


def test_department_fields_head_second_become_members(people):
    ann, bob, _ta = people
    d = DP.create({"name": "Science", "code": "sci", "faculty": "Sciences",
                   "head_id": ann.label, "second_id": bob.staff_code}, actor=ADMIN)
    assert (d.code, d.head_name, d.second_name, d.member_count) == (
        "SCI", "Ann Head", "Bob Other", 2)
    roles = {m.staff_name: m.role_in_department for m in DP.list_memberships(d.department_id)}
    assert roles == {"Ann Head": "Head of Department", "Bob Other": "Deputy / 2nd in Dept"}
    with pytest.raises(DP.ValidationError, match="already a department"):
        DP.create({"name": "science"}, actor=ADMIN)
    with pytest.raises(DP.ValidationError, match="must be different"):
        DP.update(d.department_id, {"second_id": ann.staff_id}, actor=ADMIN)
    with pytest.raises(DP.PermissionDenied):
        DP.create({"name": "Art"}, actor=ANN)


def test_budget_spend_status_and_lists(people):
    d = DP.create({"name": "English", "budget_total": "1000"}, actor=ADMIN)
    d = DP.add_spend(d.department_id, amount="1200.50", actor=ADMIN)
    assert d.budget_over and d.budget_remaining == -200.5
    assert [x.name for x in DP.list_departments(over_budget=True)] == ["English"]
    DP.set_status(d.department_id, "Restructuring", actor=ADMIN)
    assert DP.list_departments(active_only=True) == []
    with pytest.raises(DP.ValidationError, match="below zero"):
        DP.add_spend(d.department_id, amount="-5000", actor=ADMIN)
    s = DP.summary()
    assert (s["total"], s["over_budget"], s["by_status"]) == (1, 1, {"Restructuring": 1})


def test_memberships_primary_syncs_staff_department_and_end(people):
    ann, bob, ta = people
    d = DP.create({"name": "Maths"}, actor=ADMIN)
    m = DP.add_member(d.department_id, {"staff_id": ta.staff_id,
                                        "role_in_department": "Teaching Assistant",
                                        "is_primary": True}, actor=ADMIN)
    assert SD.get(ta.staff_id).department == "Maths"
    with pytest.raises(DP.ValidationError, match="already a member"):
        DP.add_member(d.department_id, {"staff_id": ta.staff_id}, actor=ADMIN)
    ended = DP.end_membership(m.membership_id, actor=ADMIN)
    assert ended.left_on and not ended.is_current
    assert DP.member_count(d.department_id) == 0
    assert [x.department_name for x in DP.memberships_for_staff(ta.staff_id)] == ["Maths"]
    with pytest.raises(DP.ValidationError, match="already ended"):
        DP.end_membership(m.membership_id, actor=ADMIN)
    assert DP.delete_membership(m.membership_id, actor=ADMIN)


def test_subjects_build_on_the_subject_department_field(people):
    sci = S.create({"code": "BIO", "name": "Biology", "department": "Science"}, actor=ADMIN)
    chem = S.create({"code": "CHEM", "name": "Chemistry"}, actor=ADMIN)
    made = DP.import_from_subjects(actor=ADMIN)
    assert [d.name for d in made] == ["Science"]
    d = made[0]
    assert [s.code for s in DP.subjects_for(d.department_id)] == ["BIO"]
    DP.assign_subject(d.department_id, chem.subject_id, actor=ADMIN)
    assert S.get(chem.subject_id).department == "Science"
    DP.update(d.department_id, {"name": "Sciences"}, actor=ADMIN)
    assert {S.get(x).department for x in (sci.subject_id, chem.subject_id)} == {"Sciences"}
    DP.remove_subject(d.department_id, chem.subject_id, actor=ADMIN)
    assert S.get(chem.subject_id).department is None
    assert [s.code for s in DP.unassigned_subjects()] == ["CHEM"]


def test_meetings_head_edits_own_department(people):
    ann, bob, _ta = people
    d = DP.create({"name": "Science", "head_id": ann.staff_id}, actor=ADMIN)
    other = DP.create({"name": "Art"}, actor=ADMIN)
    mt = DP.add_meeting(d.department_id, {"title": "Autumn review", "attendees": "Ann, Bob",
                                          "minutes": "Discussed KS3."}, actor=ANN)
    with pytest.raises(DP.PermissionDenied):
        DP.add_meeting(other.department_id, {}, actor=ANN)
    with pytest.raises(DP.PermissionDenied):
        DP.add_meeting(d.department_id, {}, actor=BOB)
    a = DP.add_action(mt.meeting_id, {"description": "Order microscopes",
                                      "owner": bob.label, "due_date": "2020-01-01"}, actor=ANN)
    assert a.overdue and a.owner_name == "Bob Other"
    done = DP.set_action_status(a.action_id, "Done", actor=BOB)  # the owner closes it
    assert done.status == "Done" and done.done_by == "bob"
    assert "Order microscopes" in DP.minutes_text(mt.meeting_id)
    with pytest.raises(DP.ValidationError, match="Archived instead"):
        DP.delete(d.department_id, actor=ADMIN)
    assert DP.delete(other.department_id, actor=ADMIN)


def test_overview_counts(people):
    ann, bob, ta = people
    m = S.create({"code": "MATH", "name": "Mathematics", "department": "Maths"}, actor=ADMIN)
    d = DP.create({"name": "Maths", "head_id": ann.staff_id}, actor=ADMIN)
    DP.add_member(d.department_id, {"staff_id": ta.staff_id}, actor=ADMIN)
    TG.create({"code": "8/Ma1", "subject_id": m.subject_id, "year_group": 8,
               "teacher_username": "ann", "lessons_per_week": 4}, actor=ADMIN)
    o = DP.overview(d.department_id, actor=BOB)
    c = o["counts"]
    assert (c["staff"], c["teaching_staff"], c["fte"], c["subjects"], c["groups"],
            c["lessons_per_week"]) == (2, 1, 1.5, 1, 1, 4)


def test_export(people, tmp_path):
    DP.create({"name": "Science"}, actor=ADMIN)
    path = tmp_path / "d.csv"
    assert DP.export_csv(path, actor=ANN) == 1
    assert list(csv.reader(open(path, encoding="utf-8")))[1][1] == "Science"
