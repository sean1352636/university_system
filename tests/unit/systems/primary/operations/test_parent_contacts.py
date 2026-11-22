"""Parent / carer contacts (domain.operations.communications.parent_contacts)."""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.operations.communications.parent_contacts import (
    parent_contacts as PC,
)


def _pupil(first="Ada", last="Lovelace", year="3"):
    return P.create_pupil({"first_name": first, "last_name": last, "year_group": year,
                           "date_of_birth": "2018-04-01"})


def _contact(pupil, first="Mary", last="Lovelace", **extra):
    data = {"student_id": pupil.pupil_id, "first_name": first, "last_name": last,
            "email": f"{first.lower()}@home.test"}
    data.update(extra)
    return PC.create_contact(data)


# ── create / read ───────────────────────────────────────────────────

def test_empty_database():
    assert PC.list_contacts() == []
    assert PC.get_contact(1) is None
    assert PC.search_contacts("") == []
    assert PC.list_contacts_with_detail() == []


def test_create_applies_defaults():
    p = _pupil()
    c = _contact(p)
    assert c.student_id == p.pupil_id
    assert c.relationship == "Parent"
    assert c.preferred_method == "Email"
    assert c.preferred_language == "English"
    assert c.is_primary is False
    assert c.is_emergency_contact is True
    assert c.has_parental_responsibility is True
    assert c.receives_communications is True
    assert c.lives_with_student is True
    assert c.full_name == "Mary Lovelace"


def test_create_stores_every_field():
    p = _pupil()
    c = PC.create_contact({
        "student_id": f" {p.pupil_id} ", "relationship": "Grandmother", "title": "Mrs",
        "first_name": " Joan ", "last_name": " Byron ", "email": " JOAN@Home.Test ",
        "primary_phone": "+44 (0)1234-567890", "secondary_phone": "07700 900123",
        "address": " 1 Lane ", "preferred_method": "SMS", "preferred_language": "Polish",
        "is_primary": True, "is_emergency_contact": False,
        "has_parental_responsibility": False, "receives_communications": False,
        "lives_with_student": False, "notes": " collects Fridays "})
    got = PC.get_contact(c.contact_id)
    assert got == c
    assert c.student_id == p.pupil_id
    assert c.full_name == "Mrs Joan Byron"
    assert c.email == "joan@home.test"
    assert c.primary_phone == "+44 (0)1234-567890"
    assert c.address == "1 Lane" and c.notes == "collects Fridays"
    assert (c.relationship, c.preferred_method, c.preferred_language) == (
        "Grandmother", "SMS", "Polish")
    assert c.is_primary is True
    assert not (c.is_emergency_contact or c.has_parental_responsibility
                or c.receives_communications or c.lives_with_student)


def test_phone_only_contact_is_allowed():
    c = _contact(_pupil(), email=None, primary_phone="01234 567890")
    assert c.email is None and c.primary_phone == "01234 567890"


# ── validation ──────────────────────────────────────────────────────

def test_pupil_is_required_and_must_exist():
    with pytest.raises(PC.ValidationError, match="Student ID is required"):
        PC.create_contact({"first_name": "A", "last_name": "B", "email": "a@b.cd"})
    with pytest.raises(PC.ValidationError, match="No student with id 9999999"):
        PC.create_contact({"student_id": "9999999", "first_name": "A", "last_name": "B",
                           "email": "a@b.cd"})


def test_names_are_required():
    p = _pupil()
    with pytest.raises(PC.ValidationError, match="First name is required"):
        _contact(p, first=" ")
    with pytest.raises(PC.ValidationError, match="Last name is required"):
        _contact(p, last="")


@pytest.mark.parametrize("field,value,msg", [
    ("relationship", "Cousin", "Relationship must be one of"),
    ("preferred_method", "Pigeon", "Preferred method must be one of"),
    ("preferred_language", "Klingon", "Preferred language must be one of"),
])
def test_allowed_value_lists(field, value, msg):
    with pytest.raises(PC.ValidationError, match=msg):
        _contact(_pupil(), **{field: value})


def test_email_must_look_like_an_address():
    with pytest.raises(PC.ValidationError, match="Email is not a valid address"):
        _contact(_pupil(), email="mary at home")


@pytest.mark.parametrize("field,label", [("primary_phone", "Primary phone"),
                                         ("secondary_phone", "Secondary phone")])
def test_phones_may_only_use_phone_characters(field, label):
    with pytest.raises(PC.ValidationError, match=f"{label} can only contain"):
        _contact(_pupil(), **{field: "call me maybe"})


def test_at_least_one_way_to_reach_the_contact():
    with pytest.raises(PC.ValidationError, match="At least one of email"):
        _contact(_pupil(), email="")


def test_nothing_saved_on_refusal():
    p = _pupil()
    with pytest.raises(PC.ValidationError):
        _contact(p, relationship="Cousin")
    assert PC.list_contacts() == []


# ── primary contact rule ────────────────────────────────────────────

def test_only_one_primary_per_pupil():
    p = _pupil()
    other = _pupil("Bob", "Smith")
    a = _contact(p, "Mary", is_primary=True)
    b = _contact(p, "John", is_primary=True)
    o = _contact(other, "Sue", is_primary=True)
    assert PC.get_contact(a.contact_id).is_primary is False
    assert PC.get_contact(b.contact_id).is_primary is True
    assert PC.get_contact(o.contact_id).is_primary is True       # other pupil untouched
    assert PC.primary_for_student(p.pupil_id).contact_id == b.contact_id


def test_set_primary_moves_the_flag():
    p = _pupil()
    a = _contact(p, "Mary", is_primary=True)
    b = _contact(p, "John")
    assert PC.set_primary(b.contact_id).is_primary is True
    assert PC.get_contact(a.contact_id).is_primary is False
    with pytest.raises(PC.ValidationError, match="No contact with id 404"):
        PC.set_primary(404)


def test_update_to_primary_clears_the_old_one():
    p = _pupil()
    a = _contact(p, "Mary", is_primary=True)
    b = _contact(p, "John")
    PC.update_contact(b.contact_id, {"is_primary": True})
    assert PC.get_contact(a.contact_id).is_primary is False
    assert PC.primary_for_student(p.pupil_id).first_name == "John"


def test_primary_for_pupil_without_one_is_none():
    p = _pupil()
    _contact(p)
    assert PC.primary_for_student(p.pupil_id) is None


# ── update / delete ─────────────────────────────────────────────────

def test_update_merges_and_keeps_the_pupil():
    p = _pupil()
    other = _pupil("Bob", "Smith")
    c = _contact(p)
    u = PC.update_contact(c.contact_id, {"relationship": "Mother", "email": "NEW@x.org",
                                         "receives_communications": False,
                                         "student_id": other.pupil_id})
    assert u.relationship == "Mother"
    assert u.email == "new@x.org"
    assert u.receives_communications is False
    assert u.first_name == "Mary"
    assert u.student_id == p.pupil_id             # a contact cannot be moved


def test_update_still_validates():
    c = _contact(_pupil())
    with pytest.raises(PC.ValidationError, match="At least one of email"):
        PC.update_contact(c.contact_id, {"email": ""})
    with pytest.raises(PC.ValidationError, match="No contact with id 404"):
        PC.update_contact(404, {})


def test_delete_contact():
    c = _contact(_pupil())
    assert PC.delete_contact(c.contact_id) is True
    assert PC.get_contact(c.contact_id) is None
    assert PC.delete_contact(c.contact_id) is False


def test_deleting_the_pupil_removes_their_contacts():
    p = _pupil()
    keep = _pupil("Bob", "Smith")
    _contact(p)
    k = _contact(keep, "Sue")
    assert P.delete_pupil(p.pupil_id) is True
    assert [c.contact_id for c in PC.list_contacts()] == [k.contact_id]


# ── listing / search ────────────────────────────────────────────────

def test_list_filters_and_order():
    p = _pupil()
    q = _pupil("Bob", "Smith")
    m = _contact(p, "Mary", "Zed", relationship="Mother", is_emergency_contact=False)
    f = _contact(p, "Fred", "Abe", relationship="Father", is_primary=True,
                 receives_communications=False)
    g = _contact(q, "Gran", "Smith", relationship="Grandmother")

    # pupil order, then the primary first, then surname
    rows = PC.list_contacts(student_id=p.pupil_id)
    assert [c.contact_id for c in rows] == [f.contact_id, m.contact_id]
    assert PC.contacts_for_student(q.pupil_id) == [g]

    def ids(**kw):
        return {c.contact_id for c in PC.list_contacts(**kw)}

    assert ids(relationship="Grandmother") == {g.contact_id}
    assert ids(primary_only=True) == {f.contact_id}
    assert ids(emergency_only=True) == {f.contact_id, g.contact_id}
    assert ids(receives_only=True) == {m.contact_id, g.contact_id}
    with pytest.raises(PC.ValidationError, match="Relationship must be one of"):
        PC.list_contacts(relationship="Neighbour")


def test_search_matches_names_email_phone_and_pupil():
    p = _pupil()
    a = _contact(p, "Mary", "Zed", primary_phone="0111 222333")
    b = _contact(_pupil("Bob", "Smith"), "Gran", "Smith", email="gran@farm.test")
    assert {c.contact_id for c in PC.search_contacts("zed")} == {a.contact_id}
    assert {c.contact_id for c in PC.search_contacts("farm")} == {b.contact_id}
    assert {c.contact_id for c in PC.search_contacts("222333")} == {a.contact_id}
    assert {c.contact_id for c in PC.search_contacts(p.pupil_id)} == {a.contact_id}
    assert len(PC.search_contacts("  ")) == 2
    assert PC.search_contacts("nobody") == []


def test_list_with_detail_names_the_pupil():
    p = _pupil()
    c = _contact(p)
    rows = PC.list_contacts_with_detail(student_id=p.pupil_id)
    assert len(rows) == 1
    assert rows[0].contact == c
    assert rows[0].student_name == "Ada Lovelace"


# ── summary ─────────────────────────────────────────────────────────

def test_summary_flags_gaps_and_counts():
    full = _pupil("Ada", "One")
    no_primary = _pupil("Bob", "Two")
    no_emerg = _pupil("Cat", "Three")
    nobody = _pupil("Dan", "Four")
    _contact(full, "A", is_primary=True, relationship="Mother")
    _contact(full, "B", email=None, primary_phone="01234 567890", preferred_method="SMS",
             receives_communications=False)
    _contact(no_primary, "C", preferred_language="Urdu")
    _contact(no_emerg, "D", is_primary=True, is_emergency_contact=False)

    s = PC.summary()
    assert s.total == 4
    assert s.students_with_contact == 3
    assert s.students_without_contact == [nobody.pupil_id]
    assert s.students_without_primary == [no_primary.pupil_id]
    assert s.students_without_emergency == [no_emerg.pupil_id]
    assert s.by_relationship["Mother"] == 1 and s.by_relationship["Parent"] == 3
    assert s.by_preferred_method["SMS"] == 1 and s.by_preferred_method["Email"] == 3
    assert s.by_language["Urdu"] == 1 and s.by_language["English"] == 3
    assert s.receives_communications == 3
    assert s.no_email == 1
    assert s.no_phone == 3


def test_summary_with_pupils_but_no_contacts():
    a = _pupil()
    s = PC.summary()
    assert s.total == 0
    assert s.students_with_contact == 0
    assert s.students_without_contact == [a.pupil_id]
    assert s.students_without_primary == []
