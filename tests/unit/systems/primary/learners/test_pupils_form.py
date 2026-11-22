"""The primary Add Pupil form and profile ask/show the same things as the
secondary school's (identity, school, address, needs) plus parent/carer and
medical. No Tk window is opened: these read the form's field table."""

from __future__ import annotations

from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.interfaces.gui.learners.pupils import pupil_views

PARITY = {"first_name", "middle_names", "last_name", "preferred_name", "date_of_birth",
          "gender", "upn", "year_group", "class_name", "admission_date", "roll_status",
          "left_date", "exit_reason", "address_line1", "address_line2", "town",
          "postcode", "sen_status", "fsm_eligible", "eal", "notes", "parent_name",
          "parent_relationship", "parent_phone", "parent_email", "medical_notes"}


def test_form_asks_every_parity_field_in_sections():
    assert set(pupil_views._FIELDS) == PARITY
    assert [title for title, _keys in pupil_views._SECTIONS] == [
        "Identity", "School", "Address", "Needs", "Parent / carer", "Medical"]
    assert set(pupil_views._LABELS) >= PARITY


def test_form_choices_match_the_domain_lists():
    assert [v for v, _l in pupil_views._SEN_CHOICES] == ["N", "K", "E"]
    assert [v for v, _l in pupil_views._ROLL_CHOICES] == list(P.ROLL_STATUSES)
    assert P.GENDERS == ("Female", "Male")


def test_edit_form_starts_from_every_stored_field():
    made = P.create_pupil({"first_name": "Ada", "last_name": "Lovelace", "year_group": "3",
                           "gender": "Female", "town": "Bath", "sen_status": "K"})
    initial = pupil_views._initial_from(P.get_pupil(made.pupil_id))
    assert set(initial) == PARITY
    assert (initial["gender"], initial["town"], initial["sen_status"]) == (
        "Female", "Bath", "K")


def test_profile_shows_each_section():
    made = P.create_pupil({"first_name": "Ada", "last_name": "Lovelace", "year_group": "3",
                           "postcode": "BA1 1AA", "parent_email": "anne@example.com",
                           "medical_notes": "Asthma", "sen_status": "E"})
    sections = dict(pupil_views._profile_sections(made))
    assert list(sections) == ["Identity", "School", "Address", "Needs",
                              "Parent / carer", "Medical"]
    flat = {k: v for items in sections.values() for k, v in items}
    assert flat["Postcode"] == "BA1 1AA"
    assert flat["Parent e-mail"] == "anne@example.com"
    assert flat["Medical notes"] == "Asthma"
    assert flat["SEN"].startswith("E ")
