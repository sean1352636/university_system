"""Class teacher assignments (systems.primary.domain.staff.class_teachers.class_teachers)."""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.academics.classes import classes as CL
from education_system.systems.primary.domain.staff.class_teachers import class_teachers as CT

YEAR = "2026-27"


def _class(name="3A", year_group="3"):
    return CL.create({"name": name, "year_group": year_group})


def _assign(class_id, staff_name="Ms Teach", **extra):
    return CT.create({"class_id": class_id, "staff_name": staff_name,
                      "academic_year": YEAR, **extra})


# ── Create ───────────────────────────────────────────────────────────

def test_create_defaults_and_read_back():
    c = _class()
    a = _assign(c.class_id, staff_id=" T1234567 ", notes=" n ", start_date="2026-09-01",
                end_date="2027-07-20")
    assert (a.class_id, a.staff_name, a.staff_id, a.academic_year) == \
        (c.class_id, "Ms Teach", "T1234567", YEAR)
    assert (a.role, a.is_primary, a.notes) == ("Class Teacher", False, "n")
    assert (a.start_date, a.end_date) == ("2026-09-01", "2027-07-20")
    assert CT.get(a.assignment_id) == a
    assert CT.get(99999) is None
    # not primary → class teacher left untouched
    assert CL.get(c.class_id).teacher is None


def test_primary_assignment_is_mirrored_to_class_and_demotes_the_old_one():
    c = _class()
    first = _assign(c.class_id, "Mr One", is_primary=True)
    assert CL.get(c.class_id).teacher == "Mr One"
    second = _assign(c.class_id, "Ms Two", is_primary=True)
    assert CT.get(first.assignment_id).is_primary is False
    assert CT.get(second.assignment_id).is_primary is True
    assert CL.get(c.class_id).teacher == "Ms Two"


def test_primary_is_per_class_and_year():
    c = _class()
    other = _class("4B", "4")
    a = _assign(c.class_id, "Mr One", is_primary=True)
    b = _assign(other.class_id, "Ms Two", is_primary=True)
    old = CT.create({"class_id": c.class_id, "staff_name": "Old Hand",
                     "academic_year": "2025-26", "is_primary": True})
    assert all(CT.get(x.assignment_id).is_primary for x in (a, b, old))


@pytest.mark.parametrize("bad, msg", [
    ({"class_id": None}, "Class is required"),
    ({"class_id": "abc"}, "Class ID must be an integer"),
    ({"staff_name": "  "}, "Staff name is required"),
    ({"staff_name": "x" * 81}, "80 characters or fewer"),
    ({"academic_year": ""}, "Academic year is required"),
    ({"academic_year": "26/27"}, "Academic year must look like"),
    ({"role": "Headteacher"}, "Role must be one of"),
    ({"start_date": "1/9/2026"}, "Start date must be YYYY-MM-DD"),
    ({"end_date": "2027/07/20"}, "End date must be YYYY-MM-DD"),
    ({"start_date": "2026-09-01", "end_date": "2026-08-31"}, "End date cannot be before"),
])
def test_create_refusals(bad, msg):
    c = _class()
    data = {"class_id": c.class_id, "staff_name": "Ms Teach", "academic_year": YEAR, **bad}
    with pytest.raises(CT.ValidationError, match=msg):
        CT.create(data)
    assert CT.list_assignments() == []


def test_academic_year_formats_accepted():
    c = _class()
    for i, ay in enumerate(("2026", "2026-27", "2026-2027")):
        assert CT.create({"class_id": c.class_id, "staff_name": f"T{i}",
                          "academic_year": ay}).academic_year == ay


def test_unknown_class_and_duplicate_refused():
    with pytest.raises(CT.ValidationError, match="No class #999"):
        CT.create({"class_id": 999, "staff_name": "X", "academic_year": YEAR})
    c = _class()
    _assign(c.class_id)
    with pytest.raises(CT.ValidationError, match="already assigned"):
        _assign(c.class_id)
    # same person in a different role is allowed
    assert _assign(c.class_id, role="Cover Teacher").role == "Cover Teacher"


# ── Update / set_primary / delete ────────────────────────────────────

def test_update_merges_and_validates():
    c = _class()
    a = _assign(c.class_id, notes="keep")
    out = CT.update(a.assignment_id, {"role": "Teaching Assistant"})
    assert (out.role, out.notes, out.staff_name) == ("Teaching Assistant", "keep", "Ms Teach")
    with pytest.raises(CT.ValidationError, match="No assignment #999"):
        CT.update(999, {"notes": "x"})
    with pytest.raises(CT.ValidationError, match="No class #555"):
        CT.update(a.assignment_id, {"class_id": 555})
    b = _assign(c.class_id, "Mr Other", role="Teaching Assistant")
    with pytest.raises(CT.ValidationError, match="same class/staff/year/role"):
        CT.update(b.assignment_id, {"staff_name": "Ms Teach"})


def test_update_to_primary_demotes_others_and_syncs():
    c = _class()
    a = _assign(c.class_id, "Mr One", is_primary=True)
    b = _assign(c.class_id, "Ms Two")
    CT.update(b.assignment_id, {"is_primary": True})
    assert CT.get(a.assignment_id).is_primary is False
    assert CL.get(c.class_id).teacher == "Ms Two"


def test_set_primary():
    c = _class()
    a = _assign(c.class_id, "Mr One", is_primary=True)
    b = _assign(c.class_id, "Ms Two")
    out = CT.set_primary(b.assignment_id)
    assert out.is_primary is True
    assert CT.get(a.assignment_id).is_primary is False
    assert CL.get(c.class_id).teacher == "Ms Two"
    with pytest.raises(CT.ValidationError, match="No assignment #999"):
        CT.set_primary(999)


def test_delete():
    c = _class()
    a = _assign(c.class_id)
    assert CT.delete(a.assignment_id) is True
    assert CT.get(a.assignment_id) is None
    assert CT.delete(a.assignment_id) is False


def test_deleting_class_cascades_assignments():
    c = _class()
    a = _assign(c.class_id)
    assert CL.delete(c.class_id) is True
    assert CT.get(a.assignment_id) is None


# ── Listing ──────────────────────────────────────────────────────────

def test_list_assignments_filters_and_order():
    c3 = _class()
    c4 = _class("4B", "4")
    ta = _assign(c3.class_id, "Mr Aide", role="Teaching Assistant")
    p = _assign(c3.class_id, "Ms Lead", is_primary=True)
    other = _assign(c4.class_id, "Ms Lead")
    old = CT.create({"class_id": c3.class_id, "staff_name": "Old Hand",
                     "academic_year": "2025-26"})
    rows = CT.list_assignments()
    # newest year first; within a class the primary comes first
    assert [a.assignment_id for a, _ in rows] == [
        p.assignment_id, ta.assignment_id, other.assignment_id, old.assignment_id]
    assert rows[0][1].name == "3A"
    assert [a.assignment_id for a, _ in CT.list_assignments(class_id=c4.class_id)] == \
        [other.assignment_id]
    assert [a.assignment_id for a, _ in CT.list_assignments(academic_year="2025-26")] == \
        [old.assignment_id]
    assert [a.assignment_id for a, _ in CT.list_assignments(role="Teaching Assistant")] == \
        [ta.assignment_id]
    assert {a.assignment_id for a, _ in CT.list_assignments(staff_name="lead")} == \
        {p.assignment_id, other.assignment_id}
    with pytest.raises(CT.ValidationError, match="Role filter"):
        CT.list_assignments(role="Boss")


def test_list_for_class_and_staff():
    c = _class()
    a = _assign(c.class_id, "Ms Lead", is_primary=True)
    b = _assign(c.class_id, "Mr Aide", role="Teaching Assistant")
    old = CT.create({"class_id": c.class_id, "staff_name": "Ms Lead",
                     "academic_year": "2025-26"})
    assert [x.assignment_id for x in CT.list_for_class(c.class_id)] == \
        [a.assignment_id, b.assignment_id, old.assignment_id]
    assert [x.assignment_id for x in CT.list_for_class(c.class_id, "2025-26")] == \
        [old.assignment_id]
    with pytest.raises(CT.ValidationError, match="No class #404"):
        CT.list_for_class(404)
    mine = CT.list_for_staff("lead")
    assert [x.assignment_id for x, _ in mine] == [a.assignment_id, old.assignment_id]
    assert mine[0][1].class_id == c.class_id
    assert CT.list_for_staff("nobody") == []
    with pytest.raises(CT.ValidationError, match="Staff name is required"):
        CT.list_for_staff(" ")


def test_known_years_and_counts():
    assert CT.known_years() == []
    assert CT.counts() == {"total": 0, "primary": 0, "staff": 0}
    c = _class()
    _assign(c.class_id, "Ms Lead", is_primary=True)
    _assign(c.class_id, "Mr Aide", role="Teaching Assistant")
    CT.create({"class_id": c.class_id, "staff_name": "Ms Lead", "academic_year": "2025-26",
               "is_primary": True})
    assert CT.known_years() == [YEAR, "2025-26"]
    assert CT.counts() == {"total": 3, "primary": 2, "staff": 2}
    assert CT.counts(YEAR) == {"total": 2, "primary": 1, "staff": 2}
    assert CT.counts("2019-20") == {"total": 0, "primary": 0, "staff": 0}
