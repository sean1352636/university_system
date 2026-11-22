"""The add-learner details that match the other systems' add-learner forms:
identity, address, emergency contact, needs and medical, the duplicate check,
editing without losing hidden fields, and creating the learner's login."""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from education_system.systems.fe_college.domain.students.models import Student, ValidationError

FULL = {
    "student_id": "", "first_name": "Leo", "middle_name": "James", "last_name": "Grant",
    "preferred_name": "Lee", "date_of_birth": date(2008, 5, 6), "gender": "Male",
    "email": "leo.grant@example.org", "phone": "07700 900111",
    "address": "2 Mill Lane", "town": "Hull", "postcode": "hu12aa",
    "emergency_contact_name": "Kim Grant", "emergency_contact_relationship": "Parent",
    "emergency_contact_phone": "07700 900222",
    "has_lldd": True, "has_ehcp": True, "medical_notes": "Nut allergy",
    "learning_support": "Reader in exams", "start_date": date(2026, 9, 1),
    "end_date": date(2028, 7, 1),
}


@pytest.fixture(autouse=True)
def platform_auth_db(tmp_path, monkeypatch):
    """Keep every shared-login and platform write off the live ``auth.db``.

    ``auth.db.connect()`` reads ``PLATFORM_AUTH_DB_FILE`` when called, so
    repointing it moves them all; the cross-system "schema ready" caches are
    reset or the new file would never get its tables.
    """
    from education_system import paths
    from education_system.platform.cross_system import (
        destinations,
        enrolment_schema,
        identity_service,
        qualifications,
    )
    from education_system.platform.identity.auth import db as auth_db
    from education_system.platform.identity.auth.schema import initialise_auth_db

    path = tmp_path / "platform_auth.db"
    for module, name in ((auth_db, "PLATFORM_AUTH_DB_FILE"), (auth_db, "AUTH_DB_FILE"),
                         (paths, "PLATFORM_AUTH_DB_FILE"), (paths, "PLATFORM_AUTH_DB")):
        value = str(path) if isinstance(getattr(module, name, None), str) else path
        monkeypatch.setattr(module, name, value, raising=False)
    for module in (identity_service, enrolment_schema, destinations, qualifications):
        monkeypatch.setattr(module, "_initialised", set())
    initialise_auth_db(str(path))
    yield str(path)


@pytest.fixture(autouse=True)
def college_db(tmp_path, monkeypatch):
    """A fresh FE College database, and no real e-mail delivery."""
    from education_system.systems.fe_college.infrastructure import persistence
    from education_system.systems.fe_college.infrastructure.persistence import schema
    from education_system.systems.fe_college.services import email_service

    persistence.set_db_path(tmp_path / "fe_college.db")
    schema.init_db()
    monkeypatch.setattr(email_service, "_delivery_configured", lambda: False)
    yield
    persistence.set_db_path(None)


@pytest.fixture
def students():
    from education_system.systems.fe_college.services import student_service
    return student_service


@pytest.fixture
def accounts():
    from education_system.systems.fe_college.services import learner_accounts
    return learner_accounts


class TestDetails:
    def test_every_detail_is_stored(self, students):
        learner = students.get(students.create(Student(**FULL)).student_id)
        assert learner.legal_name == "Leo James Grant"
        assert learner.preferred_name == "Lee"
        assert learner.gender == "Male"
        assert learner.full_address == "2 Mill Lane, Hull, HU1 2AA"
        assert (learner.emergency_contact_name, learner.emergency_contact_relationship,
                learner.emergency_contact_phone) == ("Kim Grant", "Parent", "07700 900222")
        assert learner.has_lldd is True and learner.has_ehcp is True
        assert learner.medical_notes == "Nut allergy"

    @pytest.mark.parametrize("change, message", [
        ({"postcode": "NOT A POSTCODE"}, "postcode"),
        ({"gender": "Unknown"}, "Gender"),
        ({"emergency_contact_phone": "call me"}, "phone"),
        ({"emergency_contact_phone": ""}, "both a name and a phone"),
        ({"medical_notes": "x" * 2001}, "2000"),
    ])
    def test_bad_details_are_refused(self, students, change, message):
        with pytest.raises(ValidationError, match=message):
            students.create(Student(**{**FULL, **change}))

    def test_the_edit_form_keeps_what_it_does_not_show(self, students):
        """Edit used to rebuild the record from the form alone, blanking
        learning support and the end date."""
        from education_system.systems.fe_college.interfaces.gui.windows.admin import (
            students as screen,
        )

        learner = students.get(students.create(Student(**FULL)).student_id)
        values = screen._from_student(learner)
        for key in ("date_of_birth", "start_date"):       # the form hands back dates
            values[key] = date.fromisoformat(values[key]) if values[key] else None
        values["town"] = "York"
        students.update(screen._to_student(values, base=learner))

        saved = students.get(learner.student_id)
        assert saved.town == "York"
        assert saved.learning_support == "Reader in exams"
        assert saved.end_date == date(2028, 7, 1)


class TestDuplicates:
    def test_same_name_and_birthday_is_caught_when_asked(self, students):
        first = students.create(Student(**FULL))
        with pytest.raises(students.DuplicateLearner) as caught:
            students.create(Student(**{**FULL, "email": ""}), check_duplicate=True)
        assert caught.value.matches[0].student_id == first.student_id

    def test_same_email_is_caught(self, students):
        students.create(Student(**FULL))
        with pytest.raises(students.DuplicateLearner):
            students.create(
                Student(**{**FULL, "first_name": "Other", "date_of_birth": date(2001, 1, 1)}),
                check_duplicate=True,
            )

    def test_staff_can_save_anyway(self, students):
        """Twins share a surname and a birthday; the check is a prompt, not a wall."""
        students.create(Student(**FULL))
        assert students.create(Student(**{**FULL, "email": ""})).student_id


class TestLogin:
    def test_creates_a_login_that_works(self, students, accounts, platform_auth_db):
        learner = students.create(Student(**FULL))
        new = accounts.create_login(learner.student_id)

        assert new.username == learner.student_id
        row = sqlite3.connect(platform_auth_db).execute(
            "SELECT us.system_key, us.role FROM users u "
            "JOIN user_systems us ON us.user_id = u.id WHERE u.username = ?",
            (new.username,),
        ).fetchone()
        assert tuple(row) == ("fe_college", "student")

        from education_system.platform.identity.auth.core import UserAuth
        assert UserAuth().login(new.username, new.password)

    def test_welcome_email_goes_to_the_learner(self, students, accounts):
        from education_system.systems.fe_college.services import email_service

        learner = students.create(Student(**FULL))
        new = accounts.create_login(learner.student_id)
        sent = email_service.for_learner(learner.student_id)
        assert any(m.subject.endswith("login, Lee") for m in sent)
        assert "Email centre" in new.welcome_detail

    def test_no_email_address_means_no_welcome(self, students, accounts):
        learner = students.create(Student(**{**FULL, "email": ""}))
        assert "no welcome e-mail" in accounts.create_login(learner.student_id).welcome_detail

    def test_an_existing_login_is_never_changed(self, students, accounts):
        learner = students.create(Student(**FULL))
        accounts.create_login(learner.student_id)
        assert accounts.has_login(learner.student_id)
        with pytest.raises(ValidationError, match="already has a login"):
            accounts.create_login(learner.student_id)
