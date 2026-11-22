"""Pupils (domain.learners.pupils.pupils): the primary school roll."""

from __future__ import annotations

import pytest

from education_system.platform.cross_system import identity_service, person
from education_system.systems.primary.domain.learners.pupils import pupils as P


@pytest.fixture(autouse=True)
def _journey_stamps_in_sandbox(monkeypatch):
    """``person`` keeps a dict of system DB paths the sandbox cannot remap;
    point the primary entry at the sandbox so a journey stamp lands there."""
    monkeypatch.setitem(person.SYSTEM_DB_PATHS, "primary", P.DB_PATH)


def _data(**over):
    base = {"first_name": "Ada", "last_name": "Lovelace", "year_group": "3",
            "class_name": "3A", "date_of_birth": "2018-04-01",
            "parent_name": "Anne Lovelace", "parent_phone": "01234 567890",
            "medical_notes": "Asthma", "send_status": "no"}
    base.update(over)
    return base


def _pupil(**over):
    return P.create_pupil(_data(**over))


# ── create / get ─────────────────────────────────────────────────────

def test_create_stores_every_field_and_reads_back():
    made = _pupil()
    got = P.get_pupil(made.pupil_id)
    assert got.pupil_id == made.pupil_id and got.email == made.email
    assert got.first_name == "Ada" and got.last_name == "Lovelace"
    assert got.year_group == "3" and got.class_name == "3A"
    assert got.date_of_birth == "2018-04-01"
    assert got.parent_name == "Anne Lovelace" and got.parent_phone == "01234 567890"
    assert got.medical_notes == "Asthma" and got.send_status == "no"
    assert got.roll_status == "on_roll"
    assert got.left_date is None and got.exit_reason is None
    assert got.full_name == "Ada Lovelace"


def test_pupil_id_has_p_prefix_and_seven_digits_and_email_follows_it():
    made = _pupil()
    assert made.pupil_id.startswith("P")
    assert len(made.pupil_id) == 8 and made.pupil_id[1:].isdigit()
    assert made.email == f"{made.pupil_id.lower()}@primaryschool.local"


def test_generate_pupil_id_shape():
    pid = P.generate_pupil_id()
    assert pid[0] == "P" and len(pid) == 8 and pid[1:].isdigit()


def test_generate_pupil_id_gives_up_after_fifty_collisions(monkeypatch):
    taken = _pupil()
    n = int(taken.pupil_id[1:])
    monkeypatch.setattr(P.random, "randint", lambda a, b: n)
    with pytest.raises(RuntimeError, match="50"):
        P.generate_pupil_id()


def test_blank_optional_fields_are_stored_as_none_and_text_is_trimmed():
    made = P.create_pupil({"first_name": "  Ben ", "last_name": " Ng ", "year_group": "R",
                           "class_name": "  ", "date_of_birth": "", "parent_name": "",
                           "parent_phone": "", "medical_notes": "  ", "send_status": ""})
    assert made.first_name == "Ben" and made.last_name == "Ng"
    assert made.class_name is None and made.date_of_birth is None
    assert made.parent_name is None and made.parent_phone is None
    assert made.medical_notes is None and made.send_status is None


def test_send_status_is_lower_cased():
    assert _pupil(send_status="YES").send_status == "yes"
    assert _pupil(send_status="No").send_status == "no"


def test_every_year_group_r_to_6_is_accepted():
    for yg in ("R", "1", "2", "3", "4", "5", "6"):
        assert _pupil(year_group=yg).year_group == yg


def test_create_as_applicant_with_journey():
    made = P.create_pupil(_data(date_of_birth=""), roll_status="applicant",
                          journey_id="j-1")
    assert made.roll_status == "applicant"
    assert P.find_by_journey("j-1").pupil_id == made.pupil_id


def test_get_unknown_pupil_is_none():
    assert P.get_pupil("P0000000") is None


# ── validation ───────────────────────────────────────────────────────

@pytest.mark.parametrize("field,label", [
    ("first_name", "First name"), ("last_name", "Last name"), ("year_group", "Year group")])
def test_required_fields(field, label):
    with pytest.raises(P.ValidationError, match=f"{label} is required"):
        P.create_pupil(_data(**{field: "   "}))


@pytest.mark.parametrize("bad", ["7", "0", "Y3", "r", "Nursery"])
def test_year_group_outside_r_to_6_is_refused(bad):
    with pytest.raises(P.ValidationError, match="Year group must be one of"):
        _pupil(year_group=bad)


@pytest.mark.parametrize("bad", ["01/04/2018", "2018-4-1", "yesterday"])
def test_date_of_birth_must_be_iso(bad):
    with pytest.raises(P.ValidationError, match="YYYY-MM-DD"):
        _pupil(date_of_birth=bad)


@pytest.mark.parametrize("bad", ["12345", "phone-me-now", "0123456789012345678901", "07700;900"])
def test_parent_phone_shape(bad):
    with pytest.raises(P.ValidationError, match="Parent phone"):
        _pupil(parent_phone=bad)


def test_parent_phone_allows_plus_brackets_spaces_and_dashes():
    assert _pupil(parent_phone="+44 (0)1234-567890").parent_phone == "+44 (0)1234-567890"


def test_send_status_must_be_yes_or_no():
    with pytest.raises(P.ValidationError, match="SEND status"):
        _pupil(send_status="maybe")


def test_unknown_roll_status_is_refused_before_anything_is_written():
    with pytest.raises(P.ValidationError, match="Roll status"):
        P.create_pupil(_data(), roll_status="expelled")
    assert P.list_pupils(include_off_roll=True) == []


def test_duplicate_journey_id_is_refused():
    P.create_pupil(_data(date_of_birth=""), journey_id="j-dup")
    with pytest.raises(P.ValidationError, match="Could not create pupil"):
        P.create_pupil(_data(first_name="Other", date_of_birth=""), journey_id="j-dup")


# ── journey registration ─────────────────────────────────────────────

def test_create_with_name_and_dob_registers_and_stamps_a_journey():
    made = _pupil()
    row = identity_service.find_by_student("primary", made.pupil_id)
    assert row is not None
    assert row["legal_first_name"] == "Ada" and row["date_of_birth"] == "2018-04-01"
    assert P.get_pupil(made.pupil_id).journey_id == row["journey_id"]
    assert P.find_by_journey(row["journey_id"]).pupil_id == made.pupil_id


def test_create_without_dob_registers_no_journey():
    made = _pupil(date_of_birth="")
    assert identity_service.find_by_student("primary", made.pupil_id) is None
    assert P.get_pupil(made.pupil_id).journey_id is None


def test_find_by_journey_blank_or_unknown_is_none():
    _pupil()
    assert P.find_by_journey("") is None
    assert P.find_by_journey(None) is None
    assert P.find_by_journey("no-such-journey") is None


# ── roll status ──────────────────────────────────────────────────────

def test_set_roll_status_left_records_date_and_reason():
    made = _pupil()
    left = P.set_roll_status(made.pupil_id, "left", left_date="2026-07-20",
                             exit_reason="Moved away")
    assert left.roll_status == "left"
    assert left.left_date == "2026-07-20" and left.exit_reason == "Moved away"


def test_back_on_roll_clears_left_date_and_reason():
    made = _pupil()
    P.set_roll_status(made.pupil_id, "left", left_date="2026-07-20", exit_reason="Moved")
    back = P.set_roll_status(made.pupil_id, "on_roll", left_date="2026-09-01",
                             exit_reason="ignored")
    assert back.roll_status == "on_roll"
    assert back.left_date is None and back.exit_reason is None


def test_set_roll_status_refuses_unknown_status_and_unknown_pupil():
    made = _pupil()
    with pytest.raises(P.ValidationError, match="Roll status"):
        P.set_roll_status(made.pupil_id, "graduated")
    with pytest.raises(P.ValidationError, match="No pupil with id P0000000"):
        P.set_roll_status("P0000000", "left")


def test_setting_left_keeps_the_row():
    made = _pupil()
    P.set_roll_status(made.pupil_id, "left")
    assert P.get_pupil(made.pupil_id) is not None


# ── listing and searching ────────────────────────────────────────────

def test_empty_roll_lists_nothing():
    assert P.list_pupils() == []
    assert P.list_pupils(include_off_roll=True) == []
    assert P.search_pupils("a") == []


def test_list_is_sorted_by_year_then_last_then_first_name():
    _pupil(first_name="Zed", last_name="Brown", year_group="2")
    _pupil(first_name="Amy", last_name="Brown", year_group="2")
    _pupil(first_name="Cal", last_name="Adams", year_group="2")
    _pupil(first_name="Dot", last_name="Aaron", year_group="1")
    names = [(p.year_group, p.full_name) for p in P.list_pupils()]
    assert names == [("1", "Dot Aaron"), ("2", "Cal Adams"), ("2", "Amy Brown"),
                     ("2", "Zed Brown")]


def test_list_hides_applicants_and_leavers_unless_asked():
    on = _pupil(first_name="On")
    app = P.create_pupil(_data(first_name="App"), roll_status="applicant")
    gone = _pupil(first_name="Gone")
    P.set_roll_status(gone.pupil_id, "left")
    assert [p.pupil_id for p in P.list_pupils()] == [on.pupil_id]
    assert {p.pupil_id for p in P.list_pupils(include_off_roll=True)} == {
        on.pupil_id, app.pupil_id, gone.pupil_id}


def test_search_matches_id_names_email_and_class():
    a = _pupil(first_name="Ada", last_name="Lovelace", class_name="3A")
    b = _pupil(first_name="Brian", last_name="May", class_name="4M", year_group="4")
    assert [p.pupil_id for p in P.search_pupils("lovel")] == [a.pupil_id]
    assert [p.pupil_id for p in P.search_pupils("bri")] == [b.pupil_id]
    assert [p.pupil_id for p in P.search_pupils("4M")] == [b.pupil_id]
    assert [p.pupil_id for p in P.search_pupils(a.pupil_id)] == [a.pupil_id]
    assert [p.pupil_id for p in P.search_pupils(b.email)] == [b.pupil_id]
    assert P.search_pupils("nobody-like-this") == []


def test_blank_search_returns_everyone_on_roll():
    a, b = _pupil(), _pupil(first_name="Bea")
    assert {p.pupil_id for p in P.search_pupils("")} == {a.pupil_id, b.pupil_id}
    assert {p.pupil_id for p in P.search_pupils(None)} == {a.pupil_id, b.pupil_id}


def test_search_respects_roll_status():
    gone = _pupil(first_name="Gina")
    P.set_roll_status(gone.pupil_id, "left")
    assert P.search_pupils("Gina") == []
    assert [p.pupil_id for p in P.search_pupils("Gina", include_off_roll=True)] == [
        gone.pupil_id]


# ── update / delete ──────────────────────────────────────────────────

def test_update_changes_editable_fields_but_not_id_email_or_roll():
    made = _pupil()
    P.set_roll_status(made.pupil_id, "applicant")
    up = P.update_pupil(made.pupil_id, _data(first_name="Augusta", year_group="4",
                                             class_name="4B", send_status="yes",
                                             parent_phone=""))
    assert up.first_name == "Augusta" and up.year_group == "4" and up.class_name == "4B"
    assert up.send_status == "yes" and up.parent_phone is None
    assert up.pupil_id == made.pupil_id and up.email == made.email
    assert up.roll_status == "applicant"


def test_update_validates_like_create():
    made = _pupil()
    with pytest.raises(P.ValidationError, match="Year group must be one of"):
        P.update_pupil(made.pupil_id, _data(year_group="7"))
    assert P.get_pupil(made.pupil_id).year_group == "3"


def test_update_unknown_pupil_is_refused():
    with pytest.raises(P.ValidationError, match="No pupil with id P0000000"):
        P.update_pupil("P0000000", _data())


def test_delete_removes_and_reports():
    made = _pupil()
    assert P.delete_pupil(made.pupil_id) is True
    assert P.get_pupil(made.pupil_id) is None
    assert P.delete_pupil(made.pupil_id) is False


def test_init_db_is_idempotent_and_adds_late_columns():
    P.init_db()
    P.init_db()
    with P._connect() as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(pupils)")}
    assert {"roll_status", "journey_id", "left_date", "exit_reason"} <= cols


# ── parity with the secondary school's pupil record ──────────────────

def _upn(body: str = "201234567890") -> str:
    return P.upn_check_letter(body) + body


def _full(**over):
    extra = dict(middle_names="Augusta", preferred_name="Addie", gender="Female",
                 upn=_upn(), admission_date="2024-09-02",
                 address_line1="12 Byron Road", address_line2="Marylebone",
                 town="London", postcode="sw1a1aa", sen_status="E",
                 fsm_eligible="yes", eal="no", notes="Loves numbers",
                 parent_relationship="mother", parent_email="Anne@Example.com")
    return _data(**{**extra, **over})


def test_create_stores_every_parity_field():
    made = P.create_pupil(_full())
    got = P.get_pupil(made.pupil_id)
    assert (got.middle_names, got.preferred_name, got.gender) == ("Augusta", "Addie",
                                                                  "Female")
    assert got.upn == _upn() and got.admission_date == "2024-09-02"
    assert (got.address_line1, got.address_line2, got.town) == (
        "12 Byron Road", "Marylebone", "London")
    assert got.postcode == "SW1A 1AA"
    assert got.sen_status == "E" and got.sen_label == "EHC plan"
    assert got.fsm_eligible is True and got.eal is False
    assert got.notes == "Loves numbers"
    assert got.parent_relationship == "Mother"
    assert got.parent_email == "anne@example.com"
    assert got.display_name == "Addie Lovelace"
    assert got.legal_name == "Ada Augusta Lovelace"


def test_sen_status_drives_the_yes_no_send_flag():
    assert _pupil(sen_status="K", send_status=None).send_status == "yes"
    assert _pupil(sen_status="E").send_status == "yes"
    assert _pupil(sen_status="N", send_status="yes").send_status == "no"
    # The picker's label form is accepted too.
    assert _pupil(sen_status="K – SEN support").sen_status == "K"
    with pytest.raises(P.ValidationError, match="SEN status must be N, K or E"):
        _pupil(sen_status="X")


def test_old_callers_passing_only_send_status_get_a_matching_sen_status():
    assert _pupil(send_status="yes").sen_status == "K"
    assert _pupil(send_status="no").sen_status == "N"
    assert _pupil(send_status="").sen_status is None


def test_update_with_only_the_old_keys_keeps_the_parity_fields():
    made = P.create_pupil(_full())
    old_keys = {k: getattr(made, k) for k in (
        "first_name", "last_name", "year_group", "class_name", "date_of_birth",
        "parent_name", "parent_phone", "medical_notes", "send_status")}
    up = P.update_pupil(made.pupil_id, {**old_keys, "year_group": "4"})
    assert up.year_group == "4"
    # send_status "yes" keeps the EHC plan rather than downgrading it to K.
    assert up.sen_status == "E" and up.send_status == "yes"
    assert up.upn == made.upn and up.postcode == "SW1A 1AA"
    assert up.parent_email == "anne@example.com" and up.fsm_eligible is True


def test_update_changes_parity_fields_when_given():
    made = P.create_pupil(_full())
    up = P.update_pupil(made.pupil_id, _full(sen_status="N", town="Bath", eal="yes"))
    assert up.sen_status == "N" and up.send_status == "no"
    assert up.town == "Bath" and up.eal is True


def test_admission_date_defaults_to_today():
    import datetime as dt
    assert _pupil().admission_date == dt.date.today().isoformat()


def test_admission_date_cannot_precede_birth():
    with pytest.raises(P.ValidationError, match="Admission date can't be before"):
        _pupil(admission_date="2017-01-01")


@pytest.mark.parametrize("bad, problem", [
    ("A12345678901", "13 characters"),
    ("I201234567890", "check letter"),
    ("A2012345678X0", "digits"),
])
def test_upn_shape_is_checked(bad, problem):
    with pytest.raises(P.ValidationError, match=problem):
        _pupil(upn=bad)


def test_upn_check_letter_must_match():
    good = _upn()
    wrong = ("B" if good[0] != "B" else "C") + good[1:]
    with pytest.raises(P.ValidationError, match="check letter doesn't match"):
        _pupil(upn=wrong)


def test_upn_check_letter_matches_the_dfe_rule():
    body = "201234567890"
    total = sum(w * int(c) for w, c in enumerate(body, start=2))
    assert P.upn_check_letter(body) == "ABCDEFGHJKLMNPQRTUVWXYZ"[total % 23]


def test_upn_must_be_unique():
    _pupil(upn=_upn())
    with pytest.raises(P.ValidationError, match="already recorded"):
        _pupil(first_name="Other", upn=_upn())


def test_gender_must_be_female_or_male():
    assert _pupil(gender="male").gender == "Male"
    with pytest.raises(P.ValidationError, match="Gender must be Female or Male"):
        _pupil(gender="Unknown")


@pytest.mark.parametrize("field, value, problem", [
    ("postcode", "NOTAPOSTCODE", "UK postcode"),
    ("parent_email", "not-an-email", "e-mail"),
    ("fsm_eligible", "maybe", "Free school meals must be yes or no"),
])
def test_contact_and_needs_fields_are_sanity_checked(field, value, problem):
    with pytest.raises(P.ValidationError, match=problem):
        _pupil(**{field: value})


def test_complete_requires_date_of_birth_and_gender():
    with pytest.raises(P.ValidationError, match="Date of birth is required"):
        P.create_pupil(_data(date_of_birth="", gender="Female"), complete=True)
    with pytest.raises(P.ValidationError, match="Gender is required"):
        P.create_pupil(_data(), complete=True)
    assert P.create_pupil(_data(gender="Female"), complete=True).gender == "Female"


def test_duplicate_name_and_birth_date_is_caught_only_when_asked():
    first = _pupil()
    with pytest.raises(P.DuplicatePupil) as caught:
        P.create_pupil(_data(first_name="ADA"), check_duplicate=True)
    assert caught.value.existing.pupil_id == first.pupil_id
    assert _pupil().pupil_id != first.pupil_id      # programmatic callers unaffected


def test_left_needs_a_date_and_reason_and_on_roll_clears_them():
    with pytest.raises(P.ValidationError, match="leaving date"):
        _pupil(roll_status="left")
    with pytest.raises(P.ValidationError, match="leaving reason"):
        _pupil(roll_status="left", left_date="2026-07-20")
    made = _pupil(roll_status="left", left_date="2026-07-20", exit_reason="Moved away")
    assert (made.roll_status, made.left_date, made.exit_reason) == (
        "left", "2026-07-20", "Moved away")
    back = P.update_pupil(made.pupil_id, _data(roll_status="on_roll",
                                               left_date="2026-07-20"))
    assert (back.roll_status, back.left_date, back.exit_reason) == ("on_roll", None, None)


def test_init_db_adds_the_parity_columns():
    P.init_db()
    with P._connect() as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(pupils)")}
    assert set(P._PARITY_FIELDS) <= cols
    assert {"middle_names", "gender", "upn", "sen_status", "parent_email"} <= cols


def test_old_constructor_shape_still_builds_a_pupil():
    p = P.Pupil("P1", "A", "B", "3", None, None, "p1@x", None, None, None, None)
    assert p.sen_status is None and p.fsm_eligible is False and p.upn is None
