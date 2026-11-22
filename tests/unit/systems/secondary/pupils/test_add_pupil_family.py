"""Add Pupil asks the same things as the primary school: as well as the pupil
record, the first parent/carer (-> pupil_contacts, priority 1) and medical /
care notes (-> the medical register). Scratch databases only."""

from __future__ import annotations

import pytest

from education_system.systems.secondary.modules.medical.domain import medical as M
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="teacher1", role="teacher")


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    monkeypatch.setattr(accounts, "staff_logins", lambda: [])
    yield tmp_path
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


def _data(**over):
    base = {"legal_first_name": "Ada", "legal_last_name": "Lovelace",
            "date_of_birth": "2014-04-02", "gender": "Female", "year_group": 7,
            "admission_date": "2025-09-03"}
    base.update(over)
    return base


PARENT = {"full_name": "Anne Lovelace", "relationship": "Mother",
          "phone": "01234 567890", "email": "Anne@Example.com"}


def test_add_saves_pupil_parent_and_care_notes():
    pupil, warnings = P.create_pupil_with_family(
        _data(), actor=ADMIN, contact=PARENT, medical_notes="Inhaler in bag")
    assert warnings == []
    [contact] = C.list_for_pupil(pupil.pupil_id)
    assert (contact.full_name, contact.relationship, contact.priority) == (
        "Anne Lovelace", "Mother", 1)
    assert contact.phone == "01234 567890" and contact.email == "anne@example.com"
    assert contact.parental_responsibility is True
    [cond] = M.list_conditions(pupil_id=pupil.pupil_id)
    assert cond.condition == P.CARE_NOTES_CONDITION
    assert cond.notes == "Inhaler in bag"


def test_blank_parent_and_notes_add_only_the_pupil():
    pupil, warnings = P.create_pupil_with_family(
        _data(), actor=ADMIN, contact={"full_name": "", "relationship": "",
                                       "phone": "", "email": ""}, medical_notes="  ")
    assert warnings == []
    assert C.list_for_pupil(pupil.pupil_id) == []
    assert M.list_conditions(pupil_id=pupil.pupil_id) == []


def test_bad_parent_details_save_nothing_and_list_every_problem():
    with pytest.raises(P.ValidationError) as caught:
        P.create_pupil_with_family(
            _data(gender=""), actor=ADMIN,
            contact={"full_name": "Anne", "relationship": "Aunt", "phone": "",
                     "email": "not-an-email"})
    problems = caught.value.problems
    assert any(p.startswith("Gender") for p in problems)
    assert any(p.startswith("Parent / carer: Relationship") for p in problems)
    assert any("E-mail" in p for p in problems)
    assert P.list_pupils(roll_status=None) == []


def test_parent_needs_a_phone_or_email():
    with pytest.raises(P.ValidationError, match="phone number"):
        P.create_pupil_with_family(_data(), actor=ADMIN,
                                   contact={"full_name": "Anne", "relationship": "Mother"})


def test_duplicate_is_still_caught_and_can_be_confirmed():
    P.create_pupil(_data(), actor=ADMIN)
    with pytest.raises(P.DuplicatePupil):
        P.create_pupil_with_family(_data(), actor=ADMIN, contact=PARENT)
    pupil, _w = P.create_pupil_with_family(_data(), actor=ADMIN, contact=PARENT,
                                           allow_duplicate=True)
    assert [c.full_name for c in C.list_for_pupil(pupil.pupil_id)] == ["Anne Lovelace"]


def test_only_pupil_editors_add():
    with pytest.raises(P.PermissionDenied):
        P.create_pupil_with_family(_data(), actor=TEACHER, contact=PARENT)


def test_a_failed_extra_is_reported_not_raised(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("medical register offline")
    monkeypatch.setattr(M, "add_condition", boom)
    pupil, warnings = P.create_pupil_with_family(_data(), actor=ADMIN, contact=PARENT,
                                                 medical_notes="Epipen")
    assert P.get_pupil(pupil.pupil_id) is not None
    assert len(warnings) == 1 and "medical / care notes were not saved" in warnings[0]
    assert len(C.list_for_pupil(pupil.pupil_id)) == 1


def test_profile_needs_line_shows_care_notes():
    from education_system.systems.secondary.modules.pupils.domain import profile_linked
    pupil, _w = P.create_pupil_with_family(_data(), actor=ADMIN,
                                           medical_notes="Inhaler in bag")
    lines = profile_linked._needs(pupil)
    assert any("Inhaler in bag" in str(line) for line in lines)
