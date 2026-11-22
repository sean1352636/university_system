"""The add-apprentice details that match the other systems' add-learner forms:
identity, address, emergency contact, needs and medical, the duplicate check,
and creating the apprentice's login."""

from __future__ import annotations

import sqlite3

import pytest

from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.communications import email_service
from education_system.systems.apprenticeships.application.security import account_service
from education_system.systems.apprenticeships.application.security.access import PermissionDenied
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError

FULL = {
    "given_name": "Priya", "middle_name": "Kaur", "family_name": "Shah",
    "preferred_name": "Pri", "date_of_birth": "2004-02-03", "gender": "Female",
    "email": "priya.shah@example.org", "phone": "07700 900123",
    "address_line1": "1 High Street", "town": "Leeds", "postcode": "ls11aa",
    "emergency_contact_name": "Anita Shah", "emergency_contact_relationship": "Parent",
    "emergency_contact_phone": "07700 900456",
    "has_lldd": True, "has_ehcp": False, "medical_notes": "Asthma; inhaler in bag",
}


@pytest.fixture(autouse=True)
def no_smtp(monkeypatch):
    """Never try real delivery from a test."""
    monkeypatch.setattr(email_service, "_delivery_configured", lambda: False)


class TestDetails:
    def test_every_detail_is_stored(self, db, admin):
        record = apprentice_service.create_apprentice(admin, FULL)
        assert record.legal_name == "Priya Kaur Shah"
        assert record.preferred_name == "Pri"
        assert record.gender == "Female"
        assert record.address == "1 High Street, Leeds, LS1 1AA"
        assert (record.emergency_contact_name, record.emergency_contact_relationship,
                record.emergency_contact_phone) == ("Anita Shah", "Parent", "07700 900456")
        assert record.has_lldd is True and record.has_ehcp is False
        assert record.medical_notes == "Asthma; inhaler in bag"

    def test_a_partial_edit_keeps_the_rest(self, db, admin):
        record = apprentice_service.create_apprentice(admin, FULL)
        updated = apprentice_service.update_apprentice(
            admin, record.apprentice_id, {"town": "York", "has_ehcp": True},
        )
        assert updated.town == "York" and updated.has_ehcp is True
        assert updated.postcode == "LS1 1AA" and updated.medical_notes

    @pytest.mark.parametrize("change, message", [
        ({"postcode": "NOT A POSTCODE"}, "postcode"),
        ({"gender": "Unknown"}, "Gender"),
        ({"emergency_contact_phone": "call me"}, "phone"),
        ({"emergency_contact_phone": ""}, "both a name and a phone"),
        ({"medical_notes": "x" * 2001}, "2000"),
    ])
    def test_bad_details_are_refused(self, db, admin, change, message):
        with pytest.raises(ValidationError, match=message):
            apprentice_service.create_apprentice(admin, {**FULL, **change})


class TestDuplicates:
    def test_same_name_and_birthday_is_caught_when_asked(self, db, admin):
        apprentice_service.create_apprentice(admin, FULL)
        with pytest.raises(apprentice_service.DuplicateApprentice) as caught:
            apprentice_service.create_apprentice(
                admin, {**FULL, "email": ""}, check_duplicate=True,
            )
        assert caught.value.matches[0].full_name == "Priya Shah"

    def test_same_email_is_caught(self, db, admin):
        apprentice_service.create_apprentice(admin, FULL)
        with pytest.raises(apprentice_service.DuplicateApprentice):
            apprentice_service.create_apprentice(
                admin, {**FULL, "given_name": "Other", "date_of_birth": "2001-01-01"},
                check_duplicate=True,
            )

    def test_staff_can_save_anyway(self, db, admin):
        """Twins share a surname and a birthday; the check is a prompt, not a wall."""
        apprentice_service.create_apprentice(admin, FULL)
        twin = apprentice_service.create_apprentice(admin, {**FULL, "email": ""})
        assert twin.apprentice_id

    def test_the_check_is_off_by_default(self, db, admin):
        """Cross-system handovers call create without it and must never be blocked."""
        apprentice_service.create_apprentice(admin, FULL)
        apprentice_service.create_apprentice(admin, {**FULL, "email": ""})


class TestLogin:
    def test_creates_a_login_that_works(self, db, admin, platform_auth_db):
        record = apprentice_service.create_apprentice(admin, FULL)
        new = account_service.create_apprentice_login(admin, record.apprentice_id)

        assert new.username == "pshah"
        row = sqlite3.connect(platform_auth_db).execute(
            "SELECT us.system_key, us.role FROM users u "
            "JOIN user_systems us ON us.user_id = u.id WHERE u.username = ?",
            (new.username,),
        ).fetchone()
        assert tuple(row) == ("apprenticeships", "apprentice")
        assert apprentice_service.get_apprentice(
            admin, record.apprentice_id).apprentice.username == "pshah"

        from education_system.platform.identity.auth.core import UserAuth
        assert UserAuth().login(new.username, new.password)

    def test_welcome_email_goes_to_the_apprentice(self, db, admin):
        record = apprentice_service.create_apprentice(admin, FULL)
        new = account_service.create_apprentice_login(admin, record.apprentice_id)
        sent = email_service.for_apprentice(admin, record.apprentice_id)
        assert any(m["subject"].startswith("Your apprenticeship login") for m in sent)
        assert "Correspondence" in new.welcome_detail

    def test_no_email_address_means_no_welcome(self, db, admin):
        record = apprentice_service.create_apprentice(admin, {**FULL, "email": ""})
        new = account_service.create_apprentice_login(admin, record.apprentice_id)
        assert "no welcome e-mail" in new.welcome_detail

    def test_a_taken_username_gets_a_number(self, db, admin):
        first = apprentice_service.create_apprentice(admin, FULL)
        second = apprentice_service.create_apprentice(
            admin, {**FULL, "email": "", "given_name": "Pavan"},
        )
        account_service.create_apprentice_login(admin, first.apprentice_id)
        assert account_service.create_apprentice_login(
            admin, second.apprentice_id).username == "pshah2"

    def test_an_existing_login_is_never_changed(self, db, admin):
        record = apprentice_service.create_apprentice(admin, FULL)
        account_service.create_apprentice_login(admin, record.apprentice_id)
        with pytest.raises(ValidationError, match="already has a login"):
            account_service.create_apprentice_login(admin, record.apprentice_id)

    def test_only_a_manager_may_create_one(self, db, admin, cohort):
        with pytest.raises(PermissionDenied):
            account_service.create_apprentice_login(
                cohort["tutor"], cohort["apprentice_id"],
            )
