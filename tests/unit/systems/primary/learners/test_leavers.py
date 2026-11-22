"""Leavers (domain.learners.pupils.leavers.leavers): the former-pupils register."""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.learners.pupils.leavers import leavers as LV


def _data(**over):
    base = {"first_name": "Ada", "last_name": "Lovelace", "year_left": "6",
            "date_of_birth": "2014-04-01", "leaving_date": "2026-07-20",
            "destination_school": "Hill Academy", "current_email": "ada@hill.example",
            "parent_phone": "01234 567890", "reason": "End of Year 6",
            "notes": "Settled well"}
    base.update(over)
    return base


def _pupil(first="Ben", year="6", **extra):
    return P.create_pupil({"first_name": first, "last_name": "Ng", "year_group": year,
                           **extra})


# ── create / get ─────────────────────────────────────────────────────

def test_create_stores_every_field_and_defaults_to_active():
    rec = LV.create_leaver(_data())
    got = LV.get_leaver(rec.leaver_id)
    assert got == rec
    assert got.leaver_id.startswith("LV") and len(got.leaver_id) == 9
    assert got.pupil_id is None
    assert (got.first_name, got.last_name, got.year_left) == ("Ada", "Lovelace", "6")
    assert got.leaving_date == "2026-07-20"
    assert got.destination_school == "Hill Academy"
    assert got.current_email == "ada@hill.example"
    assert got.reason == "End of Year 6" and got.notes == "Settled well"
    assert got.status == "active"
    assert got.full_name == "Ada Lovelace"


def test_blank_optionals_are_none_and_status_is_lower_cased():
    rec = LV.create_leaver({"first_name": "A", "last_name": "B", "year_left": "R",
                            "status": "INACTIVE", "destination_school": " ",
                            "current_email": "", "notes": ""})
    assert rec.status == "inactive"
    assert rec.destination_school is None and rec.current_email is None
    assert rec.notes is None and rec.date_of_birth is None


def test_get_unknown_leaver_is_none():
    assert LV.get_leaver("LV0000000") is None


@pytest.mark.parametrize("field,message", [
    ("first_name", "First name is required"),
    ("last_name", "Last name is required"),
    ("year_left", "Year left is required"),
])
def test_required_fields(field, message):
    with pytest.raises(P.ValidationError, match=message):
        LV.create_leaver(_data(**{field: ""}))


@pytest.mark.parametrize("over,message", [
    ({"year_left": "7"}, "Year left must be one of"),
    ({"date_of_birth": "1/4/2014"}, "Date of birth must be YYYY-MM-DD"),
    ({"leaving_date": "July 2026"}, "Leaving date must be YYYY-MM-DD"),
    ({"current_email": "not-an-email"}, "Current email is not a valid address"),
    ({"current_email": "a@b"}, "Current email is not a valid address"),
    ({"parent_phone": "call me"}, "Parent phone contains invalid characters"),
    ({"status": "archived"}, "Status must be one of"),
])
def test_field_rules(over, message):
    with pytest.raises(P.ValidationError, match=message):
        LV.create_leaver(_data(**over))


def test_a_pupil_can_be_a_leaver_only_once():
    first = LV.create_leaver(_data(pupil_id="P1234567"))
    with pytest.raises(P.ValidationError, match=f"already a leaver \\({first.leaver_id}\\)"):
        LV.create_leaver(_data(pupil_id="P1234567"))


def test_legacy_leavers_without_pupil_ids_can_repeat():
    LV.create_leaver(_data())
    LV.create_leaver(_data())
    assert len(LV.list_leavers()) == 2


# ── list / search ────────────────────────────────────────────────────

def test_empty_register():
    assert LV.list_leavers() == []
    assert LV.search_leavers("x") == []
    assert LV.status_counts() == {"active": 0, "inactive": 0}


def test_list_newest_leaving_date_first_then_name():
    LV.create_leaver(_data(first_name="Old", leaving_date="2024-07-20"))
    LV.create_leaver(_data(first_name="Zed", last_name="Brown"))
    LV.create_leaver(_data(first_name="Amy", last_name="Adams"))
    assert [r.first_name for r in LV.list_leavers()] == ["Amy", "Zed", "Old"]


def test_list_filters_by_status_and_year():
    a = LV.create_leaver(_data(year_left="6"))
    b = LV.create_leaver(_data(year_left="4", status="inactive"))
    assert [r.leaver_id for r in LV.list_leavers(status="active")] == [a.leaver_id]
    assert [r.leaver_id for r in LV.list_leavers(year_left="4")] == [b.leaver_id]
    assert LV.list_leavers(status="inactive", year_left="6") == []


def test_list_filters_are_validated():
    with pytest.raises(P.ValidationError, match="Status filter"):
        LV.list_leavers(status="gone")
    with pytest.raises(P.ValidationError, match="Year filter"):
        LV.list_leavers(year_left="9")


def test_search_matches_names_ids_email_and_destination():
    a = LV.create_leaver(_data(pupil_id="P7654321"))
    b = LV.create_leaver(_data(first_name="Bo", last_name="Bee",
                               destination_school="Vale High", current_email="bo@vale.example"))
    assert [r.leaver_id for r in LV.search_leavers("vale high")] == [b.leaver_id]
    assert [r.leaver_id for r in LV.search_leavers("P7654321")] == [a.leaver_id]
    assert [r.leaver_id for r in LV.search_leavers(b.leaver_id)] == [b.leaver_id]
    assert [r.leaver_id for r in LV.search_leavers("bo@vale")] == [b.leaver_id]
    assert LV.search_leavers("zzz") == []


def test_blank_search_lists_everyone():
    LV.create_leaver(_data())
    LV.create_leaver(_data(first_name="Bo"))
    assert len(LV.search_leavers("  ")) == 2


# ── update / status / delete ─────────────────────────────────────────

def test_update_rewrites_the_record():
    rec = LV.create_leaver(_data())
    up = LV.update_leaver(rec.leaver_id, _data(destination_school="Vale High",
                                               status="inactive", notes=""))
    assert up.destination_school == "Vale High" and up.status == "inactive"
    assert up.notes is None and up.leaver_id == rec.leaver_id


def test_update_unknown_or_invalid_is_refused():
    with pytest.raises(P.ValidationError, match="No leaver with id LV0000000"):
        LV.update_leaver("LV0000000", _data())
    rec = LV.create_leaver(_data())
    with pytest.raises(P.ValidationError, match="Year left must be one of"):
        LV.update_leaver(rec.leaver_id, _data(year_left="Y6"))


def test_update_cannot_take_another_leavers_pupil_id():
    LV.create_leaver(_data(pupil_id="P1111111"))
    other = LV.create_leaver(_data(pupil_id="P2222222"))
    with pytest.raises(P.ValidationError, match="P1111111 is already a leaver"):
        LV.update_leaver(other.leaver_id, _data(pupil_id="P1111111"))
    # Keeping its own pupil id is fine.
    assert LV.update_leaver(other.leaver_id, _data(pupil_id="P2222222")).pupil_id == "P2222222"


def test_set_status_and_counts():
    a = LV.create_leaver(_data())
    LV.create_leaver(_data())
    LV.create_leaver(_data(status="inactive"))
    assert LV.status_counts() == {"active": 2, "inactive": 1}
    assert LV.set_status(a.leaver_id, "inactive").status == "inactive"
    assert LV.status_counts() == {"active": 1, "inactive": 2}


def test_set_status_refuses_unknown_status_or_leaver():
    a = LV.create_leaver(_data())
    with pytest.raises(P.ValidationError, match="Status must be one of"):
        LV.set_status(a.leaver_id, "Active ")
    with pytest.raises(P.ValidationError, match="No leaver with id"):
        LV.set_status("LV0000000", "inactive")


def test_delete_leaver():
    a = LV.create_leaver(_data())
    assert LV.delete_leaver(a.leaver_id) is True
    assert LV.get_leaver(a.leaver_id) is None
    assert LV.delete_leaver(a.leaver_id) is False


# ── promote from a pupil ─────────────────────────────────────────────

def test_promote_copies_the_pupil_merges_extras_and_removes_the_pupil():
    p = _pupil(date_of_birth="2014-02-02", parent_phone="07700 900123")
    rec = LV.promote_from_pupil(p.pupil_id, {"destination_school": "Hill Academy",
                                             "reason": "Moved house", "notes": ""})
    assert rec.pupil_id == p.pupil_id
    assert (rec.first_name, rec.last_name, rec.year_left) == ("Ben", "Ng", "6")
    assert rec.date_of_birth == "2014-02-02" and rec.parent_phone == "07700 900123"
    assert rec.destination_school == "Hill Academy" and rec.reason == "Moved house"
    assert rec.notes is None
    assert P.get_pupil(p.pupil_id) is None


def test_promote_refuses_blank_unknown_and_repeat():
    with pytest.raises(P.ValidationError, match="Pupil ID is required"):
        LV.promote_from_pupil("  ")
    with pytest.raises(P.ValidationError, match="No pupil with id P0000000"):
        LV.promote_from_pupil("P0000000")
    p = _pupil()
    LV.create_leaver(_data(pupil_id=p.pupil_id))
    with pytest.raises(P.ValidationError, match="already a leaver"):
        LV.promote_from_pupil(p.pupil_id)
    assert P.get_pupil(p.pupil_id) is not None


def test_promote_with_bad_extras_writes_nothing():
    p = _pupil()
    with pytest.raises(P.ValidationError, match="Current email"):
        LV.promote_from_pupil(p.pupil_id, {"current_email": "nope"})
    assert P.get_pupil(p.pupil_id) is not None
    assert LV.list_leavers() == []
