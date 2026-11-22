"""Sixth form Add Student asks for what the other systems' add forms ask for.

Covers the parts that are not plain record columns: needs and medical
notes routed to their registers (``new_learner``), and the emergency
contact pick list / name-and-phone rule shared with FE College and
Apprenticeships. No database: the record and register writers are
replaced, so nothing reaches sixthform.db or auth.db.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from education_system.systems.sixth_form.domain.learners.students import (
    new_learner,
    student_profile,
)
from education_system.systems.sixth_form.domain.learners.students.student_profile import (
    ValidationError,
)


# ── Emergency contact ────────────────────────────────────────────────

class TestRelationship:
    def test_same_pick_list_as_fe_college(self):
        from education_system.systems.fe_college import config as fe

        assert student_profile.EMERGENCY_RELATIONSHIPS == fe.EMERGENCY_RELATIONSHIPS

    @pytest.mark.parametrize("raw, expected", [
        ("parent", "Parent"),
        ("  OTHER relative ", "Other relative"),
        ("father", "Parent"),
        ("Mum", "Parent"),
        ("Parent/Carer", "Parent"),   # college_intake's value
        ("sister", "Sibling"),
        ("Nan", "Grandparent"),
        ("wife", "Spouse"),
        ("uncle", "Other relative"),
    ])
    def test_maps_onto_the_list(self, raw, expected):
        assert student_profile.normalise_relationship(raw) == expected

    def test_blank_is_none(self):
        assert student_profile.normalise_relationship("   ") is None
        assert student_profile.normalise_relationship(None) is None

    def test_unknown_text_from_imports_is_kept(self):
        assert student_profile.normalise_relationship("Social worker") == "Social worker"

    def test_over_long_text_refused(self):
        with pytest.raises(ValidationError):
            student_profile.normalise_relationship("x" * 41)


class TestEmergencyContactRule:
    def test_all_blank_is_fine(self):
        student_profile.check_emergency_contact({})

    def test_name_and_phone_is_fine(self):
        student_profile.check_emergency_contact({
            "emergency_contact_name": "Ann Smith",
            "emergency_contact_phone": "07700 900123",
            "emergency_contact_relation": "Parent"})

    @pytest.mark.parametrize("payload", [
        {"emergency_contact_name": "Ann Smith"},
        {"emergency_contact_phone": "07700 900123"},
        {"emergency_contact_relation": "Parent"},
    ])
    def test_half_a_contact_refused(self, payload):
        with pytest.raises(ValidationError, match="both a name and a phone"):
            student_profile.check_emergency_contact(payload)


# ── Needs and medical ────────────────────────────────────────────────

class TestValidateNeeds:
    def test_reads_ticks_and_yes_no_text(self):
        out = new_learner.validate_needs({
            "has_lldd": "yes", "has_ehcp": False,
            "send_details": "  dyslexia ", "medical_notes": ""})
        assert out == {"has_lldd": True, "has_ehcp": False,
                       "send_details": "dyslexia", "medical_notes": ""}

    @pytest.mark.parametrize("key", ["send_details", "medical_notes"])
    def test_length_limit(self, key):
        with pytest.raises(ValidationError):
            new_learner.validate_needs({key: "x" * (student_profile.NOTES_MAX_LENGTH + 1)})


@pytest.fixture
def fake_record(monkeypatch):
    """Replace the record write and the register writers; return the calls."""
    calls = SimpleNamespace(create=[], send=[], medical=[], history=[])

    def create_student(record, *, allow_duplicate=False, password=None):
        calls.create.append((record, allow_duplicate, password))
        return SimpleNamespace(student_id="C1234567", **record)

    monkeypatch.setattr(new_learner._s, "create_student", create_student)
    monkeypatch.setattr(new_learner._s, "record_history",
                        lambda sid, field, **kw: calls.history.append((sid, field, kw)))
    monkeypatch.setattr(new_learner, "_to_send_register",
                        lambda sid, needs: calls.send.append((sid, needs)) or "send ok")
    monkeypatch.setattr(new_learner, "_to_medical_profile",
                        lambda sid, text: calls.medical.append((sid, text)) or "medical ok")
    return calls


class TestAddLearner:
    def test_needs_are_not_stored_on_the_record(self, fake_record):
        new_learner.add_learner({
            "first_name": "Amy", "last_name": "Lee", "notes": "Keen on chess",
            "has_lldd": True, "has_ehcp": True, "send_details": "ASD",
            "medical_notes": "Asthma; inhaler in bag"})
        record, allow_duplicate, password = fake_record.create[0]
        assert not set(new_learner.NEEDS_KEYS) & set(record)
        assert record["notes"] == "Keen on chess"
        assert allow_duplicate is False
        assert password and len(password) == 12

    def test_needs_and_medical_go_to_their_registers(self, fake_record):
        added = new_learner.add_learner({
            "first_name": "Amy", "last_name": "Lee",
            "has_ehcp": "y", "medical_notes": "Asthma"})
        assert [sid for sid, _n in fake_record.send] == ["C1234567"]
        assert fake_record.send[0][1]["has_ehcp"] is True
        assert fake_record.medical == [("C1234567", "Asthma")]
        assert added.needs == ["send ok", "medical ok"]

    def test_nothing_declared_writes_no_register(self, fake_record):
        added = new_learner.add_learner({"first_name": "Amy", "last_name": "Lee"})
        assert fake_record.send == [] and fake_record.medical == []
        assert added.needs == []

    def test_allow_duplicate_passed_through(self, fake_record):
        new_learner.add_learner({"first_name": "Amy", "last_name": "Lee"},
                                allow_duplicate=True)
        assert fake_record.create[0][1] is True

    def test_bad_needs_refused_before_the_record_is_written(self, fake_record):
        with pytest.raises(ValidationError):
            new_learner.add_learner({
                "first_name": "Amy", "last_name": "Lee",
                "medical_notes": "x" * (student_profile.NOTES_MAX_LENGTH + 1)})
        assert fake_record.create == []

    def test_password_has_no_lookalike_characters(self):
        for _ in range(50):
            assert not set(new_learner.temporary_password()) & set("0O1lI")


def test_send_register_failure_keeps_the_learner(monkeypatch):
    """A register that refuses the needs is reported, not raised."""
    from education_system.systems.sixth_form.domain.pastoral.send import send as _send

    history = []
    monkeypatch.setattr(new_learner._s, "record_history",
                        lambda sid, field, **kw: history.append(kw.get("note")))

    def refuse(payload):
        raise RuntimeError("register locked")

    monkeypatch.setattr(_send, "create_entry", refuse)
    line = new_learner._to_send_register(
        "C1234567", {"has_lldd": True, "has_ehcp": False,
                     "send_details": "", "medical_notes": ""})
    assert "not added" in line and "register locked" in line
    assert any("not added" in (n or "") for n in history)


# ── Gender and address, the same as every system ─────────────────────

class TestGender:
    def test_same_five_options_as_fe_college(self):
        from education_system.systems.fe_college import config as fe

        assert student_profile.GENDER_OPTIONS == fe.GENDERS

    @pytest.mark.parametrize("raw, code", [
        ("Female", "female"), ("male", "male"), ("Non-binary", "non-binary"),
        ("Prefer not to say", "prefer not to say"), ("M", "male"), ("", None)])
    def test_stored_lower_case(self, raw, code):
        assert student_profile.gender_code(raw) == code

    def test_unknown_refused(self):
        with pytest.raises(ValidationError):
            student_profile.gender_code("robot")

    def test_label_for_display(self):
        assert student_profile.gender_label("non-binary") == "Non-binary"

    def test_applicant_sex_uses_the_same_values(self):
        from education_system.systems.sixth_form.domain.admissions import applicant_details
        from education_system.systems.sixth_form.domain.learners.students import students

        assert applicant_details.SEXES == students.GENDERS == student_profile.GENDER_CODES


class TestAddressLines:
    def _addr(self, **data):
        out = student_profile._validate_profile(data)
        return tuple(out[k] for k in ("address_line1", "address_line2", "town",
                                      "postcode", "address"))

    def test_lines_build_the_joined_address(self):
        assert self._addr(address_line1="1 High St", town="Leeds", postcode="ls14ab") == (
            "1 High St", None, "Leeds", "LS1 4AB", "1 High St\nLeeds")

    def test_one_address_string_is_split(self):
        assert self._addr(address="1 High St, Flat 2, Leeds, LS1 4AB") == (
            "1 High St", "Flat 2", "Leeds", "LS1 4AB", "1 High St\nFlat 2\nLeeds")

    def test_two_parts_are_line_and_town(self):
        assert self._addr(address="1 High St\nLeeds")[:3] == ("1 High St", None, "Leeds")

    def test_old_record_split_for_the_form(self):
        old = SimpleNamespace(address="1 High St\nFlat 2\nLeeds", address_line1=None,
                              address_line2=None, town=None)
        assert student_profile.address_parts(old) == ("1 High St", "Flat 2", "Leeds")
