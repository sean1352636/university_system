"""The nursery child record asks the same things as the primary and secondary
schools' Add Pupil (2026-11-05): identity, admission/roll status, address,
needs, parent/carer and medical, plus the nursery's room, key person, funded
hours and allergies.

Every database is under ``tmp_path`` (``init_db`` seeds its five demo
children there, so tests pick out their own rows by name); the journey registration that
``create_child`` attempts (auth.db) is stubbed out. No Tk window is opened:
the GUI tests read the form's field table and profile sections only.
"""

from __future__ import annotations

import builtins
import sqlite3

import pytest

from education_system.systems.nursery.domain.learners.children import children as C


@pytest.fixture(autouse=True)
def nursery_db(tmp_path, monkeypatch):
    from education_system.platform.cross_system import progression
    from education_system.systems.nursery.infrastructure import database

    path = tmp_path / "nursery.db"
    monkeypatch.setattr(database, "NURSERY_DB", path)
    monkeypatch.setattr(database, "ensure_nursery_directories", lambda: None)
    # create_child registers a journey in the platform auth.db; keep it out.
    monkeypatch.setattr(progression, "register_local_student",
                        lambda *a, **k: None)
    return path


def _upn(body: str = "201234567890") -> str:
    return C.upn_check_letter(body) + body


def _full(**over):
    data = {
        "first_name": "Maya", "middle_names": "Grace", "last_name": "Okafor",
        "preferred_name": "May", "date_of_birth": "2021-05-04", "gender": "Female",
        "upn": _upn(), "start_date": "2023-09-04", "roll_status": "on_roll",
        "address_line1": "1 High Street", "address_line2": "Flat 2", "town": "Bath",
        "postcode": "ba11aa", "sen_status": "K", "fsm_eligible": "yes", "eal": "yes",
        "notes": "Loves trains", "parent_name": "Ngozi Okafor",
        "parent_relationship": "mother", "parent_phone": "07123 456789",
        "parent_email": "Ngozi@Example.test", "medical_notes": "Inhaler",
        "room": "Preschool Room", "funded_hours": "30 hours", "allergies": "Peanuts",
    }
    data.update(over)
    return data


# ── Domain ──────────────────────────────────────────────────────────────────

def test_constants_match_the_schools():
    assert C.GENDERS == ("Female", "Male")
    assert C.SEN_STATUSES == {"N": "No special educational need",
                              "K": "SEN support", "E": "EHC plan"}
    assert C.ROLL_STATUS_LABELS["on_roll"] == "On roll"
    assert C.ROLL_STATUS_LABELS["left"] == "Left"
    assert C.PARENT_RELATIONSHIPS[0] == "Mother"
    assert "Other" in C.LEAVING_REASONS


def test_create_stores_every_parity_field_and_keeps_nursery_fields():
    c = C.create_child(_full(), complete=True)
    assert (c.middle_names, c.preferred_name, c.gender) == ("Grace", "May", "Female")
    assert c.upn == _upn()
    assert (c.address_line1, c.address_line2, c.town, c.postcode) == (
        "1 High Street", "Flat 2", "Bath", "BA1 1AA")
    assert (c.sen_status, c.fsm_eligible, c.eal, c.notes) == ("K", True, True, "Loves trains")
    assert (c.parent_relationship, c.parent_email) == ("Mother", "ngozi@example.test")
    assert (c.room, c.funded_hours, c.allergies) == ("Preschool Room", "30 hours", "Peanuts")
    assert c.start_date == c.admission_date == "2023-09-04"
    assert (c.status, c.roll_status, c.roll_status_label) == ("active", "on_roll", "On roll")
    assert c.legal_name == "Maya Grace Okafor"
    assert c.display_name == "May Okafor"
    assert c.sen_label == "SEN support"


def test_old_callers_still_create_without_dob_or_gender():
    c = C.create_child({"first_name": "Old", "last_name": "Way"})
    assert c.status == "active"
    assert c.gender is None and c.start_date is None
    assert (c.fsm_eligible, c.eal) == (False, False)


def test_complete_requires_date_of_birth_and_gender():
    with pytest.raises(C.ValidationError, match="Date of birth is required"):
        C.create_child({"first_name": "A", "last_name": "B", "gender": "Male"},
                       complete=True)
    with pytest.raises(C.ValidationError, match="Gender is required"):
        C.create_child({"first_name": "A", "last_name": "B",
                        "date_of_birth": "2022-01-01"}, complete=True)


def test_complete_defaults_the_start_date_to_today():
    import datetime as dt
    c = C.create_child({"first_name": "A", "last_name": "B", "gender": "Male",
                        "date_of_birth": "2022-01-01"}, complete=True)
    assert c.start_date == dt.date.today().isoformat()


def test_start_date_cannot_precede_birth():
    with pytest.raises(C.ValidationError, match="before the date of birth"):
        C.create_child(_full(start_date="2020-01-01"))


@pytest.mark.parametrize("bad, problem", [
    ("A2012345678", "13 characters"),
    ("I201234567890", "check letter"),
    ("A20123456789X", "digit or a letter"),
])
def test_upn_shape_is_checked(bad, problem):
    with pytest.raises(C.ValidationError, match=problem):
        C.create_child(_full(upn=bad))


def test_upn_check_letter_must_match_and_be_unique():
    wrong = ("B" if _upn()[0] != "B" else "C") + _upn()[1:]
    with pytest.raises(C.ValidationError, match="doesn't match"):
        C.create_child(_full(upn=wrong))
    C.create_child(_full())
    with pytest.raises(C.ValidationError, match="already recorded"):
        C.create_child(_full(first_name="Other"))


@pytest.mark.parametrize("field, value, problem", [
    ("gender", "Unknown", "Gender must be"),
    ("postcode", "NOT A CODE", "UK postcode"),
    ("sen_status", "Z", "N, K or E"),
    ("eal", "maybe", "yes or no"),
    ("parent_email", "nope", "valid address"),
    ("date_of_birth", "2021-02-30", "not a real date"),
])
def test_fields_are_sanity_checked(field, value, problem):
    with pytest.raises(C.ValidationError, match=problem):
        C.create_child(_full(**{field: value}))


def test_duplicate_name_and_birth_date_is_caught_only_when_asked():
    first = C.create_child(_full(upn=""))
    with pytest.raises(C.DuplicateChild) as exc:
        C.create_child(_full(upn="", first_name="maya"), check_duplicate=True)
    assert exc.value.existing.pupil_id == first.pupil_id
    second = C.create_child(_full(upn=""))
    assert second.pupil_id != first.pupil_id


def test_update_with_only_the_old_keys_keeps_everything_else():
    c = C.create_child(_full(), complete=True)
    u = C.update_child(c.pupil_id, {"first_name": "Maya", "last_name": "Okafor-Smith"})
    assert u.last_name == "Okafor-Smith"
    assert (u.upn, u.town, u.sen_status, u.eal) == (_upn(), "Bath", "K", True)
    assert (u.room, u.allergies, u.date_of_birth) == ("Preschool Room", "Peanuts",
                                                      "2021-05-04")


def test_update_without_status_does_not_put_a_leaver_back_on_roll():
    c = C.create_child(_full())
    C.set_status(c.pupil_id, "left", left_date="2025-07-18", exit_reason="Relocated")
    u = C.update_child(c.pupil_id, {"town": "Bristol"})
    assert (u.status, u.town) == ("left", "Bristol")
    assert (u.left_date, u.exit_reason) == ("2025-07-18", "Relocated")


def test_update_changes_parity_fields_when_given():
    c = C.create_child(_full())
    u = C.update_child(c.pupil_id, {"gender": "Male", "sen_status": "", "eal": "no"})
    assert (u.gender, u.sen_status, u.eal) == ("Male", None, False)


def test_left_through_the_form_needs_a_date_and_reason():
    c = C.create_child(_full())
    with pytest.raises(C.ValidationError, match="leaving date"):
        C.update_child(c.pupil_id, {"roll_status": "left"})
    with pytest.raises(C.ValidationError, match="leaving reason"):
        C.update_child(c.pupil_id, {"roll_status": "left", "left_date": "2025-07-18"})
    u = C.update_child(c.pupil_id, {"roll_status": "left", "left_date": "2025-07-18",
                                    "exit_reason": "Moved to school"})
    assert (u.status, u.roll_status_label, u.left_date, u.exit_reason) == (
        "left", "Left", "2025-07-18", "Moved to school")
    back = C.update_child(c.pupil_id, {"roll_status": "on_roll"})
    assert (back.status, back.left_date, back.exit_reason) == ("active", None, None)


def test_set_status_keeps_its_old_signature_and_records_leaving():
    c = C.create_child(_full())
    left = C.set_status(c.pupil_id, "left")
    assert left.status == "left" and left.left_date  # defaults to today
    again = C.set_status(c.pupil_id, "active")
    assert (again.status, again.left_date, again.exit_reason) == ("active", None, None)
    assert C.set_status(c.pupil_id, "on_roll").status == "active"
    with pytest.raises(C.ValidationError):
        C.set_status(c.pupil_id, "gone")


def test_leavers_register_supplies_the_leaving_details():
    from education_system.systems.nursery.domain.learners.leavers import leavers
    c = C.create_child(_full())
    leavers.record_leaver({"pupil_id": c.pupil_id, "leaving_date": "2025-08-01",
                           "reason": "Relocated"})
    got = C.get_child(c.pupil_id)
    assert (got.status, got.left_date, got.exit_reason) == ("left", "2025-08-01",
                                                           "Relocated")


def test_search_matches_preferred_name_and_upn():
    c = C.create_child(_full())
    assert c.pupil_id in [x.pupil_id for x in C.search_children("May")]
    assert [x.pupil_id for x in C.search_children(_upn()[:6])] == [c.pupil_id]


def test_init_db_adds_the_parity_columns_to_an_old_table(nursery_db):
    from education_system.systems.nursery.infrastructure import database
    conn = sqlite3.connect(nursery_db)
    conn.executescript(database._STAFF_SCHEMA)
    conn.execute(
        "CREATE TABLE pupils (pupil_id TEXT PRIMARY KEY, first_name TEXT NOT NULL, "
        "last_name TEXT NOT NULL, date_of_birth TEXT, room TEXT, key_person TEXT, "
        "funded_hours TEXT, start_date TEXT, parent_name TEXT, parent_phone TEXT, "
        "parent_email TEXT, allergies TEXT, medical_notes TEXT, "
        "status TEXT NOT NULL DEFAULT 'active', created_at TEXT)")
    conn.execute("INSERT INTO pupils (pupil_id, first_name, last_name) "
                 "VALUES ('NCH900', 'Old', 'Row')")
    conn.commit()
    conn.close()
    database.init_db()
    database.init_db()  # idempotent
    conn = sqlite3.connect(nursery_db)
    have = {r[1] for r in conn.execute("PRAGMA table_info(pupils)")}
    conn.close()
    assert {name for name, _decl in database.PUPILS_PARITY_COLUMNS} <= have
    old = C.get_child("NCH900")
    assert (old.gender, old.eal, old.roll_status) == (None, False, "on_roll")


def test_old_constructor_shape_still_builds_a_child():
    c = C.Child("NCH1", "A", "B", None, None, None, None, None, None, None,
                None, None, None, "active")
    assert (c.gender, c.fsm_eligible, c.roll_status) == (None, False, "on_roll")


# ── GUI form tables (no window) ─────────────────────────────────────────────

PARITY = {"first_name", "middle_names", "last_name", "preferred_name", "date_of_birth",
          "gender", "upn", "start_date", "roll_status", "left_date", "exit_reason",
          "address_line1", "address_line2", "town", "postcode", "sen_status",
          "fsm_eligible", "eal", "notes", "parent_name", "parent_relationship",
          "parent_phone", "parent_email", "medical_notes",
          "room", "key_person", "funded_hours", "allergies"}


def test_form_asks_every_field_in_the_schools_sections():
    from education_system.systems.nursery.interfaces.gui.learners.children import (
        children_views as V,
    )
    assert set(V._FIELDS) == PARITY
    assert [t for t, _k in V._SECTIONS] == [
        "Identity", "Admission", "Address", "Needs", "Parent / carer", "Medical",
        "Nursery"]
    assert set(V._LABELS) >= PARITY
    assert V._DATES == {"date_of_birth", "start_date", "left_date"}
    assert [v for v, _l in V._SEN_CHOICES] == ["N", "K", "E"]
    assert [v for v, _l in V._ROLL_CHOICES] == list(C.ROLL_STATUSES)


def test_edit_form_starts_from_every_stored_field():
    from education_system.systems.nursery.interfaces.gui.learners.children import (
        children_views as V,
    )
    c = C.create_child(_full())
    initial = V._initial_from(C.get_child(c.pupil_id))
    assert set(initial) == PARITY
    assert (initial["gender"], initial["town"], initial["roll_status"]) == (
        "Female", "Bath", "on_roll")


def test_profile_shows_each_section():
    from education_system.systems.nursery.interfaces.gui.learners.children import (
        children_views as V,
    )
    c = C.create_child(_full())
    sections = dict(V._profile_sections(c))
    assert list(sections) == ["Identity", "Admission", "Address", "Needs",
                              "Parent / carer", "Medical", "Nursery"]
    flat = {k: v for items in sections.values() for k, v in items}
    assert flat["Postcode"] == "BA1 1AA"
    assert flat["SEN"].startswith("K ")
    assert flat["Allergies"] == "Peanuts"
    assert flat["Roll status"] == "On roll"


# ── CLI (scripted answers) ──────────────────────────────────────────────────

# One answer per question, in the order _collect_fields asks them.
_ADD_ANSWERS = [
    "Maya", "Grace", "Okafor", "May", "2021-05-04", "1", "",   # identity
    "2023-09-04", "",                                           # admission (on roll)
    "1 High Street", "", "Bath", "ba1 1aa",                     # address
    "2", "n", "y", "",                                          # needs
    "Ngozi Okafor", "1", "07123 456789", "ngozi@example.test",  # parent / carer
    "Inhaler",                                                  # medical
    "", "", "2", "Peanuts",                                     # nursery
]


def _mayas() -> list[C.Child]:
    return [c for c in C.list_children() if c.first_name == "Maya"]


def _script(monkeypatch, answers):
    it = iter(answers)
    monkeypatch.setattr(builtins, "input", lambda _msg="": next(it))


def test_cli_add_asks_the_same_questions(monkeypatch):
    from education_system.systems.nursery.interfaces.cli.learners.children import (
        children_cli as cli,
    )
    _script(monkeypatch, _ADD_ANSWERS)
    cli.open_add_child()
    [c] = _mayas()
    assert (c.gender, c.middle_names, c.postcode) == ("Female", "Grace", "BA1 1AA")
    assert (c.sen_status, c.eal, c.fsm_eligible) == ("K", True, False)
    assert (c.parent_relationship, c.funded_hours, c.allergies) == (
        "Mother", "30 hours", "Peanuts")


def test_cli_add_asks_before_adding_a_duplicate(monkeypatch):
    from education_system.systems.nursery.interfaces.cli.learners.children import (
        children_cli as cli,
    )
    _script(monkeypatch, _ADD_ANSWERS)
    cli.open_add_child()
    _script(monkeypatch, [*_ADD_ANSWERS, "n"])
    cli.open_add_child()
    assert len(_mayas()) == 1
    _script(monkeypatch, [*_ADD_ANSWERS, "y"])
    cli.open_add_child()
    assert len(_mayas()) == 2


def test_cli_edit_enter_keeps_every_value(monkeypatch):
    from education_system.systems.nursery.interfaces.cli.learners.children import (
        children_cli as cli,
    )
    c = C.create_child(_full())
    # Child ID, then Enter for every question (25 asked while on roll).
    _script(monkeypatch, [c.pupil_id] + [""] * 40)
    cli.open_edit_child()
    after = C.get_child(c.pupil_id)
    assert (after.upn, after.town, after.sen_status, after.room) == (
        _upn(), "Bath", "K", "Preschool Room")
